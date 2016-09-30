# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import fcntl
import glob
import os
import time

# our imports
from mockbuild.mounts import BindMountPoint
from mockbuild.trace_decorator import getLog, traceLog
import mockbuild.util

# set up logging, module options
requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    YumCache(plugins, conf, buildroot)


class YumCache(object):
    """ mount /var/cache/yum or /var/cache/dnf of your machine to chroot """

    METADATA_EXTS = (".sqlite", ".xml", ".bz2", ".gz", ".xz", ".solv", ".solvx")

    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.yum_cache_opts = conf
        self.yum_cache_opts['package_manager'] = self.config['package_manager']
        self.yumSharedCachePath = self.yum_cache_opts['dir'] % self.yum_cache_opts
        self.target_path = self.yum_cache_opts['target_dir'] % self.yum_cache_opts
        self.online = self.config['online']
        plugins.add_hook("preyum", self._yumCachePreYumHook)
        plugins.add_hook("postyum", self._yumCachePostYumHook)
        plugins.add_hook("preinit", self._yumCachePreInitHook)
        buildroot.mounts.add(BindMountPoint(srcpath=self.yumSharedCachePath,
                                            bindpath=buildroot.make_chroot_path(self.target_path)))
        mockbuild.util.mkdirIfAbsent(self.yumSharedCachePath)
        self.yumCacheLock = open(os.path.join(self.yumSharedCachePath, "yumcache.lock"), "a+")

    # =============
    # 'Private' API
    # =============
    # lock the shared yum cache (when enabled) before any access
    # by yum, and prior to cleaning it. This prevents simultaneous access from
    # screwing things up. This can possibly happen, eg. when running multiple
    # mock instances with --uniqueext=
    @traceLog()
    def _yumCachePreYumHook(self):
        try:
            fcntl.lockf(self.yumCacheLock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            self.state.start("Waiting for yumcache lock")
            fcntl.lockf(self.yumCacheLock.fileno(), fcntl.LOCK_EX)
            self.state.finish("Waiting for yumcache lock")

    @traceLog()
    def _yumCachePostYumHook(self):
        fcntl.lockf(self.yumCacheLock.fileno(), fcntl.LOCK_UN)

    def _format_pm(self, s):
        return s.format(pm=self.config['package_manager'])

    @traceLog()
    def _yumCachePreInitHook(self):
        getLog().info(self._format_pm("enabled {pm} cache"))
        mockbuild.util.mkdirIfAbsent(self.buildroot.make_chroot_path(self.target_path))

        # lock so others dont accidentally use yum cache while we operate on it.
        self._yumCachePreYumHook()

        if self.online:
            state = self._format_pm("cleaning {pm} metadata")
            self.state.start(state)
            for (dirpath, _, filenames) in os.walk(self.yumSharedCachePath):
                for filename in filenames:
                    fullPath = os.path.join(dirpath, filename)
                    statinfo = os.stat(fullPath)
                    file_age_days = (time.time() - statinfo.st_ctime) / (60 * 60 * 24)
                    # prune repodata so yum redownloads.
                    # prevents certain errors where yum gets stuck due to bad metadata
                    for ext in self.METADATA_EXTS:
                        if filename.endswith(ext) and file_age_days > self.yum_cache_opts['max_metadata_age_days']:
                            os.unlink(fullPath)
                            fullPath = None
                            break

                    if fullPath is None:
                        continue
                    if file_age_days > self.yum_cache_opts['max_age_days']:
                        os.unlink(fullPath)
                        continue
            self.state.finish(state)

        # yum made an rpmdb cache dir in $cachedir/installed for a while;
        # things can go wrong in a specific mock case if this happened.
        # So - just nuke the dir and all that's in it.
        if os.path.exists(self.yumSharedCachePath + '/installed'):
            for fn in glob.glob(self.yumSharedCachePath + '/installed/*'):
                os.unlink(fn)
            os.rmdir(self.yumSharedCachePath + '/installed')

        self._yumCachePostYumHook()
