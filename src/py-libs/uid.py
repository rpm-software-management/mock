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
    def __init__(self):
        self.saveCurrentPrivs()

    @traceLog(log)
    def saveCurrentPrivs(self):
        self.origruid = os.getuid() # 500
        self.origeuid = os.geteuid() # 0
        self.origrgid=os.getgid()  # 500
        self.origegid=os.getegid()  # 500

    @traceLog(log)
    def elevatePrivs(self):
        os.setreuid(0, 0)
        os.setregid(0, 0)

    @traceLog(log)
    def dropPrivsTemp(self):
        self.elevatePrivs()
        os.setregid(self.origrgid, self.origegid)
        os.setreuid(0, self.origruid)

    @traceLog(log)
    def dropPrivsForever(self):
        self.elevatePrivs()
        os.setregid(self.origrgid, self.origegid)
        os.setreuid(self.origruid, self.origruid)

    @traceLog(log)
    def becomeUser(self, uid, gid=None):
        self.elevatePrivs()
        os.setreuid(0, uid)
        if gid is not None:
            os.setregid(gid, gid)

