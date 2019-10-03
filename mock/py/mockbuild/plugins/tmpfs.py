# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import os

# our imports
from mockbuild.trace_decorator import getLog, traceLog
import mockbuild.util

requires_api_version = "1.1"


# plugin entry point
@traceLog()
def init(plugins, conf, buildroot):
    system_ram_bytes = os.sysconf(os.sysconf_names['SC_PAGE_SIZE']) * os.sysconf(os.sysconf_names['SC_PHYS_PAGES'])
    system_ram_mb = system_ram_bytes / (1024 * 1024)
    if system_ram_mb > conf['required_ram_mb']:
        Tmpfs(plugins, conf, buildroot)
    else:
        getLog().warning(
            "Tmpfs plugin disabled. "
            "System does not have the required amount of RAM to enable the tmpfs plugin. "
            "System has %sMB RAM, but the config specifies the minimum required is %sMB RAM. ",
            system_ram_mb, conf['required_ram_mb'])


class Tmpfs(object):
    """Mounts a tmpfs on the chroot dir"""
    # pylint: disable=too-few-public-methods
    @traceLog()
    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.main_config = buildroot.config
        self.state = buildroot.state
        self.conf = conf
        self.maxSize = self.conf['max_fs_size']
        self.mode = self.conf['mode']
        self.optArgs = ['-o', 'mode=%s' % self.mode]
        self.optArgs += ['-o', 'nr_inodes=0']
        if self.maxSize:
            self.optArgs += ['-o', 'size=' + self.maxSize]
        plugins.add_hook("mount_root", self._tmpfsMount)
        plugins.add_hook("postumount", self._tmpfsPostUmount)
        plugins.add_hook("umount_root", self._tmpfsUmount)
        if not os.path.ismount(self.buildroot.make_chroot_path()):
            self.mounted = False
        else:
            self.mounted = True
        getLog().info("tmpfs initialized")

    @traceLog()
    def _tmpfsMount(self):
        getLog().info("mounting tmpfs at %s.", self.buildroot.make_chroot_path())

        if not self.mounted:
            mountCmd = ["mount", "-n", "-t", "tmpfs"] + self.optArgs + \
                       ["mock_chroot_tmpfs", self.buildroot.make_chroot_path()]
            mockbuild.util.do(mountCmd, shell=False)
        else:
            getLog().info("reusing tmpfs at %s.", self.buildroot.make_chroot_path())
        self.mounted = True

    @traceLog()
    def _tmpfsPostUmount(self):
        if "keep_mounted" in self.conf and self.conf["keep_mounted"]:
            self.mounted = False
        else:
            self._tmpfsUmount()

    @traceLog()
    def _tmpfsUmount(self):
        if not self.mounted:
            return
        force = False
        getLog().info("unmounting tmpfs.")
        umountCmd = ["umount", "-n", self.buildroot.make_chroot_path()]
        # since we're in a separate namespace, the mount will be cleaned up
        # on exit, so just warn if it fails here
        try:
            mockbuild.util.do(umountCmd, shell=False)
        # pylint: disable=bare-except
        except:
            getLog().warning("tmpfs-plugin: exception while umounting tmpfs! (cwd: %s)", mockbuild.util.pretty_getcwd())
            force = True

        if force:
            # try umounting with force option
            umountCmd = ["umount", "-R", "-n", "-f", self.buildroot.make_chroot_path()]
            try:
                mockbuild.util.do(umountCmd, shell=False)
            # pylint: disable=bare-except
            except:
                getLog().warning(
                    "tmpfs-plugin: exception while force umounting tmpfs! (cwd: %s)", mockbuild.util.pretty_getcwd())
        self.mounted = False
