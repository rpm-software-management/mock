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

class LvmPlugin(object):
    def __init__(self, plugins, lvm_conf, buildroot):
        self.buildroot = buildroot
        self.lvm_conf = lvm_conf
        self.vg_name = lvm_conf.get('volume_group')
        self.pool_name = buildroot.shared_root_name
        self.lv_name = '{0}-current'.format(self.pool_name)
        self.fs_type = lvm_conf.get('filesystem', 'ext4')
        if not self.vg_name:
            raise RuntimeError("Volume group must be specified")

        self.snap_info = os.path.normpath(os.path.join(buildroot.basedir, '..',
                                     '.snapinfo-' + self.pool_name))
        self.mount = None

        prefix = 'hook_'
        for member in dir(self):
            if member.startswith(prefix):
                method = getattr(self, member)
                hook_name = member[len(prefix):]
                plugins.add_hook(hook_name, method)

    def prefix_name(self, name):
        return self.pool_name + '-' + name

    def get_lv_path(self, lv_name=None):
        name = lv_name or self.lv_name
        with volume_group(self.vg_name) as vg:
            lv = vg.lvFromName(name)
            return lv.getProperty('lv_path')[0]

    def _lv_predicate(self, name, predicate):
        with volume_group(self.vg_name) as vg:
            try:
                lv = vg.lvFromName(name)
                return predicate(lv)
            except lvm.LibLVMError:
                pass
        return False

    def lv_exists(self, lv_name=None):
        name = lv_name or self.lv_name
        return self._lv_predicate(name, lambda lv: True)

    def lv_is_our(self, name):
        predicate = lambda lv: lv.getProperty('pool_lv')[0] == self.pool_name
        return self._lv_predicate(name, predicate)

    def get_current_snapshot(self):
        if os.path.exists(self.snap_info):
            with open(self.snap_info) as ac_record:
                name = ac_record.read().rstrip()
            if self.lv_is_our(name):
                return name

    def set_current_snapshot(self, name):
        if not self.lv_is_our(name):
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

    def make_snapshot(self, name):
        lvcreate = ['lvcreate', '-s', self.vg_name + '/' + self.lv_name, '-n', name]
        util.do(lvcreate, printOutput=True)
        self.set_current_snapshot(name)

    def rollback(self):
        snapshot_name = self.get_current_snapshot()
        if snapshot_name:
            lvremove = ['lvremove', '-f', self.vg_name + '/' + self.lv_name]
            util.do(lvremove, printOutput=True)
            lvrename = ['lvrename', self.vg_name, snapshot_name, self.lv_name]
            util.do(lvrename, printOutput=True)
            lvchange = ['lvchange', self.vg_name + '/' + self.lv_name,
                        '-a', 'y', '-k', 'n', '-K']
            util.do(lvchange, printOutput=True)
            self.make_snapshot(snapshot_name)

    def hook_make_snapshot(self, name):
        name = self.prefix_name(name)
        self.make_snapshot(name)

    def hook_postclean(self):
        self.rollback()

    def hook_rollback_to(self, name):
        name = self.prefix_name(name)
        self.set_current_snapshot(name)
        self.rollback()

    def create_base(self):
        size = self.lvm_conf.get('size', '2G')
        pool_id = self.vg_name + '/' + self.pool_name
        create_pool = ['lvcreate', '-T', pool_id, '-L', str(size)]
        util.do(create_pool, printOutput=True)
        create_lv = ['lvcreate', '-T', pool_id, '-V', str(size), '-n', self.lv_name]
        util.do(create_lv, printOutput=True)
        mkfs = self.lvm_conf.get('mkfs_command', 'mkfs.' + self.fs_type)
        mkfs_args = self.lvm_conf.get('mkfs_args', [])
        util.do([mkfs, self.get_lv_path()] + mkfs_args)

    def hook_mount_root(self):
        if not self.lv_exists():
            self.create_base()
        mount_options = self.lvm_conf.get('mount_options')
        root_path = self.buildroot.make_chroot_path()
        self.mount = mounts.FileSystemMountPoint(root_path, self.fs_type,
                                                 self.get_lv_path(),
                                                 options=mount_options)
        self.mount.mount()

    def hook_umount_root(self):
        if self.mount:
            self.mount.umount()

    def hook_postinit(self):
        if not self.buildroot.chroot_was_initialized:
            snapshot_name = self.prefix_name('postinit')
            self.make_snapshot(snapshot_name)
            self.set_current_snapshot(snapshot_name)

    def hook_scrub(self, what):
        if what in ('lvm', 'all'):
            self.unset_current_snapshot()
            util.do(['lvremove', '-f', self.vg_name + '/' + self.pool_name],
                    printOutput=True)

def init(plugins, lvm_conf, buildroot):
    LvmPlugin(plugins, lvm_conf, buildroot)
