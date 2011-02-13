# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import fcntl
import os
import time
from glob import glob

# our imports
from mock.trace_decorator import decorate, traceLog, getLog
import mock.util

requires_api_version = "1.0"

# plugin entry point
decorate(traceLog())
def init(rootObj, conf):
    RootCache(rootObj, conf)

# classes
class RootCache(object):
    """caches root environment in a tarball"""
    decorate(traceLog())


    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.root_cache_opts = conf
        self.rootSharedCachePath = self.root_cache_opts['dir'] % self.root_cache_opts
        self.rootCacheFile = os.path.join(self.rootSharedCachePath, "cache.tar")
        self.rootCacheLock = None
        self.compressProgram = self.root_cache_opts['compress_program']
        if self.compressProgram:
             self.compressArgs = ['--use-compress-program', self.compressProgram]
             self.rootCacheFile = self.rootCacheFile + self.root_cache_opts['extension']
        else:
             self.compressArgs = []
        self.state = rootObj.state
        rootObj.rootCacheObj = self
        rootObj.addHook("preinit", self._rootCachePreInitHook)
        rootObj.addHook("postinit", self._rootCachePostInitHook)
        self.exclude_dirs = ["./proc", "./sys", "./dev", "./tmp/ccache", "./var/cache/yum" ]
        self.exclude_tar_cmds = [ "--exclude=" + dir for dir in self.exclude_dirs]

    # =============
    # 'Private' API
    # =============
    decorate(traceLog())
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

    decorate(traceLog())
    def _rootCacheUnlock(self):
        fcntl.lockf(self.rootCacheLock.fileno(), fcntl.LOCK_UN)

    decorate(traceLog())
    def _rootCachePreInitHook(self):
        getLog().info("enabled root cache")
        mock.util.mkdirIfAbsent(self.rootSharedCachePath)
        # lock so others dont accidentally use root cache while we operate on it.
        if self.rootCacheLock is None:
            self.rootCacheLock = open(os.path.join(self.rootSharedCachePath, "rootcache.lock"), "a+")

        # check cache status
        try:
            # see if it aged out
            statinfo = os.stat(self.rootCacheFile)
            file_age_days = (time.time() - statinfo.st_ctime) / (60 * 60 * 24)
            if file_age_days > self.root_cache_opts['max_age_days']:
                getLog().info("root cache aged out! cache will be rebuilt")
                os.unlink(self.rootCacheFile)
            else:
                # make sure no config file is newer than the cache file
                for cfg in self.rootObj.configs:
                    if os.stat(cfg).st_mtime > statinfo.st_mtime:
                        getLog().info("%s newer than root cache; cache will be rebuilt" % cfg)
                        os.unlink(self.rootCacheFile)
                        break
        except OSError:
            pass

        # optimization: don't unpack root cache if chroot was not cleaned
        if os.path.exists(self.rootCacheFile) and self.rootObj.chrootWasCleaned:
            self.state("unpacking root cache")
            self._rootCacheLock()
            mock.util.do(
                ["tar"] + self.compressArgs + ["-xf", self.rootCacheFile, "-C", self.rootObj.makeChrootPath()],
                shell=False
                )
            for dir in self.exclude_dirs:
                mock.util.mkdirIfAbsent(self.rootObj.makeChrootPath(dir))
            self._rootCacheUnlock()
            self.rootObj.chrootWasCleaned = False
            self.rootObj.chrootWasCached = True

    decorate(traceLog())
    def _rootCachePostInitHook(self):
        try:
            self._rootCacheLock(shared=0)
            # nuke any rpmdb tmp files
            for tmp in glob(self.rootObj.makeChrootPath('var/lib/rpm/__db*')):
                os.unlink(tmp)

            # truncate the sparse files in /var/log
            for logfile in ('/var/log/lastlog', '/var/log/faillog'):
                f = open(self.rootObj.makeChrootPath(logfile), "w")
                f.truncate(0)
                f.close()

            # never rebuild cache unless it was a clean build.
            if self.rootObj.chrootWasCleaned:
                mock.util.do(["sync"], shell=False)
                self.state("creating cache")
                try:
                    mock.util.do(
                        ["tar"] + self.compressArgs + ["-cf", self.rootCacheFile,
                                                       "-C", self.rootObj.makeChrootPath()] +
                        self.exclude_tar_cmds + ["."],
                        shell=False
                        )
                except:
                    if os.path.exists(self.rootCacheFile):
                        os.remove(self.rootCacheFile)
                    raise
                # now create the cache log file
                l = open(os.path.join(self.rootSharedCachePath, "cache.log"), "w")
                l.write(self.rootObj.yum_init_install_output)
                l.close()
        finally:
            self._rootCacheUnlock()
