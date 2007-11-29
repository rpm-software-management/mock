# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING
# Written by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>

# python library imports
import logging
import os

# our imports
from mock.trace_decorator import traceLog

# set up logging
log = logging.getLogger("mock.uid")

# class
class uidManager(object):
    @traceLog(log)
    def __init__(self, unprivUid=-1, unprivGid=-1):
        self.privStack = []
        self.unprivUid = unprivUid
        self.unprivGid = unprivGid

    @traceLog(log)
    def becomeUser(self, uid, gid=-1):
        # save current ruid, euid, rgid, egid
        self._push()
        self._becomeUser(uid, gid)

    @traceLog(log)
    def dropPrivsTemp(self):
        # save current ruid, euid, rgid, egid
        self._push()
        self._becomeUser(self.unprivUid, self.unprivGid)

    @traceLog(log)
    def restorePrivs(self):
        # back to root first
        self._elevatePrivs()

        # then set saved 
        privs = self.privStack.pop()
        os.setregid(privs[2], privs[3])
        os.setreuid(privs[0], privs[1])

    @traceLog(log)
    def dropPrivsForever(self):
        self._elevatePrivs()
        os.setregid(self.unprivGid, self.unprivGid)
        os.setreuid(self.unprivUid, self.unprivUid)

    @traceLog(log)
    def _push(self):
         # save current ruid, euid, rgid, egid
        self.privStack.append([
            os.getuid(),
            os.geteuid(),
            os.getgid(),
            os.getegid(),
            ])

    @traceLog(log)
    def _elevatePrivs(self):
        os.setreuid(0, 0)
        os.setregid(0, 0)

    @traceLog(log)
    def _becomeUser(self, uid, gid=None):
        self._elevatePrivs()
        if gid is not None:
            os.setregid(gid, gid)
        os.setreuid(0, uid)
