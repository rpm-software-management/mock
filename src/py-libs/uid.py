#!/usr/bin/python -tt
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Written by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# revised and adapted by Michael Brown

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
        os.setreuid(0, 0)
        os.setregid(0, 0)

        # then set saved 
        privs = self.privStack.pop()
        os.setregid(privs[2], privs[3])
        os.setreuid(privs[0], privs[1])

    @traceLog(log)
    def dropPrivsForever(self):
        self.elevatePrivs()
        os.setregid(self.origrgid, self.origegid)
        os.setreuid(self.origruid, self.origruid)

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
    def _becomeUser(self, uid, gid=None):
        os.setreuid(0, 0)
        os.setregid(0, 0)
        if gid is not None:
            os.setregid(gid, gid)
        os.setreuid(0, uid)

