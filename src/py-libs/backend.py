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
from mock.trace_decorator import traceLog

# set up logging
moduleLog = logging.getLogger("mock")

# classes
class Root(object):
    """controls setup of chroot environment"""
    @traceLog(moduleLog)
    def __init__(self, config, uidManager):
        self._state = 'unstarted'
        self.uidManager = uidManager

        root = config['root']
        if config.has_key('unique-ext'):
            root = "%s-%s" % (root, config['unique-ext'])

        self.basedir = os.path.join(config['basedir'], root)
        self.target_arch = config['target_arch']
        self.rootdir = os.path.join(self.basedir, 'root')
        self.homedir = config['chroothome']
        self.builddir = os.path.join(self.homedir, 'build')
        self.cache_file = os.path.join(config['basedir'], 
                config['cache_topdir'], config['root'] + config['cache_ext'])

        # result dir
        if not config.has_key('resultdir'):
            self.resultdir = os.path.join(self.basedir, 'result')
        else:
            self.resultdir = config['resultdir']

        # state dir
        if not config.has_key('statedir'):
            self.statedir = os.path.join(self.basedir, 'state')
        else:
            self.statedir = config['statedir']
        
        self.root_log = logging.getLogger("mock")
        self.build_log = logging.getLogger("mock.Root.build")
        self._state_log = logging.getLogger("mock.Root.state")

        # config options
        self.chrootuid = config['chrootuid']
        self.yum_conf_content = config['yum.conf']
        self.use_host_resolv = config['use_host_resolv']
        self.chroot_file_contents = config['files']

        # officially set state so it is logged
        self.state("unstarted")

    # =============
    #  'Public' API
    # =============

    @traceLog(moduleLog)
    def state(self, newState = None):
        if newState is not None:
            self._state = newState
            self._state_log.info("State Changed: %s" % self._state)

        return self._state

    @traceLog(moduleLog)
    def clean(self):
        """clean out chroot with extreme prejudice :)"""
        self.state("clean")
        self.root_log.info("Cleaning chroot")
        try:
            shutil.rmtree(self.basedir)
        except OSError, e:
            if e.errno != 2: # no such file or directory
                raise

    @traceLog(moduleLog)
    def init(self):
        self.state("init")

        # NOTE: removed the following stuff vs mock v0:
        #   --> /etc/ is no longer 02775 (new privs model)
        #   --> no /etc/yum.conf symlink (F7 and above)

        self.root_log.debug("elevating privs")
        self.uidManager.elevatePrivs()

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

        self.root_log.debug("uid:%d, gid:%d" % (os.getuid(), os.getgid()))


        # create skeleton dirs
        self.root_log.info('create skeleton dirs')
        for item in [
                     os.path.join(self.rootdir, 'var/lib/rpm'),
                     os.path.join(self.rootdir, 'var/log'),
                     os.path.join(self.rootdir, 'var/lock/rpm'),
                     os.path.join(self.rootdir, 'dev'),
                     os.path.join(self.rootdir, 'etc/rpm'),
                     os.path.join(self.rootdir, 'tmp'),
                     os.path.join(self.rootdir, 'var/tmp'),
                     os.path.join(self.rootdir, 'etc/yum.repos.d'),
                     os.path.join(self.rootdir, 'etc/yum'),
                    ]:
            mock.util.mkdirIfAbsent(item)

        # touch files
        self.root_log.info('touch required files')
        for item in [os.path.join(self.rootdir, 'etc', 'mtab'),
                     os.path.join(self.rootdir, 'etc', 'fstab'),
                     os.path.join(self.rootdir, 'var', 'log', 'yum.log')]:
            mock.util.touch(item)

        # write in yum.conf into chroot
        # always truncate and overwrite (w+)
        self.root_log.info('configure yum')
        yumconf = os.path.join(self.rootdir, 'etc', 'yum.conf')
        yumconf_fo = open(yumconf, 'w+')
        yumconf_fo.write(self.yum_conf_content)
        yumconf_fo.close()

        # set up resolv.conf
        if self.use_host_resolv:
            resolvdir = os.path.join(self.rootdir, 'etc')
            resolvpath = os.path.join(self.rootdir, 'etc', 'resolv.conf')
            if os.path.exists(resolvpath):
                os.remove(resolvpath)
            shutil.copy2('/etc/resolv.conf', resolvdir)

        # files in /etc that need doing
        for key in self.chroot_file_contents:
            p = os.path.join(self.rootdir, *key.split('/'))
            if not os.path.exists(p):
                # write file
                fo = open(p, 'w+')
                fo.write(self.chroot_file_contents[key])
                fo.close()

        # yum stuff
        # create user
        # create rpmbuild dir
   

    # =============
    # 'Private' API
    # =============
    @traceLog(moduleLog)
    def _yum(self):
        pass
    
    @traceLog(moduleLog)
    def _resetLogging(self):
        # attach logs to log files. 
        # This happens in addition to anything
        # is set up in the config file... ie. logs go everywhere
        formatter = logging.Formatter("%(asctime)s - %(module)s:%(lineno)d:%(levelname)s: %(message)s")
        for (log, filename) in ( 
                (self._state_log, "state.log"), 
                (self.build_log, "build.log"), 
                (self.root_log, "root.log")):
            fullPath = os.path.join(self.statedir, filename)
            fh = logging.FileHandler(fullPath, "w+")
            fh.setFormatter(formatter)
            fh.setLevel(logging.NOTSET)
            log.addHandler(fh)

