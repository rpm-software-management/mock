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
import mock.util

# classes
class Root:
    """controls setup of chroot environment"""
    def __init__(self, config):
        self._state = 'unstarted'

        self.config = config

        root = config['root']
        if config.has_key('unique-ext'):
            root = "%s-%s" % (root, config['unique-ext'])

        self.basedir = os.path.join(config['basedir'], root)
        self.target_arch = config['target_arch']
        self.rootdir = os.path.join(self.basedir, 'root')
        self.homedir = self.config['chroothome']
        self.builddir = os.path.join(self.homedir, 'build')
        self.cache_file = os.path.join(self.config['basedir'], 
                self.config['cache_topdir'], self.config['root'] + self.config['cache_ext'])

        # result dir
        if not self.config.has_key('resultdir'):
            self.resultdir = os.path.join(self.basedir, 'result')
        else:
            self.resultdir = self.config['resultdir']

        # state dir
        if not self.config.has_key('statedir'):
            self.statedir = os.path.join(self.basedir, 'state')
        else:
            self.statedir = self.config['statedir']
        
        self._build_log = logging.getLogger("mock.Root.build")
        self._root_log = logging.getLogger("mock.Root.root")
        self._config_log = logging.getLogger("mock.Root.config")
        self._state_log = logging.getLogger("mock.Root.state")

        mock.util.mkdirIfAbsent(self.basedir)
        mock.util.mkdirIfAbsent(self.statedir)
        mock.util.mkdirIfAbsent(self.rootdir)
        mock.util.mkdirIfAbsent(self.resultdir)

        # set up file handlers
        #formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        #ch = logging.FileHandler(os.path.join(self.statedir, "state.log"))
        #ch = logging.FileHandler(os.path.join(self.statedir, "build.log"))
        #ch = logging.FileHandler(os.path.join(self.statedir, "root.log"))
        #ch = logging.FileHandler(os.path.join(self.statedir, "config.log"))
        #ch.setLevel(logging.DEBUG)
        
        # write out the config file
        self._config_log.info('rootdir = %s\n' % self.rootdir)
        self._config_log.info('resultdir = %s\n' % self.resultdir)
        self._config_log.info('statedir = %s\n' % self.statedir)
 
    def state(self, state):
        pass
