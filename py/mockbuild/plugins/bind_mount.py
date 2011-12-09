# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import os

# our imports
from mockbuild.trace_decorator import decorate, traceLog

import mockbuild.util

from mockbuild.mounts import BindMountPoint

requires_api_version = "1.0"

# plugin entry point
decorate(traceLog())
def init(rootObj, conf):
    BindMount(rootObj, conf)

# classes
class BindMount(object):
    """bind mount dirs from host into chroot"""
    decorate(traceLog())
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.bind_opts = conf
        rootObj.bindMountObj = self
        rootObj.addHook("preinit",  self._bindMountPreInitHook)
        rootObj.addHook("preshell",  self._bindMountPreInitHook)
        rootObj.addHook("prechroot",  self._bindMountPreInitHook)
        for srcdir, destdir in self.bind_opts['dirs']:
            rootObj.mounts.add(BindMountPoint(srcpath=srcdir, bindpath=rootObj.makeChrootPath(destdir)))

    decorate(traceLog())
    def _bindMountPreInitHook(self):
        create_dirs = self.rootObj.pluginConf['bind_mount_opts']['create_dirs']
        for srcdir, destdir in self.bind_opts['dirs']:
            if create_dirs: mockbuild.util.mkdirIfAbsent(srcdir)
            mockbuild.util.mkdirIfAbsent(self.rootObj.makeChrootPath(destdir))
