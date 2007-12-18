# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import os

# our imports
from mock.trace_decorator import decorate, traceLog, getLog
import mock.util

requires_api_version = "1.0"

# plugin entry point
decorate(traceLog())
def init(rootObj, conf):
    Tmpfs(rootObj, conf)

# classes
class Tmpfs(object):
    """Mounts a tmpfs on the chroot dir"""
    decorate(traceLog())
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.conf = conf
        rootObj.addHook("preinit",  self._tmpfsPreInitHook)

    decorate(traceLog())
    def _tmpfsPreInitHook(self):
        mountCmd = "mount -n -t tmpfs  mock_chroot_tmpfs %s" % self.makeChrootPath()
        mock.util.do(mountCmd)

