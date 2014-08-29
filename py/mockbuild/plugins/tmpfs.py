# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import os

# our imports
from mockbuild.trace_decorator import traceLog, getLog
import mockbuild.util

requires_api_version = "1.0"

# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    system_ram_bytes = os.sysconf(os.sysconf_names['SC_PAGE_SIZE']) * os.sysconf(os.sysconf_names['SC_PHYS_PAGES'])
    system_ram_mb = system_ram_bytes / (1024 * 1024)
    if system_ram_mb > conf['required_ram_mb']:
        Tmpfs(plugins, conf, buildroot)
    else:
        getLog().warning("Tmpfs plugin disabled. "
            "System does not have the required amount of RAM to enable the tmpfs plugin. "
            "System has %sMB RAM, but the config specifies the minimum required is %sMB RAM. "
            %
            (system_ram_mb, conf['required_ram_mb']))

# classes
class Tmpfs(object):
    """Mounts a tmpfs on the chroot dir"""
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.main_config = buildroot.config
        self.state = buildroot.state
        self.conf = conf
        self.maxSize = self.conf['max_fs_size']
        self.mode = self.conf['mode']
        self.optArgs = ['-o', 'mode=%s' % self.mode]
        if self.maxSize:
            self.optArgs += ['-o', 'size=' + self.maxSize]
        plugins.add_hook("preinit", self._tmpfsMount)
        plugins.add_hook("preshell", self._tmpfsMount)
        plugins.add_hook("prechroot", self._tmpfsMount)
        plugins.add_hook("postshell", self._tmpfsUmount)
        plugins.add_hook("postbuild", self._tmpfsUmount)
        plugins.add_hook("postchroot", self._tmpfsUmount)
        plugins.add_hook("initfailed", self._tmpfsUmount)
        getLog().info("tmpfs initialized")

    @traceLog()
    def _tmpfsMount(self):
        getLog().info("mounting tmpfs at %s." % self.buildroot.make_chroot_path())
        mountCmd = ["mount", "-n", "-t", "tmpfs"] + self.optArgs + \
                   ["mock_chroot_tmpfs", self.buildroot.make_chroot_path()]
        mockbuild.util.do(mountCmd, shell=False)

    @traceLog()
    def _tmpfsUmount(self):
        force = False
        getLog().info("unmounting tmpfs.")
        umountCmd = ["umount", "-n", self.buildroot.make_chroot_path()]
        # since we're in a separate namespace, the mount will be cleaned up
        # on exit, so just warn if it fails here
        try:
            mockbuild.util.do(umountCmd, shell=False)
        except:
            getLog().warning("tmpfs-plugin: exception while umounting tmpfs! (cwd: %s)" % os.getcwd())
            force = True

        if force:
            # try umounting with force option
            umountCmd = ["umount", "-n", "-f", self.buildroot.make_chroot_path()]
            try:
                mockbuild.util.do(umountCmd, shell=False)
            except:
                getLog().warning("tmpfs-plugin: exception while force umounting tmpfs! (cwd: %s)" % os.getcwd())
