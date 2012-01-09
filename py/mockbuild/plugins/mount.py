# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Daniel Mach
# Copyright (C) 2011 Daniel Mach <dmach@redhat.com>


"""
# The mount plugin is enabled by default.
# To disable it, use following option:
config_opts['plugin_conf']['mount_enable'] = False


# To configure the mount plugin, for each mount point use following option:
config_opts['plugin_conf']['mount_opts']['dirs'].append(("/dev/device", "/mount/path/in/chroot/", "vfstype", "mount_options"))

# A real life example:
config_opts['plugin_conf']['mount_opts']['dirs'].append(("server.example.com:/exports/data", "/mnt/data", "nfs", "rw,hard,intr,nosuid,nodev,noatime,tcp"))
"""


import mockbuild.util
from mockbuild.trace_decorator import decorate, traceLog
from mockbuild.mounts import FileSystemMountPoint

requires_api_version = "1.0"


# plugin entry point
decorate(traceLog())
def init(rootObj, conf):
    Mount(rootObj, conf)


# classes
class Mount(object):
    """mount dirs into chroot"""
    decorate(traceLog())
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.opts = conf
        rootObj.mountObj = self
        rootObj.addHook("preinit", self._mountPreInitHook)
        rootObj.addHook("preshell", self._mountPreInitHook)
        rootObj.addHook("prechroot", self._mountPreInitHook)
        for device, dest_dir, vfstype, mount_opts in self.opts['dirs']:
            if vfstype:
                vfstype = "-t " + vfstype
            else:
                vfstype = ""
            rootObj.mounts.add(FileSystemMountPoint(rootObj.makeChrootPath(dest_dir),
                                                    filetype=vfstype,
                                                    device=device,
                                                    options=mount_opts))
    decorate(traceLog())
    def _mountPreInitHook(self):
        for device, dest_dir, vfstype, mount_opts in self.opts['dirs']:
            mockbuild.util.mkdirIfAbsent(self.rootObj.makeChrootPath(dest_dir))
