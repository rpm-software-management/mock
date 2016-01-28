# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports

# our imports
from mockbuild.trace_decorator import traceLog

import mockbuild.util

from mockbuild.mounts import BindMountPoint

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    BindMount(plugins, conf, buildroot)


class BindMount(object):
    """bind mount dirs from host into chroot"""
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.bind_opts = conf
        plugins.add_hook("preinit", self._bindMountPreInitHook)
        for srcdir, destdir in self.bind_opts['dirs']:
            buildroot.mounts.add(BindMountPoint(srcpath=srcdir, bindpath=buildroot.make_chroot_path(destdir)))

    @traceLog()
    def _bindMountPreInitHook(self):
        create_dirs = self.config['plugin_conf']['bind_mount_opts']['create_dirs']
        for srcdir, destdir in self.bind_opts['dirs']:
            if create_dirs:
                mockbuild.util.mkdirIfAbsent(srcdir)
            mockbuild.util.mkdirIfAbsent(self.buildroot.make_chroot_path(destdir))
