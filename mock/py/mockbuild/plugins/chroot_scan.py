# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Clark Williams
# Copyright (C) 2013 Clark Williams <clark.williams@gmail.com>

# python library imports
import os
import os.path
import re
import shutil

# our imports
from mockbuild.trace_decorator import getLog, traceLog
from mockbuild import util, file_util

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    ChrootScan(plugins, conf, buildroot)


class ChrootScan(object):
    """scan chroot for files of interest, copying to resultdir with relative paths"""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.scan_opts = conf
        plugins.add_hook("postbuild", self._scanChroot)
        plugins.add_hook("initfailed", self._scanChroot)
        getLog().info("chroot_scan: initialized")

    @property
    def resultdir(self):
        """
        The plugin's self.resultdir is a subdir of buildroot.resultdir, which
        is, e.g., for --chain, changed for every single package.
        """
        return os.path.join(self.buildroot.resultdir, "chroot_scan")

    def _only_failed(self):
        """ Returns boolean value if option 'only_failed' is set. """
        return str(self.scan_opts.get('only_failed')) == 'True'

    def _tarball(self):
        """ Returns boolean value if option 'write_tar' is set. """
        return str(self.scan_opts.get('write_tar')) == 'True'

    @traceLog()
    def _scanChroot(self):
        is_failed = self.state.result != "success"
        if (self._only_failed() and is_failed) or not self._only_failed():
            self.__scanChroot()

    def __scanChroot(self):
        regexstr = "|".join(self.scan_opts['regexes'])
        regex = re.compile(regexstr)
        chroot = self.buildroot.make_chroot_path()
        self.buildroot.create_resultdir()
        # self.resultdir != self.buildroot.resultdir
        file_util.mkdirIfAbsent(self.resultdir)
        count = 0
        logger = getLog()
        logger.debug("chroot_scan: Starting scan of %s", chroot)
        copied = []
        for root, _, files in os.walk(chroot):
            for f in files:
                m = regex.search(f)
                if m:
                    srcpath = os.path.join(root, f)
                    # we intentionally ignore errors here:
                    # https://github.com/rpm-software-management/mock/issues/1455
                    util.do(["cp", "--preserve=mode", "--parents", srcpath,
                             self.resultdir], raiseExc=False)
                    count += 1
                    copied.append(srcpath)
        logger.debug("chroot_scan: finished with %d files found", count)
        if count:
            logger.info("chroot_scan: %d files copied to %s", count, self.resultdir)
            logger.info("\n".join(copied))
            self.buildroot.uid_manager.changeOwner(self.resultdir, recursive=True)
            # some packages installs 555 perms on dirs,
            # so user can't delete/move chroot_scan's results
            util.do(['chmod', '-R', 'u+w', self.resultdir])
            if self._tarball():
                tarfile = self.resultdir + ".tar.gz"
                logger.info("chroot_scan: creating tarball %s", tarfile)
                __tar_cmd = self.config["tar_binary"]
                util.do(
                    [__tar_cmd, "-czf", tarfile, self.resultdir],
                    shell=False, printOutput=True
                )
                shutil.rmtree(self.resultdir)
                self.buildroot.uid_manager.changeOwner(tarfile)
