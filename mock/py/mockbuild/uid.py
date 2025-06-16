# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

import atexit
import ctypes
import errno
import grp
import multiprocessing
import os
import pwd
import sys
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager

from .trace_decorator import traceLog

_libc = ctypes.CDLL(None, use_errno=True)


@traceLog()
def setup_uid_manager():
    mockgid = grp.getgrnam('mock').gr_gid
    unprivUid = os.getuid()
    unprivGid = mockgid

    # sudo
    if os.environ.get("SUDO_UID") is not None:
        unprivUid = int(os.environ['SUDO_UID'])
        os.setgroups((mockgid,))

    # consolehelper
    if os.environ.get("USERHELPER_UID") is not None:
        unprivUid = int(os.environ['USERHELPER_UID'])
        unprivName = pwd.getpwuid(unprivUid).pw_name
        secondary_groups = [g.gr_gid for g in grp.getgrall() if unprivName in g.gr_mem]
        os.setgroups([mockgid] + secondary_groups)

    uidManager = UidManager(unprivUid, unprivGid)
    return uidManager

class UidManager(object):
    @traceLog()
    def __init__(self, unprivUid=-1, unprivGid=-1):
        self.privStack = []
        self.privEnviron = []
        self.unprivUid = unprivUid
        self.unprivGid = unprivGid
        self.unprivEnviron = dict(os.environ)
        self.unprivEnviron['HOME'] = pwd.getpwuid(unprivUid).pw_dir
        self.mockgid = grp.getgrnam('mock').gr_gid

    @traceLog()
    def __enter__(self):
        self.dropPrivsTemp()
        return self

    @traceLog()
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restorePrivs()

    @contextmanager
    def elevated_privileges(self):
        self._push()
        self._elevatePrivs()
        try:
            yield
        finally:
            self.restorePrivs()

    @traceLog()
    def becomeUser(self, uid, gid=-1):
        # save current ruid, euid, rgid, egid
        self._push()
        self.become_user_without_push(uid, gid)

    @traceLog()
    def dropPrivsTemp(self):
        # save current ruid, euid, rgid, egid
        self._push()
        self.become_user_without_push(self.unprivUid, self.unprivGid)
        os.environ.clear()
        os.environ.update(self.unprivEnviron)

    @traceLog()
    def restorePrivs(self):
        # back to root first
        self._elevatePrivs()

        # then set saved
        privs = self.privStack.pop()
        os.environ.clear()
        os.environ.update(self.privEnviron.pop())
        os.setregid(privs['rgid'], privs['egid'])
        setresuid(privs['ruid'], privs['euid'])

    @traceLog()
    def dropPrivsForever(self):
        self._elevatePrivs()
        os.setregid(self.unprivGid, self.unprivGid)
        os.setreuid(self.unprivUid, self.unprivUid)

    @traceLog()
    def _push(self):
        # save current ruid, euid, rgid, egid
        self.privStack.append({
            "ruid": os.getuid(),
            "euid": os.geteuid(),
            "rgid": os.getgid(),
            "egid": os.getegid(),
        })
        self.privEnviron.append(dict(os.environ))

    @traceLog()
    # pylint: disable=no-self-use
    def _elevatePrivs(self):
        setresuid(0, 0, 0)
        os.setregid(0, 0)

    @traceLog()
    def become_user_without_push(self, uid, gid=None):
        self._elevatePrivs()
        if gid is not None:
            os.setregid(gid, gid)
        setresuid(uid, uid, 0)

    @traceLog()
    def changeOwner(self, path, uid=None, gid=None, recursive=False):
        self._elevatePrivs()
        if uid is None:
            uid = self.unprivUid
        if gid is None:
            gid = self.unprivGid
        self._tolerant_chown(path, uid, gid)
        if recursive:
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    self._tolerant_chown(os.path.join(root, d), uid, gid)
                for f in files:
                    self._tolerant_chown(os.path.join(root, f), uid, gid)

    @staticmethod
    def _tolerant_chown(path, uid, gid):
        """ chown() which does not raise error if file does not exist. """
        try:
            os.lchown(path, uid, gid)
        except OSError as e:
            if e.errno == errno.ENOENT:
                pass
            else:
                raise

    @traceLog()
    def fix_different_chrootgid(self, config_opts):
        """ Allow a different mock group to be specified.
            This tries to solve chicken-egg problem. Because the uidManager
            has to be initialized before reading config, but config_opts['chrootgid']
            is known only after reading config
        """
        if config_opts['chrootgid'] != self.mockgid:
            self.restorePrivs()
            os.setgroups((self.mockgid, config_opts['chrootgid']))
            self.dropPrivsTemp()

    def drop_privs_forever_and_execute(self, method, *args, **kwargs):
        """
        Assure that the process can not re-elevate privileges to root, and
        execute the given method.
        """
        self.dropPrivsForever()
        atexit._clear()
        return method(*args, **kwargs)

    def run_in_subprocess_without_privileges(self, method, *args, **kwargs):
        """
        Execute the given method in a forked process that can not re-elevate
        privileges to root (we drop the saved set-*IDs).  The exceptions from
        the child pops up to the parent.
        """
        if sys.version_info >= (3, 14):
            # RHEL 9+ supports this too
            # Fedora 43+ needs this
            pool_executor = ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("fork"))
        else:
            # Can be removed when we stop supporting RHEL8
            pool_executor = ProcessPoolExecutor(max_workers=1)
        with pool_executor as executor:
            future = executor.submit(self.drop_privs_forever_and_execute,
                                     method, *args, **kwargs)
            return future.result()

def getresuid():
    ruid = ctypes.c_long()
    euid = ctypes.c_long()
    suid = ctypes.c_long()
    res = _libc.getresuid(ctypes.byref(ruid), ctypes.byref(euid), ctypes.byref(suid))
    if res:
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
    return (ruid.value, euid.value, suid.value)


def setresuid(ruid=-1, euid=-1, suid=-1):
    ruid = ctypes.c_long(ruid)
    euid = ctypes.c_long(euid)
    suid = ctypes.c_long(suid)
    res = _libc.setresuid(ruid, euid, suid)
    if res:
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))


def getresgid():
    rgid = ctypes.c_long()
    egid = ctypes.c_long()
    sgid = ctypes.c_long()
    res = _libc.getresgid(ctypes.byref(rgid), ctypes.byref(egid), ctypes.byref(sgid))
    if res:
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
    return (rgid.value, egid.value, sgid.value)


def setresgid(rgid=-1, egid=-1, sgid=-1):
    rgid = ctypes.c_long(rgid)
    egid = ctypes.c_long(egid)
    sgid = ctypes.c_long(sgid)
    res = _libc.setresgid(rgid, egid, sgid)
    if res:
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
