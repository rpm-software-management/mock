# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Jan Vcelak
# Copyright (C) 2010 Jan Vcelak <jvcelak@redhat.com>

# python library imports
import atexit
import os
import stat
import sys
import tempfile

# our imports
from mockbuild.mounts import BindMountPoint
from mockbuild.trace_decorator import getLog, traceLog
import mockbuild.util

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    if mockbuild.util.selinuxEnabled() and not mockbuild.util.USE_NSPAWN:
        getLog().info("selinux enabled")
        SELinux(plugins, conf, buildroot)
    else:
        getLog().info("selinux disabled")


class SELinux(object):
    """On SELinux enabled box, this plugin will pretend, that SELinux is disabled in build environment.

       - fake /proc/filesystems is mounted into build environment, excluding selinuxfs
       - option '--setopt=tsflags=nocontext' is appended to each 'yum' command
    """
    # pylint: disable=too-few-public-methods

    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self._originalUtilDo = mockbuild.util.do

        self.buildroot = buildroot
        self.config = buildroot.config
        self.state = buildroot.state
        self.conf = conf

        self.filesystems = self._selinuxCreateFauxFilesystems()
        self.chrootFilesystems = buildroot.make_chroot_path("/proc/filesystems")

        atexit.register(self._selinuxAtExit)

        self.buildroot.mounts.add(BindMountPoint(srcpath=self.filesystems, bindpath=self.chrootFilesystems))

        if self._selinuxYumIsSetoptSupported():
            plugins.add_hook("preyum", self._selinuxPreYumHook)
            plugins.add_hook("postyum", self._selinuxPostYumHook)
        else:
            getLog().warning("selinux: 'yum' does not support '--setopt' option")

    @traceLog()
    def _selinuxCreateFauxFilesystems(self):
        (fd, path) = tempfile.mkstemp(prefix="mock-selinux-plugin.")
        with os.fdopen(fd, 'w') as out:
            with open("/proc/filesystems") as host:
                for line in host:
                    if "selinuxfs" not in line:
                        out.write(line)

        os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        return path

    def _selinuxAtExit(self):
        if os.path.exists(self.filesystems):
            try:
                os.unlink(self.filesystems)
            except OSError as e:
                getLog().warning("unable to delete selinux filesystems (%s): %s", self.filesystems, e)
                pass

    @traceLog()
    def _selinuxPreYumHook(self):
        mockbuild.util.do = self._selinuxDoYum

    @traceLog()
    def _selinuxPostYumHook(self):
        mockbuild.util.do = self._originalUtilDo

    @traceLog()
    def _selinuxDoYum(self, command, *args, **kargs):
        option = "--setopt=tsflags=nocontexts"

        if type(command) is list:
            if command[0].startswith(self.buildroot.pkg_manager.command):
                command.append(option)
        elif type(command) is str:
            if command.startswith(self.buildroot.pkg_manager.command):
                command += " %s" % option

        return self._originalUtilDo(command, *args, **kargs)

    @traceLog()
    def _selinuxYumIsSetoptSupported(self):
        try:
            # ugly hack: discover, whether yum supports --setopt option
            sys.path.insert(0, '/usr/share/yum-cli')
            import cli
            supported = hasattr(cli.YumBaseCli, "_parseSetOpts")
            sys.path.pop(0)
            return supported
        except SyntaxError:
            # We're on python 3, assuming yum is new enough
            return True
