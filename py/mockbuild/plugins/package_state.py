# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Seth Vidal
# Copyright (C) 2012 Red Hat, Inc

# this plugin dumps out two lists of pkgs:
# A list of all available pkgs + repos + other data
# A list of all installed pkgs + repos + other data
# into the results dir
# two files - available_pkgs
#             installed_pkgs

# our imports
from mockbuild.trace_decorator import decorate, traceLog
import mockbuild.util
import tempfile
import os

#repoquery used
repoquery_avail_opts = "-a --qf '%{nevra} %{buildtime} %{size} %{pkgid} %{repoid}'"
repoquery_install_opts = "--installed -a --qf '%{nevra} %{buildtime} %{size} %{pkgid} %{yumdb_info.from_repo}'"

# set up logging, module options
requires_api_version = "1.0"

# plugin entry point
decorate(traceLog())
def init(plugins, conf, buildroot):
    PackageState(plugins, conf, buildroot)

# classes
class PackageState(object):
    """dumps out a list of packages available and in the chroot"""
    decorate(traceLog())
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.avail_done = False
        self.inst_done = False
        self.online = self.config['online']
        plugins.add_hook("postyum", self._availablePostYumHook)
        plugins.add_hook("prebuild", self._installedPreBuildHook)

    decorate(traceLog())
    def _availablePostYumHook(self):
        if self.online and not self.avail_done:
            self.buildroot.uid_manager.dropPrivsTemp()
            self.state.start("Outputting list of available packages")
            out_file = self.buildroot.resultdir + '/available_pkgs'
            chrootpath = self.buildroot.make_chroot_path()
            cmd = "/usr/bin/repoquery --installroot=%s -c %s/etc/yum.conf %s > %s" % (
                           chrootpath, chrootpath, repoquery_avail_opts, out_file)
            mockbuild.util.do(cmd, shell=True, env=self.buildroot.env)
            self.avail_done = True
            self.state.finish("Outputting list of available packages")
            self.buildroot.uid_manager.restorePrivs()

    decorate(traceLog())
    def _installedPreBuildHook(self):
        if self.online and not self.inst_done:
            self.state.start("Outputting list of installed packages")
            fd, fn = tempfile.mkstemp()
            fo = os.fdopen(fd, 'w')
            fo.write('[main]\ninstallroot=%s' % self.buildroot.make_chroot_path())
            fo.flush()
            fo.close()
            out_file = self.buildroot.resultdir + '/installed_pkgs'
            cmd = "/usr/bin/repoquery --installroot=%s -c %s %s > %s" % (
                self.buildroot.make_chroot_path(), fn, repoquery_install_opts, out_file)
            self.buildroot.uid_manager.restorePrivs()
            mockbuild.util.do(cmd, shell=True, env=self.buildroot.env)
            self.buildroot.uid_manager.dropPrivsTemp()
            self.inst_done = True
            os.unlink(fn)
            self.state.finish("Outputting list of installed packages")
