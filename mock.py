#!/usr/bin/python -tt
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

import os
import os.path
import sys
import rpmUtils
try:
    test = rpmUtils.transaction.initReadOnlyTransaction()
    test = None
except:
    import rpmUtils.transaction
import rpm
import glob
import popen2
import shutil
import types
import grp
import signal
import stat
import time
from exceptions import Exception

from optparse import OptionParser

__VERSION__ = '0.7.4'

def error(msg):
    print >> sys.stderr, msg


# result/exit codes
# 0 = yay!
# 1 = something happened  - it's bad
# 30 = Yum emitted an error of some sort
# 40 = some error in the pkg we're building
# 10 = problem building the package
# 20 = error in the chroot of some kind

class Error(Exception):
    def __init__(self, msg):
        Exception.__init__(self)
        self.msg = msg
        self.resultcode = 1

    def __str__(self):
        return self.msg

class commandTimeoutExpired(Error): pass

class YumError(Error): 
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 30

class PkgError(Error):
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 40

class BuildError(Error):
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 10

class RootError(Error):
    def __init__(self, msg):
        Error.__init__(self, msg)
        self.msg = msg
        self.resultcode = 20


class LogBuffer:

    lines = []

    def clear(self):
        self.lines = []

    def write(self, line):
        if line[-1] != '\n':
            line += '\n'
        self.lines.append(line)

    def writelines(self, lines):
        for l in lines:
            self.write(l)

    def readlines(self):
        return self.lines

    def flush(self):
        pass

class Root:
    """base root object"""
    def __init__(self, config):
        self._state = 'unstarted'
        self.tmplog = LogBuffer()
        self.config = config
        self.mountorder = []
        self.mounts = {}
        root = config['root']
        if config.has_key('unique-ext'):
            root = "%s-%s" % (root, config['unique-ext'])
        self.basedir = os.path.join(config['basedir'], root)
        if self.basedir.find("/var/lib/mock") != 0:
            raise RootError, "Cannot change basedir location!"
        self.target_arch = config['target_arch']
        self.rootdir = os.path.join(self.basedir, 'root')
        self.homedir = self.config['chroothome']
        self.builddir = os.path.join(self.homedir, 'build')
        self.cache_file = os.path.join(self.config['basedir'], 
                self.config['cache_topdir'], self.config['root'] + self.config['cache_ext'])
        if not self.config.has_key('resultdir'):
            self.resultdir = os.path.join(self.basedir, 'result')
        else:
            self.resultdir = self.config['resultdir']
        if not self.config.has_key('statedir'):
            self.statedir = os.path.join(self.basedir, 'state')
        else:
            self.statedir = self.config['statedir']
        
        self._ensure_dir(self.statedir)
        self.state("init")
        
        if config['clean']: 
            self.clean()

        self._ensure_dir(self.basedir)
        self._ensure_dir(self.rootdir)
        self._ensure_dir(self.statedir)
        self._ensure_dir(self.resultdir)
        
        # open the log files
        root_log = os.path.join(self.resultdir, 'root.log')
        self._root_log = open(root_log, 'w+')
        build_log = os.path.join(self.resultdir, 'build.log')
        self._build_log = open(build_log, 'w+')
        
        # write out the config file
        cfg_log = os.path.join(self.resultdir, 'mockconfig.log')
        cfgout = open(cfg_log, 'w+')
        cfgout.write('rootdir = %s\n' % self.rootdir)
        cfgout.write('resultdir = %s\n' % self.resultdir)
        cfgout.write('statedir = %s\n' % self.statedir)
        cfgout.flush()
        cfgout.close()
    
    def root_log(self, content):

        if type(content) is list:
            self.tmplog.writelines(content)
            if self.config['verbose']:
                for l in content: print l
        else:
            self.tmplog.write(content)
            if self.config['verbose']: print content
        
        # do this so if the log dir isn't ready yet we can still get those logs
        if hasattr(self, '_root_log'):
            self._root_log.writelines(self.tmplog.readlines())
            self._root_log.flush()
            self.tmplog.clear()

    def debug(self, msg):
        if self.config['debug']:
            print "DEBUG: %s" % msg
    
    def clean(self):
        """clean out chroot with extreme prejudice :)"""
        self.state("clean")

        self.root_log('Cleaning Root')
        if os.path.exists('%s/%s' % (self.rootdir, 'proc')):
            self._umount('proc')
        if os.path.exists('%s/%s' % (self.rootdir, 'dev/pts')):
            self._umount('dev/pts')
            
        if os.path.exists(self.basedir):
            cmd = '%s -rf %s' % (self.config['rm'], self.basedir)
            (retval, output) = self.do(cmd)

            if retval != 0:
                error(output)
                if os.path.exists(self.rootdir):
                    raise RootError, "Failed to clean basedir, exiting"


    def state(self, curstate=None):
        """returns/writes state. If curstate is given then write the
           state out and report it back. If curstate is not given report
           self.state"""
        
        if curstate:
            sf = os.path.join(self.statedir, 'status')
            sfo = open(sf, 'w')
            sfo.write('%s\n' % curstate)
            sfo.close()
            self._state = curstate
            print curstate
        else:
            return self._state

    def unpack(self):
        self.state('unpack cache')
        cmd = '%s %s %s' % (self.config['unpack_cmd'], self.basedir, self.cache_file)
        self.do(cmd)

    def pack(self):
        self.state('create cache')
        self._ensure_dir(os.path.join(self.config['basedir'], self.config['cache_topdir']))
        cmd = '%s %s %s root' % (self.config['pack_cmd'], self.basedir, self.cache_file)
        self.do(cmd)
    
    def prep(self):
        self.state("prep")
        print "This may take a while"

        self.debug("uid:%d, gid:%d" % (os.getuid(), os.getgid()))
        create_cache=0
        if self.config['use_cache']:
            cache_exists = os.path.exists( self.cache_file )
            if cache_exists:
                cache_mtime = os.stat(self.cache_file)[stat.ST_MTIME]
                cache_age_days = (time.time() - cache_mtime) / (60 * 60 * 24)
                if self.config['max_cache_age_days'] and cache_age_days > self.config['max_cache_age_days']:
                    self.config["rebuild_cache"] = True
        
            if cache_exists and not self.config['rebuild_cache']:
                if self.config['clean']:
                    self.unpack()
                cmd = 'update'
            else:
                cmd = '%s' % self.config['chroot_setup_cmd']
                # never rebuild cache unless it was a clean build.
                if self.config['clean']:
                    create_cache = 1
        else:
            if self.config['clean']:
                cmd = '%s' % self.config['chroot_setup_cmd']
            else:
                cmd = 'update'
         
        try:
            self._prep_install()
            self.yum(cmd)
            self._prep_build()
        except:
            self._umountall()
            raise
         
        if create_cache:
            self.pack()

    def yum(self, cmd):
        """use yum to install packages/package groups into the chroot"""
        # mock-helper yum --installroot=rootdir cmd
        basecmd = '%s --installroot %s' % (self.config['yum'], self.rootdir)
        
        self._mount() # check it again        
        command = '%s %s' % (basecmd, cmd)
        self.debug("yum: command %s" % command)

        (retval, output) = self.do(command)

        if retval != 0:
            error(output)
            raise YumError, "Error performing yum command: %s" % command
        
        return (retval, output)
        
    def install_build_deps(self, srpm):
        """take an srpm, install it, rebuild it to srpm, 
           return chroot-local path to the resulting srpm"""
        
        self._mount() # check it again
        bd_out = '%s%s' % (self.rootdir, self.builddir)
        # init build_dir
        self._build_dir_setup()
        
        # copy srpm into chroot 
        srpmfn = os.path.basename(srpm)
        dest = self.rootdir + '/' + self.builddir + '/' + 'originals'
        shutil.copy2(srpm, dest)
        rootdest = os.path.join(self.builddir, 'originals', srpmfn)

        cmd = "%s -c 'rpm -Uvh --nodeps %s' %s" % (self.config['runuser'], 
                          rootdest, self.config['chrootuser'])
        (retval, output) = self.do_chroot(cmd)
        
        if retval != 0:
            msg = "Error installing srpm: %s" % srpmfn
            self.root_log(msg)
            error(output)
            raise RootError, msg
        
        specdir = os.path.join(bd_out, 'SPECS')
        specs = glob.glob('%s/*.spec' % specdir)
        if len(specs) < 1:
            msg =  "No Spec file found in srpm: %s" % srpmfn
            self.root_log(msg)
            raise PkgError, msg

        spec = specs[0] # if there's more than one then someone is an idiot
    
        chrootspec = spec.replace(self.rootdir, '') # get rid of rootdir prefix
        # grab the .spec file from the specdir
        # run rpmbuild -bs --nodeps specfile
        cmd = "%s -c 'rpmbuild -bs --target %s --nodeps %s' %s" % (self.config['runuser'], 
                    self.target_arch, chrootspec, self.config['chrootuser'])
        
        (retval, output) = self.do_chroot(cmd)
        if retval != 0:
            error(output)
            raise PkgError, "Error building srpm from installed spec. See Root log."
            
        srpmdir = os.path.join(bd_out, 'SRPMS')
        srpms = glob.glob('%s/*.src.rpm' % srpmdir)
        if len(srpms) < 1:
            msg = "No srpm created from specfile from srpm: %s" % srpmfn
            self.root_log(msg)
            raise PkgError, msg
        
        srpm = srpms[0] # if there's more than one then something is weird
        
        ts = rpmUtils.transaction.initReadOnlyTransaction(root=self.rootdir)
        hdr = rpmUtils.miscutils.hdrFromPackage(ts, srpm)
        
        # get text buildreqs
        buildreqs = self._text_requires_from_hdr(hdr, srpm)
        arg_string = ""
        for item in buildreqs:
            
            arg_string = arg_string + " " + "'%s'" % item

        # everything exists, okay, install them all.
        # pass build reqs (as strings) to installer
        if arg_string != "":
            (retval, output) = self.yum('resolvedep %s' % arg_string)
            for line in output.split('\n'):
                if line.find('No Package Found for') != -1:
                    errorpkg = line.replace('No Package Found for', '')
                    error(output)
                    raise BuildError, "Cannot find build req %s. Exiting." % errorpkg
            # nothing made us exit, so we continue
            self.yum('install %s' % arg_string)
        return srpm

    def installdeps(self, srpm):
        """build an srpm into binary rpms, capture log"""
        
        self.state("setup")
        # take srpm, pass to install_build_deps() to rebuild it to a valid srpm
        # and do build deps
        self.install_build_deps(srpm)
        
    def build(self, srpm):
        """build an srpm into binary rpms, capture log"""
        
        self.state("setup")

        # take srpm, pass to install_build_deps() to rebuild it to a valid srpm
        # and do build deps
        srpm_out = self.install_build_deps(srpm)
        srpm_in = srpm_out.replace(self.rootdir, '')
        
        srpmfn = os.path.basename(srpm_in)
        # run with --nodeps b/c of the check above we know we have our build
        # deps satisfied.
        cmd = "cd /;%s -c 'rpmbuild --rebuild  --target %s --nodeps %s' %s" % (
             self.config['runuser'], self.target_arch, srpm_in, 
             self.config['chrootuser'])
        
        self.state("build")

        try:
            (retval, output) = self.do_chroot(cmd, timeout=self.config['rpmbuild_timeout'])
            
            if retval != 0:
                error(output)
                raise BuildError, "Error building package from %s, See build log" % srpmfn
        except commandTimeoutExpired:
            raise BuildError, "Error building package from %s. Exceeded rpmbuild_timeout which was set to %s seconds." % (srpmfn, self.config['rpmbuild_timeout'])
        
        bd_out = self.rootdir + self.builddir 
        rpms = glob.glob(bd_out + '/RPMS/*.rpm')
        srpms = glob.glob(bd_out + '/SRPMS/*.rpm')
        packages = rpms + srpms
        
        self.root_log("Copying packages to result dir")
        for item in packages:
            shutil.copy2(item, self.resultdir)
        

    def close(self):
        """unmount things and clean up a bit"""
        self.root_log("Cleaning up...")
        self.state("ending")
        self._umountall()
        self._build_log.close()
        self.state("done")
        self.root_log("Done.")
        self._root_log.close()
        
        
    def _ensure_dir(self, path):
        """check for dir existence and/or makedir, if error out then raise Error"""
        
        msg = "ensuring dir %s" % path
        self.debug(msg)
        self.root_log("%s" % msg)

        if not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError, e:
                raise Error, "Could not create dir %s. Error: %s" % (path, e)

    def _mount(self):
        """mount proc and devpts into chroot"""
        mf = os.path.join(self.statedir, 'mounted-locations')
        track = open(mf, 'w+')

        # mount proc
        if not self.mounts.has_key('proc'):
            procdir = os.path.join(self.rootdir, 'proc')
            self._ensure_dir(procdir)

            self.debug("mounting proc in %s" % procdir)
            command = '%s -t proc proc %s/proc' % (self.config['mount'], 
                                               self.rootdir)
            track.write('proc\n')
            (retval, output) = self.do(command)
            track.flush()
        
            if retval != 0:
                if output.find('already mounted') == -1: # probably won't work in other LOCALES
                    error("could not mount proc error was: %s" % output)

            self.mounts['proc'] = procdir
            self.mountorder.append('proc')
            self.debug("mounted proc on %s" % procdir)
            
        # bind mount the host /dev
        if not self.mounts.has_key('dev'):
            devdir = os.path.join(self.rootdir, 'dev')
            self._ensure_dir(devdir)

            self.debug("bind mounting /dev in %s" % devdir)
            command = '%s --bind /dev %s' % (self.config['mount'], devdir)
            track.write('dev\n')
            (retval, output) = self.do(command)
            track.flush()
            self.mountorder.append('dev')
            self.mounts['dev'] = devdir
            self.debug("bind mounted dev on %s" % devdir)
        

        # mount dev/pts
        if not self.mounts.has_key('devpts'):
            devptsdir = os.path.join(self.rootdir, 'dev/pts')
            self._ensure_dir(devptsdir)
            self.debug("mounting devpts in %s" % devptsdir)
            command = '%s -t devpts devpts %s' % (self.config['mount'], devptsdir)
            track.write('dev/pts\n')
            (retval, output) = self.do(command)
            track.flush()
            track.close()

            if retval != 0:
                if output.find('already mounted') == -1: # probably won't work in other LOCALES
                    error(output)
                    raise RootError, "could not mount /dev/pts error was: %s" % output
        
            self.mountorder.append('devpts')
            self.mounts['devpts'] = devptsdir
            self.debug("mounted pts on %s" % devptsdir)

    def _umount(self, path):
        if path.find(self.rootdir) == -1:
            item = '%s/%s' % (self.rootdir, path)
        else:
            item = path
        command = '%s %s' % (self.config['umount'], item)
        (retval, output) = self.do(command)
    
        if retval != 0:
            if output.find('not mounted') == -1: # this probably won't work in other LOCALES
                error(output)
                raise RootError, "could not umount %s error was: %s" % (path, output)


    def _umountall(self):
        self.mountorder.reverse()
        for key in self.mountorder:
            self.debug("umounting %s" % self.mounts[key])
            self._umount(self.mounts[key])

    def _umount_by_file(self):
                
        mf = os.path.join(self.statedir, 'mounted-locations')
        if not os.path.exists(mf):
            return
            
        track = open(mf, 'r')
        lines = track.readlines()
        track.close()

        # umount in reverse order of mount
        lines.reverse()
        
        for item in lines:
            item = item.replace('\n','')
            if len(item.strip()) < 1:
                continue
            
            self._umount(item)
            
        # poof, no more file
        if os.path.exists(mf):
            os.unlink(mf)

    def do(self, command, timeout=0):
        """execute given command outside of chroot"""
        class alarmExc(Exception): pass
        def alarmhandler(signum,stackframe):
            raise alarmExc("timeout expired")
        
        retval = 0
        msg = "Executing timeout(%s): %s" % (timeout, command)
        self.debug(msg)
        self.root_log(msg)

        if hasattr(self, '_root_log'):
            logfile = self._root_log
        else:
            logfile = self.tmplog
        if self.state() == "build":
            logfile = self._build_log

        output=""
        (r,w) = os.pipe()
        pid = os.fork()
        if pid: #parent
            rpid = ret = 0
            os.close(w)
            oldhandler=signal.signal(signal.SIGALRM,alarmhandler)
            starttime = time.time()
            # timeout=0 means disable alarm signal. no timeout
            signal.alarm(timeout)

            try:
                # read output from child
                r = os.fdopen(r, "r")
                for line in r:
                    logfile.write(line)
                    if self.config['debug'] or self.config['verbose']:
                        print line[:-1]
                        sys.stdout.flush()
                    logfile.flush()
                    output += line

                # close read handle, get child return status, etc
                r.close()
                (rpid, ret) = os.waitpid(pid, 0)
                signal.alarm(0)
                signal.signal(signal.SIGALRM,oldhandler)

            except alarmExc:
                os.kill(-pid, signal.SIGTERM)
                time.sleep(1)
                os.kill(-pid, signal.SIGKILL)
                (rpid, ret) = os.waitpid(pid, 0)
                signal.signal(signal.SIGALRM,oldhandler)
                raise commandTimeoutExpired( "Timeout(%s) exceeded for command: %s" % (timeout, command))

            # mask and return just return value, plus child output
            return ((ret & 0xFF00) >> 8, output)

        else: #child
            os.close(r)
            # become process group leader so that our parent
            # can kill our children
            os.setpgrp()  

            child = popen2.Popen4(command)
            child.tochild.close()

            w = os.fdopen(w, "w")
            for line in child.fromchild:
                w.write(line)
            w.close()
            retval=child.wait()
            os._exit( (retval & 0xFF00) >> 8 )
    

    def do_chroot(self, command, fatal = False, exitcode=None, timeout=0):
        """execute given command in root"""
        cmd = ""
        
        if command.find('-c "') > -1:
            cmd = "%s %s %s" % (self.config['chroot'], self.rootdir, command)
        else:
            # we use double quotes to protect the commandline since
            # we use single quotes to protect the args in command
            # weird - why is it finding this at all.
            cmd = "%s %s %s - root -c \"%s\"" % (self.config['chroot'],
                                                 self.rootdir,
                                                 self.config['runuser'],
                                                 command)
        (ret, output) = self.do(cmd, timeout=timeout)
        if (ret != 0) and fatal:
            self.close()
            if exitcode:
                ret = exitcode
            error("Non-zero return value %d on executing %s\n" % (ret, cmd))
            error(output)
            sys.exit(ret)
        return (ret, output)

    def _text_requires_from_hdr(self, hdr, srpm):
        """take a header and hand back a unique'd list of the requires as
           strings"""
           
        reqlist = []
        names = hdr[rpm.RPMTAG_REQUIRENAME]
        flags = hdr[rpm.RPMTAG_REQUIREFLAGS]
        ver = hdr[rpm.RPMTAG_REQUIREVERSION]
        if names is not None:
            tmplst = zip(names, flags, ver)
        
        for (n, f, v) in tmplst:
            if n.startswith('rpmlib'):
                continue

            req = rpmUtils.miscutils.formatRequire(n, v, f)
            reqlist.append(req)
        
        # Extract SRPM name components - still not nice, shouldn't this
        # be somewhere in the "hdr" parameter?
        fname = os.path.split(str(srpm))[1]
        name, ver, rel, epoch, arch = rpmUtils.miscutils.splitFilename(fname)

        # Add the 'more_buildreqs' for this SRPM (if defined)
        for this_srpm in ['-'.join([name,ver,rel]),
                          '-'.join([name,ver]),
                          '-'.join([name]),]:
            if self.config['more_buildreqs'].has_key(this_srpm):
                more_reqs = self.config['more_buildreqs'][this_srpm]
                if type(more_reqs) in (type(u''), type(''),):
                    more_reqs = [more_reqs] # be nice if we get a string
                for req in more_reqs:
                    reqlist.append(req)
                break
        
        return rpmUtils.miscutils.unique(reqlist)
    
    def _prep_install(self):
        """prep chroot for installation"""
        # make chroot dir
        # make /dev, mount /proc
        #
        for item in [self.basedir, self.rootdir, self.statedir, self.resultdir,
                     os.path.join(self.rootdir, 'var/lib/rpm'),
                     os.path.join(self.rootdir, 'var/log'),
                     os.path.join(self.rootdir, 'var/lock/rpm'),
                     os.path.join(self.rootdir, 'dev'),
                     os.path.join(self.rootdir, 'etc/rpm'),
                     os.path.join(self.rootdir, 'tmp'),
                     os.path.join(self.rootdir, 'var/tmp'),
                     os.path.join(self.rootdir, 'etc/yum.repos.d')]:
            self._ensure_dir(item)
        
        self._mount()

        for item in [os.path.join(self.rootdir, 'etc', 'mtab'),
                     os.path.join(self.rootdir, 'etc', 'fstab'),
                     os.path.join(self.rootdir, 'var', 'log', 'yum.log')]:
            if not os.path.exists(item):
                fo = open(item, 'w')
                fo.close()

        # ensure /etc/ perms are correct
        cmd = '%s 2775 %s' % (self.config['chmod'], os.path.join(self.rootdir, "etc"))
        (retval, output) = self.do(cmd)
        cmd = '%s %s.%s %s' % (self.config['chown'], self.config['chrootuid'], self.config['chrootgid'], os.path.join(self.rootdir, "etc"))
        (retval, output) = self.do(cmd)
        
        # write in yum.conf into chroot
        yumconf = os.path.join(self.rootdir, 'etc', 'yum.conf')
        # always truncate and overwrite (w+)
        yumconf_fo = open(yumconf, 'w+')
        yumconf_content = self.config['yum.conf']
        yumconf_fo.write(yumconf_content)
        yumconf_fo.close()

        # symlink /etc/yum.conf to /etc/yum/yum.conf to deal with
        # (possible) yum breakage
        # if symlink already exists, no need to recreate.
        yumdir = os.path.join(self.rootdir, 'etc', 'yum')
        self._ensure_dir(yumdir)
        yumlink = os.path.join(yumdir, 'yum.conf')
        if not os.path.exists(yumlink):
            os.symlink('../yum.conf', yumlink)

        if self.config.setdefault('use_host_resolv', True) == True:
            resolvdir = os.path.join(self.rootdir, 'etc')
            resolvpath = os.path.join(self.rootdir, 'etc', 'resolv.conf')
            if os.path.exists(resolvpath):
                os.remove(resolvpath)
            shutil.copy2('/etc/resolv.conf', resolvdir)
            
        # files in /etc that need doing
        filedict = self.config['files']
        for key in filedict:
            p = os.path.join(self.rootdir, key)
            if not os.path.exists(p):
                # write file
                fo = open(p, 'w+')
                fo.write(filedict[key])
                fo.close()

    def _make_our_user(self):
        if not os.path.exists(os.path.join(self.rootdir, 'usr/sbin/useradd')):
            raise RootError, "Could not find useradd in chroot, maybe the install failed?"
        # should check if the user exists first
        # make the buildusers/groups
        need_add_user = 0
        if not os.path.exists(self.rootdir + self.homedir):
            need_add_user = 1
        else:
            # check for the following conditions:
            #  -- using cache and current user is different from original cache creator
            #  -- using --no-clean and current user is different from original creator
            curruid = self.config['chrootuid']
            chrootuid = None
            passwd = os.path.join(self.rootdir, 'etc', 'passwd')

            # find UID used to set up buildroot
            fd = open( passwd, "r" )
            while 1:
                line = fd.readline()
                if line == "": break
                if line.startswith(self.config["chrootuser"]): 
                    chrootuid = int(line.split(":")[2])

            # do fixups if they are different
            # if uid is different, assume we need to fix gid also
            if chrootuid is not None and curruid != chrootuid:
                need_add_user = 1
                self.do_chroot('/usr/sbin/userdel -r %s' % self.config["chrootuser"], fatal = False)
                self.do_chroot('/usr/sbin/groupdel %s' % self.config["chrootgroup"], fatal = False)
                self.do_chroot('chown -R %s.%s %s' % (self.config["chrootuid"],
                                                      self.config["chrootgid"],
                                                      self.config["chroothome"]), fatal = False)
                # may need a few other chown here if there are other files that have to be edited

        if need_add_user:
            cmd = '/usr/sbin/useradd -m -u %s -d %s %s' % (self.config['chrootuid'], 
                    self.homedir, self.config['chrootuser'])
            self.do_chroot(cmd, fatal = True)

    def _build_dir_setup(self):
        # ensure /etc/ perms are correct
        cmd = '%s 2775 %s' % (self.config['chmod'], os.path.join(self.rootdir, "etc"))
        (retval, output) = self.do(cmd)
        cmd = '%s %s.%s %s' % (self.config['chown'], self.config['chrootuid'], self.config['chrootgid'], os.path.join(self.rootdir, "etc"))
        (retval, output) = self.do(cmd)

        # purge the builddir, if it exists
        bd_out = '%s%s' % (self.rootdir, self.builddir)
        if os.path.exists(bd_out):
            cmd = 'rm -rf %s' % self.builddir
            self.do_chroot(cmd, fatal=True)
    
        # create dir structure
        for subdir in ('RPMS', 'SRPMS', 'SOURCES', 'SPECS', 'BUILD', 'originals'):
            cmd = "mkdir -p %s/%s" % (self.builddir, subdir)
            self.do_chroot(cmd, fatal = True)

        # change ownership so we can write to build home dir
        cmd = "chown -R %s.%s %s" % (self.config['chrootuser'], 
           self.config['chrootgroup'], self.homedir)
        self.do_chroot(cmd, fatal = True)
        
        # change mode so we can write to build home dir
        cmd = "chmod -R 0777 %s" % (self.homedir)
        self.do_chroot(cmd, fatal = True)
        
        # rpmmacros default
        macrofile_out = '%s%s/.rpmmacros' % (self.rootdir, self.homedir)
        if not os.path.exists(macrofile_out):
            rpmmacros = open(macrofile_out, 'w')
            self.config['macros'] = self.config['macros'] + "\n%%_rpmlock_path	%s/var/lib/rpm/__db.000" % self.basedir
            rpmmacros.write(self.config['macros'])
            rpmmacros.close()
        
    
    def _prep_build(self):
        """prep the chroot for building packages"""
        self._make_our_user()
        self._build_dir_setup()
        self._mount() # check it again
        
def command_parse():
    """return options and args from parsing the command line"""
    
    usage = """
    usage:
           mock [options] [rebuild] /path/to/srpm(s)
           mock [options] chroot <cmd>
           mock [options] {init|clean|shell}
    commands: 
        rebuild - build the specified SRPM(s) [default command]
        chroot - run the specified command within the chroot
        shell - run an interactive shell within specified chroot
        clean - clean out the specified chroot
        init - initialize the chroot, do not build anything
        installdeps - install build dependencies"""

    parser = OptionParser(usage=usage, version=__VERSION__)
    parser.add_option("-r", action="store", type="string", dest="chroot",
                      help="chroot name/config file name default: %default", 
                      default='default')
    parser.add_option("--no-clean", action ="store_false", dest="clean", 
                      help="do not clean chroot before building", default=True)
    parser.add_option("--arch", action ="store", dest="arch", 
                      default=None, help="target build arch")
    parser.add_option("--debug", action ="store_true", dest="debug", 
                      default=False, help="Output copious debugging information")
    parser.add_option("--resultdir", action="store", type="string", 
                      default=None, help="path for resulting files to be put")
    parser.add_option("--statedir", action="store", type="string", default=None,
                      help="Path to directory where state information is written")
    parser.add_option("--uniqueext", action="store", type="string", default=None,
                      help="Arbitrary, unique extension to append to buildroot directory name")
    parser.add_option("--configdir", action="store", dest="configdir", default=None,
                      help="Change where config files are found")
    parser.add_option("--verbose", action ="store_true", dest="verbose", 
                      default=False, help="verbose down output")
    parser.add_option("--autocache", action ="store_true", dest="use_cache",
                      default=False, help="Turn on build-root caching")
    parser.add_option("--rebuildcache", action ="store_true", dest="rebuild_cache",
                      default=False, help="Force rebuild of build-root cache")
    parser.add_option("--rpmbuild_timeout", action="store", dest="rpmbuild_timeout", type="int",
                      default=None, help="Fail build if rpmbuild takes longer than 'timeout' seconds ")
    
    return parser.parse_args()

def setup_default_config_opts(config_opts):
    config_opts['basedir'] = '/var/lib/mock/' # root name is automatically added to this
    config_opts['chroot'] = '/usr/sbin/mock-helper chroot'
    config_opts['mount'] = '/usr/sbin/mock-helper mount'
    config_opts['orphanskill'] = '/usr/sbin/mock-helper orphanskill'
    config_opts['umount'] = '/usr/sbin/mock-helper umount'
    config_opts['rm'] = '/usr/sbin/mock-helper rm'
    config_opts['mknod'] = '/usr/sbin/mock-helper mknod'
    config_opts['yum'] = '/usr/sbin/mock-helper yum'
    config_opts['chmod'] = '/usr/sbin/mock-helper chmod'
    config_opts['chown'] = '/usr/sbin/mock-helper chown'
    config_opts['rpmbuild_timeout'] = 0
    config_opts['runuser'] = '/sbin/runuser'
    config_opts['chroot_setup_cmd'] = 'install buildsys-build'
    config_opts['chrootuser'] = 'mockbuild'
    config_opts['chrootgroup'] = 'mockbuild'
    config_opts['use_host_resolv'] = True

    import grp
    config_opts['chrootuid'] = os.geteuid()
    config_opts['chrootgid'] = grp.getgrnam("mock")[2]

    config_opts['chroothome'] = '/builddir'
    config_opts['clean'] = True
    config_opts['debug'] = False
    config_opts['verbose'] = False
    config_opts['target_arch'] = 'i386'
    config_opts['files'] = {}
    config_opts['yum.conf'] = ''
    config_opts['macros'] = """
%%_topdir %s/build
%%_rpmfilename   %%%%{NAME}-%%%%{VERSION}-%%%%{RELEASE}.%%%%{ARCH}.rpm
    
""" % config_opts['chroothome']
    
    config_opts['more_buildreqs'] = {}
    config_opts['files']['/etc/hosts'] = "127.0.0.1 localhost localhost.localdomain\n"

    # caching-related config options
    config_opts['rebuild_cache'] = False
    config_opts['use_cache'] = True
    config_opts['pack_cmd'] = "/usr/sbin/mock-helper pack"
    config_opts['unpack_cmd'] = "/usr/sbin/mock-helper unpack"
    config_opts['cache_ext'] = ".tar.gz"
    config_opts['cache_topdir'] = "root-cache"
    config_opts['max_cache_age_days'] = 15

def set_config_opts_per_cmdline(config_opts, options):
    # do some other options and stuff
    if options.arch:
        config_opts['target_arch'] = options.arch
    if not options.clean:
        config_opts['clean'] = options.clean
    if options.debug:
        config_opts['debug'] = options.debug
    if options.verbose:
        config_opts['verbose'] = options.verbose
    if options.use_cache:
        config_opts['use_cache'] = options.use_cache
    if options.rebuild_cache:
        config_opts['rebuild_cache'] = options.rebuild_cache
    if config_opts['rebuild_cache']: 
        config_opts['use_cache'] = True
    if config_opts['rebuild_cache']: 
        config_opts['use_cache'] = True
    if options.resultdir:
        config_opts['resultdir'] = options.resultdir
    if options.statedir:
        config_opts['statedir'] = options.statedir
    if options.uniqueext:
        config_opts['unique-ext'] = options.uniqueext
    if options.rpmbuild_timeout is not None:
        config_opts['rpmbuild_timeout'] = options.rpmbuild_timeout

def do_clean(config_opts, init=0):
        my = None
        try:
            my = Root(config_opts)
            if init: my.prep()
        except Error, e:
            print e
            if my:
                my.close()
            sys.exit(100)
        except KeyboardInterrupt, e:
            if my: my.close()
            raise

        my.close()
        if init:
            print 'Finished initializing root'
        else:
            print 'Finished cleaning root'

def do_run_cmd(config_opts, cmd, env='', raw_chroot=0):
        my = Root(config_opts)
        os.umask(0002) # set umask so mock group can all share.
        my.debug("executing: %s" % cmd)
        my._mount()
        # Orphans killing must be included it to the same command as otherwise
        # self.do() would get stuck.
        # orphanskill output is visible only with the --debug option.
        cmd += '; %s %s' % (config_opts['orphanskill'], my.rootdir)
        if raw_chroot: 
            cmd = '%s %s %s %s' % (env, config_opts['chroot'], my.rootdir, cmd)
            os.system(cmd)
        else:
            my.do_chroot(cmd, True)
        my.close()
        my.debug('finished chroot command')
               
def ensure_filetype_srpm(srpms):
    for srpm in srpms:
        ts = rpmUtils.transaction.initReadOnlyTransaction()
        try:
            hdr = rpmUtils.miscutils.hdrFromPackage(ts, srpm)
        except rpmUtils.RpmUtilsError, e:
            error("Specified srpm %s cannot be found/opened" % srpm)
            sys.exit(50)
   
        if hdr[rpm.RPMTAG_SOURCEPACKAGE] != 1:
            error("Specified srpm isn't a srpm!  Can't go on")
            sys.exit(50)

def do_rebuild(config_opts, srpms):
    # Prep build root
    my = None  # if Root() fails, my will be undefined so we force it to None
    try:
        my = Root(config_opts)
        os.umask(0002) # set umask so mock group can all share.
    except Error, e:
        error(e)
        if my:
            my.close()
        sys.exit(e.resultcode)
    except KeyboardInterrupt, e:
        if my: my.close()
        raise
   
    for srpm in srpms:
        try:
            my.prep()
            my.build(srpm)
        except Error, e:
            error(e)
            if my:
                my.close()
            sys.exit(e.resultcode)
        except KeyboardInterrupt, e:
            if my: my.close()
            raise
    
    my.close()
    print "Results and/or logs in: %s" % my.resultdir

def main():
    # before we go on, make sure the user is a member of the 'mock' group.
    member = False
    for item in os.getgroups():
        try:
            grptup = grp.getgrgid(item)
        except KeyError, e:
            continue
        if grptup[0] == 'mock':
            member = True

    if not member:
        print "You need to be a member of the mock group for this to work"
        sys.exit(1)

    # and make sure they're not root
    if os.geteuid() == 0:
        error("Don't try to run mock as root!")
        sys.exit(1)
        
    # defaults
    config_opts = {}
    setup_default_config_opts(config_opts)
    
    # cli option parsing
    (options, args) = command_parse()
    
    if len(args) < 1:
        error("No srpm or command specified - nothing to do")
        sys.exit(50)

    # config path -- can be overridden on cmdline
    config_path='/etc/mock'
    if options.configdir:
        config_path = options.configdir
    
    # Read in the default values which can be overwritten
    # with the more specific config being loaded below.
    cfg = os.path.join(config_path, 'defaults.cfg')
    if os.path.exists(cfg):
        execfile(cfg)
    else:
        if config_path != "/etc/mock" and os.path.exists("/etc/mock/defaults.cfg"):
            execfile("/etc/mock/defaults.cfg")
    
    # read in the config file by chroot name
    if options.chroot.endswith('.cfg'):
        cfg = '%s/%s' % (config_path, options.chroot)
    else:
        cfg = '%s/%s.cfg' % (config_path, options.chroot)
        
    if os.path.exists(cfg):
        execfile(cfg)
    else:
        error("Could not find config file %s for chroot %s" % (cfg, options.chroot))
        sys.exit(1)
    
    # cmdline options override config options
    set_config_opts_per_cmdline(config_opts, options)

    # do whatever we're here to do
    if args[0] == 'clean':
        # unset a --no-clean
        config_opts['clean'] = True
        do_clean(config_opts, init=0)
        
    elif args[0] == 'init':
        do_clean(config_opts, init=1)

    elif args[0] == 'chroot':
        # catch-all for executing arbitrary commands in the chroot
        config_opts['clean'] = False
        cmd = ' '.join(args[1:])
        do_run_cmd(config_opts, cmd, raw_chroot=0)
        
    elif args[0] == 'shell':
        # debugging tool for interactive poking around in the chroot
        config_opts['clean'] = False
        do_run_cmd(config_opts, "/bin/bash", env='PS1="mock-chroot> "', raw_chroot=1)

    elif args[0] == 'installdeps':
        if len(args) > 1:
            srpm = args[1]
        else:
            error("No package specified to installdeps command.")
            sys.exit(50)
        config_opts['clean'] = False
        ts = rpmUtils.transaction.initReadOnlyTransaction()
        try:
            hdr = rpmUtils.miscutils.hdrFromPackage(ts, srpm)
        except rpmUtils.RpmUtilsError, e:
            error("Specified srpm %s cannot be found/opened" % srpm)
            sys.exit(50)
        if hdr[rpm.RPMTAG_SOURCEPACKAGE] != 1:
            error("Specified srpm isn't a srpm!  Can't go on")
            sys.exit(50)
        try:
            my = None  # if Root() fails, my will be undefined so we force it to None
            my = Root(config_opts)
            os.umask(0002) # set umask so mock group can all share.
            my.prep()
            my.installdeps(srpm)
        except Error, e:
            error(e)
            if my:
                my.close()
            sys.exit(e.resultcode)
        except KeyboardInterrupt, e:
            if my: my.close()
            raise
        my.close()
        print "Logs in: %s" % my.resultdir

    else:
        if args[0] == 'rebuild':
            if len(args) > 1:
                srpms = args[1:]
            else:
                error("No package specified to rebuild command.")
                sys.exit(50)
        else:
            srpms = args[0:]

        # exit here if everything isn't kosher
        ensure_filetype_srpm(srpms)

        do_rebuild(config_opts, srpms)

if __name__ == '__main__':
    main()


