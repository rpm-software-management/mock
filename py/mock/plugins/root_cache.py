# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import fcntl
import logging
import os
import time

# our imports
from mock.trace_decorator import traceLog
import mock.util

# set up logging, module options
moduleLog = logging.getLogger("mock")
requires_api_version = "1.0"

# plugin entry point
def init(rootObj, conf):
    RootCache(rootObj, conf)

# classes
class RootCache(object):
    """caches root environment in a tarball"""
    @traceLog(moduleLog)
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.root_cache_opts = conf
        self.rootSharedCachePath = self.root_cache_opts['dir'] % self.root_cache_opts
        self.rootCacheFile = os.path.join(self.rootSharedCachePath, "cache.tar.gz")
        self.rootCacheLock = None
        self.state = rootObj.state
        self.rootdir = rootObj.rootdir
        rootObj.rootCacheObj = self
        rootObj.addHook("preinit", self._rootCachePreInitHook)
        rootObj.addHook("postinit", self._rootCachePostInitHook)

    # =============
    # 'Private' API
    # =============
    @traceLog(moduleLog)
    def _rootCacheLock(self, shared=1):
        lockType = fcntl.LOCK_EX
        if shared: lockType = fcntl.LOCK_SH
        try:
            fcntl.lockf(self.rootCacheLock.fileno(), lockType | fcntl.LOCK_NB)
        except IOError, e:
            oldState = self.state()
            self.state("Waiting for rootcache lock")
            fcntl.lockf(self.rootCacheLock.fileno(), lockType)
            self.state(oldState)

    @traceLog(moduleLog)
    def _rootCacheUnlock(self):
        fcntl.lockf(self.rootCacheLock.fileno(), fcntl.LOCK_UN)

    @traceLog(moduleLog)
    def _rootCachePreInitHook(self):
        moduleLog.info("enabled root cache")
        mock.util.mkdirIfAbsent(self.rootSharedCachePath)
        # lock so others dont accidentally use root cache while we operate on it.
        if self.rootCacheLock is None:
            self.rootCacheLock = open(os.path.join(self.rootSharedCachePath, "rootcache.lock"), "a+")

        # check cache age:
        try:
            statinfo = os.stat(self.rootCacheFile)
            file_age_days = (time.time() - statinfo.st_ctime) / (60 * 60 * 24)
            if file_age_days > self.root_cache_opts['max_age_days']:
                os.unlink(self.rootCacheFile)
        except OSError:
            pass

        # optimization: dont unpack root cache if chroot was not cleaned
        if os.path.exists(self.rootCacheFile) and self.rootObj.chrootWasCleaned:
            self.state("unpacking cache")
            self._rootCacheLock()
            mock.util.do("tar xzf %s -C %s" % (self.rootCacheFile, self.rootdir))
            self._rootCacheUnlock()
            self.chroot_setup_cmd = "update"
            self.rootObj.chrootWasCleaned = False

    @traceLog(moduleLog)
    def _rootCachePostInitHook(self):
        # never rebuild cache unless it was a clean build.
        if self.rootObj.chrootWasCleaned:
            self.state("creating cache")
            self._rootCacheLock(shared=0)
            mock.util.do("tar czf %s -C %s ." % (self.rootCacheFile, self.rootdir))
            self._rootCacheUnlock()

