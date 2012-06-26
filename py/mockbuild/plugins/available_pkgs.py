# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Seth Vidal
# Copyright (C) 2012 Red Hat, Inc

# this plugin dumps out a list of all pkgs + what repo they came from
# into the results dir

# our imports
from mockbuild.trace_decorator import decorate, traceLog, getLog
import mockbuild.util


# set up logging, module options
requires_api_version = "1.0"

# plugin entry point
decorate(traceLog())
def init(rootObj, conf):
    AvailablePackages(rootObj, conf)

# classes
class AvailablePackages(object):
    """dumps out a list of packages available to the build"""
    decorate(traceLog())
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.done = False
        rootObj.addHook("postyum", self._availablePostYumHook)

    decorate(traceLog())
    def _availablePostYumHook(self):
        if not self.done:
            self.rootObj.start("Outputting list of available packages")
            ap_file = self.rootObj.resultdir + '/available_pkgs'
            cmd = "/usr/bin/repoquery -c %s/etc/yum.conf -a --qf '%%{nevra} %%{repoid}' > %s" % (self.rootObj._rootdir, ap_file)
            mockbuild.util.do(cmd, shell=True)
            self.done = True
            self.rootObj.finish()
    


