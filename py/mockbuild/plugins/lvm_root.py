import os
import lvm

from contextlib import contextmanager

from mockbuild import util, mounts

requires_api_version = "1.0"

@contextmanager
def volume_group(name, mode='r'):
    try:
        vg = lvm.vgOpen(name, mode)
        yield vg
    finally:
        vg.close()

def lv_exists(vg_name, lv_name):
    with volume_group(vg_name) as vg:
        try:
            vg.lvFromName(lv_name)
            return True
        except lvm.LibLVMError:
            return False

class SnapshotRegistry(object):
    def __init__(self, vg_name, snap_info):
        self.vg_name = vg_name
        self.snap_info = snap_info

    def get_current_snapshot(self):
        if os.path.exists(self.snap_info):
            with open(self.snap_info) as ac_record:
                name = ac_record.read().rstrip()
            if lv_exists(self.vg_name, name):
                return name

    def set_current_snapshot(self, name):
        if not lv_exists(self.vg_name, name):
            raise RuntimeError("Snapshot {0} doesn't exist".format(name))
        with open(self.snap_info, 'w') as ac_record:
            ac_record.write(name)

    def unset_current_snapshot(self):
        if os.path.exists(self.snap_info):
            os.remove(self.snap_info)

    def get_snapshot_origin(self, name):
        with volume_group(self.vg_name) as vg:
            lv = vg.lvFromName(name)
            return lv.getOrigin()

def init(plugins, lvm_conf, buildroot):
    vg_name = lvm_conf.get('volume_group')
    pool_name = buildroot.shared_root_name
    lv_name = '{0}-current'.format(pool_name)
    lv_path = os.path.join('/dev', vg_name, lv_name)
    fs_type = lvm_conf.get('filesystem', 'ext4')
    if not vg_name:
        raise RuntimeError("Volume group must be specified")

    snap_info = os.path.normpath(os.path.join(buildroot.basedir, '..',
                                 '.snapinfo-' + pool_name))
    registry = SnapshotRegistry(vg_name, snap_info)

    def create_base():
        size = lvm_conf.get('size', '2G')
        pool_id = vg_name + '/' + pool_name
        create_pool = ['lvcreate', '-T', pool_id, '-L', str(size)]
        util.do(create_pool, printOutput=True)
        create_lv = ['lvcreate', '-T', pool_id, '-V', str(size), '-n', lv_name]
        util.do(create_lv, printOutput=True)
        mkfs = lvm_conf.get('mkfs_command', 'mkfs.' + fs_type)
        mkfs_args = lvm_conf.get('mkfs_args', [])
        util.do([mkfs, lv_path] + mkfs_args)

    lv_mounts = []
    def mount_root():
        if not os.path.exists(lv_path):
            create_base()
        lv_mounts.append(mounts.FileSystemMountPoint(buildroot.make_chroot_path(),
                                                     fs_type, lv_path))
        lv_mounts[0].mount()

    def umount_root():
        for mount in lv_mounts:
            mount.umount()

    def make_snapshot(snapshot_name):
        lvcreate = ['lvcreate', '-s', vg_name + '/' + lv_name, '-n', snapshot_name]
        util.do(lvcreate, printOutput=True)
        registry.set_current_snapshot(snapshot_name)

    def rollback():
        snapshot_name = registry.get_current_snapshot()
        if snapshot_name:
            lvremove = ['lvremove', '-f', vg_name + '/' + lv_name]
            util.do(lvremove, printOutput=True)
            lvrename = ['lvrename', vg_name, snapshot_name, lv_name]
            util.do(lvrename, printOutput=True)
            lvchange = ['lvchange', vg_name + '/' + lv_name,
                        '-a', 'y', '-k', 'n', '-K']
            util.do(lvchange, printOutput=True)
            make_snapshot(snapshot_name)

    def rollback_to(name):
        registry.set_current_snapshot(name)
        rollback()

    def postinit():
        if not buildroot.chroot_was_initialized:
            snapshot_name = '{0}-postinit'.format(pool_name)
            make_snapshot(snapshot_name)
            registry.set_current_snapshot(snapshot_name)

    def scrub_root(what):
        if what in ('lvm', 'all'):
            registry.unset_current_snapshot()
            util.do(['lvremove', '-f', vg_name + '/' + pool_name],
                    printOutput=True)

    plugins.add_hook('mount_root', mount_root)
    plugins.add_hook('umount_root', umount_root)
    plugins.add_hook('postclean', rollback)
    plugins.add_hook('postinit', postinit)
    plugins.add_hook('scrub', scrub_root)
    plugins.add_hook('make_snapshot', make_snapshot)
    plugins.add_hook('rollback_to', rollback_to)
