# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import os

# our imports
from mock.trace_decorator import decorate, traceLog, getLog
import mock.util

requires_api_version = "1.0"

# plugin entry point
decorate(traceLog())
def init(rootObj, conf):
    CCache(rootObj, conf)

# classes
class CCache(object):
    """enables ccache in buildroot/rpmbuild"""
    decorate(traceLog())
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.ccache_opts = conf
        self.ccachePath = self.ccache_opts['dir'] % self.ccache_opts
        rootObj.ccacheObj = self
        rootObj.preExistingDeps.append("ccache")
        rootObj.addHook("prebuild", self._ccacheBuildHook)
        rootObj.addHook("preinit",  self._ccachePreInitHook)
        rootObj.umountCmds.append('umount -n %s' % rootObj.makeChrootPath("/tmp/ccache"))
        rootObj.mountCmds.append('mount -n --bind %s  %s' % (self.ccachePath, rootObj.makeChrootPath("/tmp/ccache")))

    # =============
    # 'Private' API
    # =============
    # set the max size before we actually use it during a build.
    # ccache itself manages size and settings.
    decorate(traceLog())
    def _ccacheBuildHook(self):
        self.rootObj.doChroot(["ccache", "-M", str(self.ccache_opts['max_cache_size'])], shell=False)

    # basic idea here is that we add 'cc', 'gcc', 'g++' shell scripts to
    # to /tmp/ccache, which is bind-mounted from a shared location.
    # we then add this to the front of the path.
    # we also set a few admin variables used by ccache to find the shared
    # cache.
    decorate(traceLog())
    def _ccachePreInitHook(self):
        getLog().info("enabled ccache")
        mock.util.mkdirIfAbsent(self.rootObj.makeChrootPath('/tmp/ccache'))
        os.environ['CCACHE_DIR'] = "/tmp/ccache"
        os.environ['CCACHE_UMASK'] = "002"
        mock.util.mkdirIfAbsent(self.ccachePath)
        self.rootObj.uidManager.changeOwner(self.ccachePath)
