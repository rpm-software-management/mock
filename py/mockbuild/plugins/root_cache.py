# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import fcntl
import os
import time

# our imports
from mockbuild.trace_decorator import decorate, traceLog, getLog
import mockbuild.util

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
        if self.compressProgram == 'pigz' and not os.path.exists('/usr/bin/pigz'):
            getLog().warning("specified 'pigz' as the root cache compress program but not available; using gzip")
            self.compressProgram = 'gzip'
        if self.compressProgram:
             self.compressArgs = ['--use-compress-program', self.compressProgram]
             self.rootCacheFile = self.rootCacheFile + self.root_cache_opts['extension']
        else:
             self.compressArgs = []
        rootObj.rootCacheObj = self
        rootObj.addHook("preinit", self._rootCachePreInitHook)
        rootObj.addHook("preshell", self._rootCachePreShellHook)
        rootObj.addHook("prechroot", self._rootCachePreShellHook)
        rootObj.addHook("preyum", self._rootCachePreYumHook)
        rootObj.addHook("postinit", self._rootCachePostInitHook)
        rootObj.addHook("postshell", self._rootCachePostShellHook)
        rootObj.addHook("postchroot", self._rootCachePostShellHook)
        rootObj.addHook("postyum", self._rootCachePostShellHook)
        self.exclude_dirs = self.root_cache_opts['exclude_dirs']
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
            self.rootObj.start("Waiting for rootcache lock")
            fcntl.lockf(self.rootCacheLock.fileno(), lockType)
            self.rootObj.finish("Waiting for rootcache lock")

    decorate(traceLog())
    def _rootCacheUnlock(self):
        fcntl.lockf(self.rootCacheLock.fileno(), fcntl.LOCK_UN)

    decorate(traceLog())
    def _rootCachePreInitHook(self):
        getLog().info("enabled root cache")
        self._unpack_root_cache()

    decorate(traceLog())
    def _unpack_root_cache(self):
        # check cache status
        try:
            if self.root_cache_opts['age_check']:
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
            else:
                getLog().info("skipping root_cache aging check")
        except OSError:
            pass

        mockbuild.util.mkdirIfAbsent(self.rootSharedCachePath)
        # lock so others dont accidentally use root cache while we operate on it.
        if self.rootCacheLock is None:
            self.rootCacheLock = open(os.path.join(self.rootSharedCachePath, "rootcache.lock"), "a+")

        # optimization: don't unpack root cache if chroot was not cleaned (unless we are using tmpfs)
        if os.path.exists(self.rootCacheFile):
            if (not self.rootObj.chroot_was_initialized()
                    or self.rootObj.pluginConf['tmpfs_enable']):
                self.rootObj.start("unpacking root cache")
                self._rootCacheLock()
                #
                # deal with NFS homedir and root_squash
                #
                if mockbuild.util.get_fs_type(os.getcwd()).startswith('nfs'):
                    os.chdir(mockbuild.util.find_non_nfs_dir())
                mockbuild.util.do(
                    ["tar"] + self.compressArgs + ["-xf", self.rootCacheFile, "-C", self.rootObj.makeChrootPath()],
                    shell=False
                    )
                for dir in self.exclude_dirs:
                    mockbuild.util.mkdirIfAbsent(self.rootObj.makeChrootPath(dir))
                self._rootCacheUnlock()
                self.rootObj.chrootWasCached = True
                self.rootObj.finish("unpacking root cache")

    decorate(traceLog())
    def _rootCachePreShellHook(self):
        if self.rootObj.pluginConf['tmpfs_enable']:
            self._unpack_root_cache()

    decorate(traceLog())
    def _rootCachePreYumHook(self):
        if self.rootObj.pluginConf['tmpfs_enable']:
            if not os.listdir(self.rootObj.makeChrootPath()) or self.rootObj.cache_alterations:
                self._unpack_root_cache()

    decorate(traceLog())
    def _root_cache_handle_mounts(self):
        for m in self.rootObj.mounts.get_mountpoints():
            if m.startswith('/'):
                self.exclude_tar_cmds.append('--exclude=.%s' % m)
            else:
                self.exclude_tar_cmds.append('--exclude=./%s' % m)

    decorate(traceLog())
    def _rootCachePostInitHook(self):
        self._rebuild_root_cache()

    decorate(traceLog())
    def _rebuild_root_cache(self):
        try:
            self._rootCacheLock(shared=0)
            # nuke any rpmdb tmp files
            self.rootObj._nuke_rpm_db()

            # truncate the sparse files in /var/log
            for logfile in ('/var/log/lastlog', '/var/log/faillog'):
                try:
                    f = open(self.rootObj.makeChrootPath(logfile), "w")
                    f.truncate(0)
                    f.close()
                except:
                    pass

            # never rebuild cache unless it was a clean build, or we are explicitly caching alterations
            if not self.rootObj.chroot_was_initialized() or self.rootObj.cache_alterations:
                mockbuild.util.do(["sync"], shell=False)
                self._root_cache_handle_mounts()
                self.rootObj.start("creating cache")
                try:
                    mockbuild.util.do(
                        ["tar", "--one-file-system"] + self.compressArgs + ["-cf", self.rootCacheFile,
                                                       "-C", self.rootObj.makeChrootPath()] +
                        self.exclude_tar_cmds + ["."],
                        shell=False
                        )
                except:
                    if os.path.exists(self.rootCacheFile):
                        os.remove(self.rootCacheFile)
                    raise
                # now create the cache log file
                try:
                    l = open(os.path.join(self.rootSharedCachePath, "cache.log"), "w")
                    l.write(self.rootObj.yum_init_install_output)
                    l.close()
                except:
                    pass
                self.rootObj.finish("creating cache")
        finally:
            self._rootCacheUnlock()

    decorate(traceLog())
    def _rootCachePostShellHook(self):
        if self.rootObj.pluginConf['tmpfs_enable'] and self.rootObj.cache_alterations:
            self._rebuild_root_cache()

