# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by clime
# Copyright (C) 2020 clime <clime@fedoraproject.org>

# python library imports
import os
import os.path
import re
import subprocess
import configparser
import shlex

# our imports
import mockbuild.util
from mockbuild.trace_decorator import getLog, traceLog
from mockbuild.exception import PkgError

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    RpkgPreprocessor(plugins, conf, buildroot)


class RpkgPreprocessor(object):
    """preprocess spec file by using rpkg utilities"""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.opts = conf
        self.log = getLog()
        plugins.add_hook("pre_srpm_build", self._preprocess_proxy)
        self.log.info("rpkg_preprocessor: initialized")

    @traceLog()
    def _install_requires(self, requires):
        try:
            self.buildroot.uid_manager.becomeUser(0, 0)
            self.buildroot.pkg_manager.install(*requires, check=True)
        finally:
            self.buildroot.uid_manager.restorePrivs()

    @traceLog()
    def _preprocess_proxy(self, host_chroot_spec, host_chroot_sources):
        if not host_chroot_sources or not os.path.isdir(host_chroot_sources):
            self.log.debug("Sources not specified or not a directory. "
                           "Skipping rpkg preprocessing step.")
            return

        self._preprocess(host_chroot_spec, host_chroot_sources)

    @traceLog()
    def _preprocess(self, host_chroot_spec, host_chroot_sources):
        rpkg_conf_path = os.path.join(host_chroot_sources, 'rpkg.conf')
        force_enable = self.opts.get('force_enable', False)

        if not force_enable:
            if not os.path.isfile(rpkg_conf_path):
                self.log.info("rpkg.conf not found. "
                              "Skipping rpkg preprocessing step.")
                return

            parser = configparser.ConfigParser(
                interpolation=configparser.ExtendedInterpolation())

            try:
                parser.read(rpkg_conf_path)
            except configparser.ParsingError as e:
                raise PkgError("Parsing of %s failed with error: %s" % (rpkg_conf_path, repr(e)))

            try:
                preprocess_spec = parser.getboolean('rpkg', 'preprocess_spec')
            except (configparser.Error, ValueError):
                self.log.warning(
                    "Could not get boolean value of rpkg.preprocess_spec option from rpkg.conf.")
                preprocess_spec = False

            if not preprocess_spec:
                self.log.info("preprocess_spec not enabled in rpkg.conf. "
                              "Skipping rpkg preprocessing step.")
                return

        # try to locate spec file in SOURCES, which will be our input
        host_chroot_sources_spec = os.path.join(host_chroot_sources,
                                                os.path.basename(host_chroot_spec))

        if not os.path.isfile(host_chroot_sources_spec):
            raise PkgError("%s is not a file. Spec file needs to be among sources." %
                           host_chroot_sources_spec)

        self.log.info("Installing rpkg preprocessing requires...")
        self._install_requires(self.opts.get('requires', []))

        # get rid of host rootdir prefixes
        rootdir_prefix = self.buildroot.make_chroot_path()
        chroot_spec = host_chroot_spec.replace(rootdir_prefix, '')
        chroot_sources = host_chroot_sources.replace(rootdir_prefix, '')
        chroot_sources_spec = host_chroot_sources_spec.replace(rootdir_prefix, '')

        command_str = self.opts.get('cmd') % {'source_spec': chroot_sources_spec,
                                              'target_spec': chroot_spec}
        command = shlex.split(command_str)

        # determine whether to use private network or not based on rpmbuild_networking
        private_network = (not self.config.get('rpmbuild_networking', False))

        self.buildroot.doChroot(
            command,
            shell=False,
            cwd=chroot_sources,
            logger=self.buildroot.build_log,
            uid=self.buildroot.chrootuid,
            gid=self.buildroot.chrootgid,
            user=self.buildroot.chrootuser,
            unshare_net=private_network,
            nspawn_args=self.config.get('nspawn_args', []),
            printOutput=self.config.get('print_main_output', True)
        )
