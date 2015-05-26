import fcntl
import glob
import grp
import logging
import os
import pwd
import shutil
import stat
import tempfile

from . import util
from . import mounts
from .exception import BuildRootLocked, RootError, \
                                ResultDirNotAccessible, Error
from .package_manager import PackageManager
from .trace_decorator import getLog, traceLog

class Buildroot(object):
    @traceLog()
    def __init__(self, config, uid_manager, state, plugins):
        self.config = config
        self.uid_manager = uid_manager
        self.state = state
        self.plugins = plugins
        self.shared_root_name = config['root']
        if 'unique-ext' in config:
            config['root'] = "%s-%s" % (config['root'], config['unique-ext'])
        self.root_name = config['root']
        self.mockdir = config['basedir']
        self.basedir = os.path.join(config['basedir'], config['root'])
        if 'rootdir' in config:
            self.rootdir = config['rootdir']
        else:
            self.rootdir = os.path.join(self.basedir, 'root')
        self.resultdir = config['resultdir'] % config
        self.homedir = config['chroothome']
        self.cache_topdir = config['cache_topdir']
        self.cachedir = os.path.join(self.cache_topdir, self.shared_root_name)
        self.builddir = os.path.join(self.homedir, 'build')
        self._lock_file = None
        self.selinux = (not self.config['plugin_conf']['selinux_enable']
                        and util.selinuxEnabled())

        self.chrootuid = config['chrootuid']
        self.chrootuser = 'mockbuild'
        self.chrootgid = config['chrootgid']
        self.chrootgroup = 'mockbuild'
        self.env = config['environment']
        self.env['HOME'] = self.homedir
        proxy_env = util.get_proxy_environment(config)
        self.env.update(proxy_env)
        os.environ.update(proxy_env)

        self.pkg_manager = PackageManager(config, self, plugins)
        self.mounts = mounts.Mounts(self)

        self.root_log = getLog("mockbuild")
        self.build_log = getLog("mockbuild.Root.build")
        self.logging_initialized = False
        self.chroot_was_initialized = False
        self.preexisting_deps = []
        self.plugins.init_plugins(self)
        self.tmpdir = None
        self.nosync_path = None

    @traceLog()
    def make_chroot_path(self, *paths):
        new_path = self.rootdir
        for path in paths:
            if path.startswith('/'):
                path = path[1:]
            new_path = os.path.join(new_path, path)
        return new_path

    @traceLog()
    def initialize(self, prebuild=False, do_log=True):
        """
        Initialize the builroot to a point where it's possible to execute
        commands in chroot. If it was already initialized, just lock the shared
        lock.
        """
        try:
            self._lock_buildroot(exclusive=True)
            self._init(prebuild=prebuild, do_log=do_log)
        except BuildRootLocked:
            pass
        finally:
            self._lock_buildroot(exclusive=False)
        if do_log:
            self._resetLogging()

    @traceLog()
    def chroot_is_initialized(self):
        return os.path.exists(self.make_chroot_path('.initialized'))

    @traceLog()
    def _setup_result_dir(self):
        self.uid_manager.dropPrivsTemp()
        try:
            util.mkdirIfAbsent(self.resultdir)
        except Error:
            raise ResultDirNotAccessible(ResultDirNotAccessible.__doc__ % self.resultdir)
        finally:
            self.uid_manager.restorePrivs()

    @traceLog()
    def _init(self, prebuild, do_log):
        # If previous run didn't finish properly
        self._umount_residual()

        self.state.start("chroot init")
        util.mkdirIfAbsent(self.basedir)
        mockgid = grp.getgrnam('mock').gr_gid
        os.chown(self.basedir, os.getuid(), mockgid)
        os.chmod(self.basedir, 0o2775)
        util.mkdirIfAbsent(self.make_chroot_path())
        self.plugins.call_hooks('mount_root')
        self.chroot_was_initialized = self.chroot_is_initialized()
        self._setup_result_dir()
        getLog().info("calling preinit hooks")
        self.plugins.call_hooks('preinit')
        self.chroot_was_initialized = self.chroot_is_initialized()

        self._setup_dirs()
        if do_log:
            self._resetLogging()
        if not util.USE_NSPAWN:
            self._setup_devices()
        self._setup_files()
        self._setup_nosync()
        self.mounts.mountall()

        # write out config details
        self.root_log.debug('rootdir = %s' % self.make_chroot_path())
        self.root_log.debug('resultdir = %s' % self.resultdir)

        self.pkg_manager.initialize()
        if not self.chroot_was_initialized:
            self._setup_resolver_config()
            self._setup_dbus_uuid()
            self._init_aux_files()
            if not util.USE_NSPAWN:
                self._setup_timezone()
            self._init_pkg_management()
            self._setup_files_postinstall()
            self._make_build_user()
            self._setup_build_dirs()
        elif prebuild:
            # Recreates build user to ensure the uid/gid are up to date with config
            # and there's no garbage left by previous build
            self._make_build_user()
            self._setup_build_dirs()
            if (self.config['online'] and self.config['update_before_build']
                    and self.config['clean']):
                update_state = "{0} update".format(self.pkg_manager.name)
                self.state.start(update_state)
                self.pkg_manager.update()
                self.state.finish(update_state)

        # mark the buildroot as initialized
        util.touch(self.make_chroot_path('.initialized'))

        # done with init
        self.plugins.call_hooks('postinit')
        self.state.finish("chroot init")

    def doChroot(self, command, shell=True, nosync=False, *args, **kargs):
        """execute given command in root"""
        self._nuke_rpm_db()
        env = dict(self.env)
        if nosync and self.nosync_path:
            env['LD_PRELOAD'] = self.nosync_path
        return util.do(command, chrootPath=self.make_chroot_path(),
                       env=env, shell=shell, *args, **kargs)

    @traceLog()
    def _copy_config(self, filename):
        etcdir = self.make_chroot_path('etc')
        conf_file = os.path.join(etcdir, filename)
        if os.path.exists(conf_file):
            os.remove(conf_file)
        orig_conf_file = os.path.join('/etc', filename)
        if os.path.exists(orig_conf_file):
            shutil.copy2(orig_conf_file, etcdir)
        else:
            self.root_log.warn("File {0} not present. It is not copied into the chroot.".format(orig_conf_file))

    @traceLog()
    def _setup_resolver_config(self):
        if self.config['use_host_resolv']:
            self._copy_config('resolv.conf')
            self._copy_config('hosts')

    @traceLog()
    def _setup_dbus_uuid(self):
        try:
            import uuid
            machine_uuid = uuid.uuid4().hex
            dbus_uuid_path = self.make_chroot_path('var', 'lib', 'dbus', 'machine-id')
            with open(dbus_uuid_path, 'w') as uuid_file:
                uuid_file.write(machine_uuid)
                uuid_file.write('\n')
        except ImportError:
            pass

    @traceLog()
    def _setup_timezone(self):
        self._copy_config('localtime')

    @traceLog()
    def _init_pkg_management(self):
        update_state = '{0} install'.format(self.pkg_manager.name)
        self.state.start(update_state)
        cmd = self.config['chroot_setup_cmd']
        if isinstance(cmd, util.basestring):
            cmd = cmd.split()
        self.pkg_manager.execute(*cmd)
        self.state.finish(update_state)

    @traceLog()
    def _make_build_user(self):
        if not os.path.exists(self.make_chroot_path('usr/sbin/useradd')):
            raise RootError("Could not find useradd in chroot, maybe the install failed?")

        dets = {'uid': str(self.chrootuid), 'gid': str(self.chrootgid),
                'user': self.chrootuser, 'group': self.chrootgroup, 'home': self.homedir}

        excluded = [self.make_chroot_path(self.homedir, path)
                    for path in self.config['exclude_from_homedir_cleanup']]
        util.rmtree(self.make_chroot_path(self.homedir),
                    selinux=self.selinux, exclude=excluded)

        # ok for these two to fail
        if self.config['clean']:
            self.doChroot(['/usr/sbin/userdel', '-r', '-f', dets['user']],
                          shell=False, raiseExc=False, nosync=True)
        else:
            self.doChroot(['/usr/sbin/userdel', '-f', dets['user']],
                          shell=False, raiseExc=False, nosync=True)
        self.doChroot(['/usr/sbin/userdel', '-r', '-f', dets['user']],
                      shell=False, raiseExc=False, nosync=True)
        self.doChroot(['/usr/sbin/groupdel', dets['group']],
                      shell=False, raiseExc=False, nosync=True)

        self.doChroot(['/usr/sbin/groupadd', '-g', dets['gid'], dets['group']],
                      shell=False, nosync=True)
        self.doChroot(self.config['useradd'] % dets, shell=True, nosync=True)
        self._enable_chrootuser_account()

    @traceLog()
    def _enable_chrootuser_account(self):
        passwd = self.make_chroot_path('/etc/passwd')
        lines = open(passwd).readlines()
        disabled = False
        newlines = []
        for l in lines:
            parts = l.strip().split(':')
            if parts[0] == self.chrootuser and parts[1].startswith('!!'):
                disabled = True
                parts[1] = parts[1][2:]
            newlines.append(':'.join(parts))
        if disabled:
            f = open(passwd, "w")
            for l in newlines:
                f.write(l+'\n')
            f.close()

    @traceLog()
    def _resetLogging(self):
        # ensure we dont attach the handlers multiple times.
        if self.logging_initialized:
            return
        self.logging_initialized = True


        try:
            self.uid_manager.dropPrivsTemp()
            util.mkdirIfAbsent(self.resultdir)

            # attach logs to log files.
            # This happens in addition to anything that
            # is set up in the config file... ie. logs go everywhere
            for (log, filename, fmt_str) in (
                    (self.state.state_log, "state.log", self.config['state_log_fmt_str']),
                    (self.build_log, "build.log", self.config['build_log_fmt_str']),
                    (self.root_log, "root.log", self.config['root_log_fmt_str'])):
                fullPath = os.path.join(self.resultdir, filename)
                fh = logging.FileHandler(fullPath, "a+")
                formatter = logging.Formatter(fmt_str)
                fh.setFormatter(formatter)
                fh.setLevel(logging.NOTSET)
                log.addHandler(fh)
                log.info("Mock Version: %s" % self.config['version'])
        finally:
            self.uid_manager.restorePrivs()

    @traceLog()
    def _init_aux_files(self):
        chroot_file_contents = self.config['files']
        for key in chroot_file_contents:
            p = self.make_chroot_path(key)
            if not os.path.exists(p):
                util.mkdirIfAbsent(os.path.dirname(p))
                with open(p, 'w+') as fo:
                    fo.write(chroot_file_contents[key])

    @traceLog()
    def _nuke_rpm_db(self):
        """remove rpm DB lock files from the chroot"""

        dbfiles = glob.glob(self.make_chroot_path('var/lib/rpm/__db*'))
        if not dbfiles:
            return
        self.root_log.debug("removing %d rpm db files" % len(dbfiles))
        # become root
        self.uid_manager.becomeUser(0, 0)
        try:
            for tmp in dbfiles:
                self.root_log.debug("_nuke_rpm_db: removing %s" % tmp)
                try:
                    os.unlink(tmp)
                except OSError as e:
                    getLog().error("%s" % e)
                    raise
        finally:
            self.uid_manager.restorePrivs()

    @traceLog()
    def _open_lock(self):
        util.mkdirIfAbsent(self.basedir)
        self._lock_file = open(os.path.join(self.basedir, "buildroot.lock"), "a+")

    @traceLog()
    def _lock_buildroot(self, exclusive):
        lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        if not self._lock_file:
            self._open_lock()
        try:
            fcntl.lockf(self._lock_file.fileno(), lock_type | fcntl.LOCK_NB)
        except IOError:
            raise BuildRootLocked("Build root is locked by another process.")

    @traceLog()
    def _unlock_buildroot(self):
        if self._lock_file:
            self._lock_file.close()
        self._lock_file = None

    @traceLog()
    def _setup_dirs(self):
        self.root_log.debug('create skeleton dirs')
        dirs = ['var/lib/rpm',
                     'var/lib/yum',
                     'var/lib/dbus',
                     'var/log',
                     'var/cache/yum',
                     'etc/rpm',
                     'tmp',
                     'tmp/ccache',
                     'var/tmp',
                     #dnf?
                     'etc/yum.repos.d',
                     'etc/yum',
                     'proc',
                     'sys']
        dirs += self.config['extra_chroot_dirs']
        for item in dirs:
            util.mkdirIfAbsent(self.make_chroot_path(item))

    @traceLog()
    def chown_home_dir(self):
        """ set ownership of homedir and subdirectories to mockbuild user """
        for (dirpath, dirnames, filenames) in os.walk(self.make_chroot_path(self.homedir)):
            for path in dirnames + filenames:
                filepath = os.path.join(dirpath, path)
                # ignore broken symlinks
                if os.path.exists(filepath):
                    os.lchown(filepath, self.chrootuid, self.chrootgid)
                    os.chmod(filepath, 0o755)

    @traceLog()
    def _setup_build_dirs(self):
        build_dirs = ['RPMS', 'SPECS', 'SRPMS', 'SOURCES', 'BUILD', 'BUILDROOT',
                      'originals']
        self.uid_manager.dropPrivsTemp()
        try:
            for item in build_dirs:
                util.mkdirIfAbsent(self.make_chroot_path(self.builddir, item))
            if self.config['clean']:
                self.chown_home_dir()
            # rpmmacros default
            macrofile_out = self.make_chroot_path(self.homedir, ".rpmmacros")
            rpmmacros = open(macrofile_out, 'w+')

            # user specific from rpm macro file defenitions first
            if 'macrofile' in self.config:
                macro_conf = open(self.config['macrofile'], 'r')
                rpmmacros.write("%s\n\n" % macro_conf.read())
                macro_conf.close()

            for key, value in list(self.config['macros'].items()):
                rpmmacros.write("%s %s\n" % (key, value))
            rpmmacros.close()
        finally:
            self.uid_manager.restorePrivs()

    @traceLog()
    def _setup_devices(self):
        if self.config['internal_dev_setup']:
            util.rmtree(self.make_chroot_path("dev"), selinux=self.selinux)
            util.mkdirIfAbsent(self.make_chroot_path("dev", "pts"))
            util.mkdirIfAbsent(self.make_chroot_path("dev", "shm"))
            prevMask = os.umask(0000)
            devFiles = [
                (stat.S_IFCHR | 0o666, os.makedev(1, 3), "dev/null"),
                (stat.S_IFCHR | 0o666, os.makedev(1, 7), "dev/full"),
                (stat.S_IFCHR | 0o666, os.makedev(1, 5), "dev/zero"),
                (stat.S_IFCHR | 0o666, os.makedev(1, 8), "dev/random"),
                (stat.S_IFCHR | 0o444, os.makedev(1, 9), "dev/urandom"),
                (stat.S_IFCHR | 0o666, os.makedev(5, 0), "dev/tty"),
                (stat.S_IFCHR | 0o600, os.makedev(5, 1), "dev/console"),
                (stat.S_IFCHR | 0o666, os.makedev(5, 2), "dev/ptmx"),
                ]
            kver = os.uname()[2]
            self.root_log.debug("kernel version == {0}".format(kver))
            for i in devFiles:
                # create node
                os.mknod(self.make_chroot_path(i[2]), i[0], i[1])
                # set context. (only necessary if host running selinux enabled.)
                # fails gracefully if chcon not installed.
                if self.selinux:
                    util.do(
                        ["chcon", "--reference=/" + i[2], self.make_chroot_path(i[2])],
                         raiseExc=0, shell=False, env=self.env)

            os.symlink("/proc/self/fd/0", self.make_chroot_path("dev/stdin"))
            os.symlink("/proc/self/fd/1", self.make_chroot_path("dev/stdout"))
            os.symlink("/proc/self/fd/2", self.make_chroot_path("dev/stderr"))

            if os.path.isfile(self.make_chroot_path('etc', 'mtab')) or \
               os.path.islink(self.make_chroot_path('etc', 'mtab')):
                os.remove(self.make_chroot_path('etc', 'mtab'))
            os.symlink("../proc/self/mounts", self.make_chroot_path('etc', 'mtab'))

            os.chown(self.make_chroot_path('dev/tty'), pwd.getpwnam('root')[2], grp.getgrnam('tty')[2])
            os.chown(self.make_chroot_path('dev/ptmx'), pwd.getpwnam('root')[2], grp.getgrnam('tty')[2])

            # symlink /dev/fd in the chroot for everything except RHEL4
            if util.cmpKernelVer(kver, '2.6.9') > 0:
                os.symlink("/proc/self/fd", self.make_chroot_path("dev/fd"))

            os.umask(prevMask)

            if util.cmpKernelVer(kver, '2.6.18') >= 0:
                os.unlink(self.make_chroot_path('/dev/ptmx'))
            os.symlink("pts/ptmx", self.make_chroot_path('/dev/ptmx'))

    @traceLog()
    def _setup_files(self):
        #self.root_log.debug('touch required files')
        for item in [self.make_chroot_path('etc', 'fstab'),
                     self.make_chroot_path('var', 'log', 'yum.log')]:
            util.touch(item)

    @traceLog()
    def _setup_files_postinstall(self):
        for item in [self.make_chroot_path('etc', 'os-release')]:
            util.touch(item)

    @traceLog()
    def _setup_nosync(self):
        multilib = ('x86_64', 's390x')
        self.tmpdir = tempfile.mkdtemp()
        os.chmod(self.tmpdir, 0o777)
        tmp_libdir = os.path.join(self.tmpdir, '$LIB')
        mock_libdir = self.make_chroot_path(tmp_libdir)
        nosync_unresolved = '/usr/$LIB/nosync/nosync.so'
        def copy_nosync(lib64=False):
            def resolve(path):
                return path.replace('$LIB', 'lib64' if lib64 else 'lib')
            nosync = resolve(nosync_unresolved)
            if not os.path.exists(nosync):
                return False
            for dst_unresolved in (tmp_libdir, mock_libdir):
                dst = resolve(dst_unresolved)
                util.mkdirIfAbsent(dst)
                shutil.copy2(nosync, dst)
            return True

        if self.config['nosync']:
            target_arch = self.config['target_arch']
            copied_lib = copy_nosync()
            copied_lib64 = copy_nosync(lib64=True)
            if not copied_lib and not copied_lib64:
                self.root_log.warn("nosync is enabled but the library wasn't "
                                   "found on the system")
                return
            if (target_arch in multilib and not self.config['nosync_force']
                    and copied_lib != copied_lib64):
                self.root_log.warn("For multilib systems, both architectures "
                                   "of nosync library need to be installed")
                return
            self.nosync_path = os.path.join(tmp_libdir, 'nosync.so')


    @traceLog()
    def finalize(self):
        """
        Do the cleanup if this is the last process working with the buildroot.
        """
        if os.path.exists(self.make_chroot_path()):
            try:
                if self.tmpdir:
                    for d in self.tmpdir, self.make_chroot_path(self.tmpdir):
                        if os.path.exists(d):
                            shutil.rmtree(d)
                self._lock_buildroot(exclusive=True)
                util.orphansKill(self.make_chroot_path())
                self._umount_all()
                self.plugins.call_hooks('postumount')
            except BuildRootLocked:
                pass
            finally:
                self._unlock_buildroot()

    @traceLog()
    def delete(self):
        """
        Deletes the buildroot contents.
        """
        if os.path.exists(self.basedir):
            p = self.make_chroot_path()
            self._lock_buildroot(exclusive=True)
            util.orphansKill(p)
            self._umount_all()
            self.plugins.call_hooks('umount_root')
            self._unlock_buildroot()
            subv = util.find_btrfs_in_chroot(self.mockdir, p)
            if subv:
                util.do(["btrfs", "subv", "delete", "/" + subv])
            util.rmtree(self.basedir, selinux=self.selinux)
        self.chroot_was_initialized = False
        self.plugins.call_hooks('postclean')

    @traceLog()
    def _umount_all(self):
        """umount all mounted chroot fs."""

        # first try removing all expected mountpoints.
        self.mounts.umountall()

        # then remove anything that might be left around.
        self._umount_residual()

    @traceLog()
    def _mount_is_ours(self, mountpoint):
        mountpoint = os.path.realpath(mountpoint)
        our_dir = os.path.realpath(self.make_chroot_path())
        assert our_dir
        if mountpoint.startswith(our_dir + '/'):
            return True
        return False


    @traceLog()
    def _umount_residual(self):
        def force_umount(mountpoint):
            cmd = "umount -n -l %s" % mountpoint
            self.root_log.warning("Forcibly unmounting '%s' from chroot." % mountpoint)
            util.do(cmd, raiseExc=0, shell=True, env=self.env)

        def get_our_mounts():
            mountpoints = open("/proc/mounts").read().strip().split("\n")
            our_mounts = []
            # umount in reverse mount order to prevent nested mount issues that
            # may prevent clean unmount.
            for mountline in reversed(mountpoints):
                mountpoint = mountline.split()[1]
                if self._mount_is_ours(mountpoint):
                    our_mounts.append(mountpoint)
            return our_mounts

        prev_mounts = []
        while True:
            current_mounts = get_our_mounts()
            if current_mounts == prev_mounts:
                return
            for mount in current_mounts:
                force_umount(mount)
            prev_mounts = current_mounts
