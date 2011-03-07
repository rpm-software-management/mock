# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Originally written by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Major reorganization and adaptation by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import fcntl
import glob
import imp
import logging
import os
import shutil
import stat
import grp
try:
    import uuid
    gotuuid = True
except:
    gotuuid = False


# our imports
import mock.util
import mock.exception
from mock.trace_decorator import traceLog, decorate, getLog

# classes
class Root(object):
    """controls setup of chroot environment"""
    decorate(traceLog())
    def __init__(self, config, uidManager):
        self._state = 'unstarted'
        self.uidManager = uidManager
        self._hooks = {}
        self.chrootWasCached = False
        self.chrootWasCleaned = False
        self.preExistingDeps = []
        self.logging_initialized = False
        self.buildrootLock = None
        self.version = config['version']

        self.sharedRootName = config['root']
        if config.has_key('unique-ext'):
            config['root'] = "%s-%s" % (config['root'], config['unique-ext'])

        self.basedir = os.path.join(config['basedir'], config['root'])
        self.rpmbuild_arch = config['rpmbuild_arch']
        self._rootdir = os.path.join(self.basedir, 'root')
        self.homedir = config['chroothome']
        self.builddir = os.path.join(self.homedir, 'build')

        # result dir
        self.resultdir = config['resultdir'] % config

        self.root_log = getLog("mock")
        self.build_log = getLog("mock.Root.build")
        self._state_log = getLog("mock.Root.state")

        # config options
        self.configs = config['config_paths']
        self.config_name = config['chroot_name']
        self.chrootuid = config['chrootuid']
        self.chrootuser = 'mockbuild'
        self.chrootgid = config['chrootgid']
        self.chrootgroup = 'mockbuild'
        self.yum_conf_content = config['yum.conf']
        self.use_host_resolv = config['use_host_resolv']
        self.chroot_file_contents = config['files']
        self.chroot_setup_cmd = config['chroot_setup_cmd']
        if isinstance(self.chroot_setup_cmd, basestring):
            # accept strings in addition to other sequence types
            self.chroot_setup_cmd = self.chroot_setup_cmd.split()
        self.yum_path = '/usr/bin/yum'
        self.yum_builddep_path = '/usr/bin/yum-builddep'
        self.macros = config['macros']
        self.more_buildreqs = config['more_buildreqs']
        self.cache_topdir = config['cache_topdir']
        self.cachedir = os.path.join(self.cache_topdir, self.sharedRootName)
        self.useradd = config['useradd']
        self.online = config['online']
        self.internal_dev_setup = config['internal_dev_setup']

        self.plugins = config['plugins']
        self.pluginConf = config['plugin_conf']
        self.pluginDir = config['plugin_dir']
        for key in self.pluginConf.keys():
            if not key.endswith('_opts'): continue
            self.pluginConf[key]['basedir'] = self.basedir
            self.pluginConf[key]['cache_topdir'] = self.cache_topdir
            self.pluginConf[key]['cachedir'] = self.cachedir
            self.pluginConf[key]['root'] = self.sharedRootName

        # mount/umount
        self.umountCmds = ['umount -n %s' % self.makeChrootPath('proc'),
                'umount -n %s' % self.makeChrootPath('sys')
               ]
        self.mountCmds = ['mount -n -t proc   mock_chroot_proc   %s' % self.makeChrootPath('proc'),
                'mount -n -t sysfs  mock_chroot_sysfs  %s' % self.makeChrootPath('sys'),
               ]

        self.build_log_fmt_str = config['build_log_fmt_str']
        self.root_log_fmt_str = config['root_log_fmt_str']
        self._state_log_fmt_str = config['state_log_fmt_str']

        self.state("init plugins")
        self._initPlugins()

        # default to not doing selinux things
        self.selinux = False

        # if the selinux plugin is disabled and we have SELinux enabled
        # on the host, we need to do SELinux things, so set the selinux
        # state variable to true
        if self.pluginConf['selinux_enable'] == False and mock.util.selinuxEnabled():
            self.selinux = True

        # officially set state so it is logged
        self.state("start")

    # =============
    #  'Public' API
    # =============
    decorate(traceLog())
    def addHook(self, stage, function):
        hooks = self._hooks.get(stage, [])
        if function not in hooks:
            hooks.append(function)
            self._hooks[stage] = hooks

    decorate(traceLog())
    def state(self, newState = None):
        if newState is not None:
            self._state = newState
            self._state_log.info("State Changed: %s" % self._state)

        return self._state

    decorate(traceLog())
    def clean(self):
        """clean out chroot with extreme prejudice :)"""
        self.tryLockBuildRoot()
        self.state("clean")
        self._callHooks('clean')
        self._unlock_and_rm_chroot()
        self.chrootWasCleaned = True
        self.unlockBuildRoot()

    decorate(traceLog())
    def _unlock_and_rm_chroot(self):
        if not os.path.exists(self.basedir):
            return
        t = self.basedir + ".tmp"
        if os.path.exists(t):
            mock.util.rmtree(t, selinux=self.selinux)
        os.rename(self.basedir, t)
        self.buildrootLock.close()
        try:
            mock.util.rmtree(t, selinux=self.selinux)
        except OSError, e:
            self.root_log.error(e)
            self.root_log.error("contents of /proc/mounts:\n%s" % open('/proc/mounts').read())
            self.root_log.error("looking for users of %s" % t)
            self._show_path_user(t)
            raise
        self.root_log.info("chroot (%s) unlocked and deleted" % self.basedir)

    decorate(traceLog())
    def scrub(self, scrub_opts):
        """clean out chroot and/or cache dirs with extreme prejudice :)"""
        self.tryLockBuildRoot()
        self.state("clean")
        self._resetLogging()
        self._callHooks('clean')
        for scrub in scrub_opts:
            if scrub == 'all':
                self.root_log.info("scrubbing everything for %s" % self.config_name)
                self._unlock_and_rm_chroot()
                self.chrootWasCleaned = True
                mock.util.rmtree(self.cachedir, selinux=self.selinux)
            elif scrub == 'chroot':
                self.root_log.info("scrubbing chroot for %s" % self.config_name)
                self._unlock_and_rm_chroot()
                self.chrootWasCleaned = True
            elif scrub == 'cache':
                self.root_log.info("scrubbing cache for %s" % self.config_name)
                mock.util.rmtree(self.cachedir, selinux=self.selinux)
            elif scrub == 'c-cache':
                self.root_log.info("scrubbing c-cache for %s" % self.config_name)
                mock.util.rmtree(os.path.join(self.cachedir, 'ccache'), selinux=self.selinux)
            elif scrub == 'root-cache':
                self.root_log.info("scrubbing root-cache for %s" % self.config_name)
                mock.util.rmtree(os.path.join(self.cachedir, 'root_cache'), selinux=self.selinux)
            elif scrub == 'yum-cache':
                self.root_log.info("scrubbing yum-cache for %s" % self.config_name)
                mock.util.rmtree(os.path.join(self.cachedir, 'yum_cache'), selinux=self.selinux)
        self.unlockBuildRoot()

    decorate(traceLog())
    def tryLockBuildRoot(self):
        self.state("lock buildroot")
        try:
            self.buildrootLock = open(os.path.join(self.basedir, "buildroot.lock"), "a+")
        except IOError, e:
            return 0

        try:
            fcntl.lockf(self.buildrootLock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError, e:
            raise mock.exception.BuildRootLocked, "Build root is locked by another process."

        return 1

    decorate(traceLog())
    def unlockBuildRoot(self):
        self.state("unlock buildroot")
        if self.buildrootLock:
            self.buildrootLock.close()
            try:
                os.remove(os.path.join(self.basedir, "buildroot.lock"))
            except OSError,e:
                pass
        return 0

    decorate(traceLog())
    def makeChrootPath(self, *args):
        '''For safety reasons, self._rootdir should not be used directly. Instead
        use this handy helper function anytime you want to reference a path in
        relation to the chroot.'''
        tmp = self._rootdir + "/" + "/".join(args)
        return tmp.replace("//", "/")

    decorate(traceLog())
    def init(self):
        try:
            self._init()
        except (KeyboardInterrupt, Exception):
            self._callHooks('initfailed')
            raise

    decorate(traceLog())
    def _init(self):
        self.state("init")

        # NOTE: removed the following stuff vs mock v0:
        #   --> /etc/ is no longer 02775 (new privs model)
        #   --> no /etc/yum.conf symlink (F7 and above)

        # create our base directory hierarchy
        mock.util.mkdirIfAbsent(self.basedir)
        mock.util.mkdirIfAbsent(self.makeChrootPath())

        self.uidManager.dropPrivsTemp()
        try:
            mock.util.mkdirIfAbsent(self.resultdir)
        except (OSError,), e:
            if e.errno == 13:
                raise mock.exception.ResultDirNotAccessible( ResultDirNotAccessible.__doc__ % self.resultdir )
        self.uidManager.restorePrivs()

        # lock this buildroot so we dont get stomped on.
        self.tryLockBuildRoot()

        # create our log files. (if they havent already)
        self._resetLogging()

        # write out config details
        self.root_log.debug('rootdir = %s' % self.makeChrootPath())
        self.root_log.debug('resultdir = %s' % self.resultdir)

        # set up plugins:
        self._callHooks('preinit')

        # create skeleton dirs
        self.root_log.debug('create skeleton dirs')
        for item in [
                     'var/lib/rpm',
                     'var/lib/yum',
                     'var/lib/dbus',
                     'var/log',
                     'var/lock/rpm',
                     'etc/rpm',
                     'tmp',
                     'var/tmp',
                     'etc/yum.repos.d',
                     'etc/yum',
                     'proc',
                     'sys',
                    ]:
            mock.util.mkdirIfAbsent(self.makeChrootPath(item))

        # touch files
        self.root_log.debug('touch required files')
        for item in [self.makeChrootPath('etc', 'mtab'),
                     self.makeChrootPath('etc', 'fstab'),
                     self.makeChrootPath('var', 'log', 'yum.log')]:
            mock.util.touch(item)

        # write in yum.conf into chroot
        # always truncate and overwrite (w+)
        self.root_log.debug('configure yum')
        yumconf = self.makeChrootPath('etc', 'yum', 'yum.conf')
        yumconf_fo = open(yumconf, 'w+')
        yumconf_fo.write(self.yum_conf_content)
        yumconf_fo.close()

        # symlink /etc/yum.conf to /etc/yum/yum.conf (FC6 requires)
        try:
            os.unlink(self.makeChrootPath("etc", "yum.conf"))
        except OSError:
            pass
        os.symlink('yum/yum.conf', self.makeChrootPath("etc", "yum.conf"))

        # set up resolver configuration
        if self.use_host_resolv:
            etcdir = self.makeChrootPath('etc')

            resolvconfpath = self.makeChrootPath('etc', 'resolv.conf')
            if os.path.exists(resolvconfpath):
                os.remove(resolvconfpath)
            shutil.copy2('/etc/resolv.conf', etcdir)

            hostspath = self.makeChrootPath('etc', 'hosts')
            if os.path.exists(hostspath):
                os.remove(hostspath)
            shutil.copy2('/etc/hosts', etcdir)

        if gotuuid:
            # Anything that tries to use libdbus inside the chroot will require this
            # FIXME - merge this code with other OS-image building code
            machine_uuid = uuid.uuid4().hex
            dbus_uuid_path = self.makeChrootPath('var', 'lib', 'dbus', 'machine-id')
            f = open(dbus_uuid_path, 'w')
            f.write(machine_uuid)
            f.write('\n')
            f.close()

        # files that need doing
        for key in self.chroot_file_contents:
            p = self.makeChrootPath(key)
            if not os.path.exists(p):
                # create directory if necessary
                mock.util.mkdirIfAbsent(os.path.dirname(p))
                # write file
                fo = open(p, 'w+')
                fo.write(self.chroot_file_contents[key])
                fo.close()

        if self.internal_dev_setup:
            self._setupDev()

        # yum stuff
        self.state("running yum")
        try:
            self._mountall()
            if self.chrootWasCleaned:
                self.yum_init_install_output = self._yum(self.chroot_setup_cmd, returnOutput=1)
            if self.chrootWasCached:
                self._yum(('update',), returnOutput=1)

            # create user
            self._makeBuildUser()

            # create rpmbuild dir
            self._buildDirSetup()

            # set up timezone to match host
            localtimedir = self.makeChrootPath('etc')
            localtimepath = self.makeChrootPath('etc', 'localtime')
            if os.path.exists(localtimepath):
                os.remove(localtimepath)
            shutil.copy2('/etc/localtime', localtimedir)

            # done with init
            self._callHooks('postinit')
        finally:
            self._umountall()
        self.unlockBuildRoot()

    decorate(traceLog())
    def _setupDev(self):
        # files in /dev
        mock.util.rmtree(self.makeChrootPath("dev"), selinux=self.selinux)
        mock.util.mkdirIfAbsent(self.makeChrootPath("dev", "pts"))
        mock.util.mkdirIfAbsent(self.makeChrootPath("dev", "shm"))
        prevMask = os.umask(0000)
        devFiles = [
            (stat.S_IFCHR | 0666, os.makedev(1, 3), "dev/null"),
            (stat.S_IFCHR | 0666, os.makedev(1, 7), "dev/full"),
            (stat.S_IFCHR | 0666, os.makedev(1, 5), "dev/zero"),
            (stat.S_IFCHR | 0666, os.makedev(1, 8), "dev/random"),
            (stat.S_IFCHR | 0444, os.makedev(1, 9), "dev/urandom"),
            (stat.S_IFCHR | 0600, os.makedev(5, 1), "dev/console"),
        ]
        kver = os.uname()[2]
        getLog().debug("kver == %s" % kver)
        # make the device node for el4 and el5
        if mock.util.cmpKernelEVR(kver, '2.6.18') <= 0:
            devFiles.append((stat.S_IFCHR | 0666, os.makedev(5, 2), "dev/ptmx"))

        for i in devFiles:
            # create node
            os.mknod( self.makeChrootPath(i[2]), i[0], i[1])
            # set context. (only necessary if host running selinux enabled.)
            # fails gracefully if chcon not installed.
            if self.selinux:
                mock.util.do(
                    ["chcon", "--reference=/%s"% i[2], self.makeChrootPath(i[2])]
                    , raiseExc=0, shell=False)

        os.symlink("/proc/self/fd/0", self.makeChrootPath("dev/stdin"))
        os.symlink("/proc/self/fd/1", self.makeChrootPath("dev/stdout"))
        os.symlink("/proc/self/fd/2", self.makeChrootPath("dev/stderr"))

        # if hosted on EL{4,5} create /dev/tty node in chroot
        if mock.util.cmpKernelEVR(kver, '2.6.19') <= 0:
            os.mknod(self.makeChrootPath("dev/tty"), stat.S_IFCHR|0666, os.makedev(5, 0))
            getLog().debug("created /dev/tty node device node")

        # symlink /dev/fd in the chroot for everything except RHEL4
        if mock.util.cmpKernelEVR(kver, '2.6.9') > 0:
            os.symlink("/proc/self/fd",   self.makeChrootPath("dev/fd"))

        # comment the below out for now
        # symlinks for Fedora and el6 hosts
        # if mock.util.cmpKernelEVR(kver, '2.6.19') > 0:
        #    os.symlink("/dev/pts/ptmx", self.makeChrootPath("dev/ptmx"))
        #    if os.path.exists(self.makeChrootPath("dev/tty")):
        #        getLog().debug("removed dev/tty device node!")
        #        os.remove(self.makeChrootPath("dev/tty"))
        #    os.symlink("/dev/ptmx", self.makeChrootPath("dev/tty"))
        #    getLog().debug("symlinked dev/tty to ptmx")

        os.umask(prevMask)

        # mount/umount
        for devUnmtCmd in (
                'umount -n %s' % self.makeChrootPath('/dev/pts'),
                'umount -n %s' % self.makeChrootPath('/dev/shm') ):
            if devUnmtCmd not in self.umountCmds:
                self.umountCmds.append(devUnmtCmd)

        mountopt = 'gid=%d,mode=0620,ptmxmode=0666' % grp.getgrnam('tty').gr_gid
        if mock.util.cmpKernelEVR(kver, '2.6.29') >= 0:
            mountopt += ',newinstance'

        for devMntCmd in (
                'mount -n -t devpts -o %s mock_chroot_devpts %s' % (mountopt, self.makeChrootPath('/dev/pts')),
                'mount -n -t tmpfs mock_chroot_shmfs %s' % self.makeChrootPath('/dev/shm') ):
            if devMntCmd not in self.mountCmds:
                self.mountCmds.append(devMntCmd)

    # bad hack
    # comment out decorator here so we dont get double exceptions in the root log
    #decorate(traceLog())
    def doChroot(self, command, env="", shell=True, *args, **kargs):
        """execute given command in root"""
        return mock.util.do(command, chrootPath=self.makeChrootPath(),
                            shell=shell, *args, **kargs )

    decorate(traceLog())
    def yumInstall(self, *rpms):
        """call yum to install the input rpms into the chroot"""
        # pass build reqs (as strings) to installer
        self.root_log.info("installing package(s): %s" % " ".join(rpms))
        try:
            self._mountall()
            output = self._yum(['install'] + list(rpms), returnOutput=1)
            self.root_log.info(output)
        finally:
            self._umountall()

    decorate(traceLog())
    def yumUpdate(self):
        """use yum to update the chroot"""
        try:
            self._mountall()
            self._yum(('update',), returnOutput=1)
        finally:
            self._umountall()

    decorate(traceLog())
    def installSrpmDeps(self, *srpms):
        """figure out deps from srpm. call yum to install them"""
        try:
            self.uidManager.becomeUser(0, 0)

            def _yum_and_check(cmd):
                output = self._yum(cmd, returnOutput=1)
                for line in output.split('\n'):
                    if line.lower().find('No Package found for'.lower()) != -1:
                        raise mock.exception.BuildError, "Bad build req: %s. Exiting." % line

            # first, install pre-existing deps and configured additional ones
            deps = list(self.preExistingDeps)
            for hdr in mock.util.yieldSrpmHeaders(srpms, plainRpmOk=1):
                # get text buildreqs
                deps.extend(mock.util.getAddtlReqs(hdr, self.more_buildreqs))
            if deps:
                # everything exists, okay, install them all.
                # pass build reqs to installer
                args = ['resolvedep'] + deps
                _yum_and_check(args)
                # nothing made us exit, so we continue
                args[0] = 'install'
                self._yum(args, returnOutput=1)

            # install actual build dependencies
            _yum_and_check(['builddep'] + list(srpms))
        finally:
            self.uidManager.restorePrivs()


    #
    # UNPRIVILEGED:
    #   Everything in this function runs as the build user
    #       -> except hooks. :)
    #
    decorate(traceLog())
    def build(self, srpm, timeout):
        """build an srpm into binary rpms, capture log"""

        # tell caching we are building
        self._callHooks('earlyprebuild')

        try:
            self._setupDev()
            self._mountall()
            self.uidManager.becomeUser(self.chrootuid, self.chrootgid)
            self.state("setup")

            srpmChrootFilename = self._copySrpmIntoChroot(srpm)
            srpmBasename = os.path.basename(srpmChrootFilename)

            # Completely/Permanently drop privs while running the following:
            self.doChroot(
                ["rpm", "-Uvh", "--nodeps", srpmChrootFilename],
                shell=False,
                uid=self.chrootuid,
                gid=self.chrootgid,
                )

            # rebuild srpm/rpm from SPEC file
            specs = glob.glob(self.makeChrootPath(self.builddir, "SPECS", "*.spec"))
            if len(specs) < 1:
                raise mock.exception.PkgError, "No Spec file found in srpm: %s" % srpmBasename

            spec = specs[0] # if there's more than one then someone is an idiot
            chrootspec = spec.replace(self.makeChrootPath(), '') # get rid of rootdir prefix
            # Completely/Permanently drop privs while running the following:

            self.doChroot(
                ["bash", "--login", "-c", 'rpmbuild -bs --target %s --nodeps %s' % (self.rpmbuild_arch, chrootspec)],
                shell=False,
                logger=self.build_log, timeout=timeout,
                uid=self.chrootuid,
                gid=self.chrootgid,
                )

            rebuiltSrpmFile = glob.glob("%s/%s/SRPMS/*.src.rpm" % (self.makeChrootPath(), self.builddir))
            if len(rebuiltSrpmFile) != 1:
                raise mock.exception.PkgError, "Expected to find single rebuilt srpm, found %d." % len(rebuiltSrpmFile)

            rebuiltSrpmFile = rebuiltSrpmFile[0]
            self.installSrpmDeps(rebuiltSrpmFile)

            #have to permanently drop privs or rpmbuild regains them
            self.state("build")

            # tell caching we are building
            self._callHooks('prebuild')

            # --nodeps because rpm in the root may not be able to read rpmdb
            # created by rpm that created it (outside of chroot)
            self.doChroot(
                ["bash", "--login", "-c", 'rpmbuild -bb --target %s --nodeps %s' % (self.rpmbuild_arch, chrootspec)],
                shell=False,
                logger=self.build_log, timeout=timeout,
                uid=self.chrootuid,
                gid=self.chrootgid,
                )

            bd_out = self.makeChrootPath(self.builddir)
            rpms = glob.glob(bd_out + '/RPMS/*.rpm')
            srpms = glob.glob(bd_out + '/SRPMS/*.rpm')
            packages = rpms + srpms

            self.root_log.debug("Copying packages to result dir")
            for item in packages:
                shutil.copy2(item, self.resultdir)

        finally:
            self.uidManager.restorePrivs()
            self._umountall()

            # tell caching we are done building
            self._callHooks('postbuild')


    #
    # UNPRIVILEGED:
    #   Everything in this function runs as the build user
    #       -> except hooks. :)
    #
    decorate(traceLog())
    def buildsrpm(self, spec, sources, timeout):
        """build an srpm, capture log"""

        # tell caching we are building
        self._callHooks('earlyprebuild')

        try:
            self._mountall()
            self.uidManager.becomeUser(self.chrootuid, self.chrootgid)
            self.state("setup")

            # copy spec/sources
            shutil.copy(spec, self.makeChrootPath(self.builddir, "SPECS"))

            # Resolve any symlinks
            sources = os.path.realpath(sources)

            if os.path.isdir(sources):
                os.rmdir(self.makeChrootPath(self.builddir, "SOURCES"))
                shutil.copytree(sources, self.makeChrootPath(self.builddir, "SOURCES"))
            else:
                shutil.copy(sources, self.makeChrootPath(self.builddir, "SOURCES"))

            spec =  self.makeChrootPath(self.builddir, "SPECS", os.path.basename(spec))
            chrootspec = spec.replace(self.makeChrootPath(), '') # get rid of rootdir prefix

            spec =  self.makeChrootPath(self.builddir, "SPECS", os.path.basename(spec))
            chrootspec = spec.replace(self.makeChrootPath(), '') # get rid of rootdir prefix

            # Completely/Permanently drop privs while running the following:
            self.state("buildsrpm")
            self.doChroot(
                ["bash", "--login", "-c", 'rpmbuild -bs --target %s --nodeps %s' % (self.rpmbuild_arch, chrootspec)],
                shell=False,
                logger=self.build_log, timeout=timeout,
                uid=self.chrootuid,
                gid=self.chrootgid,
                )

            rebuiltSrpmFile = glob.glob("%s/%s/SRPMS/*.src.rpm" % (self.makeChrootPath(), self.builddir))
            if len(rebuiltSrpmFile) != 1:
                raise mock.exception.PkgError, "Expected to find single rebuilt srpm, found %d." % len(rebuiltSrpmFile)

            rebuiltSrpmFile = rebuiltSrpmFile[0]
            srpmBasename = rebuiltSrpmFile.split("/")[-1]

            self.root_log.debug("Copying package to result dir")
            shutil.copy2(rebuiltSrpmFile, self.resultdir)

            resultSrpmFile = self.resultdir + "/" + srpmBasename

        finally:
            self.uidManager.restorePrivs()
            self._umountall()

            # tell caching we are done building
            self._callHooks('postbuild')

            try:
                return resultSrpmFile
            except:
                return None




    # =============
    # 'Private' API
    # =============
    decorate(traceLog())
    def _callHooks(self, stage):
        hooks = self._hooks.get(stage, [])
        for hook in hooks:
            hook()

    decorate(traceLog())
    def _initPlugins(self):
        # Import plugins  (simplified copy of what yum does). Can add yum
        #  features later when we prove we need them.
        for modname, modulefile in [ (p, os.path.join(self.pluginDir, "%s.py" % p)) for p in self.plugins ]:
            if not self.pluginConf.get("%s_enable"%modname): continue
            fp, pathname, description = imp.find_module(modname, [self.pluginDir])
            try:
                module = imp.load_module(modname, fp, pathname, description)
            finally:
                fp.close()

            if not hasattr(module, 'requires_api_version'):
                raise mock.exception.Error('Plugin "%s" doesn\'t specify required API version' % modname)

            module.init(self, self.pluginConf["%s_opts" % modname])

    decorate(traceLog())
    def _mountall(self):
        """mount 'normal' fs like /dev/ /proc/ /sys"""
        for cmd in self.mountCmds:
            self.root_log.debug(cmd)
            mock.util.do(cmd, shell=True)

    decorate(traceLog())
    def _umountall(self):
        """umount all mounted chroot fs."""
        # first try removing all expected mountpoints.
        for cmd in reversed(self.umountCmds):
            try:
                mock.util.do(cmd, raiseExc=1, shell=True)
            except mock.exception.Error, e:
                # the exception already contains info about the error.
                self.root_log.warning(e)
                self._show_path_user(cmd.split()[-1])
        # then remove anything that might be left around.
        mountpoints = open("/proc/mounts").read().strip().split("\n")
        # umount in reverse mount order to prevent nested mount issues that
        # may prevent clean unmount.
        for mountline in reversed(mountpoints):
            mountpoint = mountline.split()[1]
            if os.path.realpath(mountpoint).startswith(os.path.realpath(self.makeChrootPath()) + "/"):
                cmd = "umount -n %s" % mountpoint
                self.root_log.warning("Forcibly unmounting '%s' from chroot." % mountpoint)
                mock.util.do(cmd, raiseExc=0, shell=True)

    decorate(traceLog())
    def _show_path_user(self, path):
        cmd = ['/sbin/fuser', '-a', '-v', path]
        self.root_log.debug("using 'fuser' to find users of %s" % path)
        out = mock.util.do(cmd, returnOutput=1)
        self.root_log.debug(out)
        return out

    decorate(traceLog())
    def _yum(self, cmd, returnOutput=0):
        """use yum to install packages/package groups into the chroot"""

        yumcmd = [self.yum_path]
        cmdix = 0
        # invoke yum-builddep instead of yum if cmd is builddep
        if cmd[0] == "builddep":
            yumcmd[0] = self.yum_builddep_path
            cmdix = 1
        yumcmd.extend(('--installroot', self.makeChrootPath()))
        if not self.online:
            yumcmd.append("-C")
        yumcmd.extend(cmd[cmdix:])
        self.root_log.debug(yumcmd)
        output = ""
        try:
            self._callHooks("preyum")
            output = mock.util.do(yumcmd, returnOutput=returnOutput)
            self._callHooks("postyum")
            return output
        except mock.exception.Error, e:
            raise mock.exception.YumError, str(e)

    decorate(traceLog())
    def _makeBuildUser(self):
        if not os.path.exists(self.makeChrootPath('usr/sbin/useradd')):
            raise mock.exception.RootError, "Could not find useradd in chroot, maybe the install failed?"

        # safe and easy. blow away existing /builddir and completely re-create.
        mock.util.rmtree(self.makeChrootPath(self.homedir), selinux=self.selinux)
        dets = { 'uid': str(self.chrootuid), 'gid': str(self.chrootgid), 'user': self.chrootuser, 'group': self.chrootgroup, 'home': self.homedir }

        # ok for these two to fail
        self.doChroot(['/usr/sbin/userdel', '-r', '-f', dets['user']], shell=False, raiseExc=False)
        self.doChroot(['/usr/sbin/groupdel', dets['group']], shell=False, raiseExc=False)

        self.doChroot(['/usr/sbin/groupadd', '-g', dets['gid'], dets['group']], shell=False)
        self.doChroot(self.useradd % dets, shell=True)
        self._enable_chrootuser_account()

    decorate(traceLog())
    def _enable_chrootuser_account(self):
        passwd = self.makeChrootPath('/etc/passwd')
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

    decorate(traceLog())
    def _resetLogging(self):
        # ensure we dont attach the handlers multiple times.
        if self.logging_initialized:
            return
        self.logging_initialized = True

        try:
            self.uidManager.dropPrivsTemp()

            # attach logs to log files.
            # This happens in addition to anything that
            # is set up in the config file... ie. logs go everywhere
            for (log, filename, fmt_str) in (
                    (self._state_log, "state.log", self._state_log_fmt_str),
                    (self.build_log, "build.log", self.build_log_fmt_str),
                    (self.root_log, "root.log", self.root_log_fmt_str)):
                fullPath = os.path.join(self.resultdir, filename)
                fh = logging.FileHandler(fullPath, "a+")
                formatter = logging.Formatter(fmt_str)
                fh.setFormatter(formatter)
                fh.setLevel(logging.NOTSET)
                log.addHandler(fh)
                log.info("Mock Version: %s" % self.version)
        finally:
            self.uidManager.restorePrivs()


    #
    # UNPRIVILEGED:
    #   Everything in this function runs as the build user
    #
    decorate(traceLog())
    def _buildDirSetup(self):
        # create all dirs as the user who will be dropping things there.
        self.uidManager.becomeUser(self.chrootuid, self.chrootgid)
        try:
            # create dir structure
            for subdir in [self.makeChrootPath(self.builddir, s) for s in ('RPMS', 'SRPMS', 'SOURCES', 'SPECS', 'BUILD', 'BUILDROOT', 'originals')]:
                mock.util.mkdirIfAbsent(subdir)

            # change ownership so we can write to build home dir
            for (dirpath, dirnames, filenames) in os.walk(self.homedir):
                for path in dirnames + filenames:
                    os.chown(os.path.join(dirpath, path), self.chrootuid, -1)
                    os.chmod(os.path.join(dirpath, path), 0755)

            # rpmmacros default
            macrofile_out = self.makeChrootPath(self.homedir, ".rpmmacros")
            rpmmacros = open(macrofile_out, 'w+')
            for key, value in self.macros.items():
                rpmmacros.write( "%s %s\n" % (key, value) )
            rpmmacros.close()

        finally:
            self.uidManager.restorePrivs()

    #
    # UNPRIVILEGED:
    #   Everything in this function runs as the build user
    #
    decorate(traceLog())
    def _copySrpmIntoChroot(self, srpm):
        srpmFilename = os.path.basename(srpm)
        dest = self.makeChrootPath(self.builddir, 'originals')
        shutil.copy2(srpm, dest)
        return os.path.join(self.builddir, 'originals', srpmFilename)

