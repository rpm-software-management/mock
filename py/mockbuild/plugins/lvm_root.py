import os

from mockbuild import util, mounts

requires_api_version = "1.0"

def create_logical_volume(vg_name, lv_name, lv_path, fs_type, lvm_conf):
    size = lvm_conf.get('size', '2G')
    mkfs = lvm_conf.get('mkfs_command', 'mkfs.' + fs_type)
    mkfs_args = lvm_conf.get('mkfs_args', [])
    lvcreate = ['lvcreate', vg_name, '-n', lv_name, '-L', str(size)]
    util.do(lvcreate, printOutput=True)
    util.do([mkfs, lv_path] + mkfs_args)

def init(plugins, lvm_conf, buildroot):
    snapshot_size = lvm_conf.get('snapshot_size', '2G')
    vg_name = lvm_conf.get('volume_group')
    lv_name = buildroot.shared_root_name
    snapshot_name = '{0}-work'.format(lv_name)
    snapshot_path = os.path.join('/dev', vg_name, snapshot_name)
    lv_path = os.path.join('/dev', vg_name, lv_name)
    fs_type = lvm_conf.get('filesystem', 'ext4')
    if not vg_name:
        raise RuntimeError("Volume group must be specified")

    lv_mounts = []
    def mount_root():
        if not os.path.exists(lv_path):
            create_logical_volume(vg_name, lv_name, lv_path, fs_type, lvm_conf)
        path = snapshot_path if os.path.exists(snapshot_path) else lv_path
        lv_mounts.append(mounts.FileSystemMountPoint(buildroot.make_chroot_path(),
                                                  fs_type, path))
        lv_mounts[0].mount()

    def umount_root():
        for mount in lv_mounts:
            mount.umount()

    def make_snapshot():
        lvcreate = ['lvcreate', '-s', vg_name + '/' + lv_name, '-n', snapshot_name,
                    '-L', str(snapshot_size)]
        util.do(lvcreate, printOutput=True)

    def rollback():
        if os.path.exists(os.path.join('/dev', vg_name, snapshot_name)):
            util.do(['lvremove', '-f', vg_name + '/' + snapshot_name],
                    printOutput=True)
            make_snapshot()

    def postinit():
        if not buildroot.chroot_was_initialized:
            make_snapshot()
            buildroot._umount_all()
            lv_mounts[0].umount()
            lv_mounts[0] = mounts.FileSystemMountPoint(buildroot.make_chroot_path(),
                                                    fs_type, snapshot_path)
            lv_mounts[0].mount()
            buildroot.mounts.mountall()

    def scrub_root(what):
        if what in ('lvm', 'all'):
            if os.path.exists(snapshot_path):
                util.do(['lvremove', '-f', vg_name + '/' + snapshot_name],
                        printOutput=True)
            if os.path.exists(lv_path):
                util.do(['lvremove', '-f', vg_name + '/' + lv_name],
                        printOutput=True)

    plugins.add_hook('mount_root', mount_root)
    plugins.add_hook('umount_root', umount_root)
    plugins.add_hook('postclean', rollback)
    plugins.add_hook('postinit', postinit)
    plugins.add_hook('scrub', scrub_root)
