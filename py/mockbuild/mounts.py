# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import grp
import os
import os.path

from . import exception
from . import util
from .trace_decorator import traceLog


class MountPoint(object):
    '''base class for mounts'''
    @traceLog()
    def __init__(self, mountsource, mountpath):
        self.mountpath = mountpath
        self.mountsource = mountsource

    @traceLog()
    def ismounted(self):
        with open('/proc/mounts') as f:
            if self.mountpath in [x.split()[1] for x in f]:
                return True
        return False

    def __repr__(self):
        return "<mockbuild.mounts.MountPoint object [mountsource: {0}, mountpath: {1}]>".format(
            self.mountsource, self.mountpath)


class FileSystemMountPoint(MountPoint):
    '''class for managing filesystem mounts in the chroot'''
    @traceLog()
    def __init__(self, path, filetype=None, device=None, options=None, keep_mounted=False):
        if not path:
            raise RuntimeError("no path specified for mountpoint")
        if not filetype:
            raise RuntimeError("no filetype specified for mountpoint")
        if filetype in ('pts', 'proc', 'sys', 'sysfs', 'tmpfs', 'devpts'):
            device = filetype
        if not device:
            raise RuntimeError("no device file specified for mountpoint")

        MountPoint.__init__(self, mountsource=device, mountpath=path)
        self.device = device
        self.path = path
        self.filetype = filetype
        self.options = options
        self.mounted = self.ismounted()
        self.keep_mounted = keep_mounted

    @traceLog()
    def mount(self):
        if self.mounted:
            return

        util.mkdirIfAbsent(self.path)
        cmd = ['/bin/mount', '-n', '-t', self.filetype]
        if self.options:
            cmd += ['-o', self.options]
        cmd += [self.device, self.path]
        util.do(cmd)
        self.mounted = True
        return True

    @traceLog()
    # pylint: disable=unused-argument
    def umount(self, force=False, nowarn=False):
        if not self.mounted:
            return
        if self.keep_mounted and not force:
            return
        cmd = ['/bin/umount', '-n', '-l', self.path]
        try:
            util.do(cmd)
        except exception.Error:
            return False
        self.mounted = False
        return True

    def __repr__(self):
        return ("<mockbuild.mounts.FileSystemMountPoint object [device: {0}, path: {1}, filetype: {2}, options: {3}, "
                "mounted: {4}]>".format(
                    self.device, self.path, self.filetype, self.options, self.mounted))


class BindMountPoint(MountPoint):
    '''class for managing bind-mounts in the chroot'''
    @traceLog()
    def __init__(self, srcpath, bindpath):
        MountPoint.__init__(self, mountsource=srcpath, mountpath=bindpath)
        self.srcpath = srcpath
        self.bindpath = bindpath
        self.mounted = self.ismounted()

    @traceLog()
    def mount(self):
        if not self.mounted:
            util.mkdirIfAbsent(self.bindpath)
            cmd = ['/bin/mount', '-n', '--bind', self.srcpath, self.bindpath]
            util.do(cmd)
        self.mounted = True
        return True

    @traceLog()
    def umount(self):
        if not self.mounted:
            return
        cmd = ['/bin/umount', '-n', self.bindpath]
        try:
            util.do(cmd)
        except exception.Error:
            return False
        self.mounted = False
        return True

    def __repr__(self):
        return "<mockbuild.mounts.BindMountPoint object [src: {0}, bindpath: {1}, mounted: {2}]>".format(
            self.srcpath, self.bindpath, self.mounted)

class Mounts(object):
    '''class to manage all mountpoints'''
    @traceLog()
    def __init__(self, rootObj):
        self.rootObj = rootObj
        self.managed_mounts = []  # mounts owned by mock
        self.user_mounts = []  # mounts injected by user
        if not util.USE_NSPAWN:
            self.managed_mounts = [
                FileSystemMountPoint(filetype='proc',
                                     device='mock_chroot_proc',
                                     path=rootObj.make_chroot_path('/proc')),
                FileSystemMountPoint(filetype='sysfs',
                                     device='mock_chroot_sys',
                                     path=rootObj.make_chroot_path('/sys')),
            ]
            if rootObj.config['internal_dev_setup']:
                self.managed_mounts.append(
                    FileSystemMountPoint(
                        filetype='tmpfs',
                        device='mock_chroot_shmfs',
                        path=rootObj.make_chroot_path('/dev/shm')
                    )
                )
                opts = 'gid=%d,mode=0620,ptmxmode=0666' % grp.getgrnam('tty').gr_gid
                if util.cmpKernelVer(os.uname()[2], '2.6.29') >= 0:
                    opts += ',newinstance'
                    self.managed_mounts.append(
                        FileSystemMountPoint(
                            filetype='devpts',
                            device='mock_chroot_devpts',
                            path=rootObj.make_chroot_path('/dev/pts'),
                            options=opts
                        )
                    )

    @traceLog()
    def add(self, mount):
        self.managed_mounts.append(mount)

    @traceLog()
    def add_user_mount(self, mount):
        self.user_mounts.append(mount)

    @traceLog()
    def mountall_managed(self):
        for m in self.managed_mounts:
            m.mount()

    @traceLog()
    def mountall_user(self):
        for m in self.user_mounts:
            m.mount()

    @traceLog()
    # pylint: disable=unused-argument
    def umountall(self, force=False, nowarn=False):
        failed_old = 1
        failed_new = 0
        while (failed_new != failed_old):
            # there can be deps, we will try to umount everything several times
            # as long as in every loop at least one umount succeed.
            failed_old = failed_new
            failed_new = 0
            for m in reversed(self.managed_mounts + self.user_mounts):
                if m.umount() is False:
                    failed_new += 1

    @traceLog()
    def get_mountpoints(self):
        return [m.mountpath for m in self.managed_mounts + self.user_mounts]

    def __repr__(self):
        return "<mockbuild.mounts.Mounts object managed: {0}, user: {1}>".format(repr(self.managed_mounts),
                                                                                 repr(self.user_mounts))
