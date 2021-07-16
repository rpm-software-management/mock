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
import sys
import tempfile
import getpass

# 3rd party imports
import rpm
from mockbuild.mounts import BindMountPoint

from . import file_util
from . import text
from . import util
from .external import ExternalDeps
from .file_downloader import FileDownloader
from .exception import PkgError, Error, RootError, BuildError, ExternalDepsError
from .trace_decorator import getLog, traceLog
from .rebuild import do_rebuild


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
        self.external = ExternalDeps(buildroot, bootstrap_buildroot, uid_manager)

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
        if isinstance(self.chroot_setup_cmd, str):
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
        file_util.mkdirIfAbsent(dstdir)
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
                        file_util.rmtree(self.buildroot.cachedir, selinux=self.buildroot.selinux)
                        if self.bootstrap_buildroot is not None:
                            self.bootstrap_buildroot.delete()
                            file_util.rmtree(self.bootstrap_buildroot.cachedir,
                                             selinux=self.bootstrap_buildroot.selinux)
                    elif scrub == 'chroot':
                        self.buildroot.root_log.info("scrubbing chroot for %s", self.config_name)
                        self.buildroot.delete()
                    elif scrub == 'cache':
                        self.buildroot.root_log.info("scrubbing cache for %s", self.config_name)
                        file_util.rmtree(self.buildroot.cachedir, selinux=self.buildroot.selinux)
                    elif scrub == 'c-cache':
                        self.buildroot.root_log.info("scrubbing c-cache for %s", self.config_name)
                        file_util.rmtree(os.path.join(self.buildroot.cachedir, 'ccache'),
                                         selinux=self.buildroot.selinux)
                    elif scrub == 'root-cache':
                        self.buildroot.root_log.info("scrubbing root-cache for %s", self.config_name)
                        file_util.rmtree(os.path.join(self.buildroot.cachedir, 'root_cache'),
                                         selinux=self.buildroot.selinux)
                    elif scrub in ['yum-cache', 'dnf-cache']:
                        self.buildroot.root_log.info("scrubbing yum-cache and dnf-cache for %s", self.config_name)
                        file_util.rmtree(os.path.join(self.buildroot.cachedir, 'yum_cache'),
                                         selinux=self.buildroot.selinux)
                        file_util.rmtree(os.path.join(self.buildroot.cachedir, 'dnf_cache'),
                                         selinux=self.buildroot.selinux)
                    elif scrub == 'bootstrap' and self.bootstrap_buildroot is not None:
                        self.buildroot.root_log.info("scrubbing bootstrap for %s", self.config_name)
                        self.bootstrap_buildroot.delete()
                        file_util.rmtree(self.bootstrap_buildroot.cachedir, selinux=self.bootstrap_buildroot.selinux)

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
                file_util.mkdirIfAbsent(self.buildroot.make_chroot_path())
                self.bootstrap_buildroot.initialize(**kwargs)
            self.buildroot.initialize(**kwargs)
            if not self.buildroot.chroot_was_initialized:
                self._show_installed_packages()
        except (KeyboardInterrupt, Exception):
            self.plugins.call_hooks('initfailed')
            # intentionally we do not call bootstrap hook here - it does not have sense
            raise

    @traceLog()
    def getPreconfiguredDeps(self, srpms):
        """
        First check that some plugin didn't request installation of additional
        packages into buildroot.

        Second, introspect the given array of SRPMs and check whether user did
        not want to install additional packages for them
        (config['more_buildreqs']).

        Return the list of additional requirements that should be installed.
        """
        deps = list(self.buildroot.preexisting_deps)

        if not self.more_buildreqs:
            # no need to analyze the src.rpm headers for NVR match
            return deps

        # Check whether the N/NV/NVR isn't configured to have additional
        # explicit BuildRequires.
        for hdr in util.yieldSrpmHeaders(srpms, plainRpmOk=1):
            # get text buildreqs
            deps.extend(util.getAddtlReqs(hdr, self.more_buildreqs))

        return deps

    @traceLog()
    def installSrpmDeps(self, *srpms):
        """Figure out deps from srpm. Call package manager to install them"""
        try:
            self.uid_manager.becomeUser(0, 0)

            deps = self.getPreconfiguredDeps(srpms)
            if deps:
                self.buildroot.pkg_manager.install(*deps, check=True)

            # install actual build dependencies
            self.buildroot.pkg_manager.builddep(*srpms, check=True)
        finally:
            self.uid_manager.restorePrivs()

    @traceLog()
    def installSpecDeps(self, spec_file):
        try:
            # pylint: disable=no-member
            spec_file = util.host_file(spec_file)
            spec = rpm.spec(spec_file).sourceHeader.dsFromHeader()
            self.uid_manager.becomeUser(0, 0)
            for i in range(len(spec)): # pylint: disable=consider-using-enumerate
                requirement_name = spec[i][2:]
                self.buildroot.pkg_manager.install(requirement_name, check=True)

        finally:
            self.uid_manager.restorePrivs()

    @traceLog()
    def _show_installed_packages(self):
        '''report the installed packages in the chroot to the root log'''
        pkgs = self.buildroot.all_chroot_packages()
        self.buildroot.root_log.info("Installed packages:")
        self.buildroot.root_log.info('\n'.join(pkgs))

    @traceLog()
    def install_external(self, requires):
        """ requires is list of packages to be install.
        This function extract any external:* and install them.
        """
        external_deps = self.external.extract_external_deps(requires)
        if external_deps:
            if not self.config.get('use_bootstrap'):
                raise Error('ExternalBuildRequires requires `use_bootstrap` to be set on.')
            if self.config.get('external_buildrequires'):
                self.external.install_external_deps(external_deps)
            else:
                raise Error('ExternalBuildRequires are found but support is disabled.'
                            ' See "external_buildrequires" in config_opts.')
    #
    # UNPRIVILEGED:
    #   Everything in this function runs as the build user
    #       -> except hooks. :)
    #
    @traceLog()
    def build(self, srpm, timeout, check=True, spec=None):
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
        buildsetup_finished = False
        try:
            if not util.USE_NSPAWN:
                self.uid_manager.becomeUser(self.buildroot.chrootuid, self.buildroot.chrootgid)
                dropped_privs = True
            buildsetup = "build setup for %s" % baserpm
            self.state.start(buildsetup)

            srpm = self.copy_srpm_into_chroot(srpm)
            self.install_srpm(srpm)

            if spec and not self.config['scm']:
                # scm sets options.spec, but we want to get spec from SRPM when using scm
                spec_path = self.copy_spec_into_chroot(spec)
            else:
                spec = self.get_specfile_name(srpm)
                spec_path = os.path.join(self.buildroot.builddir, 'SPECS', spec)

            rebuilt_srpm = self.rebuild_installed_srpm(spec_path, timeout)

            # Check if we will have dynamic BuildRequires, but do not allow it
            hdr = next(util.yieldSrpmHeaders((rebuilt_srpm,)))
            # pylint: disable=no-member
            requires = {text._to_text(req) for req in hdr[rpm.RPMTAG_REQUIRES]}
            dynamic_buildreqs = 'rpmlib(DynamicBuildRequires)' in requires

            if dynamic_buildreqs and not self.config.get('dynamic_buildrequires'):
                raise Error('DynamicBuildRequires are found but support is disabled.'
                            ' See "dynamic_buildrequires" in config_opts.')

            self.install_external(requires)
            self.installSrpmDeps(rebuilt_srpm)
            self.state.finish(buildsetup)
            buildsetup_finished = True

            rpmbuildstate = "rpmbuild %s" % baserpm

            # tell caching we are building
            self.plugins.call_hooks('prebuild')
            # intentionally we do not call bootstrap hook here - it does not have sense

            try:
                self.state.start(rpmbuildstate)
                results = self.rebuild_package(spec_path, timeout, check, dynamic_buildreqs)
            finally:
                self.state.finish(rpmbuildstate)

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

        finally:
            if not buildsetup_finished:
                self.state.finish(buildsetup)
            self.state.finish(buildstate)
            if dropped_privs:
                self.uid_manager.restorePrivs()
            if self.state.result != 'success':
                self.state.result = 'fail'
            # tell caching we are done building
            self.plugins.call_hooks('postbuild')
            # intentionally we do not call bootstrap hook here - it does not have sense


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
        cwd = options.cwd
        if not cwd:
            # Hack!  We don't set the cwd here because we know that we work
            # with old systemd-nspawn without --chdir option.  Still, users
            # might use --chdir explicitly and such situation would still
            # result in failure.  rhbz#1976702
            if not util.USE_NSPAWN or util.check_nspawn_has_chdir_option():
                cwd = self.config['chroothome']

        try:
            self.state.start("shell")
            ret = util.doshell(chrootPath=self.buildroot.make_chroot_path(),
                               environ=self.buildroot.env, uid=uid, gid=gid,
                               cwd=cwd,
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
        result=0
        try:
            if options.unpriv:
                result = self.buildroot.doChroot(args, shell=shell, printOutput=True,
                                                 uid=self.buildroot.chrootuid, gid=self.buildroot.chrootgid,
                                                 user=self.buildroot.chrootuser, cwd=options.cwd,
                                                 nspawn_args=self._get_nspawn_args(), raiseExc=False,
                                                 unshare_net=self.private_network)[1]
            else:
                result = self.buildroot.doChroot(args, shell=shell, cwd=options.cwd,
                                                 nspawn_args=self._get_nspawn_args(),
                                                 unshare_net=self.private_network,
                                                 printOutput=True, raiseExc=False)[1]
        finally:
            self.state.finish(chrootstate)
        self.plugins.call_hooks("postchroot")
        # intentionally we do not call bootstrap hook here - it does not have sense
        return result

    @traceLog()
    def chain(self, args, options, buildroot):
        log = getLog()
        if not options.tmp_prefix:
            try:
                options.tmp_prefix = getpass.getuser()
            except Exception:  # pylint: disable=broad-except
                log.error("Could not find login name for tmp dir prefix add --tmp_prefix")
                sys.exit(1)
        pid = os.getpid()
        self.config['uniqueext'] = '{0}-{1}'.format(options.tmp_prefix, pid)

        # create a tempdir for our local info
        if options.localrepo:
            local_tmp_dir = os.path.abspath(options.localrepo)
        else:
            pre = 'mock-chain-{0}-'.format(self.config['uniqueext'])
            with self.uid_manager:
                local_tmp_dir = tempfile.mkdtemp(prefix=pre, dir='/var/tmp')

        with self.uid_manager:
            self.config['local_repo_dir'] = os.path.normpath(
                local_tmp_dir + '/results/' + self.config['chroot_name'] + '/')
            file_util.mkdirIfAbsent(self.config['local_repo_dir'])

        local_baseurl = "file://{0}".format(self.config['local_repo_dir'])
        log.info("results dir: %s", self.config['local_repo_dir'])
        # modify with localrepo
        util.add_local_repo(self.config, local_baseurl, 'local_build_repo',
                            bootstrap=buildroot.bootstrap_buildroot)

        with self.uid_manager:
            util.createrepo(self.config, self.config['local_repo_dir'])

        built_pkgs = []
        skipped_pkgs = []
        try_again = True
        to_be_built = args
        return_code = 0
        num_of_tries = 0
        while try_again:
            num_of_tries += 1
            failed = []
            for pkg in to_be_built:
                if failed and not options.cont:
                    log.error("Stopping the --chain build because --continue "
                              "isn't specified and the package '%s' failed "
                              "to build", failed[0])
                    break

                if not pkg.endswith('.rpm'):
                    log.error("%s doesn't appear to be an rpm - skipping", pkg)
                    failed.append(pkg)
                    continue

                with self.uid_manager:
                    pkg_location = pkg
                    pkg = FileDownloader.get(pkg_location)

                if not pkg:
                    failed.append(pkg_location)
                    continue

                log.info("Start chain build: %s", pkg_location)
                build_ret_code = 0
                try:
                    s_pkg = os.path.basename(pkg)
                    pdn = s_pkg.replace('.src.rpm', '')
                    resultdir = os.path.join(self.config['local_repo_dir'], pdn)
                    self.buildroot.resultdir = resultdir
                    self.buildroot._resetLogging(force=True)
                    file_util.mkdirIfAbsent(resultdir)
                    success_file = os.path.join(resultdir, 'success')
                    build_ret_code = 0
                    try:
                        if os.path.exists(success_file):
                            build_ret_code = 2
                        else:
                            do_rebuild(self.config, self, buildroot, options, [pkg])
                    except Error as err:
                        log.error(str(err))
                        build_ret_code = 1
                except (RootError,) as e:
                    log.warning(e.msg)
                    failed.append(pkg)
                log.info("End chain build: %s", pkg_location)

                with self.uid_manager:
                    if build_ret_code == 1:
                        failed.append(pkg)
                        log.info("Error building %s.", os.path.basename(pkg))
                        if options.recurse:
                            log.info("Will try to build again (if some other package will succeed).")
                        else:
                            log.info("See logs/results in %s", self.config['local_repo_dir'])
                            file_util.touch(os.path.join(resultdir, 'fail'))
                    elif build_ret_code == 0:
                        log.info("Success building %s", os.path.basename(pkg))
                        built_pkgs.append(pkg)
                        file_util.touch(success_file)
                        # createrepo with the new pkgs
                        util.createrepo(self.config, self.config['local_repo_dir'])
                    elif build_ret_code == 2:
                        log.info("Skipping already built pkg %s", os.path.basename(pkg))
                        skipped_pkgs.append(pkg)

            if failed and options.recurse:
                if len(failed) != len(to_be_built):
                    to_be_built = failed
                    try_again = True
                    log.info('Some package succeeded, some failed.')
                    log.info('Trying to rebuild %s failed pkgs, because --recurse is set.', len(failed))
                else:
                    log.info("Tried %s times - following pkgs could not be successfully built:", num_of_tries)
                    for pkg in failed:
                        msg = FileDownloader.original_name(pkg)
                        log.info(msg)
                    try_again = False
                    return_code = 4
            else:
                try_again = False
                if failed:
                    return_code = 4

        FileDownloader.cleanup()

        log.info("Results out to: %s", self.config['local_repo_dir'])
        if skipped_pkgs:
            log.info("Packages skipped: %s", len(skipped_pkgs))
            for pkg in skipped_pkgs:
                log.info(pkg)
        log.info("Packages built: %s", len(built_pkgs))
        if built_pkgs:
            if failed:
                if len(built_pkgs):
                    log.info("Some packages successfully built in this order:")
            else:
                log.info("Packages successfully built in this order:")
            for pkg in built_pkgs:
                log.info(pkg)
        return return_code

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
            host_chroot_sources = None

            # copy spec/sources
            shutil.copy(spec, self.buildroot.make_chroot_path(self.buildroot.builddir, "SPECS"))

            if sources:
                # Resolve any symlinks
                sources = os.path.realpath(sources)
                if os.path.isdir(sources):
                    host_chroot_sources = self.buildroot.make_chroot_path(
                        self.buildroot.builddir, "SOURCES")
                    file_util.rmtree(host_chroot_sources)

                    shutil.copytree(sources,
                                    host_chroot_sources,
                                    symlinks=(not follow_links))
                else:
                    host_chroot_sources = self.buildroot.make_chroot_path(
                        self.buildroot.builddir, "SOURCES", os.path.basename(sources))
                    shutil.copy(sources, host_chroot_sources)

            spec = self.buildroot.make_chroot_path(self.buildroot.builddir, "SPECS", os.path.basename(spec))

            self.plugins.call_hooks('pre_srpm_build',
                                    spec,
                                    host_chroot_sources)

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
    def copy_spec_into_chroot(self, spec_path):
        specFilename = os.path.basename(spec_path)
        dest = self.buildroot.make_chroot_path(self.buildroot.builddir, 'originals')
        shutil.copy2(spec_path, os.path.join(dest, specFilename))
        return os.path.join(self.buildroot.builddir, 'originals', specFilename)

    @traceLog()
    def get_specfile_name(self, srpm_path):
        files = self.buildroot.doChroot([self.config['rpm_command'], "-qpl", srpm_path],
                                        shell=False, uid=self.buildroot.chrootuid, gid=self.buildroot.chrootgid,
                                        nspawn_args=self._get_nspawn_args(),
                                        unshare_net=self.private_network,
                                        user=self.buildroot.chrootuser,
                                        returnOutput=True
                                       )[0]
        specs = [item.rstrip() for item in files.split('\n') if item.rstrip().endswith('.spec')]
        if len(specs) < 1:
            raise PkgError(
                "No specfile found in srpm: " + os.path.basename(srpm_path))
        return specs[0]

    @traceLog()
    def install_srpm(self, srpm_path):
        command = [self.config['rpm_command'], "-Uvh", "--nodeps", srpm_path]
        output, return_code = self.buildroot.doChroot(
            command, shell=False, uid=self.buildroot.chrootuid,
            gid=self.buildroot.chrootgid, user=self.buildroot.chrootuser,
            nspawn_args=self._get_nspawn_args(),
            unshare_net=self.private_network, returnOutput=True,
            returnStderr=True, raiseExc=False)
        if return_code:
            raise PkgError("Source RPM is not installable:\n{0}".format(output))

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
    def rebuild_package(self, spec_path, timeout, check, dynamic_buildrequires):
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

        def get_command(mode):
            command = [self.config['rpmbuild_command']] + mode + \
                      ['--target', self.rpmbuild_arch, '--nodeps'] + \
                      check_opt + [spec_path] + additional_opts
            command = ["bash", "--login", "-c"] + [' '.join(command)]
            return command

        bd_out = self.make_chroot_path(self.buildroot.builddir)
        max_loops = int(self.config.get('dynamic_buildrequires_max_loops'))
        success = False
        if dynamic_buildrequires and self.config.get('dynamic_buildrequires'):
            while not success and max_loops > 0:
                # run rpmbuild+installSrpmDeps until
                # * it fails
                # * installSrpmDeps does nothing
                # * or we run out of dynamic_buildrequires_max_loops tries
                packages_before = self.buildroot.all_chroot_packages()
                command = get_command(['-br'])
                (output, returncode) = \
                    self.buildroot.doChroot(command,
                                            shell=False, logger=self.buildroot.build_log, timeout=timeout,
                                            uid=self.buildroot.chrootuid, gid=self.buildroot.chrootgid,
                                            user=self.buildroot.chrootuser,
                                            nspawn_args=self._get_nspawn_args(),
                                            unshare_net=self.private_network, raiseExc=False,
                                            printOutput=self.config['print_main_output'])
                if returncode > 0 and returncode != 11:
                    # we treat exit status 11 as success, as well as exit
                    # status 0, see issue#434
                    raise BuildError("Command failed: \n # %s\n%s" % (command, output))
                max_loops -= 1
                self.buildroot.build_log.info("Dynamic buildrequires detected")
                self.buildroot.build_log.info("Going to install missing buildrequires. See root.log for details.")
                self.buildroot.root_log.info("Going to install missing dynamic buildrequires")
                buildreqs = glob.glob(bd_out + '/SRPMS/*.buildreqs.nosrc.rpm')
                self.installSrpmDeps(*buildreqs)
                packages_after = self.buildroot.all_chroot_packages()
                if packages_after == packages_before:
                    success = True
                for f_buildreqs in buildreqs:
                    os.remove(f_buildreqs)
                if not sc:
                    # We want to (re-)write src.rpm with dynamic BuildRequires,
                    # but with short-circuit it doesn't matter
                    mode = ['-ba']
                # rpmbuild -br already does %prep, so we don't need waste time
                # on re-doing it
                mode += ['--noprep']

        self.buildroot.doChroot(get_command(mode),
                                shell=False, logger=self.buildroot.build_log, timeout=timeout,
                                uid=self.buildroot.chrootuid, gid=self.buildroot.chrootgid,
                                user=self.buildroot.chrootuser,
                                nspawn_args=self._get_nspawn_args(),
                                unshare_net=self.private_network,
                                printOutput=self.config['print_main_output'])
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

        # Mount resultdir into bootstrap, so we can later install the build
        # results from there using bootstrap package manager.

        results_bindmount = None
        if self.bootstrap_buildroot:
            resultdir = self.buildroot.resultdir
            bootstrap_resultdir = self.bootstrap_buildroot.make_chroot_path(resultdir)
            results_bindmount = BindMountPoint(resultdir, bootstrap_resultdir,
                                               options="private")
        try:
            self.uid_manager.becomeUser(0, 0)
            if results_bindmount:
                results_bindmount.mount()
            pkgs = [pkg for pkg in results if not pkg.endswith("src.rpm")]
            try:
                self.buildroot.install(*pkgs)
            # pylint: disable=bare-except
            except:
                self.buildroot.root_log.warning("Failed install built packages")
        finally:
            if results_bindmount:
                results_bindmount.umount()
            self.uid_manager.restorePrivs()
