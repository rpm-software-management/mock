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
    system_ram_bytes = os.sysconf(os.sysconf_names['SC_PAGE_SIZE']) * os.sysconf(os.sysconf_names['SC_PHYS_PAGES'])
    system_ram_mb = system_ram_bytes / (1024 * 1024)
    if system_ram_mb > conf['required_ram_mb']:
        Tmpfs(rootObj, conf)
    else:
        getLog().warning("Tmpfs plugin disabled. "
            "System does not have the required amount of RAM to enable the tmpfs plugin. "
            "System has %sMB RAM, but the config specifies the minimum required is %sMB RAM. "
            %
            (system_ram_mb, conf['required_ram_mb']))

# classes
class Tmpfs(object):
    """Mounts a tmpfs on the chroot dir"""
    decorate(traceLog())
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.conf = conf
        rootObj.addHook("preinit",  self._tmpfsPreInitHook)
        rootObj.addHook("postbuild",  self._tmpfsPostBuildHook)
        rootObj.addHook("initfailed",  self._tmpfsPostBuildHook)

    decorate(traceLog())
    def _tmpfsPreInitHook(self):
        getLog().info("mounting tmpfs.")
        mountCmd = ["mount", "-n", "-t", "tmpfs", "mock_chroot_tmpfs", 
                    self.rootObj.makeChrootPath()]
        mock.util.do(mountCmd, shell=False)

    decorate(traceLog())
    def _tmpfsPostBuildHook(self):
        getLog().info("unmounting tmpfs.")
        mountCmd = ["umount", "-n", self.rootObj.makeChrootPath()]
        mock.util.do(mountCmd, shell=False)


