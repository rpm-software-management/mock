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
        self.chrootWasCleaned = False
        self.preExistingDeps = ""
        self.logging_initialized = False
        self.buildrootLock = None

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
        self.chrootuid = config['chrootuid']
        self.chrootuser = 'mockbuild'
        self.chrootgid = config['chrootgid']
        self.chrootgroup = 'mockbuild'
        self.yum_conf_content = config['yum.conf']
        self.use_host_resolv = config['use_host_resolv']
        self.chroot_file_contents = config['files']
        self.chroot_setup_cmd = config['chroot_setup_cmd']
        self.yum_path = '/usr/bin/yum'
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
        mock.util.rmtree(self.basedir)
        self.chrootWasCleaned = True

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

         # create our base directory heirarchy
        mock.util.mkdirIfAbsent(self.basedir)
        mock.util.mkdirIfAbsent(self.makeChrootPath())

        self.uidManager.dropPrivsTemp()
        try:
            mock.util.mkdirIfAbsent(self.resultdir)
        except OSError:
            pass
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

        # set up resolv.conf
        if self.use_host_resolv:
            resolvdir = self.makeChrootPath('etc')
            resolvpath = self.makeChrootPath('etc', 'resolv.conf')
            if os.path.exists(resolvpath):
                os.remove(resolvpath)
            shutil.copy2('/etc/resolv.conf', resolvdir)

        # files in /etc that need doing
        for key in self.chroot_file_contents:
            p = self.makeChrootPath(key)
            if not os.path.exists(p):
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
            if not self.chrootWasCleaned:
                self.chroot_setup_cmd = 'update'
            self._yum(self.chroot_setup_cmd, returnOutput=1)
        finally:
            self._umountall()

        # create user
        self._makeBuildUser()

        # create rpmbuild dir
        self._buildDirSetup()

        # done with init
        self._callHooks('postinit')

    decorate(traceLog())
    def _setupDev(self):
        # files in /dev
        mock.util.rmtree(self.makeChrootPath("dev"))
        mock.util.mkdirIfAbsent(self.makeChrootPath("dev", "pts"))
        mock.util.mkdirIfAbsent(self.makeChrootPath("dev", "shm"))
        prevMask = os.umask(0000)
        devFiles = (
            (stat.S_IFCHR | 0666, os.makedev(1, 3), "dev/null"),
            (stat.S_IFCHR | 0666, os.makedev(1, 7), "dev/full"),
            (stat.S_IFCHR | 0666, os.makedev(1, 5), "dev/zero"),
            (stat.S_IFCHR | 0666, os.makedev(1, 8), "dev/random"),
            (stat.S_IFCHR | 0444, os.makedev(1, 9), "dev/urandom"),
            (stat.S_IFCHR | 0666, os.makedev(5, 0), "dev/tty"),
            (stat.S_IFCHR | 0600, os.makedev(5, 1), "dev/console"),
            (stat.S_IFCHR | 0666, os.makedev(5, 2), "dev/ptmx"),
        )
        for i in devFiles:
            # create node
            os.mknod( self.makeChrootPath(i[2]), i[0], i[1])
            # set context. (only necessary if host running selinux enabled.)
            # fails gracefully if chcon not installed.
            mock.util.do(
                ["chcon", "--reference=/%s"% i[2], self.makeChrootPath(i[2])]
                , raiseExc=0, shell=False)

        os.symlink("/proc/self/fd/0", self.makeChrootPath("dev/stdin"))
        os.symlink("/proc/self/fd/1", self.makeChrootPath("dev/stdout"))
        os.symlink("/proc/self/fd/2", self.makeChrootPath("dev/stderr"))
        os.umask(prevMask)

        # mount/umount
        for devUnmtCmd in (
                'umount -n %s' % self.makeChrootPath('/dev/pts'),
                'umount -n %s' % self.makeChrootPath('/dev/shm') ):
            if devUnmtCmd not in self.umountCmds:
                self.umountCmds.append(devUnmtCmd)

        for devMntCmd in (
                'mount -n -t devpts mock_chroot_devpts %s' % self.makeChrootPath('/dev/pts'),
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
    def yumInstall(self, *srpms):
        """figure out deps from srpm. call yum to install them"""
        # pass build reqs (as strings) to installer
        try:
            self._mountall()
            self._yum('install %s' % ' '.join(srpms), returnOutput=1)
        finally:
            self._umountall()

    decorate(traceLog())
    def yumUpdate(self):
        """use yum to update the chroot"""
        try:
            self._mountall()
            self._yum('update', returnOutput=1)
        finally:
            self._umountall()

    decorate(traceLog())
    def installSrpmDeps(self, *srpms):
        """figure out deps from srpm. call yum to install them"""
        try:
            self.uidManager.becomeUser(0, 0)
            arg_string = self.preExistingDeps
            for hdr in mock.util.yieldSrpmHeaders(srpms, plainRpmOk=1):
                # get text buildreqs
                a = mock.util.requiresTextFromHdr(hdr)
                b = mock.util.getAddtlReqs(hdr, self.more_buildreqs)
                for item in mock.util.uniqReqs(a, b):
                    arg_string = arg_string + " '%s'" % item

            # everything exists, okay, install them all.
            # pass build reqs (as strings) to installer
            if arg_string != "":
                output = self._yum('resolvedep %s' % arg_string, returnOutput=1)
                for line in output.split('\n'):
                    if line.lower().find('No Package found for'.lower()) != -1:
                        raise mock.exception.BuildError, "Bad build req: %s. Exiting." % line
                # nothing made us exit, so we continue
                self._yum('install %s' % arg_string, returnOutput=1)
        finally:
            self.uidManager.restorePrivs()


    #
    # UNPRIVLEGED:
    #   Everything in this function runs as the build user
    #       -> except hooks. :)
    #
    decorate(traceLog())
    def build(self, srpm, timeout):
        """build an srpm into binary rpms, capture log"""

        # tell caching we are building
        self._callHooks('earlyprebuild')

        try:
            self._mountall()
            self.uidManager.becomeUser(self.chrootuid, self.chrootgid)
            self.state("setup")

            srpmChrootFilename = self._copySrpmIntoChroot(srpm)
            srpmBasename = os.path.basename(srpmChrootFilename)

            # install srpm
            os.environ["HOME"] = self.homedir
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
                raise mock.exception.PkgError, "Didnt find single rebuilt srpm."

            rebuiltSrpmFile = rebuiltSrpmFile[0]
            self.installSrpmDeps(rebuiltSrpmFile)

            #have to permanently drop privs or rpmbuild regains them
            self.state("build")

            # tell caching we are building
            self._callHooks('prebuild')

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
    # UNPRIVLEGED:
    #   Everything in this function runs as the build user
    #       -> except hooks. :)
    #
    decorate(traceLog())
    def buildsrpm(self, spec, sources, timeout):
        """build an srpm into binary rpms, capture log"""

        # tell caching we are building
        self._callHooks('earlyprebuild')

        try:
            self._mountall()
            self.uidManager.becomeUser(self.chrootuid, self.chrootgid)
            self.state("setup")

            # copy spec/sources
            shutil.copy(spec, self.makeChrootPath(self.builddir, "SPECS"))
            os.rmdir(self.makeChrootPath(self.builddir, "SOURCES"))
            shutil.copytree(sources, self.makeChrootPath(self.builddir, "SOURCES"))

            spec =  self.makeChrootPath(self.builddir, "SPECS", os.path.basename(spec))
            chrootspec = spec.replace(self.makeChrootPath(), '') # get rid of rootdir prefix

            # Completely/Permanently drop privs while running the following:
            self.state("buildsrpm")
            os.environ["HOME"] = self.homedir
            self.doChroot(
                ["bash", "--login", "-c", 'rpmbuild -bs --target %s --nodeps %s' % (self.rpmbuild_arch, chrootspec)],
                shell=False,
                logger=self.build_log, timeout=timeout,
                uid=self.chrootuid,
                gid=self.chrootgid,
                )

            rebuiltSrpmFile = glob.glob("%s/%s/SRPMS/*.src.rpm" % (self.makeChrootPath(), self.builddir))
            if len(rebuiltSrpmFile) != 1:
                raise mock.exception.PkgError, "Didnt find single rebuilt srpm."

            rebuiltSrpmFile = rebuiltSrpmFile[0]

            srpms = glob.glob(self.makeChrootPath(self.builddir) + '/SRPMS/*.rpm')
            self.root_log.debug("Copying packages to result dir")
            for item in srpms:
                shutil.copy2(item, self.resultdir)

        finally:
            self.uidManager.restorePrivs()
            self._umountall()

            # tell caching we are done building
            self._callHooks('postbuild')





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
        for cmd in self.umountCmds:
            self.root_log.debug(cmd)
            mock.util.do(cmd, raiseExc=0, shell=True)

    decorate(traceLog())
    def _yum(self, cmd, returnOutput=0):
        """use yum to install packages/package groups into the chroot"""
        # mock-helper yum --installroot=rootdir cmd
        cmdOpts = ""
        if not self.online:
            cmdOpts = "-C"

        cmd = '%s --installroot %s %s %s' % (self.yum_path, self.makeChrootPath(), cmdOpts, cmd)
        self.root_log.debug(cmd)
        output = ""
        try:
            self._callHooks("preyum")
            output = mock.util.do(cmd, returnOutput=returnOutput, shell=True)
            self._callHooks("postyum")
            return output
        except mock.exception.Error, e:
            raise mock.exception.YumError, str(e)

    decorate(traceLog())
    def _makeBuildUser(self):
        if not os.path.exists(self.makeChrootPath('usr/sbin/useradd')):
            raise mock.exception.RootError, "Could not find useradd in chroot, maybe the install failed?"

        # safe and easy. blow away existing /builddir and completely re-create.
        mock.util.rmtree(self.makeChrootPath(self.homedir))
        dets = { 'uid': str(self.chrootuid), 'gid': str(self.chrootgid), 'user': self.chrootuser, 'group': self.chrootgroup, 'home': self.homedir }

        self.doChroot(['/usr/sbin/userdel', '-r', dets['user']], shell=False, raiseExc=False)
        self.doChroot(['/usr/sbin/groupdel', dets['group']], shell=False, raiseExc=False)

        self.doChroot(['/usr/sbin/groupadd', '-g', dets['gid'], dets['group']], shell=False)
        self.doChroot(self.useradd % dets, shell=True)
        self.doChroot(
            ["perl", "-p", "-i", "-e", 's/^(%s:)!!/$1/;' % self.chrootuser, "/etc/passwd"],
            shell=False, raiseExc=True)

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
        finally:
            self.uidManager.restorePrivs()


    #
    # UNPRIVLEGED:
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
    # UNPRIVLEGED:
    #   Everything in this function runs as the build user
    #
    decorate(traceLog())
    def _copySrpmIntoChroot(self, srpm):
        srpmFilename = os.path.basename(srpm)
        dest = self.makeChrootPath(self.builddir, 'originals')
        shutil.copy2(srpm, dest)
        return os.path.join(self.builddir, 'originals', srpmFilename)

