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


class CacheDir:
    def __init__(self, buildroot, pkg_manager):
        self.buildroot = buildroot
        self.cache_path = os.path.join('/var/cache', pkg_manager)
        self.host_cache_path = os.path.join(self.buildroot.cachedir,
                                            pkg_manager + '_cache')
        self.mount_path = self.buildroot.make_chroot_path(self.cache_path)
        self.buildroot.mounts.add(BindMountPoint(
            srcpath=self.host_cache_path,
            bindpath=self.mount_path,
        ))

        mockbuild.file_util.mkdirIfAbsent(self.host_cache_path)


class YumCache(object):
    """
    Pre-mount /var/cache/yum and /var/cache/dnf machine to chroot, because
    yum/dnf stores the caches below --installroot directory, which is cleaned
    up with --clean or --scrub=chroot.
    """
    # pylint: disable=too-few-public-methods

    METADATA_EXTS = (".sqlite", ".xml", ".bz2", ".gz", ".xz", ".solv", ".solvx")

    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.yum_cache_opts = conf
        self.cache_dirs = [
            CacheDir(buildroot, 'yum'),
            CacheDir(buildroot, 'dnf'),
        ]
        self.yumSharedCachePath = self.cache_dirs[0].host_cache_path
        self.online = self.config['online']
        plugins.add_hook("preyum", self._yumCachePreYumHook)
        plugins.add_hook("postyum", self._yumCachePostYumHook)
        plugins.add_hook("preinit", self._yumCachePreInitHook)

        self.yumCacheLock = open(os.path.join(buildroot.cachedir, "yumcache.lock"), "a+")


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

    @traceLog()
    def _prune_repo_data(self, directory):
        for (dirpath, _, filenames) in os.walk(directory):
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


    @traceLog()
    def _yumCachePreInitHook(self):
        getLog().info("enabled package manager cache")

        for cdir in self.cache_dirs:
            mockbuild.file_util.mkdirIfAbsent(cdir.host_cache_path)

        # lock so others dont accidentally use yum cache while we operate on it.
        self._yumCachePreYumHook()

        if self.online:
            state = "cleaning package manager metadata"
            self.state.start(state)
            for cdir in self.cache_dirs:
                self._prune_repo_data(cdir.host_cache_path)
            self.state.finish(state)

        # yum made an rpmdb cache dir in $cachedir/installed for a while;
        # things can go wrong in a specific mock case if this happened.
        # So - just nuke the dir and all that's in it.
        if os.path.exists(self.yumSharedCachePath + '/installed'):
            for fn in glob.glob(self.yumSharedCachePath + '/installed/*'):
                os.unlink(fn)
            os.rmdir(self.yumSharedCachePath + '/installed')

        self._yumCachePostYumHook()
