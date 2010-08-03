# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Jan Vcelak
# Copyright (C) 2010 Jan Vcelak <jvcelak@redhat.com>

# python library imports
import os
import sys

# our imports
from mock.trace_decorator import decorate, traceLog, getLog
import mock.util

requires_api_version = "1.0"

# plugin entry point
decorate(traceLog())
def init(rootObj, conf):
    if mock.util.selinuxEnabled():
        getLog().info("selinux enabled")
        SELinux(rootObj, conf)
    else:
        getLog().info("selinux disabled")

# classes
class SELinux(object):
    """On SELinux enabled box, this plugin will pretend, that SELinux is disabled in build environment.

       - fake /proc/filesystems is mounted into build enviroment, excluding selinuxfs
       - option '--setopt=tsflags=nocontext' is appended to each 'yum' command
    """

    decorate(traceLog())
    def __init__(self, rootObj, conf):
        self.rootObj = rootObj
        self.conf = conf

        self.filesystems = os.path.join(conf["cachedir"], "filesystems")
        self.chrootFilesystems = rootObj.makeChrootPath("/proc/filesystems")

        rootObj.addHook("preinit", self._selinuxPreInitHook)
        rootObj.addHook("postbuild", self._selinuxPostBuildHook)
        rootObj.addHook("initfailed", self._selinuxPostBuildHook)
        if self._selinuxYumIsSetoptSupported():
            rootObj.addHook("preyum", self._selinuxPreYumHook)
            rootObj.addHook("postyum", self._selinuxPostYumHook)
        else:
            getLog().warn("selinux: 'yum' does not support '--setopt' option")

    decorate(traceLog())
    def _selinuxPreInitHook(self):
        host = open("/proc/filesystems")
        build = open(self.filesystems, "w")

        for line in host:
            if not "selinuxfs" in line:
                build.write(line)

        build.close()
        host.close()

        self.rootObj.mountCmds.append("mount -n --bind %s %s" % (self.filesystems, self.chrootFilesystems))
        self.rootObj.umountCmds.append("umount -n %s" % self.chrootFilesystems)

    decorate(traceLog())
    def _selinuxPostBuildHook(self):
        os.unlink(self.filesystems)

    decorate(traceLog())
    def _selinuxPreYumHook(self):
        self._originalUtilDo = mock.util.do
        mock.util.do = self._selinuxDoYum

    decorate(traceLog())
    def _selinuxPostYumHook(self):
        mock.util.do = self._originalUtilDo

    decorate(traceLog())
    def _selinuxDoYum(self, command, *args, **kargs):
        option = "--setopt=tsflags=nocontexts"

        if type(command) is list:
            command.append(option)
        elif type(command) is str:
            command += " %s" % option

        return self._originalUtilDo(command, *args, **kargs)

    decorate(traceLog())
    def _selinuxYumIsSetoptSupported(self):
        # ugly hack: discover, whether yum supports --setopt option
        sys.path.insert(0, '/usr/share/yum-cli')
        import cli
        supported = hasattr(cli.YumBaseCli, "_parseSetOpts")
        sys.path.pop(0)

        return supported
