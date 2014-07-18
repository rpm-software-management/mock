# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Originally written by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Major reorganization and adaptation by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

import fcntl
import glob
import imp
import logging
import os
import shutil
import stat
import pwd
import grp

try:
    import uuid
except ImportError:
    uuid = None

import mockbuild.util
import mockbuild.exception

from mockbuild.exception import BuildRootLocked
from mockbuild.trace_decorator import traceLog, decorate, getLog
from mockbuild.package_manager import PackageManager
from mockbuild.buildroot import Buildroot

class Root(object):
    """controls setup of chroot environment"""
    decorate(traceLog())
    def __init__(self, config, uidManager):
        self._state = []
        self.uidManager = uidManager
        self._hooks = {}
        self.chrootWasCached = False
        self.chrootWasCleaned = False
        self.preExistingDeps = []
        self.logging_initialized = False
        self.version = config['version']

        self.sharedRootName = config['root']
        if config.has_key('unique-ext'):
            config['root'] = "%s-%s" % (config['root'], config['unique-ext'])

        self.buildroot = Buildroot(config)
        self.env = self.buildroot.env

        self.basedir = self.buildroot.basedir
        self.homedir = config['chroothome']
        self.builddir = os.path.join(self.homedir, 'build')
        self.rpmbuild_arch = config['rpmbuild_arch']

        self.clean_the_chroot = config['clean']

        # result dir
        self.resultdir = config['resultdir'] % config

        self.root_log = getLog("mockbuild")
        self.build_log = getLog("mockbuild.Root.build")
        self._state_log = getLog("mockbuild.Root.state")

        # config options
        self.configs = config['config_paths']
        self.config_name = config['chroot_name']
        self.chrootuid = config['chrootuid']
        self.chrootuser = 'mockbuild'
        self.chrootgid = config['chrootgid']
        self.chrootgroup = 'mockbuild'
        self.yum_conf_content = config['yum.conf']
        self.yum_priorities_conf_content = config['priorities.conf']
        self.yum_rhnplugin_conf_content = config['rhnplugin.conf']
        self.yum_subscription_manager_conf_content = config['subscription-manager.conf']
        self.use_host_resolv = config['use_host_resolv']
        self.chroot_file_contents = config['files']
        self.chroot_setup_cmd = config['chroot_setup_cmd']
        if isinstance(self.chroot_setup_cmd, basestring):
            # accept strings in addition to other sequence types
            self.chroot_setup_cmd = self.chroot_setup_cmd.split()
        self.macros = config['macros']
        self.more_buildreqs = config['more_buildreqs']
        self.cache_topdir = config['cache_topdir']
        self.cachedir = os.path.join(self.cache_topdir, self.sharedRootName)
        self.cache_alterations = config['cache_alterations']
        self.useradd = config['useradd']
        self.online = config['online']
        self.internal_dev_setup = config['internal_dev_setup']

        self.backup = config['backup_on_clean']
        self.backup_base_dir = config['backup_base_dir']

        self.plugins = config['plugins']
        self.pluginConf = config['plugin_conf']
        self.pluginDir = config['plugin_dir']
        for key in self.pluginConf.keys():
            if not key.endswith('_opts'): continue
            self.pluginConf[key]['basedir'] = self.basedir
            self.pluginConf[key]['cache_topdir'] = self.cache_topdir
            self.pluginConf[key]['cachedir'] = self.cachedir
            self.pluginConf[key]['root'] = self.sharedRootName

        self.build_log_fmt_str = config['build_log_fmt_str']
        self.root_log_fmt_str = config['root_log_fmt_str']
        self._state_log_fmt_str = config['state_log_fmt_str']

        self.start("init plugins")
        self._initPlugins()
        self.finish("init plugins")

        # do we allow interactive root shells?
        self.no_root_shells = config['no_root_shells']

        # default to not doing selinux things
        self.selinux = False

        # if the selinux plugin is disabled and we have SELinux enabled
        # on the host, we need to do SELinux things, so set the selinux
        # state variable to true
        if self.pluginConf['selinux_enable'] == False and mockbuild.util.selinuxEnabled():
            self.selinux = True

        self.extra_chroot_dirs = config['extra_chroot_dirs']

        self.pkg_manager = PackageManager(config, self)

        self._resetLogging()

    @property
    def mounts(self):
        return self.buildroot.mounts

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
    def state(self):
        if not len(self._state):
            raise mockbuild.exception.StateError, "state called on empty state stack"
        return self._state[-1]

    def start(self, state):
        if state == None:
            raise mockbuild.exception.StateError, "start called with None State"
        self._state.append(state)
        self._state_log.info("Start: %s" % state)

    def finish(self, state):
        if len(self._state) == 0:
            raise mockbuild.exception.StateError, "finish called on empty state list"
        current = self._state.pop()
        if state != current:
            raise mockbuild.exception.StateError, "state finish mismatch: current: %s, state: %s" % (current, state)
        self._state_log.info("Finish: %s" % state)

    def alldone(self):
        if len(self._state) != 0:
            raise mockbuild.exception.StateError, "alldone called with pending states: %s" % ",".join(self._state)
        self.buildroot.finalize()

    decorate(traceLog())
    def backup_results(self):
        srcdir = os.path.join(self.basedir, "result")
        if not os.path.exists(srcdir):
            return
        dstdir = os.path.join(self.backup_base_dir, self.config_name)
        mockbuild.util.mkdirIfAbsent(dstdir)
        rpms = glob.glob(os.path.join(srcdir, "*rpm"))
        if len(rpms) == 0:
            return
        self._state_log.info("backup_results: saving with cp %s %s" % (" ".join(rpms), dstdir))
        mockbuild.util.run(cmd="cp %s %s" % (" ".join(rpms), dstdir))

    decorate(traceLog())
    def clean(self):
        """clean out chroot with extreme prejudice :)"""
        if self.backup:
            self.backup_results()
        self.start("clean chroot")
        mockbuild.util.orphansKill(self.makeChrootPath())
        self.buildroot.delete()
        self.chrootWasCleaned = True
        self.finish("clean chroot")

    decorate(traceLog())
    def scrub(self, scrub_opts):
        """clean out chroot and/or cache dirs with extreme prejudice :)"""
        statestr = "scrub %s" % scrub_opts
        self.start(statestr)
        try:
            try:
                self._callHooks('clean')
                for scrub in scrub_opts:
                    if scrub == 'all':
                        self.root_log.info("scrubbing everything for %s" % self.config_name)
                        self.buildroot.delete()
                        self.chrootWasCleaned = True
                        mockbuild.util.rmtree(self.cachedir, selinux=self.selinux)
                    elif scrub == 'chroot':
                        self.root_log.info("scrubbing chroot for %s" % self.config_name)
                        self.buildroot.delete()
                        self.chrootWasCleaned = True
                    elif scrub == 'cache':
                        self.root_log.info("scrubbing cache for %s" % self.config_name)
                        mockbuild.util.rmtree(self.cachedir, selinux=self.selinux)
                    elif scrub == 'c-cache':
                        self.root_log.info("scrubbing c-cache for %s" % self.config_name)
                        mockbuild.util.rmtree(os.path.join(self.cachedir, 'ccache'), selinux=self.selinux)
                    elif scrub == 'root-cache':
                        self.root_log.info("scrubbing root-cache for %s" % self.config_name)
                        mockbuild.util.rmtree(os.path.join(self.cachedir, 'root_cache'), selinux=self.selinux)
                    elif scrub == 'yum-cache':
                        self.root_log.info("scrubbing yum-cache for %s" % self.config_name)
                        mockbuild.util.rmtree(os.path.join(self.cachedir, 'yum_cache'), selinux=self.selinux)
            except IOError, e:
                getLog().warn("parts of chroot do not exist: %s" % e )
                if mockbuild.util.hostIsEL5(): pass
                raise
        finally:
            print "finishing: %s" % statestr
            self.finish(statestr)

    decorate(traceLog())
    def makeChrootPath(self, *args):
        '''For safety reasons, self._rootdir should not be used directly. Instead
        use this handy helper function anytime you want to reference a path in
        relation to the chroot.'''
        return self.buildroot.make_chroot_path(*args)

    decorate(traceLog())
    def init(self):
        try:
            self._init()
        except (KeyboardInterrupt, Exception):
            self._callHooks('initfailed')
            raise
        self._show_installed_packages()

    decorate(traceLog())
    def _write_plugin_conf(self, yumpluginconfdir, name, content):
        """ Write 'name' file into yumpluginconfdir """
        # always truncate and overwrite (w+)
        mockbuild.util.mkdirIfAbsent(yumpluginconfdir)
        conf = self.makeChrootPath('etc', 'yum', 'pluginconf.d', name)
        conf_fo = open(conf, 'w+')
        conf_fo.write(content)
        conf_fo.close()

    decorate(traceLog())
    def _init(self):
        self.start("chroot init")

        # NOTE: removed the following stuff vs mock v0:
        #   --> /etc/ is no longer 02775 (new privs model)
        #   --> no /etc/yum.conf symlink (F7 and above)

        self.buildroot.initialize()

        self.uidManager.dropPrivsTemp()
        try:
            mockbuild.util.mkdirIfAbsent(self.resultdir)
        except mockbuild.exception.Error:
            raise mockbuild.exception.ResultDirNotAccessible(mockbuild.exception.ResultDirNotAccessible.__doc__ % self.resultdir)
        self.uidManager.restorePrivs()

        # create our log files. (if they havent already)
        self._resetLogging()

        # write out config details
        self.root_log.debug('rootdir = %s' % self.makeChrootPath())
        self.root_log.debug('resultdir = %s' % self.resultdir)

        # set up plugins:
        getLog().info("calling preinit hooks")
        self._callHooks('preinit')

        # use yum plugin conf from chroot as needed
        yumpluginconfdir = self.makeChrootPath('etc', 'yum', 'pluginconf.d')
        self.yum_conf_content = self.yum_conf_content.replace("plugins=1", "plugins=1\npluginconfpath=" + yumpluginconfdir)

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

        # write in yum plugins into chroot
        self.root_log.debug('configure yum priorities')
        self._write_plugin_conf(yumpluginconfdir, 'priorities.conf', self.yum_priorities_conf_content)
        self.root_log.debug('configure yum rhnplugin')
        self._write_plugin_conf(yumpluginconfdir, 'rhnplugin.conf', self.yum_rhnplugin_conf_content)
        if self.yum_subscription_manager_conf_content:
            self.root_log.debug('configure RHSM rhnplugin')
            self._write_plugin_conf(yumpluginconfdir, 'subscription-manager.conf', self.yum_subscription_manager_conf_content)
            pem_dir = self.makeChrootPath('etc', 'pki', 'entitlement')
            mockbuild.util.mkdirIfAbsent(pem_dir)
            for pem_file in glob.glob("/etc/pki/entitlement/*.pem"):
                shutil.copy(pem_file, pem_dir)
            consumer_dir = self.makeChrootPath('etc', 'pki', 'consumer')
            mockbuild.util.mkdirIfAbsent(consumer_dir)
            for consumer_file in glob.glob("/etc/pki/consumer/*.pem"):
                shutil.copy(consumer_file, consumer_dir)
            shutil.copy('/etc/rhsm/rhsm.conf', self.makeChrootPath('etc', 'rhsm'))
            self._yum(['repolist'])

        # Copy RPM GPG keys
        pki_dir = self.makeChrootPath('etc', 'pki', 'mock')
        mockbuild.util.mkdirIfAbsent(pki_dir)
        for pki_file in glob.glob("/etc/pki/mock/RPM-GPG-KEY-*"):
            shutil.copy(pki_file, pki_dir)

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

        if uuid:
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
                mockbuild.util.mkdirIfAbsent(os.path.dirname(p))
                # write file
                fo = open(p, 'w+')
                fo.write(self.chroot_file_contents[key])
                fo.close()

        # yum stuff
        self.start("yum update")
        if self.chrootWasCleaned:
            self.yum_init_install_output = self._yum(self.chroot_setup_cmd, returnOutput=1)
        if self.chrootWasCached:
            self._yum(('update',), returnOutput=1)

        self.finish("yum update")
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
        self.finish("chroot init")

    decorate(traceLog())
    def _nuke_rpm_db(self):
        """remove rpm DB lock files from the chroot"""

        dbfiles = glob.glob(self.makeChrootPath('var/lib/rpm/__db*'))
        if not dbfiles:
            return
        self.root_log.debug("removing %d rpm db files" % len(dbfiles))
        # become root
        self.uidManager.becomeUser(0, 0)
        try:
            for tmp in dbfiles:
                self.root_log.debug("_nuke_rpm_db: removing %s" % tmp)
                try:
                    os.unlink(tmp)
                except OSError,e:
                    getLog().error("%s" % e )
                    raise
        finally:
            #restore previous privs
            self.uidManager.restorePrivs()

    # bad hack
    # comment out decorator here so we dont get double exceptions in the root log
    #decorate(traceLog())
    def doChroot(self, command, shell=True, returnOutput=False, printOutput=False, raiseExc=True, *args, **kargs):
        """execute given command in root"""
        if not mockbuild.util.hostIsEL5():
            self._nuke_rpm_db()
        return mockbuild.util.do(command, chrootPath=self.makeChrootPath(),
                                 env=self.env, raiseExc=raiseExc,
                                 returnOutput=returnOutput, shell=shell,
                                 printOutput=printOutput, *args, **kargs)

    def doNonChroot(self, command, shell=True, returnOutput=False, printOutput=False, raiseExc=True, *args, **kargs):
        '''run a command *without* chrooting'''
        self._nuke_rpm_db()
        return mockbuild.util.do(command, env=self.env, raiseExc=raiseExc,
                                 returnOutput=returnOutput, shell=shell,
                                 printOutput=printOutput, *args, **kargs)

    decorate(traceLog())
    def yumInstall(self, *rpms):
        """call yum to install the input rpms into the chroot"""
        # pass build reqs (as strings) to installer
        self.root_log.info("installing package(s): %s" % " ".join(rpms))
        output = self._yum(['install'] + list(rpms), returnOutput=1)
        self.root_log.info(output)

    decorate(traceLog())
    def yumUpdate(self):
        """use yum to update the chroot"""
        self._yum(('update',), returnOutput=1)

    decorate(traceLog())
    def yumRemove(self, *rpms):
        """call yum to remove the input rpms from the chroot"""
        self.root_log.info("removing package(s): %s" % " ".join(rpms))
        output = self._yum(['remove'] + list(rpms), returnOutput=1)
        self.root_log.info(output)

    decorate(traceLog())
    def installSrpmDeps(self, *srpms):
        """figure out deps from srpm. call yum to install them"""
        try:
            self.uidManager.becomeUser(0, 0)

            def _yum_and_check(cmd):
                output = self._yum(cmd, returnOutput=1)
                for line in output.split('\n'):
                    if line.lower().find('No Package found for'.lower()) != -1 or line.lower().find('Missing Dependency'.lower()) != -1:
                        raise mockbuild.exception.BuildError, "Bad build req: %s. Exiting." % line

            # first, install pre-existing deps and configured additional ones
            deps = list(self.preExistingDeps)
            for hdr in mockbuild.util.yieldSrpmHeaders(srpms, plainRpmOk=1):
                # get text buildreqs
                deps.extend(mockbuild.util.getAddtlReqs(hdr, self.more_buildreqs))
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


    #decorate(traceLog())
    def _show_installed_packages(self):
        '''report the installed packages in the chroot to the root log'''
        self.root_log.info("Installed packages:")
        self.doNonChroot(
            "rpm --root %s -qa" % self.makeChrootPath(),
            raiseExc=False,
            uid=self.chrootuid,
            gid=self.chrootgid,
            )




    #
    # UNPRIVILEGED:
    #   Everything in this function runs as the build user
    #       -> except hooks. :)
    #
    decorate(traceLog())
    def build(self, srpm, timeout, check=True):
        """build an srpm into binary rpms, capture log"""

        # tell caching we are building
        self._callHooks('earlyprebuild')

        baserpm = os.path.basename(srpm)

        buildstate = "build phase for %s" % baserpm
        self.start(buildstate)
        try:
            # remove rpm db files to prevent version mismatch problems
            # note: moved to do this before the user change below!
            self._nuke_rpm_db()

            # drop privs and become mock user
            self.uidManager.becomeUser(self.chrootuid, self.chrootgid)
            buildsetup = "build setup for %s" % baserpm
            self.start(buildsetup)

            srpm = self.copy_srpm_into_chroot(srpm)
            self.install_srpm(srpm)

            spec = self.get_specfile_name(srpm)
            spec_path = os.path.join(self.builddir, 'SPECS', spec)

            rebuilt_srpm = self.rebuild_installed_srpm(spec_path, timeout)

            self.installSrpmDeps(rebuilt_srpm)
            self.finish(buildsetup)

            rpmbuildstate = "rpmbuild -bb %s" % baserpm
            self.start(rpmbuildstate)

            # tell caching we are building
            self._callHooks('prebuild')

            results = self.rebuild_package(spec_path, timeout, check)

            self.copy_build_results(results)

            self.finish(rpmbuildstate)

        finally:
            self.uidManager.restorePrivs()

            # tell caching we are done building
            self._callHooks('postbuild')
        self.finish(buildstate)


    def shell(self, options, cmd=None):
        log = getLog()
        log.debug("shell: calling preshell hooks")
        self._callHooks("preshell")
        if options.unpriv or self.no_root_shells:
            uid=self.chrootuid
            gid=self.chrootgid
        else:
            uid=0
            gid=0

        try:
            self.start("shell")
            ret = mockbuild.util.doshell(chrootPath=self.makeChrootPath(),
                                         environ=self.env,
                                         uid=uid, gid=gid,
                                         cmd=cmd)
        finally:
            log.debug("shell: unmounting all filesystems")
            self.finish("shell")

        log.debug("shell: calling postshell hooks")
        self._callHooks('postshell')
        return ret

    def chroot(self, args, options):
        log = getLog()
        shell=False
        if len(args) == 1:
            args = args[0]
            shell=True
        log.info("Running in chroot: %s" % args)
        self._callHooks("prechroot")
        chrootstate = "chroot %s" % args
        self.start(chrootstate)
        try:
            if options.unpriv:
                self.doChroot(args, shell=shell, printOutput=True,
                              uid=self.chrootuid, gid=self.chrootgid, cwd=options.cwd)
            else:
                self.doChroot(args, shell=shell, cwd=options.cwd, printOutput=True)
        finally:
            self.finish(chrootstate)
        self._callHooks("postchroot")

    #
    # UNPRIVILEGED:
    #   Everything in this function runs as the build user
    #       -> except hooks. :)
    #
    #decorate(traceLog())
    def buildsrpm(self, spec, sources, timeout):
        """build an srpm, capture log"""

        # tell caching we are building
        self._callHooks('earlyprebuild')

        try:
            self.uidManager.becomeUser(self.chrootuid, self.chrootgid)
            self.start("buildsrpm")

            # copy spec/sources
            shutil.copy(spec, self.makeChrootPath(self.builddir, "SPECS"))

            # Resolve any symlinks
            sources = os.path.realpath(sources)

            if os.path.isdir(sources):
                mockbuild.util.rmtree(self.makeChrootPath(self.builddir, "SOURCES"))
                shutil.copytree(sources, self.makeChrootPath(self.builddir, "SOURCES"), symlinks=True)
            else:
                shutil.copy(sources, self.makeChrootPath(self.builddir, "SOURCES"))

            spec = self.makeChrootPath(self.builddir, "SPECS", os.path.basename(spec))
            # get rid of rootdir prefix
            chrootspec = spec.replace(self.makeChrootPath(), '')

            self.start("rpmbuild -bs")
            try:
                rebuilt_srpm = self.rebuild_installed_srpm(chrootspec, timeout)
            finally:
                self.finish("rpmbuild -bs")

            srpm_basename = os.path.basename(rebuilt_srpm)

            self.root_log.debug("Copying package to result dir")
            shutil.copy2(self.makeChrootPath(rebuilt_srpm), self.resultdir)

            return os.path.join(self.resultdir, srpm_basename)

        finally:
            self.uidManager.restorePrivs()

            # tell caching we are done building
            self._callHooks('postbuild')
            self.finish("buildsrpm")


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
                raise mockbuild.exception.Error('Plugin "%s" doesn\'t specify required API version' % modname)

            module.init(self, self.pluginConf["%s_opts" % modname])


    decorate(traceLog())
    def _show_path_user(self, path):
        cmd = ['/sbin/fuser', '-a', '-v', path]
        self.root_log.debug("using 'fuser' to find users of %s" % path)
        out = mockbuild.util.do(cmd, returnOutput=1, raiseExc=False, env=self.env)
        self.root_log.debug(out)
        return out

    decorate(traceLog())
    def _yum(self, cmd, returnOutput=0):
        """use yum to install packages/package groups into the chroot"""

        return self.pkg_manager.execute(*cmd, returnOutput=returnOutput)

    decorate(traceLog())
    def _makeBuildUser(self):
        if not os.path.exists(self.makeChrootPath('usr/sbin/useradd')):
            raise mockbuild.exception.RootError, "Could not find useradd in chroot, maybe the install failed?"

        if self.clean_the_chroot:
            # safe and easy. blow away existing /builddir and completely re-create.
            mockbuild.util.rmtree(self.makeChrootPath(self.homedir), selinux=self.selinux)

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

        util.mkdirIfAbsent(self.resultdir)

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
                mockbuild.util.mkdirIfAbsent(subdir)

            # change ownership so we can write to build home dir
            for (dirpath, dirnames, filenames) in os.walk(self.makeChrootPath(self.homedir)):
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
    def copy_srpm_into_chroot(self, srpm_path):
        srpmFilename = os.path.basename(srpm_path)
        dest = self.makeChrootPath(self.builddir, 'originals')
        shutil.copy2(srpm_path, dest)
        return os.path.join(self.builddir, 'originals', srpmFilename)

    def get_specfile_name(self, srpm_path):
        files = self.doChroot(["rpm", "-qpl", srpm_path],
                    shell=False, uid=self.chrootuid, gid=self.chrootgid,
                    returnOutput=True)
        specs = [item for item in files.split('\n') if item.endswith('.spec')]
        if len(specs) < 1:
            raise mockbuild.exception.PkgError("No specfile found in srpm: "\
                                               + os.path.basename(srpm_path))
        return specs[0]


    def install_srpm(self, srpm_path):
        self.doChroot(["rpm", "-Uvh", "--nodeps", srpm_path],
            shell=False, uid=self.chrootuid, gid=self.chrootgid)

    def rebuild_installed_srpm(self, spec_path, timeout):
        self.doChroot(["bash", "--login", "-c",
                             'rpmbuild -bs --target {0} --nodeps {1}'\
                              .format(self.rpmbuild_arch, spec_path)],
                shell=False, logger=self.build_log, timeout=timeout,
                uid=self.chrootuid, gid=self.chrootgid, returnOutput=True)
        results = glob.glob("%s/%s/SRPMS/*.src.rpm" % (self.makeChrootPath(),
                                                       self.builddir))
        if len(results) != 1:
            raise mockbuild.exception.PkgError(
                    "Expected to find single rebuilt srpm, found %d." % len(results))
        return results[0]

    def rebuild_package(self, spec_path, timeout, check):
        # --nodeps because rpm in the root may not be able to read rpmdb
        # created by rpm that created it (outside of chroot)
        check_opt = ''
        if not check:
            check_opt = '--nocheck'

        self.doChroot(["bash", "--login", "-c",
                             'rpmbuild -bb --target {0} --nodeps {1} {2}'\
                              .format(self.rpmbuild_arch, check_opt, spec_path)],
            shell=False, logger=self.build_log, timeout=timeout,
            uid=self.chrootuid, gid=self.chrootgid, returnOutput=True)
        bd_out = self.makeChrootPath(self.builddir)
        results = glob.glob(bd_out + '/RPMS/*.rpm')
        results += glob.glob(bd_out + '/SRPMS/*.rpm')
        if not results:
            raise mockbuild.exception.PkgError('No build results found')
        return results

    def copy_build_results(self, results):
        self.root_log.debug("Copying packages to result dir")
        for item in results:
            shutil.copy2(item, self.resultdir)
