# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Originally written by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Major reorganization and adaptation by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

import glob
import os
import shutil

from mockbuild.mounts import BindMountPoint
import rpm

from . import util
from .exception import PkgError
from .trace_decorator import getLog, traceLog


class Commands(object):
    """Executes mock commands in the buildroot"""
    @traceLog()
    def __init__(self, config, uid_manager, plugins, state, buildroot, bootstrap_buildroot):
        self.uid_manager = uid_manager
        self.buildroot = buildroot
        self.bootstrap_buildroot = bootstrap_buildroot
        self.state = state
        self.plugins = plugins
        self.config = config

        self.rpmbuild_arch = config['rpmbuild_arch']
        self.clean_the_chroot = config['clean']

        self.build_results = []

        # config options
        self.configs = config['config_paths']
        self.config_name = config['chroot_name']
        self.buildroot.chrootuid = config['chrootuid']
        self.buildroot.chrootgid = config['chrootgid']
        self.use_host_resolv = config['use_host_resolv']
        self.chroot_file_contents = config['files']
        self.chroot_setup_cmd = config['chroot_setup_cmd']
        self.nspawn_args = config['nspawn_args']
        if isinstance(self.chroot_setup_cmd, util.basestring):
            # accept strings in addition to other sequence types
            self.chroot_setup_cmd = self.chroot_setup_cmd.split()
        self.more_buildreqs = config['more_buildreqs']
        self.cache_alterations = config['cache_alterations']

        self.backup = config['backup_on_clean']
        self.backup_base_dir = config['backup_base_dir']

        # do we allow interactive root shells?
        self.no_root_shells = config['no_root_shells']

        self.private_network = not config['rpmbuild_networking']

    def _get_nspawn_args(self):
        nspawn_args = []
        if util.USE_NSPAWN:
            nspawn_args.extend(self.config['nspawn_args'])
        return nspawn_args

    @traceLog()
    def backup_results(self):
        srcdir = os.path.join(self.buildroot.basedir, "result")
        if not os.path.exists(srcdir):
            return
        dstdir = os.path.join(self.backup_base_dir, self.config['root'])
        util.mkdirIfAbsent(dstdir)
        rpms = glob.glob(os.path.join(srcdir, "*rpm"))
        if len(rpms) == 0:
            return
        self.state.state_log.info("backup_results: saving with cp %s %s", " ".join(rpms), dstdir)
        util.run(cmd="cp %s %s" % (" ".join(rpms), dstdir))

    @traceLog()
    def clean(self):
        """clean out chroot with extreme prejudice :)"""
        if self.backup:
            self.backup_results()
        self.state.start("clean chroot")
        self.buildroot.delete()
        if self.bootstrap_buildroot is not None:
            self.bootstrap_buildroot.delete()
        self.state.finish("clean chroot")

    @traceLog()
    def scrub(self, scrub_opts):
        """clean out chroot and/or cache dirs with extreme prejudice :)"""
        statestr = "scrub %s" % scrub_opts
        self.state.start(statestr)
        try:
            try:
                self.plugins.call_hooks('clean')
                if self.bootstrap_buildroot is not None:
                    self.bootstrap_buildroot.plugins.call_hooks('clean')
                for scrub in scrub_opts:
                    self.plugins.call_hooks('scrub', scrub)
                    if self.bootstrap_buildroot is not None:
                        self.bootstrap_buildroot.plugins.call_hooks('scrub', scrub)
                    if scrub == 'all':
                        self.buildroot.root_log.info("scrubbing everything for %s", self.config_name)
                        self.buildroot.delete()
                        util.rmtree(self.buildroot.cachedir, selinux=self.buildroot.selinux)
                        if self.bootstrap_buildroot is not None:
                            self.bootstrap_buildroot.delete()
                            util.rmtree(self.bootstrap_buildroot.cachedir, selinux=self.bootstrap_buildroot.selinux)
                    elif scrub == 'chroot':
                        self.buildroot.root_log.info("scrubbing chroot for %s", self.config_name)
                        self.buildroot.delete()
                        if self.bootstrap_buildroot is not None:
                            self.bootstrap_buildroot.delete()
                    elif scrub == 'cache':
                        self.buildroot.root_log.info("scrubbing cache for %s", self.config_name)
                        util.rmtree(self.buildroot.cachedir, selinux=self.buildroot.selinux)
                        if self.bootstrap_buildroot is not None:
                            util.rmtree(self.bootstrap_buildroot.cachedir, selinux=self.bootstrap_buildroot.selinux)
                    elif scrub == 'c-cache':
                        self.buildroot.root_log.info("scrubbing c-cache for %s", self.config_name)
                        util.rmtree(os.path.join(self.buildroot.cachedir, 'ccache'), selinux=self.buildroot.selinux)
                        if self.bootstrap_buildroot is not None:
                            util.rmtree(os.path.join(self.bootstrap_buildroot.cachedir, 'ccache'),
                                        selinux=self.bootstrap_buildroot.selinux)
                    elif scrub == 'root-cache':
                        self.buildroot.root_log.info("scrubbing root-cache for %s", self.config_name)
                        util.rmtree(os.path.join(self.buildroot.cachedir, 'root_cache'), selinux=self.buildroot.selinux)
                        if self.bootstrap_buildroot is not None:
                            util.rmtree(os.path.join(self.bootstrap_buildroot.cachedir, 'root_cache'),
                                        selinux=self.bootstrap_buildroot.selinux)
                    elif scrub == 'yum-cache' or scrub == 'dnf-cache':
                        self.buildroot.root_log.info("scrubbing yum-cache and dnf-cache for %s", self.config_name)
                        util.rmtree(os.path.join(self.buildroot.cachedir, 'yum_cache'), selinux=self.buildroot.selinux)
                        util.rmtree(os.path.join(self.buildroot.cachedir, 'dnf_cache'), selinux=self.buildroot.selinux)
                        if self.bootstrap_buildroot is not None:
                            util.rmtree(os.path.join(self.bootstrap_buildroot.cachedir, 'yum_cache'),
                                        selinux=self.bootstrap_buildroot.selinux)
                            util.rmtree(os.path.join(self.bootstrap_buildroot.cachedir, 'dnf_cache'),
                                        selinux=self.bootstrap_buildroot.selinux)
            except IOError as e:
                getLog().warning("parts of chroot do not exist: %s", e)
                raise
        finally:
            self.state.finish(statestr)

    @traceLog()
    def make_chroot_path(self, *args):
        '''For safety reasons, self._rootdir should not be used directly. Instead
        use this handy helper function anytime you want to reference a path in
        relation to the chroot.'''
        return self.buildroot.make_chroot_path(*args)

    @traceLog()
    def init(self, **kwargs):
        try:
            if self.bootstrap_buildroot is not None:
                # add the extra bind mount to the outer chroot
                inner_mount = self.bootstrap_buildroot.make_chroot_path(self.buildroot.make_chroot_path())
                util.mkdirIfAbsent(self.buildroot.make_chroot_path())
                self.bootstrap_buildroot.initialize(**kwargs)
                self.buildroot.mounts.managed_mounts.append(
                    BindMountPoint(self.buildroot.make_chroot_path(), inner_mount))
            self.buildroot.initialize(**kwargs)
            if not self.buildroot.chroot_was_initialized:
                self._show_installed_packages()
        except (KeyboardInterrupt, Exception):
            self.plugins.call_hooks('initfailed')
            # intentionally we do not call bootstrap hook here - it does not have sense
            raise

    @traceLog()
    def install(self, *rpms):
        """Call package manager to install the input rpms into the chroot"""
        # pass build reqs (as strings) to installer
        self.buildroot.root_log.info("installing package(s): %s", " ".join(rpms))
        output = self.buildroot.pkg_manager.install(*rpms, returnOutput=1)
        self.buildroot.root_log.info(output)

    @traceLog()
    def remove(self, *rpms):
        """Call package manager to remove the input rpms from the chroot"""
        self.buildroot.root_log.info("removing package(s): %s", " ".join(rpms))
        output = self.buildroot.pkg_manager.remove(*rpms, returnOutput=1)
        self.buildroot.root_log.info(output)

    @traceLog()
    def installSrpmDeps(self, *srpms):
        """Figure out deps from srpm. Call package manager to install them"""
        try:
            self.uid_manager.becomeUser(0, 0)

            # first, install pre-existing deps and configured additional ones
            deps = list(self.buildroot.preexisting_deps)
            for hdr in util.yieldSrpmHeaders(srpms, plainRpmOk=1):
                # get text buildreqs
                deps.extend(util.getAddtlReqs(hdr, self.more_buildreqs))
            if deps:
                self.buildroot.pkg_manager.install(*deps, check=True)

            # install actual build dependencies
            self.buildroot.pkg_manager.builddep(*srpms, check=True)
        finally:
            self.uid_manager.restorePrivs()

    @traceLog()
    def installSpecDeps(self, spec_file):
        try:
            spec=rpm.spec(spec_file).sourceHeader.dsFromHeader()
            self.uid_manager.becomeUser(0, 0)
            for i in range(len(spec)):
                requirement_name = spec[i][2:]
                self.buildroot.pkg_manager.install(requirement_name, check=True)

        finally:
            self.uid_manager.restorePrivs()

    @traceLog()
    def _show_installed_packages(self):
        '''report the installed packages in the chroot to the root log'''
        self.buildroot.root_log.info("Installed packages:")
        self.buildroot.nuke_rpm_db()
        util.do(
            "%s --root %s -qa" % (self.config['rpm_command'],
                                  self.buildroot.make_chroot_path()),
            raiseExc=False,
            shell=True,
            env=self.buildroot.env,
            uid=self.buildroot.chrootuid,
            user=self.buildroot.chrootuser,
            gid=self.buildroot.chrootgid,
        )

    #
    # UNPRIVILEGED:
    #   Everything in this function runs as the build user
    #       -> except hooks. :)
    #
    @traceLog()
    def build(self, srpm, timeout, check=True):
        """build an srpm into binary rpms, capture log"""

        # tell caching we are building
        self.plugins.call_hooks('earlyprebuild')
        # intentionally we do not call bootstrap hook here - it does not have sense

        baserpm = os.path.basename(srpm)

        buildstate = "build phase for %s" % baserpm
        self.state.start(buildstate)
        # remove rpm db files to prevent version mismatch problems
        # note: moved to do this before the user change below!
        self.buildroot.nuke_rpm_db()
        dropped_privs = False
        try:
            if not util.USE_NSPAWN:
                self.uid_manager.becomeUser(self.buildroot.chrootuid, self.buildroot.chrootgid)
                dropped_privs = True
            buildsetup = "build setup for %s" % baserpm
            self.state.start(buildsetup)

            srpm = self.copy_srpm_into_chroot(srpm)
            self.install_srpm(srpm)

            spec = self.get_specfile_name(srpm)
            spec_path = os.path.join(self.buildroot.builddir, 'SPECS', spec)

            rebuilt_srpm = self.rebuild_installed_srpm(spec_path, timeout)

            self.installSrpmDeps(rebuilt_srpm)
            self.state.finish(buildsetup)

            rpmbuildstate = "rpmbuild %s" % baserpm
            self.state.start(rpmbuildstate)

            # tell caching we are building
            self.plugins.call_hooks('prebuild')
            # intentionally we do not call bootstrap hook here - it does not have sense

            results = self.rebuild_package(spec_path, timeout, check)
            # In the nspawn case, we retained root until here, but we
            # need to ensure our output files are owned by the caller's uid.
            # So drop them now.
            if not dropped_privs:
                self.uid_manager.becomeUser(self.buildroot.chrootuid, self.buildroot.chrootgid)
                dropped_privs = True
            if results:
                self.build_results.extend(self.copy_build_results(results))
            elif self.config.get('short_circuit'):
                self.buildroot.root_log.info("Short circuit builds don't produce RPMs")
            else:
                raise PkgError('No build results found')
            self.state.result = 'success'

            self.state.finish(rpmbuildstate)

        finally:
            if dropped_privs:
                self.uid_manager.restorePrivs()
            if self.state.result != 'success':
                self.state.result = 'fail'
            # tell caching we are done building
            self.plugins.call_hooks('postbuild')
            # intentionally we do not call bootstrap hook here - it does not have sense

        self.state.finish(buildstate)

    @traceLog()
    def shell(self, options, cmd=None):
        log = getLog()
        log.debug("shell: calling preshell hooks")
        self.plugins.call_hooks("preshell")
        # intentionally we do not call bootstrap hook here - it does not have sense
        if options.unpriv or self.no_root_shells:
            uid = self.buildroot.chrootuid
            gid = self.buildroot.chrootgid
        else:
            uid = 0
            gid = 0

        try:
            self.state.start("shell")
            ret = util.doshell(chrootPath=self.buildroot.make_chroot_path(),
                               environ=self.buildroot.env, uid=uid, gid=gid,
                               nspawn_args=self._get_nspawn_args(),
                               unshare_net=self.private_network,
                               cmd=cmd)
        finally:
            log.debug("shell: unmounting all filesystems")
            self.state.finish("shell")

        log.debug("shell: calling postshell hooks")
        self.plugins.call_hooks('postshell')
        # intentionally we do not call bootstrap hook here - it does not have sense
        return ret

    @traceLog()
    def chroot(self, args, options):
        log = getLog()
        shell = False
        if len(args) == 1:
            args = [args[0]]
            shell = True
        log.info("Running in chroot: %s", args)
        self.plugins.call_hooks("prechroot")
        # intentionally we do not call bootstrap hook here - it does not have sense
        chrootstate = "chroot %s" % args
        self.state.start(chrootstate)
        try:
            if options.unpriv:
                self.buildroot.doChroot(args, shell=shell, printOutput=True,
                                        uid=self.buildroot.chrootuid, gid=self.buildroot.chrootgid,
                                        user=self.buildroot.chrootuser, cwd=options.cwd,
                                        nspawn_args=self._get_nspawn_args(),
                                        unshare_net=self.private_network)
            else:
                self.buildroot.doChroot(args, shell=shell, cwd=options.cwd,
                                        nspawn_args=self._get_nspawn_args(),
                                        unshare_net=self.private_network,
                                        printOutput=True)
        finally:
            self.state.finish(chrootstate)
        self.plugins.call_hooks("postchroot")
        # intentionally we do not call bootstrap hook here - it does not have sense

    #
    # UNPRIVILEGED:
    #   Everything in this function runs as the build user
    #       -> except hooks. :)
    #
    @traceLog()
    def buildsrpm(self, spec, sources, timeout, follow_links):
        """build an srpm, capture log"""

        # tell caching we are building
        self.plugins.call_hooks('earlyprebuild')
        # intentionally we do not call bootstrap hook here - it does not have sense

        try:
            self.uid_manager.becomeUser(self.buildroot.chrootuid, self.buildroot.chrootgid)
            self.state.start("buildsrpm")

            # copy spec/sources
            shutil.copy(spec, self.buildroot.make_chroot_path(self.buildroot.builddir, "SPECS"))

            # Resolve any symlinks
            sources = os.path.realpath(sources)

            if os.path.isdir(sources):
                util.rmtree(self.buildroot.make_chroot_path(self.buildroot.builddir, "SOURCES"))
                shutil.copytree(sources,
                                self.buildroot.make_chroot_path(self.buildroot.builddir, "SOURCES"),
                                symlinks=(not follow_links))
            else:
                shutil.copy(sources, self.buildroot.make_chroot_path(self.buildroot.builddir, "SOURCES"))

            spec = self.buildroot.make_chroot_path(self.buildroot.builddir, "SPECS", os.path.basename(spec))
            # get rid of rootdir prefix
            chrootspec = spec.replace(self.buildroot.make_chroot_path(), '')

            self.state.start("rpmbuild -bs")
            try:
                rebuilt_srpm = self.rebuild_installed_srpm(chrootspec, timeout)
            finally:
                self.state.finish("rpmbuild -bs")

            srpm_basename = os.path.basename(rebuilt_srpm)

            self.buildroot.root_log.debug("Copying package to result dir")
            shutil.copy2(rebuilt_srpm, self.buildroot.resultdir)

            return os.path.join(self.buildroot.resultdir, srpm_basename)

        finally:
            self.uid_manager.restorePrivs()

            # tell caching we are done building
            self.plugins.call_hooks('postbuild')
            # intentionally we do not call bootstrap hook here - it does not have sense
            self.state.finish("buildsrpm")

    #
    # UNPRIVILEGED:
    #   Everything in this function runs as the build user
    #
    @traceLog()
    def copy_srpm_into_chroot(self, srpm_path):
        srpmFilename = os.path.basename(srpm_path)
        dest = self.buildroot.make_chroot_path(self.buildroot.builddir, 'originals')
        shutil.copyfile(srpm_path, os.path.join(dest, srpmFilename))
        return os.path.join(self.buildroot.builddir, 'originals', srpmFilename)

    @traceLog()
    def get_specfile_name(self, srpm_path):
        files = self.buildroot.doChroot([self.config['rpm_command'], "-qpl", srpm_path],
                                        shell=False, uid=self.buildroot.chrootuid, gid=self.buildroot.chrootgid,
                                        nspawn_args=self._get_nspawn_args(),
                                        unshare_net=self.private_network,
                                        user=self.buildroot.chrootuser,
                                        returnOutput=True)
        specs = [item.rstrip() for item in files.split('\n') if item.rstrip().endswith('.spec')]
        if len(specs) < 1:
            raise PkgError(
                "No specfile found in srpm: " + os.path.basename(srpm_path))
        return specs[0]

    @traceLog()
    def install_srpm(self, srpm_path):
        self.buildroot.doChroot([self.config['rpm_command'], "-Uvh", "--nodeps", srpm_path],
                                shell=False, uid=self.buildroot.chrootuid, gid=self.buildroot.chrootgid,
                                user=self.buildroot.chrootuser,
                                nspawn_args=self._get_nspawn_args(),
                                unshare_net=self.private_network)

    @traceLog()
    def rebuild_installed_srpm(self, spec_path, timeout):
        command = ['{command} -bs --target {0} --nodeps {1}'.format(
            self.rpmbuild_arch, spec_path,
            command=self.config['rpmbuild_command'])]
        command = ["bash", "--login", "-c"] + command
        self.buildroot.doChroot(
            command,
            shell=False, logger=self.buildroot.build_log, timeout=timeout,
            uid=self.buildroot.chrootuid, gid=self.buildroot.chrootgid,
            user=self.buildroot.chrootuser,
            nspawn_args=self._get_nspawn_args(),
            unshare_net=self.private_network,
            printOutput=self.config['print_main_output']
        )
        results = glob.glob("%s/%s/SRPMS/*src.rpm" % (self.make_chroot_path(),
                                                      self.buildroot.builddir))
        if len(results) != 1:
            raise PkgError("Expected to find single rebuilt srpm, found %d in %s"
                           % (len(results), "%s/%s/SRPMS/*src.rpm" % (self.make_chroot_path(),
                                                                      self.buildroot.builddir)))
        return results[0]

    @traceLog()
    def rebuild_package(self, spec_path, timeout, check):
        # --nodeps because rpm in the root may not be able to read rpmdb
        # created by rpm that created it (outside of chroot)
        check_opt = []
        if not check:
            # this is because EL5/6 does not know --nocheck
            # when EL5/6 targets are not supported, replace it with --nocheck
            check_opt += ["--define", "'__spec_check_template exit 0; '"]

        mode = ['-bb']
        sc = self.config.get('short_circuit')
        if sc:
            mode[0] = {'prep': '-bp',
                       'install': '-bi',
                       'build': '-bc',
                       'binary': '-bb'}[sc]
            mode += ['--short-circuit']
        additional_opts = [self.config.get('rpmbuild_opts', '')]
        if additional_opts == ['']:
            additional_opts = []
        command = [self.config['rpmbuild_command']] + mode + \
                  ['--target', self.rpmbuild_arch, '--nodeps'] + \
                  check_opt + [spec_path] + additional_opts
        command = ["bash", "--login", "-c"] + [' '.join(command)]
        self.buildroot.doChroot(command,
                                shell=False, logger=self.buildroot.build_log, timeout=timeout,
                                uid=self.buildroot.chrootuid, gid=self.buildroot.chrootgid,
                                user=self.buildroot.chrootuser,
                                nspawn_args=self._get_nspawn_args(),
                                unshare_net=self.private_network,
                                printOutput=self.config['print_main_output'])
        bd_out = self.make_chroot_path(self.buildroot.builddir)
        results = glob.glob(bd_out + '/RPMS/*.rpm')
        results += glob.glob(bd_out + '/SRPMS/*.rpm')
        self.buildroot.final_rpm_list = [os.path.basename(result) for result in results]
        return results

    @traceLog()
    def copy_build_results(self, results):
        self.buildroot.root_log.debug("Copying packages to result dir")
        ret = []
        for item in results:
            shutil.copy2(item, self.buildroot.resultdir)
            ret.append(os.path.join(self.buildroot.resultdir, os.path.split(item)[1]))
        return ret

    @traceLog()
    def install_build_results(self, results):
        self.buildroot.root_log.info("Installing built packages")
        try:
            self.uid_manager.becomeUser(0, 0)

            pkgs = [pkg for pkg in results if not pkg.endswith("src.rpm")]
            try:
                self.install(*pkgs)
            # pylint: disable=bare-except
            except:
                self.buildroot.root_log.warning("Failed install built packages")
        finally:
            self.uid_manager.restorePrivs()
