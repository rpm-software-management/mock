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
import os

# our imports
from mock.trace_decorator import trace

# functions

origruid=os.getruid()  # 500
origeuid=os.geteuid()  #   0

@trace
def savePerms():
    global origruid
    global origeuid
    origruid = os.getruid()
    origeuid = os.geteuid()

@trace
def elevatePerms():
    os.setreuid(0, 0)

@trace
def dropPermsTemp():
    elevatePerms()
    os.setreuid(0, origruid)

@trace
def dropPermsForever():
    elevatePerms()
    os.setreuid(origruid, origruid)

@trace
def becomeUser(uid):
    elevatePerms()
    os.setreuid(0, uid)
