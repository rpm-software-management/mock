# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import fcntl
import glob
import grp
import logging
import os
import pwd
import shlex
import shutil
import stat
import tempfile
import uuid

from . import mounts
from . import uid
from . import util
from .exception import BuildRootLocked, Error, ResultDirNotAccessible, RootError
from .package_manager import package_manager
from .trace_decorator import getLog, traceLog


class Buildroot(object):
    @traceLog()
    def __init__(self, config, uid_manager, state, plugins, bootstrap_buildroot=None, is_bootstrap=False):
        self.config = config
        self.uid_manager = uid_manager
        self.state = state
        self.plugins = plugins
        self.bootstrap_buildroot = bootstrap_buildroot
        self.is_bootstrap = is_bootstrap
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
        self.chrootuser = config['chrootuser']
        self.chrootgid = config['chrootgid']
        self.chrootgroup = config['chrootgroup']
        self.env = config['environment']
        self.env['HOME'] = self.homedir
        proxy_env = util.get_proxy_environment(config)
        self.env.update(proxy_env)
        os.environ.update(proxy_env)

        self.pkg_manager = package_manager(config, self, plugins, bootstrap_buildroot)
        self.mounts = mounts.Mounts(self)

        self.root_log = getLog("mockbuild")
        self.build_log = getLog("mockbuild.Root.build")
        self.logging_initialized = False
        self.chroot_was_initialized = False
        self.preexisting_deps = []
        self.plugins.init_plugins(self)
        self.tmpdir = None
        self.nosync_path = None
        self.final_rpm_list = None

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
        Initialize the buildroot to a point where it's possible to execute
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
        with self.uid_manager:
            try:
                util.mkdirIfAbsent(self.resultdir)
            except Error:
                raise ResultDirNotAccessible(ResultDirNotAccessible.__doc__ % self.resultdir)

    @traceLog()
    def _init(self, prebuild, do_log):

        self.state.start("chroot init")
        util.mkdirIfAbsent(self.basedir)
        mockgid = grp.getgrnam('mock').gr_gid
        os.chown(self.basedir, os.getuid(), mockgid)
        os.chmod(self.basedir, 0o2775)
        util.mkdirIfAbsent(self.make_chroot_path())
        self.plugins.call_hooks('mount_root')
        # intentionally we do not call bootstrap hook here - it does not have sense
        self._setup_nosync()
        self.chroot_was_initialized = self.chroot_is_initialized()
        self._setup_result_dir()
        getLog().info("calling preinit hooks")
        self.plugins.call_hooks('preinit')
        # intentionally we do not call bootstrap hook here - it does not have sense
        self.chroot_was_initialized = self.chroot_is_initialized()

        self._setup_dirs()
        if do_log:
            self._resetLogging()
        # /dev is later overwritten by systemd-nspawn, but we need this for
        # initial installation when chroot is empty
        self._setup_devices()

        self._setup_files()
        self.mounts.mountall_managed()

        # write out config details
        self.root_log.debug('rootdir = %s', self.make_chroot_path())
        self.root_log.debug('resultdir = %s', self.resultdir)

        self.pkg_manager.initialize()
        self._setup_resolver_config()
        if not self.chroot_was_initialized:
            self._setup_dbus_uuid()
            self._init_aux_files()
            if not util.USE_NSPAWN:
                self._setup_timezone()
            self._init_pkg_management()
            self._setup_files_postinstall()
            self._make_build_user()
            self._setup_build_dirs()
        elif prebuild:
            if 'age_check' in self.config['plugin_conf']['root_cache_opts'] and \
               not self.config['plugin_conf']['root_cache_opts']['age_check']:
                self._init_pkg_management()
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
        else:
            self._fixup_build_user()
            # Change owner of homdir tree if the root of it not owned
            # by the current user.
            home = self.make_chroot_path(self.homedir)
            if os.path.exists(home) and os.stat(home).st_uid != self.chrootuid:
                self.chown_home_dir()

        # mark the buildroot as initialized
        util.touch(self.make_chroot_path('.initialized'))

        # done with init
        self.plugins.call_hooks('postinit')
        # intentionally we do not call bootstrap hook here - it does not have sense

        self.mounts.mountall_user()

        self.state.finish("chroot init")

    def doChroot(self, command, nosync=False, *args, **kargs):
        """Execute given command in root. Returns (output, child.returncode)"""
        self.nuke_rpm_db()
        env = dict(self.env)
        if nosync and self.nosync_path:
            env['LD_PRELOAD'] = self.nosync_path
        if util.USE_NSPAWN:
            if 'uid' not in kargs:
                kargs['uid'] = uid.getresuid()[1]
            if 'gid' not in kargs:
                kargs['gid'] = uid.getresgid()[1]
            if 'user' not in kargs:
                kargs['gid'] = pwd.getpwuid(kargs['uid'])[0]
            self.uid_manager.becomeUser(0, 0)
        result = util.do_with_status(command, chrootPath=self.make_chroot_path(),
                                     env=env, *args, **kargs)
        if util.USE_NSPAWN:
            self.uid_manager.restorePrivs()
        return result

    def all_chroot_packages(self):
        """package set, result of rpm -qa in the buildroot"""
        out = util.do([self.config['rpm_command'], "-qa",
                       "--root", self.make_chroot_path()],
                      returnOutput=True, printOutput=False, shell=False)
        return set(out.splitlines())

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
            self.root_log.warning("File %s not present. It is not copied into the chroot.", orig_conf_file)

    @traceLog()
    def _setup_resolver_config(self):
        if self.config['use_host_resolv'] and self.config['rpmbuild_networking']:
            self._copy_config('resolv.conf')
            self._copy_config('hosts')

    @traceLog()
    def _setup_dbus_uuid(self):
        machine_uuid = uuid.uuid4().hex
        dbus_uuid_path = self.make_chroot_path('etc', 'machine-id')
        symlink_path = self.make_chroot_path('var', 'lib', 'dbus', 'machine-id')
        with open(dbus_uuid_path, 'w') as uuid_file:
            uuid_file.write(machine_uuid)
            uuid_file.write('\n')
        if not os.path.exists(symlink_path):
            os.symlink("../../../etc/machine-id", symlink_path)

    @traceLog()
    def _setup_timezone(self):
        self._copy_config('localtime')

    @traceLog()
    def _init_pkg_management(self):
        update_state = '{0} install'.format(self.pkg_manager.name)
        self.state.start(update_state)
        if 'module_enable' in self.config and self.config['module_enable']:
            cmd = ['module', 'enable'] + self.config['module_enable']
            self.pkg_manager.init_install_output += self.pkg_manager.execute(*cmd, returnOutput=1)
        if 'module_install' in self.config and self.config['module_install']:
            cmd = ['module', 'install'] + self.config['module_install']
            self.pkg_manager.init_install_output += self.pkg_manager.execute(*cmd, returnOutput=1)

        cmd = self.config['chroot_setup_cmd']
        if cmd:
            if isinstance(cmd, util.basestring):
                cmd = cmd.split()
            self.pkg_manager.init_install_output += self.pkg_manager.execute(*cmd, returnOutput=1)

        if 'chroot_additional_packages' in self.config and self.config['chroot_additional_packages']:
            cmd = self.config['chroot_additional_packages']
            if isinstance(cmd, util.basestring):
                cmd = cmd.split()
            cmd = ['install'] + cmd
            self.pkg_manager.init_install_output += self.pkg_manager.execute(*cmd, returnOutput=1)

        self.state.finish(update_state)

    @traceLog()
    def _fixup_build_user(self):
        """ensure chrootuser has correct UID"""
        # --non-unique can be removed after 2019-03-31 (EOL of SLES 11)
        self.doChroot(['/usr/sbin/usermod', '-u', str(self.chrootuid), '--non-unique',
                       self.chrootuser],
                      shell=False, nosync=True)

    @traceLog()
    def _make_build_user(self):
        if not os.path.exists(self.make_chroot_path('usr/sbin/useradd')):
            raise RootError("Could not find useradd in chroot, maybe the install failed?")

        dets = {'uid': str(self.chrootuid), 'gid': str(self.chrootgid),
                'user': self.chrootuser, 'group': self.chrootgroup, 'home': self.homedir}

        excluded = [self.make_chroot_path(self.homedir, path)
                    for path in self.config['exclude_from_homedir_cleanup']] + \
            self.mounts.get_mountpoints()
        util.rmtree(self.make_chroot_path(self.homedir),
                    selinux=self.selinux, exclude=excluded)

        # ok for these two to fail
        if self.config['clean']:
            self.doChroot(['/usr/sbin/userdel', '-r', '-f', dets['user']],
                          shell=False, raiseExc=False, nosync=True)
        else:
            self.doChroot(['/usr/sbin/userdel', '-f', dets['user']],
                          shell=False, raiseExc=False, nosync=True)
        self.doChroot(['/usr/sbin/groupdel', dets['group']],
                      shell=False, raiseExc=False, nosync=True)

        if self.chrootgid != 0:
            self.doChroot(['/usr/sbin/groupadd', '-g', dets['gid'], dets['group']],
                          shell=False, nosync=True)
        self.doChroot(shlex.split(self.config['useradd'] % dets), shell=False, nosync=True)
        if not self.config['clean']:
            self.uid_manager.changeOwner(self.make_chroot_path(self.homedir))
        self._enable_chrootuser_account()

    @traceLog()
    def _enable_chrootuser_account(self):
        passwd = self.make_chroot_path('/etc/passwd')
        with open(passwd) as f:
            lines = f.readlines()
        disabled = False
        newlines = []
        for l in lines:
            parts = l.strip().split(':')
            if parts[0] == self.chrootuser and parts[1].startswith('!!'):
                disabled = True
                parts[1] = parts[1][2:]
            newlines.append(':'.join(parts))
        if disabled:
            with open(passwd, "w") as f:
                for l in newlines:
                    f.write(l + '\n')

    @traceLog()
    def _resetLogging(self, force=False):
        # ensure we dont attach the handlers multiple times.
        if self.logging_initialized and not force:
            return
        self.logging_initialized = True

        with self.uid_manager:
            self.uid_manager.becomeUser(0, 0)

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
                log.info("Mock Version: %s", self.config['version'])
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
    def nuke_rpm_db(self):
        """remove rpm DB lock files from the chroot"""

        dbfiles = glob.glob(self.make_chroot_path('var/lib/rpm/__db*'))
        if not dbfiles:
            return
        self.root_log.debug("removing %d rpm db files", len(dbfiles))
        # become root
        self.uid_manager.becomeUser(0, 0)
        try:
            for tmp in dbfiles:
                self.root_log.debug("nuke_rpm_db: removing %s", tmp)
                try:
                    os.unlink(tmp)
                except OSError as e:
                    getLog().error("%s", e)
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
                'etc/dnf',
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
        self.uid_manager.changeOwner(self.make_chroot_path(self.homedir),
                                     recursive=True)

    @traceLog()
    def _setup_build_dirs(self):
        build_dirs = ['RPMS', 'SPECS', 'SRPMS', 'SOURCES', 'BUILD', 'BUILDROOT',
                      'originals']
        with self.uid_manager:
            self.uid_manager.changeOwner(self.make_chroot_path(self.builddir))
            for item in build_dirs:
                path = self.make_chroot_path(self.builddir, item)
                util.mkdirIfAbsent(path)
                self.uid_manager.changeOwner(path)
            if self.config['clean']:
                self.chown_home_dir()
            # rpmmacros default
            macrofile_out = self.make_chroot_path(self.homedir, ".rpmmacros")
            with open(macrofile_out, 'w+') as rpmmacros:

                # user specific from rpm macro file definitions first
                if 'macrofile' in self.config:
                    with open(self.config['macrofile'], 'r') as macro_conf:
                        rpmmacros.write("%s\n\n" % macro_conf.read())

                for key, value in list(self.config['macros'].items()):
                    rpmmacros.write("%s %s\n" % (key, value))

    @traceLog()
    def _setup_devices(self):
        if self.config['internal_dev_setup']:
            util.rmtree(self.make_chroot_path("dev"), selinux=self.selinux, exclude=self.mounts.get_mountpoints())
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
                (stat.S_IFCHR | 0o666, os.makedev(10, 237), "dev/loop-control"),
                (stat.S_IFCHR | 0o600, os.makedev(10, 57), "dev/prandom"),
                (stat.S_IFCHR | 0o600, os.makedev(10, 183), "dev/hwrng"),
            ]
            for i in range(self.config['dev_loop_count']):
                devFiles.append((stat.S_IFBLK | 0o666, os.makedev(7, i), "dev/loop{loop_number}".format(loop_number=i)))
            kver = os.uname()[2]
            self.root_log.debug("kernel version == %s", kver)
            for i in devFiles:
                # create node, but only if it exist on host too
                # except for loop devices, which only show up on the host after they are first used
                if os.path.exists("/" + i[2]) or "loop" in i[2]:
                    os.mknod(self.make_chroot_path(i[2]), i[0], i[1])
                    # set context. (only necessary if host running selinux enabled.)
                    # fails gracefully if chcon not installed.
                    if self.selinux:
                        util.do(["chcon", "--reference=/" + i[2], self.make_chroot_path(i[2])],
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
        # self.root_log.debug('touch required files')
        for item in [self.make_chroot_path('etc', 'fstab'),
                     self.make_chroot_path('etc', 'yum', 'yum.conf'),
                     self.make_chroot_path('etc', 'dnf', 'dnf.conf'),
                     self.make_chroot_path('var', 'log', 'yum.log')]:
            util.touch(item)
        short_yum_confpath = self.make_chroot_path('etc', 'yum.conf')
        if not os.path.exists(short_yum_confpath):
            os.symlink("yum/yum.conf", short_yum_confpath)

    @traceLog()
    def _setup_files_postinstall(self):
        for item in [self.make_chroot_path('etc', 'os-release')]:
            util.touch(item)

    @traceLog()
    def _setup_nosync(self):
        multilib = ('x86_64', 's390x')
        # ld_preload need to be same as in bootstrap because we call DNF in bootstrap, but
        # but it will load nosync from the final chroot
        if self.bootstrap_buildroot is not None:
            self.tmpdir = self.bootstrap_buildroot.tmpdir
            if not os.path.isdir(self.tmpdir):
                os.mkdir(self.tmpdir, 0o700)
        else:
            self.tmpdir = tempfile.mkdtemp(prefix="tmp.mock.", dir='/var/tmp')
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
                self.root_log.warning("nosync is enabled but the library "
                                      "wasn't found on the system")
                return
            if (target_arch in multilib and not self.config['nosync_force']
                    and copied_lib != copied_lib64):
                self.root_log.warning("For multilib systems, both architectures"
                                      " of nosync library need to be installed")
                return
            self.nosync_path = os.path.join(tmp_libdir, 'nosync.so')

    @traceLog()
    def finalize(self):
        """
        Remove temporary files. If this is the last process working with the
        buildroot (exclusive lock can be acquired) also kill orphan processes,
        unmount mounts and call postumount hooks.
        """
        if self.tmpdir:
            for d in self.tmpdir, self.make_chroot_path(self.tmpdir):
                if os.path.exists(d):
                    shutil.rmtree(d)
        if os.path.exists(self.make_chroot_path()):
            try:
                self._lock_buildroot(exclusive=True)
                util.orphansKill(self.make_chroot_path())
                self.mounts.umountall()
                self.plugins.call_hooks('postumount')
                # intentionally we do not call bootstrap hook here - it does not have sense
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
            self.mounts.umountall()
            self.plugins.call_hooks('umount_root')
            # intentionally we do not call bootstrap hook here - it does not have sense
            self._unlock_buildroot()
            subv = util.find_btrfs_in_chroot(self.mockdir, p)
            if subv:
                util.do(["btrfs", "subv", "delete", "/" + subv])
            if not self.rootdir.startswith(self.basedir):
                util.rmtree(self.rootdir, selinux=self.selinux)
            util.rmtree(self.basedir, selinux=self.selinux)
        self.chroot_was_initialized = False
        self.plugins.call_hooks('postclean')
        # intentionally we do not call bootstrap hook here - it does not have sense
