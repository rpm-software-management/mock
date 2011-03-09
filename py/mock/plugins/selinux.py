# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Jan Vcelak
# Copyright (C) 2010 Jan Vcelak <jvcelak@redhat.com>

# python library imports
import os
import sys
import tempfile
import stat
import atexit

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

        self.filesystems = self._selinuxCreateFauxFilesystems()
        self.chrootFilesystems = rootObj.makeChrootPath("/proc/filesystems")

        atexit.register(self._selinuxAtExit)

        self.rootObj.mountCmds.append("mount -n --bind %s %s" % (self.filesystems, self.chrootFilesystems))
        self.rootObj.umountCmds.append("umount -n %s" % self.chrootFilesystems)

        if self._selinuxYumIsSetoptSupported():
            rootObj.addHook("preyum", self._selinuxPreYumHook)
            rootObj.addHook("postyum", self._selinuxPostYumHook)
        else:
            getLog().warn("selinux: 'yum' does not support '--setopt' option")

    decorate(traceLog())
    def _selinuxCreateFauxFilesystems(self):
        (fd, path) = tempfile.mkstemp(prefix="mock-selinux-plugin.")

        with open("/proc/filesystems") as host:
            for line in host:
                if not "selinuxfs" in line:
                    os.write(fd, line)

        os.close(fd)
        os.chmod(path, stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH)

        return path

    decorate(traceLog())
    def _selinuxAtExit(self):
        try:
            os.unlink(self.filesystems)
        except OSError, e:
            getLog().warning("unable to delete selinux filesystems (%s): %s" % (self._filesystems, e))
            pass

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
            if command[0] == self.rootObj.yum_path:
                command.append(option)
        elif type(command) is str:
            if command.startswith(self.rootObj.yum_path):
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
