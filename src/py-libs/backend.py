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
import stat

# our imports
import mock.util
import mock.exception
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
        self.chrootuser = config['chrootuser']
        self.chrootgroup = config['chrootgroup']
        self.yum_conf_content = config['yum.conf']
        self.use_host_resolv = config['use_host_resolv']
        self.chroot_file_contents = config['files']
        self.chroot_setup_cmd = config['chroot_setup_cmd']
        self.yum_path = '/usr/bin/yum'
        self.macros = config['macros']

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
        mock.util.rmtree(self.basedir)

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
                     os.path.join(self.rootdir, 'var/lib/yum'),
                     os.path.join(self.rootdir, 'var/log'),
                     os.path.join(self.rootdir, 'var/lock/rpm'),
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
        yumconf = os.path.join(self.rootdir, 'etc', 'yum', 'yum.conf')
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

        # files in /dev
        mock.util.rmtree(os.path.join(self.rootdir, "dev"))
        mock.util.mkdirIfAbsent(os.path.join(self.rootdir, "dev", "pts"))
        os.mknod(os.path.join(self.rootdir, "dev/zero"), stat.S_IFCHR | 0666, os.makedev(1, 5))
        os.mknod(os.path.join(self.rootdir, "dev/null"), stat.S_IFCHR | 0666, os.makedev(1, 3))
        os.mknod(os.path.join(self.rootdir, "dev/random"), stat.S_IFCHR | 0666, os.makedev(1, 8))
        os.mknod(os.path.join(self.rootdir, "dev/urandom"), stat.S_IFCHR | 0444, os.makedev(1, 9))
        os.mknod(os.path.join(self.rootdir, "dev/console"), stat.S_IFCHR | 0600, os.makedev(5, 1))
        os.symlink("/proc/self/fd/0", os.path.join(self.rootdir, "dev/stdin"))
        os.symlink("/proc/self/fd/1", os.path.join(self.rootdir, "dev/stdout"))
        os.symlink("/proc/self/fd/2", os.path.join(self.rootdir, "dev/stderr"))
        # "/dev/log" 

        # yum stuff
        self.root_log.info('run yum')
        self._mountall()
        self._yum(self.chroot_setup_cmd)
        self._umountall()

        # create user
        self._make_our_user()

        # create rpmbuild dir
        self._build_dir_setup()

    @traceLog(moduleLog)
    def close(self):
        """cleanup everything"""
        self.state("ending")
        self.state("done")
        self.root_log.info("Done")

    # =============
    # 'Private' API
    # =============
    @traceLog(moduleLog)
    def _mountall(self):
        """mount 'normal' fs like /dev/ /proc/ /sys"""
        cmds = ('mount -t proc   mock_chroot_proc   %s/proc' % self.rootdir,
                'mount -t devpts mock_chroot_devpts %s/dev/pts' % self.rootdir,
                'mount -t sysfs  mock_chroot_sysfs  %s/sys' % self.rootdir,
               )
    
        g = [s%self.rootdir for s in ("%s/proc", "%s/dev/pts", "%s/sys")]
        mock.util.mkdirIfAbsent(*g)
        for cmd in cmds:
            self.root_log.info(cmd)
            mock.util.do(cmd)

    @traceLog(moduleLog)
    def _umountall(self):
        """umount all mounted chroot fs."""
        cmds = ('umount %s/proc' % self.rootdir,
                'umount %s/dev/pts' % self.rootdir,
                'umount %s/sys' % self.rootdir,
               )
    
        for cmd in cmds:
            self.root_log.info(cmd)
            mock.util.do(cmd)

    @traceLog(moduleLog)
    def _yum(self, cmd):
        """use yum to install packages/package groups into the chroot"""
        # mock-helper yum --installroot=rootdir cmd
        cmd = '%s --installroot %s %s' % (self.yum_path, self.rootdir, cmd)
        self.root_log.info(cmd)
        try:
            mock.util.do(cmd)
        except mock.exception.Error, e:
            self.root_log.exception("Error performing yum command: %s" % cmd)
            raise mock.exception.YumError, "Error performing yum command: %s" % cmd

    @traceLog(moduleLog)
    def _do_chroot(self, command, *args, **kargs):
        """execute given command in root"""
        cmd = "/usr/sbin/chroot %s %s" % (self.rootdir, command)
        return mock.util.do(cmd, *args, **kargs)

    @traceLog(moduleLog)
    def _make_our_user(self):
        if not os.path.exists(os.path.join(self.rootdir, 'usr/sbin/useradd')):
            raise RootError, "Could not find useradd in chroot, maybe the install failed?"

        mock.util.rmtree(os.path.join(self.rootdir, self.homedir))
        self._do_chroot('/usr/sbin/userdel -r %s' % self.chrootuser, raiseExc=False)
        self._do_chroot('/usr/sbin/groupdel %s' % self.chrootgroup, raiseExc=False)
        self._do_chroot('/usr/sbin/useradd -m -u %s -d %s %s' % (self.chrootuid, self.homedir, self.chrootuser), raiseExc=True)


    #
    # UNPRIVLEGED: 
    #   Everything in this function runs as the build user
    #
    @traceLog(moduleLog)
    def _build_dir_setup(self):
        # create all dirs as the user who will be dropping things there.
        self.uidManager.becomeUser(self.chrootuid)
        try:
            # create dir structure
            for subdir in ["%s/%s/%s" % (self.rootdir, self.homedir, s) for s in ('RPMS', 'SRPMS', 'SOURCES', 'SPECS', 'BUILD', 'originals')]:
                mock.util.mkdirIfAbsent(subdir)

            # change ownership so we can write to build home dir
            for (dirpath, dirnames, filenames) in os.walk(self.homedir):
                for path in dirnames + filenames:
                    os.chown(os.path.join(dirpath, path), self.chrootuid, -1)
                    os.chmod(os.path.join(dirpath, path), 0755)
            
            # rpmmacros default
            self.macros['%_rpmlock_path'] = "%s/var/lib/rpm/__db.000" % self.basedir
            macrofile_out = '%s%s/.rpmmacros' % (self.rootdir, self.homedir)
            rpmmacros = open(macrofile_out, 'w+')
            for key, value in self.macros.items():
                rpmmacros.write( "%s %s\n" % (key, value) )
            rpmmacros.close()

        finally:
            self.uidManager.elevatePrivs()
    
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

