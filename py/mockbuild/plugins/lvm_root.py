import os
import lvm

from mockbuild import util, mounts

requires_api_version = "1.0"

def create_logical_volume(vg, lv_name, lv_path, fs_type, lvm_conf):
    size = lvm_conf.get('size', 2*(1024**3))
    mkfs = lvm_conf.get('mkfs_command', 'mkfs.' + fs_type)
    mkfs_args = lvm_conf.get('mkfs_args', [])
    lv = vg.createLvLinear(lv_name, size)
    util.do([mkfs, lv_path] + mkfs_args)
    return lv

def init(plugins, lvm_conf, buildroot):
    vg_name = lvm_conf.get('volume_group')
    lv_name = buildroot.shared_root_name
    lv_path = os.path.join('/dev', vg_name, lv_name)
    fs_type = lvm_conf.get('filesystem', 'ext4')
    if not vg_name:
        raise RuntimeError("Volume group must be specified")

    vg = lvm.vgOpen(vg_name, 'w')

    try:
        lv = vg.lvFromName(lv_name)
    except lvm.LibLVMError:
        lv = create_logical_volume(vg, lv_name, lv_path, fs_type, lvm_conf)
    finally:
        vg.close()

    mount = mounts.FileSystemMountPoint(buildroot.make_chroot_path(), fs_type,
                                        lv_path)

    def mount_root():
        mount.mount()
    def umount_root():
        mount.umount()
    def rollback():
        #TODO
        pass

    plugins.add_hook('mount_root', mount_root)
    plugins.add_hook('umount_root', umount_root)
    plugins.add_hook('clean', rollback)
