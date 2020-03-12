# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Seth Vidal
# Copyright (C) 2012 Red Hat, Inc

# this plugin dumps out two lists of pkgs:
# A list of all available pkgs + repos + other data
# A list of all installed pkgs + repos + other data
# into the results dir
# two files - available_pkgs.log
#             installed_pkgs.log

# our imports
from mockbuild.trace_decorator import traceLog
import mockbuild.util

# repoquery used
repoquery_avail_opts = \
    "--qf '%{name}-%{epoch}:%{version}-%{release}.%{arch} %{buildtime} %{size} %{pkgid} %{repoid}' '*'"

# set up logging, module options
requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    PackageState(plugins, conf, buildroot)


class PackageState(object):
    """dumps out a list of packages available and in the chroot"""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.state = buildroot.state
        self.conf = conf
        self.available_pkgs_enabled = self.conf['available_pkgs']
        self.installed_pkgs_enabled = self.conf['installed_pkgs']
        self.avail_done = False
        self.inst_done = False
        self.online = self.buildroot.config['online']
        plugins.add_hook("postyum", self._availablePostYumHook)
        plugins.add_hook("prebuild", self._installedPreBuildHook)

    @traceLog()
    def _availablePostYumHook(self):
        if self.online and not self.avail_done and self.available_pkgs_enabled:
            with self.buildroot.uid_manager:
                self.state.start("Outputting list of available packages")
                out_file = self.buildroot.resultdir + '/available_pkgs.log'
                chrootpath = self.buildroot.make_chroot_path()
                if self.buildroot.config['package_manager'] in ['dnf', 'microdnf']:
                    cmd = "/usr/bin/dnf --installroot={0} repoquery -c {0}/etc/dnf/dnf.conf {1} > {2}".format(
                        chrootpath, repoquery_avail_opts, out_file)
                else:
                    cmd = "/usr/bin/repoquery --installroot={0} -c {0}/etc/yum.conf {1} > {2}".format(
                        chrootpath, repoquery_avail_opts, out_file)
                mockbuild.util.do(cmd, shell=True, env=self.buildroot.env)
                self.avail_done = True
                self.state.finish("Outputting list of available packages")

    @traceLog()
    def _installedPreBuildHook(self):
        if self.inst_done or not self.installed_pkgs_enabled:
            return

        out_file = self.buildroot.resultdir + '/installed_pkgs.log'
        self.state.start("Outputting list of installed packages")

        try:
            cmd = "rpm -qa --root '%s' --qf '%%{nevra} %%{buildtime} %%{size} %%{pkgid} installed\\n'" % (
                self.buildroot.make_chroot_path())
            with self.buildroot.uid_manager:
                output, _ = self.buildroot.doOutChroot(cmd, returnOutput=1, shell=True)
                with open(out_file, 'w') as out_fd:
                    out_fd.write(output)
        finally:
            self.inst_done = True
            self.state.finish("Outputting list of installed packages")
