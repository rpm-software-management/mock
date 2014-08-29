import os
import lvm
import fcntl
import errno
import time

from contextlib import contextmanager
from textwrap import dedent

from mockbuild import util, mounts
from mockbuild.exception import LvmError, LvmLocked

requires_api_version = "1.0"

@contextmanager
def restored_ipc_ns():
    mock_ns = os.open('/proc/self/ns/ipc', os.O_RDONLY)
    util.restore_ipc_ns()
    try:
        yield
    finally:
        util.setns(mock_ns, util.CLONE_NEWIPC)
        os.close(mock_ns)

@contextmanager
def volume_group(name, mode='r'):
    with restored_ipc_ns():
        try:
            vg = lvm.vgOpen(name, mode)
            yield vg
        finally:
            vg.close()

def lvm_do(*args, **kwargs):
    with restored_ipc_ns():
        util.do(*args, **kwargs)

def current_mounts():
    with open("/proc/mounts") as proc_mounts:
        mount_lines = proc_mounts.read().strip().split('\n')
        for line in mount_lines:
            src, target = [os.path.realpath(x) for x in line.split()[:2]]
            yield src, target

class LvmPlugin(object):
    postinit_name = 'postinit'
    prefix = 'mock'

    def __init__(self, plugins, lvm_conf, buildroot):
        if not util.original_ipc_ns or not util.have_setns:
            raise LvmError("Cannot initialize setns support, which is "
                               "needed by LVM plugin")
        self.buildroot = buildroot
        self.lvm_conf = lvm_conf
        self.vg_name = lvm_conf.get('volume_group')
        self.conf_id = '{0}.{1}'.format(self.prefix, buildroot.shared_root_name)
        self.pool_name = lvm_conf.get('pool_name', self.conf_id)
        self.ext = self.buildroot.config.get('unique-ext', 'head')
        self.head_lv = '+{0}.{1}'.format(self.conf_id, self.ext)
        self.fs_type = lvm_conf.get('filesystem', 'ext4')
        self.root_path = os.path.realpath(self.buildroot.make_chroot_path())
        if not self.vg_name:
            raise LvmError("Volume group must be specified")

        snapinfo_name = '.snapinfo-{0}.{1}'.format(self.conf_id, self.ext)
        basepath = buildroot.mockdir
        self.snap_info = os.path.normpath(os.path.join(basepath, snapinfo_name))
        lock_name = '.lvm_lock-{0}'.format(self.conf_id)
        self.lock_path = os.path.normpath(os.path.join(basepath, lock_name))
        self.lock_file = open(self.lock_path, 'a+')
        self.mount = None

        prefix = 'hook_'
        for member in dir(self):
            if member.startswith(prefix):
                method = getattr(self, member)
                hook_name = member[len(prefix):]
                plugins.add_hook(hook_name, method)

    def prefix_name(self, name=''):
        return self.conf_id + '.' + name

    def remove_prefix(self, name):
        return name.replace(self.prefix_name(''), '')

    def get_lv_path(self, lv_name=None):
        name = lv_name or self.head_lv
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
        name = lv_name or self.head_lv
        return self._lv_predicate(name, lambda lv: True)

    def _open_lv_is_our(self, lv):
        return (lv.getAttr()[0] == 'V' and
                lv.getProperty('pool_lv')[0] == self.pool_name and
                lv.getName().replace('+', '').startswith(self.prefix_name()))

    def lv_is_our(self, name):
        return self._lv_predicate(name, self._open_lv_is_our)

    def get_current_snapshot(self):
        if os.path.exists(self.snap_info):
            with open(self.snap_info) as ac_record:
                name = ac_record.read().rstrip()
            if self.lv_is_our(name):
                return name
        postinit = self.prefix_name(self.postinit_name)
        if self.lv_is_our(postinit):
            # We don't have a registered snapshot, but postinit exists, so use it
            self.set_current_snapshot(postinit)
            return postinit

    def set_current_snapshot(self, name):
        if not self.lv_is_our(name):
            raise LvmError("Snapshot {0} doesn't exist".format(self.remove_prefix(name)))
        with open(self.snap_info, 'w') as ac_record:
            ac_record.write(name)

    def unset_current_snapshot(self):
        if os.path.exists(self.snap_info):
            os.remove(self.snap_info)

    def make_snapshot(self, name):
        if self.lv_exists(name):
            raise LvmError("Snapshot {name} already exists"\
                           .format(name=self.remove_prefix(name)))
        lvcreate = ['lvcreate', '-s', self.vg_name + '/' + self.head_lv, '-n', name]
        lvm_do(lvcreate)
        self.set_current_snapshot(name)

    def delete_head(self):
        self.umount()
        if self.lv_exists():
            lvm_do(['lvremove', '-f', self.vg_name + '/' + self.head_lv])

    def hook_make_snapshot(self, name):
        lv_name = self.prefix_name(name)
        self.make_snapshot(lv_name)
        self.buildroot.root_log.info("created {name} snapshot".format(name=name))

    def hook_postclean(self):
        self.delete_head()

    def hook_rollback_to(self, name):
        name = self.prefix_name(name)
        self.set_current_snapshot(name)
        self.delete_head()

    def create_pool(self):
        size = self.lvm_conf['size']
        pool_id = self.vg_name + '/' + self.pool_name
        create_pool = ['lvcreate', '-T', pool_id, '-L', str(size)]
        if 'poolmetadatasize' in self.lvm_conf:
            create_pool += ['--poolmetadatasize', self.lvm_conf['poolmetadatasize']]
        lvm_do(create_pool)
        self.buildroot.root_log.info("created LVM cache thinpool of size {size}"\
                                     .format(size=size))
    def create_base(self):
        pool_id = self.vg_name + '/' + self.pool_name
        size = self.lvm_conf['size']
        lvm_do(['lvcreate', '-T', pool_id, '-V', str(size), '-n', self.head_lv])
        mkfs = self.lvm_conf.get('mkfs_command', 'mkfs.' + self.fs_type)
        mkfs_args = self.lvm_conf.get('mkfs_args', [])
        util.do([mkfs, self.get_lv_path()] + mkfs_args)

    def force_umount_root(self):
        self.buildroot.root_log.warning("Forcibly unmounting root volume")
        util.do(['umount', '-l', self.root_path], env=self.buildroot.env)

    def prepare_mount(self):
        mount_options = self.lvm_conf.get('mount_options')
        try:
            lv_path = self.get_lv_path()
            for src, target in current_mounts():
                if target == self.root_path:
                    if src != os.path.realpath(lv_path):
                        self.force_umount_root()
            self.mount = mounts.FileSystemMountPoint(self.root_path, self.fs_type,
                                                     lv_path, options=mount_options)
        except lvm.LibLVMError:
            pass

    def umount(self):
        if not self.mount:
            self.prepare_mount()
        if self.mount:
            self.mount.umount()

    def create_head(self, snapshot_name):
        lvm_do(['lvcreate', '-s', self.vg_name + '/' + snapshot_name,
                '-n', self.head_lv, '--setactivationskip', 'n'])
        self.buildroot.root_log.info("rolled back to {name} snapshot"\
                                     .format(name=self.remove_prefix(snapshot_name)))

    def lock(self, exclusive, block=False):
        lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        try:
            fcntl.lockf(self.lock_file.fileno(),
                        lock_type | (0 if block else fcntl.LOCK_NB))
        except IOError as e:
            if e.errno in (errno.EACCES, errno.EAGAIN):
                raise LvmLocked("LVM thinpool is locked by another process")
            raise

    def unlock(self):
        if self.lock_file:
            fcntl.lockf(self.lock_file.fileno(), fcntl.LOCK_UN)

    def hook_mount_root(self):
        waiting = False
        while not self.get_current_snapshot():
            try:
                self.lock(exclusive=True)
            except LvmLocked:
                if not waiting:
                    self.buildroot.root_log.info("Waiting for LVM init lock")
                    waiting = True
                time.sleep(1)
            else:
                # Locked as exclusive so only one mock initializes postinit snapshot
                if not self.lv_exists(self.pool_name):
                    self.create_pool()
                    self.create_base()
                    break
                elif not self.get_current_snapshot():
                    if self.lv_exists():
                        # We've got the exclusive lock but there's no postinit
                        # This means init failed and we need to start over
                        lvm_do(['lvremove', '-f', self.vg_name + '/' + self.head_lv])
                    self.create_base()
                    break
        else:
            self.lock(exclusive=False, block=True)

        if not self.lv_exists():
            self.create_head(self.get_current_snapshot())

        self.prepare_mount()
        self.mount.mount()

    def hook_umount_root(self):
        self.umount()

    def hook_postumount(self):
        if self.mount and self.lvm_conf.get('umount_root'):
            self.mount.umount()

    def hook_postinit(self):
        if not self.buildroot.chroot_was_initialized:
            snapshot_name = self.prefix_name(self.postinit_name)
            self.make_snapshot(snapshot_name)
            self.set_current_snapshot(snapshot_name)
            self.buildroot.root_log.info("created {name} snapshot"\
                    .format(name=self.postinit_name))
        # Relock as shared for following operations, noop if shared already
        self.lock(exclusive=False)

    def hook_scrub(self, what):
        self.lock(exclusive=True)
        if what not in ('lvm', 'all'):
            return
        with volume_group(self.vg_name) as vg:
            try:
                lvs = vg.listLVs()
                for lv in lvs:
                    if self._open_lv_is_our(lv):
                        for src, _ in current_mounts():
                            if src == os.path.realpath(lv.getProperty('lv_path')[0]):
                                util.do(['umount', '-l', src])
            except lvm.LibLVMError:
                pass
        self.unset_current_snapshot()
        lvm_do(['lvremove', '-f', self.vg_name + '/' + self.pool_name])
        self.buildroot.root_log.info("deleted LVM cache thinpool")

    def hook_list_snapshots(self):
        with volume_group(self.vg_name) as vg:
            current = self.get_current_snapshot()
            lvs = vg.listLVs()
            print('Snapshots for {0}:'.format(self.buildroot.shared_root_name))
            for lv in lvs:
                if self._open_lv_is_our(lv):
                    name = lv.getName()
                    if name == current:
                        print('* ' + self.remove_prefix(name))
                    elif name.startswith('+'):
                        pass
                    else:
                        print('  ' + self.remove_prefix(name))

    def hook_remove_snapshot(self, name):
        if name == self.postinit_name:
            raise LvmError(dedent("""\
                    Won't remove postinit snapshot. To remove all logical
                    volumes associated with this buildroot, use --scrub lvm"""))
        lv_name = self.prefix_name(name)
        if not self.lv_is_our(lv_name):
            raise LvmError("Snapshot {0} doesn't exist".format(name))
        self.umount()
        if lv_name == self.get_current_snapshot():
            self.set_current_snapshot(self.prefix_name(self.postinit_name))
        lvm_do(['lvremove', '-f', self.vg_name + '/' + lv_name])
        self.buildroot.root_log.info("deleted {name} snapshot".format(name=name))

def init(plugins, lvm_conf, buildroot):
    LvmPlugin(plugins, lvm_conf, buildroot)
