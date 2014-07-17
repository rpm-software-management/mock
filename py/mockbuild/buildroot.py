import os
import pwd
import grp
import fcntl
import stat

from mockbuild import util
from mockbuild import mounts
from mockbuild.exception import BuildRootLocked

class Buildroot(object):
    def __init__(self, config):
        self.config = config
        self.basedir = os.path.join(config['basedir'], config['root'])
        self.rootdir = os.path.join(self.basedir, 'root')
        self._lock_file = None
        self.selinux = (not self.config['plugin_conf']['selinux_enable']
                        and util.selinuxEnabled())

        self.env = config['environment']
        proxy_env = util.get_proxy_environment(config)
        self.env.update(proxy_env)
        os.environ.update(proxy_env)

        self.mounts = mounts.Mounts(self)

    def make_chroot_path(self, *paths):
        new_path = self.rootdir
        for path in paths:
            if path.startswith('/'):
                path = path[1:]
            new_path = os.path.join(new_path, path)
        return new_path

    def initialize(self):
        """
        Initialize the builroot to a point where it's possible to execute
        commands in chroot. If it was already initialized, just lock the shared
        lock.
        """
        util.mkdirIfAbsent(self.rootdir)
        try:
            self._lock_buildroot(exclusive=True)
            # If previous run didn't finish properly
            self._umount_residual()
            self._setup_dirs()
            self._setup_devices()
            self._setup_files()
            self.mounts.mountall()
        except BuildRootLocked:
            pass
        finally:
            self._lock_buildroot(exclusive=False)

    def _open_lock(self):
        self._lock_file = open(os.path.join(self.basedir, "buildroot.lock"), "a+")

    def _lock_buildroot(self, exclusive):
        lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        if not self._lock_file:
            self._open_lock()
        try:
            fcntl.lockf(self._lock_file.fileno(), lock_type | fcntl.LOCK_NB)
        except IOError:
            raise BuildRootLocked("Build root is locked by another process.")

    def _unlock_buildroot(self):
        if self._lock_file:
            self._lock_file.close()
        self._lock_file = None

    def _setup_dirs(self):
        #self.root_log.debug('create skeleton dirs')
        dirs = ['var/lib/rpm',
                'var/lib/yum',
                'var/lib/dbus',
                'var/log',
                'var/cache/yum',
                'etc/rpm',
                'tmp',
                'tmp/ccache',
                'var/tmp',
                #dnf?
                'etc/yum.repos.d',
                'etc/yum',
                'proc',
                'sys',
                ]
        dirs += self.config['extra_chroot_dirs']
        for item in dirs:
            util.mkdirIfAbsent(self.make_chroot_path(item))

    def _setup_devices(self):
        if self.config['internal_dev_setup']:
            util.rmtree(self.make_chroot_path("dev"), selinux=self.selinux)
            util.mkdirIfAbsent(self.make_chroot_path("dev", "pts"))
            util.mkdirIfAbsent(self.make_chroot_path("dev", "shm"))
            prevMask = os.umask(0000)
            devFiles = [
                (stat.S_IFCHR | 0666, os.makedev(1, 3), "dev/null"),
                (stat.S_IFCHR | 0666, os.makedev(1, 7), "dev/full"),
                (stat.S_IFCHR | 0666, os.makedev(1, 5), "dev/zero"),
                (stat.S_IFCHR | 0666, os.makedev(1, 8), "dev/random"),
                (stat.S_IFCHR | 0444, os.makedev(1, 9), "dev/urandom"),
                (stat.S_IFCHR | 0666, os.makedev(5, 0), "dev/tty"),
                (stat.S_IFCHR | 0600, os.makedev(5, 1), "dev/console"),
                (stat.S_IFCHR | 0666, os.makedev(5, 2), "dev/ptmx"),
                ]
            kver = os.uname()[2]
            #getLog().debug("kernel version == %s" % kver)
            for i in devFiles:
                # create node
                os.mknod(self.make_chroot_path(i[2]), i[0], i[1])
                # set context. (only necessary if host running selinux enabled.)
                # fails gracefully if chcon not installed.
                if self.selinux:
                    util.do(
                        ["chcon", "--reference=/" + i[2], self.make_chroot_path(i[2])],
                         raiseExc=0, shell=False, env=self.env)

            os.symlink("/proc/self/fd/0", self.make_chroot_path("dev/stdin"))
            os.symlink("/proc/self/fd/1", self.make_chroot_path("dev/stdout"))
            os.symlink("/proc/self/fd/2", self.make_chroot_path("dev/stderr"))

            if os.path.isfile(self.makeChrootPath('etc', 'mtab')):
                os.remove(self.makeChrootPath('etc', 'mtab'))
                os.symlink("/proc/self/mounts", self.makeChrootPath('etc', 'mtab'))

            os.chown(self.make_chroot_path('dev/tty'), pwd.getpwnam('root')[2], grp.getgrnam('tty')[2])
            os.chown(self.make_chroot_path('dev/ptmx'), pwd.getpwnam('root')[2], grp.getgrnam('tty')[2])

            # symlink /dev/fd in the chroot for everything except RHEL4
            if util.cmpKernelVer(kver, '2.6.9') > 0:
                os.symlink("/proc/self/fd", self.make_chroot_path("dev/fd"))

            os.umask(prevMask)

            if util.cmpKernelVer(kver, '2.6.18') >= 0:
                os.unlink(self.make_chroot_path('/dev/ptmx'))
            os.symlink("pts/ptmx", self.make_chroot_path('/dev/ptmx'))

    def _setup_files(self):
        #self.root_log.debug('touch required files')
        for item in [self.make_chroot_path('etc', 'fstab'),
                     self.make_chroot_path('var', 'log', 'yum.log')]:
            util.touch(item)

    def finalize(self):
        """
        Do the cleanup if this is the last process working with the buildroot.
        """
        if os.path.exists(self.make_chroot_path()):
            try:
                self._lock_buildroot(exclusive=True)
                self._umount_all()
            except BuildRootLocked:
                pass
            finally:
                self._unlock_buildroot()

    def delete(self):
        """
        Deletes the buildroot contents.
        """
        if os.path.exists(self.basedir):
            self._lock_buildroot(exclusive=True)
            util.orphansKill(self.make_chroot_path())
            self._umount_all()
            tmp = self.basedir + ".tmp"
            util.rmtree(tmp, selinux=self.selinux)
            os.rename(self.basedir, tmp)
            self._unlock_buildroot()
            util.rmtree(tmp, selinux=self.selinux)

    def _umount_all(self):
        """umount all mounted chroot fs."""

        # first try removing all expected mountpoints.
        self.mounts.umountall()

        # then remove anything that might be left around.
        self._umount_residual()

    def _mount_is_ours(self, mountpoint):
        mountpoint = os.path.realpath(mountpoint)
        our_dirs = [os.path.realpath(self.make_chroot_path()) + '/',
                    os.path.realpath(self.make_chroot_path()) + '.tmp/']
        for our_dir in our_dirs:
            assert our_dir and our_dir != '/'
            if mountpoint.startswith(our_dir):
                return True
        return False


    def _umount_residual(self):
        mountpoints = open("/proc/mounts").read().strip().split("\n")

        # umount in reverse mount order to prevent nested mount issues that
        # may prevent clean unmount.
        for mountline in reversed(mountpoints):
            mountpoint = mountline.split()[1]
            if self._mount_is_ours(mountpoint):
                cmd = "umount -n -l %s" % mountpoint
                #self.root_log.warning("Forcibly unmounting '%s' from chroot." % mountpoint)
                util.do(cmd, raiseExc=0, shell=True, env=self.env)
