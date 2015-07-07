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
from mockbuild.trace_decorator import traceLog
from mockbuild.mounts import FileSystemMountPoint

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    Mount(plugins, conf, buildroot)

# classes
class Mount(object):
    """mount dirs into chroot"""
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.opts = conf
        plugins.add_hook("preinit", self._mountPreInitHook)
        for device, dest_dir, vfstype, mount_opts in self.opts['dirs']:
            buildroot.mounts.add(FileSystemMountPoint(buildroot.make_chroot_path(dest_dir),
                                                    filetype=vfstype,
                                                    device=device,
                                                    options=mount_opts))
    @traceLog()
    def _mountPreInitHook(self):
        for device, dest_dir, vfstype, mount_opts in self.opts['dirs']:
            mockbuild.util.mkdirIfAbsent(self.buildroot.make_chroot_path(dest_dir))
