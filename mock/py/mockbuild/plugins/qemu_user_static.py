# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Klaus Wenninger
# Copyright (C) 2018 Klaus Wenninger <kwenning@redhat.com>

# python library imports

# our imports

import os
import os.path
import shutil
from mockbuild.trace_decorator import traceLog
import mockbuild.util

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    QemuUserStatic(plugins, conf, buildroot)


class QemuUserStatic(object):
    """copies user-space-qemu into buildroot"""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.qemu_user_static = conf['binary_path']
        # Skip for boostrap chroot as this is anyway host-arch
        if buildroot.is_bootstrap or (self.qemu_user_static == None):
            return
        plugins.add_hook("preinit", self._copyQemuUserStatic)

    @traceLog()
    def _copyQemuUserStatic(self):
        destpath = self.buildroot.make_chroot_path(self.qemu_user_static)
        directory = os.path.dirname(destpath)

        try:
            os.stat(directory)
        except:
            os.makedirs(directory)

        try:
            os.stat(destpath)
        except:
            shutil.copy2(self.qemu_user_static, destpath)
