#!/usr/bin/python -tt
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Written by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# revised and adapted by Michael Brown

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
    rootCache = RootCache(rootObj, conf)

# classes
class RootCache(object):
    """caches root environment in a tarball"""
    @traceLog(moduleLog)
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.root_cache_opts = conf
        self.rootSharedCachePath = os.path.join(rootObj.cachedir, "root_cache")
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
        mock.util.mkdirIfAbsent(self.rootSharedCachePath)
        # lock so others dont accidentally use root cache while we operate on it.
        if self.rootCacheLock is None:
            self.rootCacheLock = open(os.path.join(self.rootSharedCachePath, "rootcache.lock"), "a+")

        # check cache age:
        self.state("enabling root cache")
        try:
            statinfo = os.stat(self.rootCacheFile)
            file_age_days = (time.time() - statinfo.st_ctime) / (60 * 60 * 24)
            if file_age_days > self.root_cache_opts['max_age_days']:
                os.unlink(self.rootCacheFile)
        except OSError:
            pass

        if os.path.exists(self.rootCacheFile):
            self.state("unpacking cache")
            self._rootCacheLock()
            mock.util.do("tar xzf %s -C %s" % (self.rootCacheFile, self.rootdir))
            self._rootCacheUnlock()
            self.chroot_setup_cmd = "update"
            self.chrootWasCleaned = False

    @traceLog(moduleLog)
    def _rootCachePostInitHook(self):
        # never rebuild cache unless it was a clean build.
        if self.chrootWasCleaned:
            self.state("creating cache")
            self._rootCacheLock(shared=0)
            mock.util.do("tar czf %s -C %s ." % (self.rootCacheFile, self.rootdir))
            self._rootCacheUnlock()

