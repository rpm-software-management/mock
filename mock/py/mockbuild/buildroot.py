# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import errno
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

from . import file_util
from . import mounts
from . import text
from . import uid
from . import util
from .exception import (BuildRootLocked, Error, ResultDirNotAccessible,
                        RootError, BadCmdline)
from .package_manager import package_manager
from .trace_decorator import getLog, traceLog
from .podman import Podman


def noop_in_bootstrap(f):
    # pylint: disable=inconsistent-return-statements
    def wrapper(self, *args, **kwargs):
        if self.is_bootstrap:
            getLog().debug("method {} skipped in bootstrap".format(f.__name__))
            return
        return f(self, *args, **kwargs)
    return wrapper


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
        self.rootdir = config['rootdir']

        # don't mixup bootstrap && normal chroot root dirs
        if is_bootstrap:
            self.rootdir = os.path.join(self.basedir, 'root')

        self.resultdir = text.compat_expand_string(config['resultdir'], config)

        # In bootstrap buildroot, resultdir _should_ be basically unused (nobody
        # looks there anyways).  But it is actually used on many fronts -- e.g.
        # by plugins, bootstrap logging, etc.
        #
        # By default, bootstrap buildroot has different resultdir from the
        # normal buildroot, as it is set to `{{basedir}}/{{root}}/result'`.  But
        # things start to be much more complicated if user sets `--resuldir
        # /static/dir` (or `config_opts["resultdir'`) and both buildroots start
        # to fight against each other.
        #
        # Let's work-around this, and always set predictable resultdir for
        # bootstrap.  We intentionally pick a directory which we can create (and
        # write into) under non-privileged user.
        if is_bootstrap:
            self.resultdir = os.path.join(self.basedir, 'results')

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

        self.use_bootstrap_image = self.config['use_bootstrap_image']
        self.bootstrap_image = self.config['bootstrap_image']

        self.pkg_manager = package_manager(config, self, plugins, bootstrap_buildroot)
        self.mounts = mounts.Mounts(self)

        self.root_log = getLog("mockbuild")
        self.build_log = getLog("mockbuild.Root.build")
        self.logging_initialized = False
        self.chroot_was_initialized = False

        additional_packages = config["additional_packages"] or []
        if is_bootstrap:
            self.preexisting_deps = []
        else:
            self.preexisting_deps = additional_packages

        self.plugins.init_plugins(self)
        self.tmpdir = None
        self.nosync_path = None
        self.final_rpm_list = None

        self._homedir_bindmounts = {}
        self._setup_nspawn_btrfs_device()
        self._setup_nspawn_loop_devices()

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
                file_util.mkdirIfAbsent(self.resultdir)
            except Error:
                raise ResultDirNotAccessible(ResultDirNotAccessible.__doc__ % self.resultdir)

    @traceLog()
    def _init(self, prebuild, do_log):

        self.state.start("chroot init")
        file_util.mkdirIfAbsent(self.basedir)
        mockgid = grp.getgrnam('mock').gr_gid
        os.chown(self.basedir, os.getuid(), mockgid)
        os.chmod(self.basedir, 0o2775)
        file_util.mkdirIfAbsent(self.make_chroot_path())
        self.plugins.call_hooks('mount_root')
        # intentionally we do not call bootstrap hook here - it does not have sense
        self._setup_nosync()
        self.chroot_was_initialized = self.chroot_is_initialized()
        self._setup_result_dir()
        getLog().info("calling preinit hooks")
        self.plugins.call_hooks('preinit')
        # intentionally we do not call bootstrap hook here - it does not have sense
        self.chroot_was_initialized = self.chroot_is_initialized()
        if self.uses_bootstrap_image and not self.chroot_was_initialized:
            podman = Podman(self, self.bootstrap_image)
            podman.pull_image()
            podman.get_container_id()
            if self.config["tar"] == "bsdtar":
                __tar_cmd = "bsdtar"
            else:
                __tar_cmd = "gtar"
            podman.install_pkgmgmt_packages()
            podman.cp(self.make_chroot_path(), __tar_cmd)
            podman.remove()

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
        self._setup_katello_ca()
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
                packages_before = self.all_chroot_packages()
                self.pkg_manager.update()
                packages_after = self.all_chroot_packages()
                if packages_before != packages_after:
                    new_packages = "\n".join(packages_after - packages_before)
                    self.root_log.info("Calling postupdate hooks because there "
                                       "are new/updated packages:\n%s",
                                       new_packages)
                    self.plugins.call_hooks('postupdate')
                self.state.finish(update_state)
        else:
            self._fixup_build_user()
            # Change owner of homdir tree if the root of it not owned
            # by the current user.
            home = self.make_chroot_path(self.homedir)
            if os.path.exists(home) and os.stat(home).st_uid != self.chrootuid:
                self.chown_home_dir()

        # mark the buildroot as initialized
        file_util.touch(self.make_chroot_path('.initialized'))

        # done with init
        self.plugins.call_hooks('postinit')
        # intentionally we do not call bootstrap hook here - it does not have sense

        self.mounts.mountall_user()

        self.state.finish("chroot init")

    def doOutChroot(self, command, *args, **kwargs):
        """
        Execute the command in bootstrap chroot (when bootstrap is enabled) or
        on host.  Return (output, exit_status) tuple.
        """
        if self.bootstrap_buildroot:
            return self.bootstrap_buildroot.doChroot(command, *args, **kwargs)
        return util.do_with_status(command, *args, **kwargs)

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
            self.uid_manager.becomeUser(0, 0)

        try:
            result = util.do_with_status(command, chrootPath=self.make_chroot_path(),
                                         env=env, *args, **kargs)
        finally:
            if util.USE_NSPAWN:
                self.uid_manager.restorePrivs()
        return result

    def all_chroot_packages(self):
        """package set, result of rpm -qa in the buildroot"""
        self.nuke_rpm_db()
        command = [self.config['rpm_command'], "-qa",
                   "--root", self.make_chroot_path()]
        out, _ = self.doOutChroot(command, returnOutput=True, printOutput=False,
                                  shell=False)
        return set(out.splitlines())

    @traceLog()
    def _copy_config(self, filename, symlink=False, warn=True):
        orig_conf_file = os.path.join('/etc', filename)
        conf_file = self.make_chroot_path(orig_conf_file)

        try:
            os.remove(conf_file)
        except FileNotFoundError:
            pass

        # for /etc sub-directories
        file_util.mkdirIfAbsent(os.path.dirname(conf_file))

        if os.path.exists(orig_conf_file):
            if symlink and os.path.islink(orig_conf_file):
                linkto = os.readlink(orig_conf_file)
                os.symlink(linkto, conf_file)
            else:
                shutil.copy2(orig_conf_file, conf_file)
        elif warn:
            self.root_log.warning("File %s not present. It is not copied into the chroot.", orig_conf_file)

    @traceLog()
    def _setup_resolver_config(self):
        if self.config['use_host_resolv'] and self.config['rpmbuild_networking']:
            self._copy_config('resolv.conf')
            self._copy_config('hosts')

    @traceLog()
    def _setup_katello_ca(self):
        if not all([self.is_bootstrap,
                    self.config["redhat_subscription_required"]]):
            return
        self._copy_config('rhsm/ca/katello-server-ca.pem', warn=False)

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
        self._copy_config('localtime', symlink=True)

    @staticmethod
    def _module_commands_from_config(config):
        commands = []
        for config_command in config:
            action, raw_modules = config_command
            if raw_modules:
                modules = str(raw_modules).strip()
                modules = [m.strip() for m in modules.split(",")]
            else:
                modules = []
            cmd = ["module", action] + modules
            commands.append(cmd)
        return commands

    @traceLog()
    def _module_setup(self):
        if 'module_enable' in self.config and self.config['module_enable']:
            cmd = ['module', 'enable'] + self.config['module_enable']
            self.pkg_manager.init_install_output += self.pkg_manager.execute(*cmd, returnOutput=1)

        if 'module_install' in self.config and self.config['module_install']:
            cmd = ['module', 'install'] + self.config['module_install']
            self.pkg_manager.init_install_output += self.pkg_manager.execute(*cmd, returnOutput=1)

        module_config = self.config["module_setup_commands"] or []
        for cmd in self._module_commands_from_config(module_config):
            self.pkg_manager.init_install_output += self.pkg_manager.execute(*cmd, returnOutput=1)

    @traceLog()
    def _init_pkg_management(self):
        if self.uses_bootstrap_image:
            # we already 'Podman.install_pkgmgmt_packages' to have working
            # pkg management stack in bootstrap (the rest of this method, like
            # modules, isn't usefull in bootstrap)
            return

        update_state = '{0} install'.format(self.pkg_manager.name)
        self.state.start(update_state)

        self._module_setup()

        cmd = self.config['chroot_setup_cmd']
        if cmd:
            if isinstance(cmd, str):
                cmd = cmd.split()
            self.pkg_manager.init_install_output += self.pkg_manager.execute(*cmd, returnOutput=1)

        if 'chroot_additional_packages' in self.config and self.config['chroot_additional_packages']:
            cmd = self.config['chroot_additional_packages']
            if isinstance(cmd, str):
                cmd = cmd.split()
            cmd = ['install'] + cmd
            self.pkg_manager.init_install_output += self.pkg_manager.execute(*cmd, returnOutput=1)

        self.state.finish(update_state)

    @traceLog()
    @noop_in_bootstrap
    def _fixup_build_user(self):
        """ensure chrootuser has correct UID"""
        self.doChroot(['/usr/sbin/usermod', '-u', str(self.chrootuid),
                       self.chrootuser],
                      shell=False, nosync=True)

    @traceLog()
    @noop_in_bootstrap
    def _make_build_user(self):
        if not os.path.exists(self.make_chroot_path('usr/sbin/useradd')):
            raise RootError("Could not find useradd in chroot, maybe the install failed?")

        excluded = [self.make_chroot_path(self.homedir, path)
                    for path in self.config['exclude_from_homedir_cleanup']] + \
            self.mounts.get_mountpoints()
        file_util.rmtree(self.make_chroot_path(self.homedir),
                    selinux=self.selinux, exclude=excluded)

        # ok for these two to fail
        if self.config['clean']:
            self.doChroot(['/usr/sbin/userdel', '-r', '-f', self.chrootuser],
                          shell=False, raiseExc=False, nosync=True)
        else:
            self.doChroot(['/usr/sbin/userdel', '-f', self.chrootuser],
                          shell=False, raiseExc=False, nosync=True)
        self.doChroot(['/usr/sbin/groupdel', self.chrootgroup],
                      shell=False, raiseExc=False, nosync=True)

        if self.chrootgid:
            self.doChroot(['/usr/sbin/groupadd', '-g', self.chrootgid, self.chrootgroup],
                          shell=False, nosync=True)
        self.doChroot(shlex.split(self.config['useradd']), shell=False, nosync=True)
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
        # TODOs:
        # - we should put all bootstrap logs to - say - bootstrap.log
        # - _resetLogging() actually needs to be called only once - only for
        #   target chroot (or ideally on global level, through
        #   'logging.getLogger()' and not through `self.*log` reference)
        # - we should **not** drop _all_ handlers here when force=True, but only
        #   those that are intended to be replaced
        # - 'Mock Version' message should only go to log file, not to stderr
        # - we need to call this method much, much sooner, ideally before
        #   bootstrap_chroot.initialize() is called;  otherwise at least
        #   root.log is far from incomplete

        # ensure we dont attach the handlers multiple times.
        if self.logging_initialized and not force:
            return
        self.logging_initialized = True

        with self.uid_manager:
            file_util.mkdirIfAbsent(self.resultdir)
            # attach logs to log files.
            # This happens in addition to anything that
            # is set up in the config file... ie. logs go everywhere
            for (log, filename, fmt_str) in (
                    (self.state.state_log, "state.log", self.config['state_log_fmt_str']),
                    (self.build_log, "build.log", self.config['build_log_fmt_str']),
                    (self.root_log, "root.log", self.config['root_log_fmt_str'])):
                # release used FileHandlers if re-initializing to not leak FDs
                if force:
                    for handler in log.handlers[:]:
                        handler.close()
                        log.removeHandler(handler)
                fullPath = os.path.join(self.resultdir, filename)
                fh = logging.FileHandler(fullPath, "a+")
                formatter = logging.Formatter(fmt_str)
                fh.setFormatter(formatter)
                fh.setLevel(logging.NOTSET)
                log.addHandler(fh)
                log.info("Mock Version: %s", self.config['version'])

    @traceLog()
    def _init_aux_files(self):
        chroot_file_contents = self.config['files']
        for key in chroot_file_contents:
            p = self.make_chroot_path(key)
            if not os.path.exists(p):
                file_util.mkdirIfAbsent(os.path.dirname(p))
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
        file_util.mkdirIfAbsent(self.basedir)
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
                'var/cache/dnf',
                'var/cache/yum',
                'etc/rpm',
                'tmp',
                'tmp/ccache',
                'var/tmp',
                'etc/dnf',
                'etc/dnf/vars',
                'etc/yum.repos.d',
                'etc/yum',
                'proc',
                'sys']
        dirs += self.config['extra_chroot_dirs']
        for item in dirs:
            file_util.mkdirIfAbsent(self.make_chroot_path(item))

    @traceLog()
    def chown_home_dir(self):
        """ set ownership of homedir and subdirectories to mockbuild user """
        self.uid_manager.changeOwner(self.make_chroot_path(self.homedir),
                                     recursive=True)

    @traceLog()
    def prepare_installation_time_homedir(self):
        """ Create a fake home directory with an appropriate .rpmmacros. """

        rpm_config_home = os.path.join(self.rootdir, "installation-homedir")
        file_util.mkdirIfAbsent(rpm_config_home)

        # Since /proc and /sys are mounted special filesystems when RPM is running
        # to install the buildroot, it doesn't make sense for RPM to try and
        # set the permissions on them - and that might fail with permission errors.
        with open(os.path.join(rpm_config_home, ".rpmmacros"), "w") as macro_fd:
            macro_fd.write("%_netsharedpath /proc:/sys\n")

        # To make the DNF (and wrapped RPM) use the appropriate .rpmmacros file
        # we need to set the $HOME environment variable to non-standard
        # directory.  But note that we don't just set HOME=/rpmconfig because
        # `rpm --rootdir <ROOTDIR>` reads the macros file from caller's
        # filesystem, so we set HOME=/var/lib/mock/<basedir>/<root>/rpmconfig.
        return rpm_config_home

    @traceLog()
    def _prepare_rpm_macros(self):
        """
        Install the /builddir/.rpmmacros file used by /bin/rpmbuild at build
        time.
        """
        macro_dir = self.make_chroot_path(self.homedir)
        file_util.mkdirIfAbsent(macro_dir)
        macrofile_out = os.path.join(macro_dir, ".rpmmacros")
        with open(macrofile_out, 'w+') as rpmmacros:

            # user specific from rpm macro file definitions first
            if 'macrofile' in self.config:
                with open(self.config['macrofile'], 'r') as macro_conf:
                    rpmmacros.write("%s\n\n" % macro_conf.read())

            for key, value in list(self.config['macros'].items()):
                rpmmacros.write("%s %s\n" % (key, value))

    @traceLog()
    def _setup_build_dirs(self):
        build_dirs = ['RPMS', 'SPECS', 'SRPMS', 'SOURCES', 'BUILD', 'BUILDROOT',
                      'originals']
        file_util.mkdirIfAbsent(self.make_chroot_path(self.builddir))
        with self.uid_manager:
            self.uid_manager.changeOwner(self.make_chroot_path(self.builddir))
            for item in build_dirs:
                path = self.make_chroot_path(self.builddir, item)
                file_util.mkdirIfAbsent(path)
                self.uid_manager.changeOwner(path)
            if self.config['clean']:
                self.chown_home_dir()
            self._prepare_rpm_macros()

    @traceLog()
    def _setup_nspawn_btrfs_device(self):
        if not util.USE_NSPAWN or self.is_bootstrap:
            return
        if os.path.exists('/dev/btrfs-control'):
            self.config['nspawn_args'].append('--bind=/dev/btrfs-control')

    @traceLog()
    def _setup_nspawn_loop_devices(self):
        if not util.USE_NSPAWN or self.is_bootstrap:
            return

        self.config['nspawn_args'].append('--bind=/dev/loop-control')
        # for nspawn we create the loop devices directly on host
        for i in range(self.config['dev_loop_count']):
            loop_file = '/dev/loop{}'.format(i)
            try:
                os.mknod(loop_file, stat.S_IFBLK | 0o666, os.makedev(7, i))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
            self.config['nspawn_args'].append('--bind={0}'.format(loop_file))

    @traceLog()
    def _setup_devices(self):
        if self.config['internal_dev_setup']:
            file_util.rmtree(self.make_chroot_path("dev"), selinux=self.selinux, exclude=self.mounts.get_mountpoints())
            file_util.mkdirIfAbsent(self.make_chroot_path("dev", "pts"))
            file_util.mkdirIfAbsent(self.make_chroot_path("dev", "shm"))
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
                (stat.S_IFCHR | 0o660, os.makedev(10, 234), "dev/btrfs-control"),
                (stat.S_IFCHR | 0o666, os.makedev(10, 237), "dev/loop-control"),
                (stat.S_IFCHR | 0o600, os.makedev(10, 57), "dev/prandom"),
                (stat.S_IFCHR | 0o600, os.makedev(10, 183), "dev/hwrng"),
            ]
            for i in range(self.config['dev_loop_count']):
                devFiles.append((stat.S_IFBLK | 0o666, os.makedev(7, i), "dev/loop{loop_number}".format(loop_number=i)))
            kver = os.uname()[2]
            self.root_log.debug("kernel version == %s", kver)
            for i in devFiles:
                src_path = "/" + i[2]
                chroot_path = self.make_chroot_path(i[2])

                if util.cmpKernelVer(kver, '2.6.18') >= 0 and src_path == '/dev/ptmx':
                    continue

                if os.path.ismount(chroot_path):
                    # repeated call of bootstrap._init() in chain() in container
                    # where we can not mknod so we bindmount instead
                    self.root_log.debug("file %s is already mounted", chroot_path)
                    continue

                # create node, but only if it exist on host too
                # except for loop devices, which only show up on the host after they are first used
                if os.path.exists(src_path) or "loop" in src_path:
                    try:
                        os.mknod(chroot_path, i[0], i[1])
                    except OSError as e:
                        # If mknod gives us a permission error, fall back to a different
                        # strategy of using a bind mount from root to host. This won't
                        # work for the loop devices, so just skip them in this case.
                        if e.errno == errno.EPERM:
                            if os.path.exists(src_path):
                                self.mounts.add_device_bindmount(src_path)
                            continue
                        raise

                    # Further adjustments if we created a new node instead of bind-mounting
                    # an existing one:

                    # set context. (only necessary if host running selinux enabled.)
                    # fails gracefully if chcon not installed.
                    if self.selinux:
                        util.do(["chcon", "--reference=" + src_path, chroot_path],
                                raiseExc=0, shell=False, env=self.env)

                    if src_path in ('/dev/tty', '/dev/ptmx'):
                        os.chown(chroot_path, pwd.getpwnam('root')[2], grp.getgrnam('tty')[2])

            os.symlink("/proc/self/fd/0", self.make_chroot_path("dev/stdin"))
            os.symlink("/proc/self/fd/1", self.make_chroot_path("dev/stdout"))
            os.symlink("/proc/self/fd/2", self.make_chroot_path("dev/stderr"))

            if os.path.isfile(self.make_chroot_path('etc', 'mtab')) or \
               os.path.islink(self.make_chroot_path('etc', 'mtab')):
                os.remove(self.make_chroot_path('etc', 'mtab'))
            os.symlink("../proc/self/mounts", self.make_chroot_path('etc', 'mtab'))

            # symlink /dev/fd in the chroot for everything except RHEL4
            if util.cmpKernelVer(kver, '2.6.9') > 0:
                os.symlink("/proc/self/fd", self.make_chroot_path("dev/fd"))

            os.umask(prevMask)

            os.symlink("pts/ptmx", self.make_chroot_path('/dev/ptmx'))

    @traceLog()
    def _setup_files(self):
        # self.root_log.debug('touch required files')
        for item in [self.make_chroot_path('etc', 'fstab'),
                     self.make_chroot_path('etc', 'yum', 'yum.conf'),
                     self.make_chroot_path('etc', 'dnf', 'dnf.conf'),
                     self.make_chroot_path('var', 'log', 'yum.log')]:
            file_util.touch(item)
        short_yum_confpath = self.make_chroot_path('etc', 'yum.conf')
        if not os.path.exists(short_yum_confpath):
            os.symlink("yum/yum.conf", short_yum_confpath)

    @traceLog()
    def _setup_files_postinstall(self):
        for item in [self.make_chroot_path('etc', 'os-release')]:
            file_util.touch(item)

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
                file_util.mkdirIfAbsent(dst)
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
    def file_on_cmdline(self, filename):
        """
        If the bootstrap chroot feature is enabled, and the FILENAME represents
        a filename (file exists on host), bind-mount it into the bootstrap
        chroot automatically and return its modified filename (relatively to
        bootstrap chroot).  But on some places, we still need to access the
        host's file so we use BindMountedFile() wrapper.
        """
        bootstrap = self.bootstrap_buildroot
        if not bootstrap:
            return filename

        # optimized of
        # not os.path.exists(filename) or not filename.lower().endswith('.rpm')
        if not (os.path.exists(filename) and filename.lower().endswith('.rpm')):
            # probably just '--install pkgname'
            # or '--install /usr/bin/time'
            return filename

        basename = os.path.basename(filename)
        if basename in self._homedir_bindmounts:
            raise BadCmdline("File '{0}' can not be bind-mounted to "
                             "bootstrap chroot twice".format(basename))
        self._homedir_bindmounts[basename] = 1

        host_filename = os.path.abspath(filename)
        chroot_filename = os.path.join(
            bootstrap.homedir, basename,
        )
        bind_path = bootstrap.make_chroot_path(chroot_filename)
        bootstrap.mounts.add_user_mount(mounts.BindMountPoint(
            srcpath=filename,
            bindpath=bind_path,
        ))

        return util.BindMountedFile(chroot_filename, host_filename)

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
                file_util.rmtree(self.rootdir, selinux=self.selinux)
            file_util.rmtree(self.basedir, selinux=self.selinux)
        self.chroot_was_initialized = False
        self.plugins.call_hooks('postclean')
        # intentionally we do not call bootstrap hook here - it does not have sense

    @property
    def uses_bootstrap_image(self):
        return self.is_bootstrap and self.use_bootstrap_image

    @traceLog()
    def install_as_root(self, *deps):
        """ Becomes root user and calls self.install() """
        try:
            self.uid_manager.becomeUser(0, 0)
            self.install(*deps)
        finally:
            self.uid_manager.restorePrivs()

    @traceLog()
    def install(self, *rpms):
        """Call package manager to install the input rpms into the chroot"""
        # pass build reqs (as strings) to installer
        self.root_log.info("installing package(s): %s", " ".join(rpms))
        output = self.pkg_manager.install(*rpms, returnOutput=1)
        self.root_log.info(output)

    @traceLog()
    def remove(self, *rpms):
        """Call package manager to remove the input rpms from the chroot"""
        self.root_log.info("removing package(s): %s", " ".join(rpms))
        output = self.pkg_manager.remove(*rpms, returnOutput=1)
        self.root_log.info(output)
