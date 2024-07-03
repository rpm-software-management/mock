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
import json
import os
import shlex
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
        plugins.add_hook("postdeps", self._installedPreBuildHook)
        if self.conf.get("buildroot_info", False):
            plugins.add_hook("postdeps", self._installedPreBuildHook2)

    @traceLog()
    def _availablePostYumHook(self):
        if self.online and not self.avail_done and self.available_pkgs_enabled:
            with self.buildroot.uid_manager:
                self.state.start("Outputting list of available packages")
                out_file = self.buildroot.resultdir + '/available_pkgs.log'
                chrootpath = self.buildroot.make_chroot_path()
                if self.buildroot.config['package_manager'] in ['dnf', 'microdnf']:
                    cmd = "/usr/bin/dnf --installroot={0} repoquery -c {0}/etc/dnf/dnf.conf {1} | sort > {2}".format(
                        chrootpath, repoquery_avail_opts, out_file)
                else:
                    cmd = "/usr/bin/repoquery --installroot={0} -c {0}/etc/yum.conf {1} | sort > {2}".format(
                        chrootpath, repoquery_avail_opts, out_file)
                mockbuild.util.do(cmd, shell=True, env=self.buildroot.env)
                self.avail_done = True
                self.state.finish("Outputting list of available packages")

    @traceLog()
    def _installedPreBuildHook2(self):
        filename = "mock-build-environment.json"
        statename = "Outputting the file " + filename
        try:
            with self.buildroot.uid_manager:
                self.state.start(statename)
                out_file = os.path.join(self.buildroot.resultdir, filename)
                chrootpath = self.buildroot.make_chroot_path()

                package_list_cmd  = "rpm --root {0} -qa".format(shlex.quote(chrootpath))
                out, _ = self.buildroot.doOutChroot(package_list_cmd, returnOutput=True, shell=True)
                packages = out.splitlines()

                cmd = "dnf -q --installroot={0} repoquery --location".format(shlex.quote(chrootpath))
                cmd += " " + " ".join(shlex.quote(p) for p in packages)
                out, _ = self.buildroot.doOutChroot(cmd, returnOutput=True, shell=True)

                self.avail_done = True
                data = {
                    "version": "0",
                    "buildroot": {
                        "packages": []
                    },
                    "config": {}
                }
                for cfg_option in [
                    "target_arch", "legal_host_arches",
                    "dist",
                    "package_manager", "chroot_setup_cmd",
                    "bootstrap_image",
                    "extra_chroot_dirs",
                ]:
                    if cfg_option in self.buildroot.config:
                        data["config"][cfg_option] = self.buildroot.config[cfg_option]

                if self.buildroot.config['bootstrap_image']:
                    data["bootstrap_image"] = self.buildroot.config['bootstrap_image']

                for pkg in out.splitlines():
                    if not pkg.endswith(".rpm"):
                        continue
                    data["buildroot"]["packages"].append({"url": pkg})

                with open(out_file, "w", encoding="utf-8") as fdlist:
                    fdlist.write(json.dumps(data, indent=4) + "\n")
        finally:
            self.state.finish(statename)

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
