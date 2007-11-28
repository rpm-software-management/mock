# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import logging
import fcntl
import time
import os

# our imports
from mock.trace_decorator import traceLog
import mock.util

# set up logging, module options
moduleLog = logging.getLogger("mock")
requires_api_version = "1.0"

# plugin entry point
def init(rootObj, conf):
    yumCache = YumCache(rootObj, conf)

# classes
class YumCache(object):
    """caches root environment in a tarball"""
    @traceLog(moduleLog)
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.yum_cache_opts = conf
        self.yumSharedCachePath = self.yum_cache_opts['dir'] % self.yum_cache_opts
        self.state = rootObj.state
        self.rootdir = rootObj.rootdir
        self.online = rootObj.online
        rootObj.yum_cacheObj = self
        rootObj.addHook("preyum", self._yumCachePreYumHook)
        rootObj.addHook("postyum", self._yumCachePostYumHook)
        rootObj.addHook("preinit", self._yumCachePreInitHook)
        rootObj.umountCmds.append('umount -n %s/var/cache/yum' % rootObj.rootdir)
        rootObj.mountCmds.append('mount -n --bind %s  %s/var/cache/yum' % (self.yumSharedCachePath, rootObj.rootdir))

    # =============
    # 'Private' API
    # =============
    # lock the shared yum cache (when enabled) before any access
    # by yum, and prior to cleaning it. This prevents simultaneous access from
    # screwing things up. This can possibly happen, eg. when running multiple
    # mock instances with --uniqueext=
    @traceLog(moduleLog)
    def _yumCachePreYumHook(self):
        try:
            fcntl.lockf(self.yumCacheLock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError, e:
            oldState = self.state()
            self.state("Waiting for yumcache lock")
            fcntl.lockf(self.yumCacheLock.fileno(), fcntl.LOCK_EX)
            self.state(oldState)

    @traceLog(moduleLog)
    def _yumCachePostYumHook(self):
        fcntl.lockf(self.yumCacheLock.fileno(), fcntl.LOCK_UN)

    @traceLog(moduleLog)
    def _yumCachePreInitHook(self):
        mock.util.mkdirIfAbsent(os.path.join(self.rootdir, 'var/cache/yum'))
        mock.util.mkdirIfAbsent(self.yumSharedCachePath)

        # lock so others dont accidentally use yum cache while we operate on it.
        self.yumCacheLock = open(os.path.join(self.yumSharedCachePath, "yumcache.lock"), "a+")
        self._yumCachePreYumHook()

        if self.online:
            self.state("enabled yum cache, cleaning yum metadata")
            for (dirpath, dirnames, filenames) in os.walk(self.yumSharedCachePath):
                for filename in filenames:
                    fullPath = os.path.join(dirpath, filename)
                    statinfo = os.stat(fullPath)
                    file_age_days = (time.time() - statinfo.st_ctime) / (60 * 60 * 24)
                    # prune repodata so yum redownloads.
                    # prevents certain errors where yum gets stuck due to bad metadata
                    for ext in (".sqllite", ".xml", ".bz2", ".gz"):
                        if filename.endswith(ext) and file_age_days > self.yum_cache_opts['max_metadata_age_days']:
                            os.unlink(fullPath)
                            fullPath = None
                            break
    
                    if fullPath is None: continue
                    if file_age_days > self.yum_cache_opts['max_age_days']:
                        os.unlink(fullPath)
                        continue

        self._yumCachePostYumHook()

