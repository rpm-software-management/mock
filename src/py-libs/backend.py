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
import time

# our imports
import mock.util
import mock.exception
from mock.trace_decorator import traceLog

# set up logging
moduleLog = logging.getLogger("mock")

# classes
class Root(object):
    """controls setup of chroot environment"""
    @traceLog(moduleLog)
    def __init__(self, config, uidManager):
        self._state = 'unstarted'
        self.uidManager = uidManager
        self._hooks = {}
        self.chrootWasCleaned = False
        self.preExistingDeps = ""

        self.sharedRootName = config['root']
        root = self.sharedRootName
        if config.has_key('unique-ext'):
            root = "%s-%s" % (root, config['unique-ext'])

        self.basedir = os.path.join(config['basedir'], root)
        self.target_arch = config['target_arch']
        self.rootdir = os.path.join(self.basedir, 'root')
        self.homedir = config['chroothome']
        self.builddir = os.path.join(self.homedir, 'build')

        # result dir
        if not config.has_key('resultdir'):
            self.resultdir = os.path.join(self.basedir, 'result')
        else:
            self.resultdir = config['resultdir']

        self.root_log = logging.getLogger("mock")
        self.build_log = logging.getLogger("mock.Root.build")
        self._state_log = logging.getLogger("mock.Root.state")

        # config options
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

        self.plugins = config['plugins']
        self.pluginConf = config['plugin_conf']
        self.pluginDir = config['plugin_dir']
        for key in self.pluginConf.keys():
            if not key.endswith("_opts"): continue
            self.pluginConf[key]["basedir"] = self.basedir
            self.pluginConf[key]["cache_topdir"] = self.cache_topdir
            self.pluginConf[key]["cachedir"] = self.cachedir
            self.pluginConf[key]["root"] = self.sharedRootName

        # mount/umount
        self.umountCmds = ['umount -n %s/proc' % self.rootdir,
                'umount -n %s/dev/pts' % self.rootdir,
                'umount -n %s/sys' % self.rootdir,
               ]
        self.mountCmds = ['mount -n -t proc   mock_chroot_proc   %s/proc' % self.rootdir,
                'mount -n -t devpts mock_chroot_devpts %s/dev/pts' % self.rootdir,
                'mount -n -t sysfs  mock_chroot_sysfs  %s/sys' % self.rootdir,
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
    @traceLog(moduleLog)
    def addHook(self, stage, function):
        hooks = self._hooks.get(stage, [])
        if function not in hooks:
            hooks.append(function)
            self._hooks[stage] = hooks

    @traceLog(moduleLog)
    def state(self, newState = None):
        if newState is not None:
            self._state = newState
            self._state_log.info("State Changed: %s" % self._state)

        return self._state

    @traceLog(moduleLog)
    def clean(self):
        """clean out chroot with extreme prejudice :)"""
        self.tryLockBuildRoot()
        self.state("clean")
        self.root_log.info("Cleaning chroot")
        mock.util.rmtree(self.basedir)
        self.chrootWasCleaned = True

    @traceLog(moduleLog)
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

    @traceLog(moduleLog)
    def init(self):
        self.state("init")

        # NOTE: removed the following stuff vs mock v0:
        #   --> /etc/ is no longer 02775 (new privs model)
        #   --> no /etc/yum.conf symlink (F7 and above)

         # create our base directory heirarchy
        mock.util.mkdirIfAbsent(self.basedir)
        mock.util.mkdirIfAbsent(self.rootdir)

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
        self.root_log.debug('rootdir = %s' % self.rootdir)
        self.root_log.debug('resultdir = %s' % self.resultdir)

        # set up plugins:
        self._callHooks('preinit')

        # create skeleton dirs
        self.root_log.info('create skeleton dirs')
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
                     'dev/pts',
                     'sys',
                    ]:
            mock.util.mkdirIfAbsent(os.path.join(self.rootdir, item))

        # touch files
        self.root_log.info('touch required files')
        for item in [os.path.join(self.rootdir, 'etc', 'mtab'),
                     os.path.join(self.rootdir, 'etc', 'fstab'),
                     os.path.join(self.rootdir, 'var', 'log', 'yum.log')]:
            mock.util.touch(item)

        # write in yum.conf into chroot
        # always truncate and overwrite (w+)
        self.root_log.info('configure yum')
        yumconf = os.path.join(self.rootdir, 'etc', 'yum', 'yum.conf')
        yumconf_fo = open(yumconf, 'w+')
        yumconf_fo.write(self.yum_conf_content)
        yumconf_fo.close()

        # symlink /etc/yum.conf to /etc/yum/yum.conf (FC6 requires)
        try:
            os.unlink(os.path.join(self.rootdir, "etc", "yum.conf"))
        except OSError:
            pass
        os.symlink('yum/yum.conf', os.path.join(self.rootdir, "etc", "yum.conf"))

        # set up resolv.conf
        if self.use_host_resolv:
            resolvdir = os.path.join(self.rootdir, 'etc')
            resolvpath = os.path.join(self.rootdir, 'etc', 'resolv.conf')
            if os.path.exists(resolvpath):
                os.remove(resolvpath)
            shutil.copy2('/etc/resolv.conf', resolvdir)

        # files in /etc that need doing
        for key in self.chroot_file_contents:
            p = os.path.join(self.rootdir, *key.split('/'))
            if not os.path.exists(p):
                # write file
                fo = open(p, 'w+')
                fo.write(self.chroot_file_contents[key])
                fo.close()

        # files in /dev
        mock.util.rmtree(os.path.join(self.rootdir, "dev"))
        mock.util.mkdirIfAbsent(os.path.join(self.rootdir, "dev", "pts"))
        prevMask = os.umask(0000)
        os.mknod(os.path.join(self.rootdir, "dev/zero"), stat.S_IFCHR | 0666, os.makedev(1, 5))
        os.mknod(os.path.join(self.rootdir, "dev/tty"), stat.S_IFCHR | 0666, os.makedev(5, 0))
        os.mknod(os.path.join(self.rootdir, "dev/null"), stat.S_IFCHR | 0666, os.makedev(1, 3))
        os.mknod(os.path.join(self.rootdir, "dev/random"), stat.S_IFCHR | 0666, os.makedev(1, 8))
        os.mknod(os.path.join(self.rootdir, "dev/urandom"), stat.S_IFCHR | 0444, os.makedev(1, 9))
        os.mknod(os.path.join(self.rootdir, "dev/console"), stat.S_IFCHR | 0600, os.makedev(5, 1))
        os.symlink("/proc/self/fd/0", os.path.join(self.rootdir, "dev/stdin"))
        os.symlink("/proc/self/fd/1", os.path.join(self.rootdir, "dev/stdout"))
        os.symlink("/proc/self/fd/2", os.path.join(self.rootdir, "dev/stderr"))
        os.umask(prevMask)

        # yum stuff
        self.root_log.info('run yum')
        self._mountall()
        try:
            if not self.chrootWasCleaned:
                self.chroot_setup_cmd = 'update'
            self._yum(self.chroot_setup_cmd)
        finally:
            self._umountall()

        # create user
        self._makeBuildUser()

        # create rpmbuild dir
        self._buildDirSetup()

        # done with init
        self._callHooks('postinit')

    @traceLog(moduleLog)
    def doChroot(self, command, env="", *args, **kargs):
        """execute given command in root"""
        return mock.util.do( command, chrootPath=self.rootdir, *args, **kargs )

    @traceLog(moduleLog)
    def yumInstall(self, *srpms):
        """figure out deps from srpm. call yum to install them"""
        # pass build reqs (as strings) to installer
        self._mountall()
        try:
            self._yum('install %s' % ' '.join(srpms))
        finally:
            self._umountall()

    @traceLog(moduleLog)
    def installSrpmDeps(self, *srpms):
        """figure out deps from srpm. call yum to install them"""
        arg_string = self.preExistingDeps
        self.uidManager.dropPrivsTemp()
        try:
            for hdr in mock.util.yieldSrpmHeaders(srpms, plainRpmOk=1):
                # get text buildreqs
                a = mock.util.requiresTextFromHdr(hdr)
                b = mock.util.getAddtlReqs(hdr, self.more_buildreqs)
                for item in mock.util.uniqReqs(a,b):
                    arg_string = arg_string + " '%s'" % item

        finally:
            self.uidManager.restorePrivs()

        # everything exists, okay, install them all.
        # pass build reqs (as strings) to installer
        if arg_string != "":
            output = self._yum('resolvedep %s' % arg_string, returnOutput=1)
            for line in output.split('\n'):
                if line.lower().find('No Package found for'.lower()) != -1:
                    raise mock.exception.BuildError, "Bad build req: %s. Exiting." % line
            # nothing made us exit, so we continue
            self._yum('install %s' % arg_string, returnOutput=1)


    #
    # UNPRIVLEGED:
    #   Everything in this function runs as the build user
    #       -> except hooks. :)
    #
    @traceLog(moduleLog)
    def build(self, srpm, timeout):
        """build an srpm into binary rpms, capture log"""

        # tell caching we are building
        self._callHooks('earlyprebuild')

        self._mountall()
        self.uidManager.becomeUser(self.chrootuid)
        try:
            self.state("setup")

            srpmChrootFilename = self._copySrpmIntoChroot(srpm)
            srpmBasename = os.path.basename(srpmChrootFilename)

            # install srpm
            os.environ["HOME"] = self.homedir 
            # Completely/Permanently drop privs while running the following:
            mock.util.do(
                "rpm -Uvh --nodeps %s" % srpmChrootFilename,
                chrootPath=self.rootdir,
                uidManager=self.uidManager,
                uid=self.chrootuid,
                gid=self.chrootgid,
                )

            # rebuild srpm/rpm from SPEC file
            specs = glob.glob("%s/%s/SPECS/*.spec" % (self.rootdir, self.builddir))
            if len(specs) < 1:
                raise mock.exception.PkgError, "No Spec file found in srpm: %s" % srpmBasename

            spec = specs[0] # if there's more than one then someone is an idiot
            chrootspec = spec.replace(self.rootdir, '') # get rid of rootdir prefix
            self.root_log.info("about to drop to unpriv mode.")
            # Completely/Permanently drop privs while running the following:
            mock.util.do(
                "rpmbuild -bs --target %s --nodeps %s" % (self.target_arch, chrootspec), 
                chrootPath=self.rootdir,
                logger=self.build_log, timeout=timeout,
                uidManager=self.uidManager,
                uid=self.chrootuid,
                gid=self.chrootgid,
                )

            rebuiltSrpmFile = glob.glob("%s/%s/SRPMS/*.src.rpm" % (self.rootdir, self.builddir))
            if len(rebuiltSrpmFile) != 1:
                raise mock.exception.PkgError, "Didnt find single rebuilt srpm." 

            rebuiltSrpmFile = rebuiltSrpmFile[0]
            self.installSrpmDeps(rebuiltSrpmFile)

            #have to permanently drop privs or rpmbuild regains them
            self.state("build")

            # tell caching we are building
            self._callHooks('prebuild')

            mock.util.do(
                "rpmbuild -bb --target %s --nodeps %s" % (self.target_arch, chrootspec), 
                chrootPath=self.rootdir,
                uidManager=self.uidManager,
                uid=self.chrootuid,
                gid=self.chrootgid,
                logger=self.build_log, timeout=timeout,
                )

            bd_out = self.rootdir + self.builddir
            rpms = glob.glob(bd_out + '/RPMS/*.rpm')
            srpms = glob.glob(bd_out + '/SRPMS/*.rpm')
            packages = rpms + srpms

            self.root_log.info("Copying packages to result dir")
            for item in packages:
                shutil.copy2(item, self.resultdir)

        finally:
            self.uidManager.restorePrivs()
            self._umountall()

        # tell caching we are done building
        self._callHooks('postbuild')

    # =============
    # 'Private' API
    # =============
    @traceLog(moduleLog)
    def _callHooks(self, stage):
        hooks = self._hooks.get(stage, [])
        for hook in hooks:
            hook()

    @traceLog(moduleLog)
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

    @traceLog(moduleLog)
    def _mountall(self):
        """mount 'normal' fs like /dev/ /proc/ /sys"""
        for cmd in self.mountCmds:
            self.root_log.info(cmd)
            mock.util.do(cmd)

    @traceLog(moduleLog)
    def _umountall(self):
        """umount all mounted chroot fs."""
        for cmd in self.umountCmds:
            self.root_log.info(cmd)
            mock.util.do(cmd, raiseExc=0)

    @traceLog(moduleLog)
    def _yum(self, cmd, returnOutput=0):
        """use yum to install packages/package groups into the chroot"""
        # mock-helper yum --installroot=rootdir cmd
        cmd = '%s --installroot %s %s' % (self.yum_path, self.rootdir, cmd)
        self.root_log.info(cmd)
        try:
            self._callHooks("preyum")
            output = mock.util.do(cmd, returnOutput=returnOutput)
            self._callHooks("postyum")
            return output
        except mock.exception.Error, e:
            self.root_log.exception("Error performing yum command: %s" % cmd)
            raise mock.exception.YumError, "Error performing yum command: %s" % cmd

    @traceLog(moduleLog)
    def _makeBuildUser(self):
        if not os.path.exists(os.path.join(self.rootdir, 'usr/sbin/useradd')):
            raise mock.exception.RootError, "Could not find useradd in chroot, maybe the install failed?"

        # safe and easy. blow away existing /builddir and completely re-create.
        mock.util.rmtree(os.path.join(self.rootdir, self.homedir))
        dets = { 'uid': self.chrootuid, 'gid': self.chrootgid, 'user': self.chrootuser, 'group': self.chrootgroup, 'home': self.homedir }

        self.doChroot('/usr/sbin/userdel -r %(user)s' % dets, raiseExc=False)
        self.doChroot('/usr/sbin/groupdel %(group)s' % dets, raiseExc=False)

        self.doChroot('/usr/sbin/groupadd -g %(gid)s %(group)s' % dets)
        self.doChroot(self.useradd % dets)
        self.doChroot("perl -p -i -e 's/^(%s:)!!/$1/;' /etc/passwd" % (self.chrootuser), raiseExc=True)

    @traceLog(moduleLog)
    def _resetLogging(self):
        # ensure we dont attach the handlers multiple times.
        if getattr(self, "logging_initialized", None):
            return
        self.logging_initialized = 1

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

    #
    # UNPRIVLEGED:
    #   Everything in this function runs as the build user
    #
    @traceLog(moduleLog)
    def _buildDirSetup(self):
        # create all dirs as the user who will be dropping things there.
        self.uidManager.becomeUser(self.chrootuid)
        try:
            # create dir structure
            for subdir in ["%s/%s/%s" % (self.rootdir, self.builddir, s) for s in ('RPMS', 'SRPMS', 'SOURCES', 'SPECS', 'BUILD', 'originals')]:
                mock.util.mkdirIfAbsent(subdir)

            # change ownership so we can write to build home dir
            for (dirpath, dirnames, filenames) in os.walk(self.homedir):
                for path in dirnames + filenames:
                    os.chown(os.path.join(dirpath, path), self.chrootuid, -1)
                    os.chmod(os.path.join(dirpath, path), 0755)

            # rpmmacros default
            self.macros['%_rpmlock_path'] = "%s/var/lib/rpm/__db.000" % self.basedir
            macrofile_out = '%s%s/.rpmmacros' % (self.rootdir, self.homedir)
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
    @traceLog(moduleLog)
    def _copySrpmIntoChroot(self, srpm):
        self.uidManager.becomeUser(self.chrootuid)
        try:
            srpmFilename = os.path.basename(srpm)
            dest = self.rootdir + '/' + self.builddir + '/' + 'originals'
            shutil.copy2(srpm, dest)
            origSrpmChrootFilename = os.path.join(self.builddir, 'originals', srpmFilename)
        finally:
            self.uidManager.restorePrivs()

        return origSrpmChrootFilename

