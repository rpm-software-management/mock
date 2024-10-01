"""
Create users/groups in chroot.  Wrapping the useradd/groupadd utilities.
"""

import grp
import os
import pwd
from mockbuild.file_util import mkdirIfAbsent
from mockbuild.util import do_with_status


class ShadowUtils:
    """
    Create a group
    """
    def __init__(self, root):
        self.root = root
        self._selinux_workaround_applied = False

    def _selinux_workaround(self):
        """
        Work-around for:
        https://github.com/shadow-maint/shadow/issues/940
        https://github.com/SELinuxProject/selinux/issues/419
        """
        if self._selinux_workaround_applied:
            return

        path = self.root.make_chroot_path("/sys/fs/selinux")
        mkdirIfAbsent(path)
        file = os.path.join(path, "enforce")
        with open(file, "w", encoding="utf-8") as fd:
            fd.write("0")
        self._selinux_workaround_applied = True

    def _execute_command(self, command, can_fail=False):
        self._selinux_workaround()

        with self.root.uid_manager.elevated_privileges():
            # Ordinarily we do not want to depend on shadow-utils in the buildroot, but
            # configuring certain options (such as FreeIPA-provided subids) can make it
            # impossible to create users in the buildroot using host shadow-utils so we
            # provide this workaround.
            # Tracking upstream bug https://github.com/shadow-maint/shadow/issues/897
            if self.root.config['use_host_shadow_utils']:
                do_with_status(command + ['--root', self.root.make_chroot_path()], raiseExc=not can_fail)
            else:
                self.root.doChroot(command, raiseExc=not can_fail)

    def delete_user(self, username, can_fail=False):
        """
        Delete user in self.root (/etc/passwd modified)
        """
        command = ["userdel", "-f", username]
        self._execute_command(command, can_fail=can_fail)

    def delete_group(self, groupname, can_fail=False):
        """
        Delete group in self.root (/etc/group modified)
        """
        command = ["groupdel", groupname]
        self._execute_command(command, can_fail=can_fail)

    def create_group(self, groupname, gid=None):
        """
        Create group in self.root (/etc/group modified)
        """
        command = ["groupadd", groupname]
        if gid is not None:
            command += ["-g", str(gid)]
        self._execute_command(command)

    def create_user(self, username, uid=None, gid=None, home=None):
        """
        Create user in self.root (/etc/passwd modified)
        """
        command = ["useradd", username]
        if uid is not None:
            command += ["-o", "-u", str(uid)]
        if gid is not None:
            command += ["-g", str(gid), "-N"]
        if home is not None:
            command += ["-d", str(home)]
        self._execute_command(command)

    def copy_from_host(self, username):
        """
        Copy user (with uid/gid/group_name) from Host into the self.root.
        """
        try:
            info = pwd.getpwnam(username)
            uid = info.pw_uid
            gid = info.pw_gid
        except KeyError as err:
            raise RuntimeError(
                f"Can not find the requested user {username} "
                "on host") from err

        try:
            group_name = grp.getgrgid(gid).gr_name
        except KeyError as err:
            raise RuntimeError(
                f"Can not find the requested GID {gid} "
                "on host") from err

        self.delete_user(username, can_fail=True)
        # This might fail because the group doesn't exist in the chroot (OK to
        # ignore), or because there still are other users in the group (a
        # serious error case, but OK to ignore because the subsequent
        # 'crate_group' attempt will fail anyway).
        self.delete_group(group_name, can_fail=True)
        self.create_group(group_name, gid=gid)
        self.create_user(group_name, uid=uid, gid=gid)
