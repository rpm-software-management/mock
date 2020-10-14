# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Daniel Mach
# Copyright (C) 2011 Daniel Mach <dmach@redhat.com>


"""
# The mount plugin is enabled by default.
# To disable it, use following option:
config_opts['plugin_conf']['mount_enable'] = False


# To configure the mount plugin, for each mount point use following option:
config_opts['plugin_conf']['mount_opts']['dirs'].append(
    ("/dev/device", "/mount/path/in/chroot/", "vfstype", "mount_options"))

# A real life example:
config_opts['plugin_conf']['mount_opts']['dirs'].append(
    ("server.example.com:/exports/data", "/mnt/data", "nfs", "rw,hard,intr,nosuid,nodev,noatime,tcp"))
"""

from mockbuild.mounts import FileSystemMountPoint
from mockbuild.trace_decorator import traceLog
from mockbuild import file_util

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    Mount(plugins, conf, buildroot)


class Mount(object):
    """mount dirs into chroot"""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.opts = conf
        # Skip mounting user-specified mounts if we're in the boostrap chroot
        if buildroot.is_bootstrap:
            return
        plugins.add_hook("postinit", self._mountCreateDirs)
        for device, dest_dir, vfstype, mount_opts in self.opts['dirs']:
            buildroot.mounts.add_user_mount(
                FileSystemMountPoint(buildroot.make_chroot_path(dest_dir),
                                     filetype=vfstype,
                                     device=device,
                                     options=mount_opts))

    @traceLog()
    def _mountCreateDirs(self):
        # pylint: disable=unused-variable
        for device, dest_dir, vfstype, mount_opts in self.opts['dirs']:
            file_util.mkdirIfAbsent(self.buildroot.make_chroot_path(dest_dir))
