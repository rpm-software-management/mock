# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import logging
import os

# our imports
from mock.trace_decorator import traceLog
import mock.util

# set up logging, module options
moduleLog = logging.getLogger("mock")
requires_api_version = "1.0"

# plugin entry point
def init(rootObj, conf):
    ccache = CCache(rootObj, conf)

# classes
class CCache(object):
    """enables ccache in buildroot/rpmbuild"""
    @traceLog(moduleLog)
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.ccache_opts = conf
        self.ccachePath = self.ccache_opts['dir'] % self.ccache_opts
        self.rootdir = rootObj.rootdir
        rootObj.ccacheObj = self
        rootObj.preExistingDeps = "ccache"
        rootObj.addHook("prebuild", self._ccacheBuildHook)
        rootObj.addHook("preinit",  self._ccachePreInitHook)
        rootObj.umountCmds.append('umount -n %s/tmp/ccache' % rootObj.rootdir)
        rootObj.mountCmds.append('mount -n --bind %s  %s/tmp/ccache' % (self.ccachePath, rootObj.rootdir))

    # =============
    # 'Private' API
    # =============
    # set the max size before we actually use it during a build.
    # ccache itself manages size and settings.
    @traceLog(moduleLog)
    def _ccacheBuildHook(self):
        self.rootObj.doChroot("ccache -M %s" % self.ccache_opts['max_cache_size'])

    # basic idea here is that we add 'cc', 'gcc', 'g++' shell scripts to
    # to /tmp/ccache, which is bind-mounted from a shared location.
    # we then add this to the front of the path.
    # we also set a few admin variables used by ccache to find the shared
    # cache.
    @traceLog(moduleLog)
    def _ccachePreInitHook(self):
        mock.util.mkdirIfAbsent(os.path.join(self.rootdir, 'tmp/ccache'))
        mock.util.mkdirIfAbsent(self.ccachePath)
        os.environ['PATH'] = "/tmp/ccache:%s" % (os.environ['PATH'])
        os.environ['CCACHE_DIR'] = "/tmp/ccache"
        os.environ['CCACHE_UMASK'] = "002"
        self._dumpToFile(os.path.join(self.ccachePath, "cc"), 
            '#!/bin/sh\nexec ccache /usr/bin/cc "$@"\n', mode=0555)
        self._dumpToFile(os.path.join(self.ccachePath, "gcc"), 
            '#!/bin/sh\nexec ccache /usr/bin/gcc "$@"\n', mode=0555)
        self._dumpToFile(os.path.join(self.ccachePath, "g++"), 
            '#!/bin/sh\nexec ccache /usr/bin/g++ "$@"\n', mode=0555)

    @traceLog(moduleLog)
    def _dumpToFile(self, filename, contents, *args, **kargs):
        fd = open(filename, "w+")
        fd.write(contents)
        fd.close()
        mode = kargs.get("mode", None)
        if mode is not None:
            os.chmod(filename, mode)


