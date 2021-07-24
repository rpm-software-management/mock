# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import grp
import os
import os.path

from . import file_util
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
            if self.mountpath.rstrip('/') in [x.split()[1] for x in f]:
                return True
        return False

    def __repr__(self):
        return "<mockbuild.mounts.MountPoint object [mountsource: {0}, mountpath: {1}]>".format(
            self.mountsource, self.mountpath)


class FileSystemMountPoint(MountPoint):
    '''class for managing filesystem mounts in the chroot'''
    @traceLog()
    def __init__(self, path, filetype=None, device=None, options=None):
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

    @traceLog()
    def mount(self):
        if self.mounted:
            return None

        file_util.mkdirIfAbsent(self.path)
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
            return None
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
    def __init__(self, srcpath, bindpath, recursive=False, options=None):
        MountPoint.__init__(self, mountsource=srcpath, mountpath=bindpath)
        self.srcpath = srcpath
        self.bindpath = bindpath
        self.recursive = recursive
        self.options = options
        self.mounted = self.ismounted()

    @traceLog()
    def mount(self):
        if self.mounted:
            return None
        if os.path.isdir(self.srcpath):
            file_util.mkdirIfAbsent(self.bindpath)
        elif not os.path.exists(self.bindpath):
            normbindpath = os.path.normpath(self.bindpath)
            file_util.mkdirIfAbsent(os.path.dirname(normbindpath))
            file_util.touch(self.bindpath)
        bind_option = 'rbind' if self.recursive else 'bind'
        util.do(['/bin/mount', '-n', '-o', bind_option, self.srcpath,
                 self.bindpath])
        self.mounted = True
        # Remount the new bind-mount to set specified options (rhbz#1584443).
        # Userspace must implement this as separate system calls anyway.
        if self.options:
            options = ','.join(['remount', self.options, bind_option])
            util.do(['/bin/mount', '-n', '-o', options, "--target",
                     self.bindpath])
        return True

    @traceLog()
    def umount(self):
        if not self.mounted:
            return None
        cmd = ['/bin/umount', '-n']
        if self.recursive:
            # The mount is busy because of the submounts - a lazy unmount
            # implies a recursive unmount, so takes care of that.
            # (-R also works, but is implemented in userspace, and thus racy)
            cmd += ['-l']
        cmd.append(self.bindpath)
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
        self.essential_mounts = [] # /proc, /sys ... normally managed by systemd
        self.managed_mounts = []  # mounts owned by mock
        self.user_mounts = []  # mounts injected by user

        # Instead of mounting a fresh procfs and sysfs, we bind mount /proc
        # and /sys. This avoids problems with kernel restrictions if running
        # within a user namespace, and is pretty much identical otherwise.
        # The bind mounts additionally need to be recursive, because the
        # kernel forbids mounts that might reveal parts of the filesystem
        # that a container runtime overmounted to hide from the container
        # (rhbz#1745048).
        for mount in ['proc', 'sys']:
            mount_point = "/" + mount
            device = 'mock_hide_{}fs_from_host'.format(mount)
            host_path = rootObj.make_chroot_path(mount_point)

            self.essential_mounts += [
                # The recursive mount point needs to be later lazy umounted and
                # it would affect hosts's counterpart sub-mounts as well.  To
                # avoid this, we need to make the mount point and parent mount
                # point private in unshare()d namespace.  But since the parent
                # mount point of /sys and /proc so far was plain '/' mount (and
                # we need to keep that one shared, to keep LVM/tmpfs features
                # working) we crate a new parent mount for the final mountpoint
                # on the same path.  So the mount graph looks like:
                #   / (shared) -> /sys (private) -> /sys (recursive, private)
                #
                # Acknowledgement, IOW: We mount on host_path twice and it is
                # expected.  This is because when you umount 'rprivate' mount
                # then parent mount point is notified .. so first we mount tmpfs
                # stub which we actually never use -- but is private -- and only
                # then we mount above the actual mount point.  This prevents
                # from umount events to propagate to host from chroot.
                FileSystemMountPoint(filetype='tmpfs',
                                     device=device,
                                     path=host_path,
                                     options="rprivate"),
                BindMountPoint(srcpath=mount_point,
                               bindpath=host_path,
                               recursive=True,
                               options="nodev,noexec,nosuid,readonly,rprivate"),
            ]

        if rootObj.config['internal_dev_setup']:
            self.essential_mounts.append(
                FileSystemMountPoint(
                    filetype='tmpfs',
                    device='mock_chroot_shmfs',
                    path=rootObj.make_chroot_path('/dev/shm')
                )
            )
            opts = 'gid=%d,mode=0620,ptmxmode=0666' % grp.getgrnam('tty').gr_gid
            if util.cmpKernelVer(os.uname()[2], '2.6.29') >= 0:
                opts += ',newinstance'
                self.essential_mounts.append(
                    FileSystemMountPoint(
                        filetype='devpts',
                        device='mock_chroot_devpts',
                        path=rootObj.make_chroot_path('/dev/pts'),
                        options=opts
                    )
                )
        self.essential_mounted = all(m.ismounted() for m in self.essential_mounts)

    @traceLog()
    def add(self, mount):
        self.managed_mounts.append(mount)

    @traceLog()
    def add_device_bindmount(self, path):
        mount = BindMountPoint(path,
                               self.rootObj.make_chroot_path(path),
                               options="noexec,nosuid,readonly")
        self.essential_mounts.append(mount)

    @traceLog()
    def add_user_mount(self, mount):
        self.user_mounts.append(mount)

    @traceLog()
    def mountall_essential(self):
        self.essential_mounted = True
        for m in self.essential_mounts:
            m.mount()

    @traceLog()
    def mountall_managed(self):
        if not util.USE_NSPAWN:
            self.mountall_essential()
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
        if self.essential_mounted:
            self.umountall_essential()

    @traceLog()
    def umountall_essential(self):
        for m in reversed(self.essential_mounts):
            m.umount()
        self.essential_mounted = False

    @traceLog()
    def get_mountpoints(self):
        # including essentials (no matter if we use nspawn)
        # this is used to exclude path in archiving etc. and we want to do that for essentials too
        return [m.mountpath for m in self.essential_mounts + self.managed_mounts + self.user_mounts]

    def __repr__(self):
        return "<mockbuild.mounts.Mounts object managed: {0}, user: {1}>".format(repr(self.managed_mounts),
                                                                                 repr(self.user_mounts))
