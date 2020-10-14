# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import fcntl
import os
import time

# our imports
from mockbuild.trace_decorator import getLog, traceLog
import mockbuild.util
import mockbuild.text

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    RootCache(plugins, conf, buildroot)


class RootCache(object):
    """caches root environment in a tarball"""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.root_cache_opts = conf
        self.config = buildroot.config
        self.state = buildroot.state
        self.rootSharedCachePath = self.root_cache_opts['dir'] % self.root_cache_opts
        self.rootCacheFile = os.path.join(self.rootSharedCachePath, "cache.tar")
        self.rootCacheLock = None
        self.compressProgram = self.root_cache_opts['compress_program']
        if self.compressProgram == 'pigz' and not os.path.exists('/bin/pigz'):
            getLog().warning("specified 'pigz' as the root cache compress program but not available; using gzip")
            self.compressProgram = 'gzip'
        # bsdtar use different decompress program
        self.decompressProgram = self.root_cache_opts['decompress_program'] or self.compressProgram
        if self.compressProgram:
            self.compressArgs = ['--use-compress-program', self.compressProgram]
            self.rootCacheFile = self.rootCacheFile + self.root_cache_opts['extension']
        else:
            self.compressArgs = []
        if self.decompressProgram:
            self.decompressArgs = ['--use-compress-program', self.decompressProgram]
        else:
            self.decompressArgs = []
        plugins.add_hook("preinit", self._rootCachePreInitHook)
        plugins.add_hook("preshell", self._rootCachePreShellHook)
        plugins.add_hook("prechroot", self._rootCachePreShellHook)
        plugins.add_hook("preyum", self._rootCachePreYumHook)
        plugins.add_hook("postinit", self._rootCachePostInitHook)
        plugins.add_hook("postshell", self._rootCachePostShellHook)
        plugins.add_hook("postchroot", self._rootCachePostShellHook)
        plugins.add_hook("postyum", self._rootCachePostShellHook)
        plugins.add_hook("postupdate", self._rootCachePostUpdateHook)
        self.exclude_dirs = self.root_cache_opts['exclude_dirs']
        self.exclude_tar_cmds = []
        for ex_dir in self.exclude_dirs:
            self._tarExcludeOption(ex_dir)

    def _tarExcludeOption(self, ex_dir):
        if self.config['tar'] == 'bsdtar':
            anchor = '^'
        else:
            anchor = ''

        self.exclude_tar_cmds.append('--exclude=' + anchor + ex_dir)

    # =============
    # 'Private' API
    # =============
    @traceLog()
    def _rootCacheLock(self, shared=1):
        lockType = fcntl.LOCK_EX
        if shared:
            lockType = fcntl.LOCK_SH
        try:
            fcntl.lockf(self.rootCacheLock.fileno(), lockType | fcntl.LOCK_NB)
        except IOError:
            self.state.start("Waiting for rootcache lock")
            fcntl.lockf(self.rootCacheLock.fileno(), lockType)
            self.state.finish("Waiting for rootcache lock")

    @traceLog()
    def _rootCacheUnlock(self):
        fcntl.lockf(self.rootCacheLock.fileno(), fcntl.LOCK_UN)

    @traceLog()
    def _rootCachePreInitHook(self):
        getLog().info("enabled root cache")
        self._unpack_root_cache()

    def _haveVolatileRoot(self):
        # pylint: disable=unneeded-not
        return self.config['plugin_conf']['tmpfs_enable'] \
            and not (str(self.config['plugin_conf']['tmpfs_opts']['keep_mounted']) == 'True')

    @traceLog()
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
                    for cfg in self.config['config_paths']:
                        if os.stat(cfg).st_mtime > statinfo.st_mtime:
                            getLog().info("%s newer than root cache; cache will be rebuilt", cfg)
                            os.unlink(self.rootCacheFile)
                            break
            else:
                getLog().info("skipping root_cache aging check")
        except OSError:
            pass

        mockbuild.file_util.mkdirIfAbsent(self.rootSharedCachePath)
        # lock so others dont accidentally use root cache while we operate on it.
        if self.rootCacheLock is None:
            self.rootCacheLock = open(os.path.join(self.rootSharedCachePath, "rootcache.lock"), "a+")

        # optimization: don't unpack root cache if chroot was not cleaned (unless we are using tmpfs)
        if os.path.exists(self.rootCacheFile):
            if (not self.buildroot.chroot_was_initialized or self._haveVolatileRoot()):
                self.state.start("unpacking root cache")
                self._rootCacheLock()
                # deal with NFS homedir and root_squash
                prev_cwd = None
                cwd = mockbuild.util.pretty_getcwd()
                if mockbuild.file_util.get_fs_type(cwd).startswith('nfs'):
                    prev_cwd = os.getcwd()
                    os.chdir(mockbuild.file_util.find_non_nfs_dir())
                mockbuild.file_util.mkdirIfAbsent(self.buildroot.make_chroot_path())
                if self.config["tar"] == "bsdtar":
                    __tar_cmd = "bsdtar"
                else:
                    __tar_cmd = "gtar"
                mockbuild.util.do(
                    [__tar_cmd] + self.decompressArgs + ["-xf", self.rootCacheFile,
                                                         "-C", self.buildroot.make_chroot_path()],
                    shell=False, printOutput=True
                )
                for item in self.exclude_dirs:
                    mockbuild.file_util.mkdirIfAbsent(self.buildroot.make_chroot_path(item))

                self._rootCacheUnlock()
                self.buildroot.chrootWasCached = True
                self.state.finish("unpacking root cache")
                if prev_cwd:
                    os.chdir(prev_cwd)

    @traceLog()
    def _rootCachePreShellHook(self):
        if self._haveVolatileRoot():
            self._unpack_root_cache()

    @traceLog()
    def _rootCachePreYumHook(self):
        if self._haveVolatileRoot():
            if not os.listdir(self.buildroot.make_chroot_path()) or self.config['cache_alterations']:
                self._unpack_root_cache()

    @traceLog()
    def _root_cache_handle_mounts(self):
        br_path = self.buildroot.make_chroot_path()
        for m in self.buildroot.mounts.get_mountpoints():
            if m.startswith('/'):
                if m.startswith(br_path):
                    self._tarExcludeOption('./' + m[len(br_path):])
                else:
                    self._tarExcludeOption('.' + m)
            else:
                self._tarExcludeOption('./' + m)

    @traceLog()
    def _rootCachePostInitHook(self):
        self._rebuild_root_cache()

    @traceLog()
    def _rebuild_root_cache(self, after_update=False):
        try:
            self._rootCacheLock(shared=0)
            # nuke any rpmdb tmp files
            self.buildroot.nuke_rpm_db()

            # truncate the sparse files in /var/log
            for logfile in ('/var/log/lastlog', '/var/log/faillog'):
                try:
                    with open(self.buildroot.make_chroot_path(logfile), "w") as f:
                        f.truncate(0)
                except (IOError, OSError):
                    pass

            # never rebuild cache unless it was a clean build, or we are explicitly caching alterations
            if not self.buildroot.chroot_was_initialized or self.config['cache_alterations'] or after_update:
                mockbuild.util.do(["sync"], shell=False)
                self._root_cache_handle_mounts()
                self.state.start("creating root cache")
                if self.config['tar'] == 'bsdtar':
                    __tar_cmd = ["bsdtar", "--one-file-system"] + self.compressArgs + \
                                ["-cf", self.rootCacheFile,
                                 "-C", self.buildroot.make_chroot_path()] + \
                                self.exclude_tar_cmds + ["."]
                else:
                    __tar_cmd = ["gtar", "--one-file-system", "--exclude-caches", "--exclude-caches-under"] + \
                                 self.compressArgs + \
                                 ["-cf", self.rootCacheFile,
                                  "-C", self.buildroot.make_chroot_path()] + \
                                 self.exclude_tar_cmds + ["."]
                try:
                    mockbuild.util.do(__tar_cmd, shell=False)
                except:
                    if os.path.exists(self.rootCacheFile):
                        os.remove(self.rootCacheFile)
                    raise
                # now create the cache log file
                with open(os.path.join(self.rootSharedCachePath, "cache.log"), "wb") as cache_log:
                    cache_log.write(self.buildroot.pkg_manager.init_install_output.encode(mockbuild.text.encoding))
                self.state.finish("creating root cache")
        finally:
            self._rootCacheUnlock()

    @traceLog()
    def _rootCachePostShellHook(self):
        if self._haveVolatileRoot() and self.config['cache_alterations']:
            self._rebuild_root_cache()

    @traceLog()
    def _rootCachePostUpdateHook(self):
        self._rebuild_root_cache(after_update=True)
