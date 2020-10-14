# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports

# our imports

import os.path
from mockbuild.mounts import BindMountPoint
from mockbuild.trace_decorator import traceLog
from mockbuild import file_util

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    BindMount(plugins, conf, buildroot)


class BindMount(object):
    """bind mount dirs from host into chroot"""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.bind_opts = conf
        # Skip mounting user-specified mounts if we're in the boostrap chroot
        if buildroot.is_bootstrap:
            return
        plugins.add_hook("postinit", self._bindMountCreateDirs)
        for srcdir, destdir in self.bind_opts['dirs']:
            buildroot.mounts.add_user_mount(
                BindMountPoint(
                    srcpath=srcdir,
                    bindpath=buildroot.make_chroot_path(destdir)
                )
            )

    @traceLog()
    def _bindMountCreateDirs(self):
        for srcdir, destdir in self.bind_opts['dirs']:
            if os.path.isdir(srcdir):
                file_util.mkdirIfAbsent(srcdir)
                file_util.mkdirIfAbsent(self.buildroot.make_chroot_path(destdir))
            else:
                file_util.touch(self.buildroot.make_chroot_path(destdir))
