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
import os.path

# our imports
import mock.exception
from mock.trace_decorator import trace

# set up logging
log = logging.getLogger("mock.util")

# classes
class commandTimeoutExpired(mock.exception.Error):
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 10

# functions
@trace
def mkdirIfAbsent(dir):
    log.debug("ensuring that dir exists: %s" % dir)
    if not os.path.exists(dir):
        try:
            log.debug("creating dir: %s" % dir)
            os.makedirs(dir)
        except OSError, e:
            log.exception()
            raise mock.exception.Error, "Could not create dir %s. Error: %s" % (dir, e)

