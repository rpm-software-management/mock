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
import shutil

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
        
        self.build_log = logging.getLogger("mock.Root.build")
        self.root_log = logging.getLogger("mock.Root.chroot")
        self._state_log = logging.getLogger("mock.Root.state")

        # officially set state so it is logged
        self.state("unstarted")


    def _resetLogging(self):
        # attach logs to log files. 
        # This happens in addition to anything
        # is set up in the config file... ie. logs go everywhere
        formatter = logging.Formatter("%(asctime)s - %(module)s:%(lineno)d - %(levelname)s - %(message)s")
        for (log, filename) in ( 
                (self._state_log, "state.log"), 
                (self.build_log, "build.log"), 
                (self.root_log, "root.log")):
            fullPath = os.path.join(self.statedir, filename)
            fh = logging.FileHandler(fullPath, "w+")
            fh.setFormatter(formatter)
            fh.setLevel(logging.NOTSET)
            log.addHandler(fh)

 
    # =============
    #  'Public' API
    # =============

    def state(self, newState = None):
        if newState is not None:
            self._state = newState
            self._state_log.info("State Changed: %s" % self._state)

        return self._state

    def clean(self):
        """clean out chroot with extreme prejudice :)"""
        self.state("clean")
        self.root_log.info("Cleaning chroot")
        try:
            shutil.rmtree(self.basedir)
        except OSError, e:
            if e.errno != 2: # no such file or directory
                raise

    def init(self):
        self.state("init")

         # create our base directory heirarchy
        mock.util.mkdirIfAbsent(self.basedir)
        mock.util.mkdirIfAbsent(self.statedir)
        mock.util.mkdirIfAbsent(self.rootdir)
        mock.util.mkdirIfAbsent(self.resultdir)

        self._resetLogging()

        # write out config details
        self.root_log.debug('rootdir = %s' % self.rootdir)
        self.root_log.debug('resultdir = %s' % self.resultdir)
        self.root_log.debug('statedir = %s' % self.statedir)

        self.root_log.debug("root_log debug message")
        self.root_log.info("root_log info message")
        self.root_log.warning("root_log warning message")
        self.root_log.error("root_log error message")
        self.root_log.critical("root_log critical message")

        self.build_log.debug("build_log debug message")
        self.build_log.info("build_log info message")
        self.build_log.warning("build_log warning message")
        self.build_log.error("build_log error message")
        self.build_log.critical("build_log critical message")
   

    # =============
    # 'Private' API
    # =============

    def prep(self):
        self.state("prep")
        self.root_log.debug("uid:%d, gid:%d" % (os.getuid(), os.getgid()))

        # create skeleton dirs
        # yum stuff
        # create user
        # create rpmbuild dir


