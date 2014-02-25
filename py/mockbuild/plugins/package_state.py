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
def init(rootObj, conf):
    PackageState(rootObj, conf)

# classes
class PackageState(object):
    """dumps out a list of packages available and in the chroot"""
    decorate(traceLog())
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.avail_done = False
        self.inst_done = False
        self.online = rootObj.online
        rootObj.addHook("postyum", self._availablePostYumHook)
        rootObj.addHook("prebuild", self._installedPreBuildHook)

    decorate(traceLog())
    def _availablePostYumHook(self):
        if self.online and not self.avail_done:
            self.rootObj.uidManager.dropPrivsTemp()
            self.rootObj.start("Outputting list of available packages")
            out_file = self.rootObj.resultdir + '/available_pkgs'
            chrootpath = self.rootObj.makeChrootPath()
            cmd = "/usr/bin/repoquery --installroot=%s -c %s/etc/yum.conf %s > %s" % (
                           chrootpath, chrootpath, repoquery_avail_opts, out_file)
            mockbuild.util.do(cmd, shell=True, env=self.rootObj.env)
            self.avail_done = True
            self.rootObj.finish("Outputting list of available packages")
            self.rootObj.uidManager.restorePrivs()

    decorate(traceLog())
    def _installedPreBuildHook(self):
        if self.online and not self.inst_done:
            self.rootObj.start("Outputting list of installed packages")
            fd, fn = tempfile.mkstemp()
            fo = os.fdopen(fd, 'w')
            fo.write('[main]\ninstallroot=%s' % self.rootObj.makeChrootPath())
            fo.flush()
            fo.close()
            out_file = self.rootObj.resultdir + '/installed_pkgs'
            cmd = "/usr/bin/repoquery --installroot=%s -c %s %s > %s" % (
                self.rootObj.makeChrootPath(), fn, repoquery_install_opts, out_file)
            self.rootObj.uidManager.restorePrivs()
            mockbuild.util.do(cmd, shell=True, env=self.rootObj.env)
            self.rootObj.uidManager.dropPrivsTemp()
            self.inst_done = True
            os.unlink(fn)
            self.rootObj.finish("Outputting list of installed packages")
