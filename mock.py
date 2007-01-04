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
except:
    import rpmUtils.transaction
import rpm
import glob
import shutil
import types
import grp
import stat
import time
import fcntl
from exceptions import Exception

from optparse import OptionParser

__VERSION__ = '0.7.1'

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

        # save our uids
        self.highuid = os.geteuid()
        self.lowuid = os.getuid()

        # set gid to mock group
        os.setgid(os.getegid())
            
        # insure we're *not* running privileged
        self.drop()
        
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

        # note that we haven't mounted anything (yet)
        self._mounted = 0

    def elevate(self):
        "elevate privileges by changing to privileged uid"
        self.debug("elevate: setting uid to %d" % self.highuid)
        os.setreuid(self.highuid, self.lowuid)

    def drop(self):
        "drop privileges by changing to unprivileged uid"
        self.debug("drop: setting uid to %d" % self.lowuid)
        os.setreuid(self.lowuid, self.highuid)
        
    def log(self, msg):
        if self.config['quiet']: return
        print msg

    def root_log(self, content):

        if type(content) is list:
            self.tmplog.writelines(content)
        else:
            self.tmplog.write(content)
        
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
            (retval, output) = self.do_elevated(cmd)
            if retval != 0:
                error("Errors cleaning out chroot: %s" % output)
                if os.path.exists(self.rootdir):
                    raise RootError, "Failed to clean basedir, exiting"


    def state(self, curstate=None):
        """returns/writes state. If curstate is given then write the
           state out and report it back. If curstate is not given report
           self.state"""
        
        if curstate:
            sf = os.path.join(self.statedir, 'status')
            sfo = open(sf, 'w')
            fcntl.flock(sfo, fcntl.LOCK_EX)
            sfo.write('%s\n' % curstate)
            fcntl.flock(sfo, fcntl.LOCK_UN)
            sfo.close()
            self._state = curstate
            self.log(curstate)
        else:
            return self._state

    def unpack(self):
        self.state('unpack_cache')
        if self.cache_file.find(".bz2") != -1:
            opts = "-jxpf"
        elif self.cache_file.find(".gz") != -1:
            opts = "-zxpf"
        else:
            opts = "-xpf"
        cmd = '%s %s %s %s' % (self.config['unpack_cmd'], opts, self.basedir, self.cache_file)
        self.debug("unpacking cache: %s" % cmd)
        (retval, output) = self.do_elevated(cmd)
        return retval

    def pack(self):
        self.state('create_cache')
        self._ensure_dir(os.path.join(self.config['basedir'], self.config['cache_topdir']))
        if self.cache_file.find(".bz2") != -1:
            opts = "-jlcf"
        elif self.cache_file.find(".gz") != -1:
            opts = "-zlcf"
        else:
            opts = "-clf"
        cmd = '%s %s %s root' % (self.config['pack_cmd'], opts, self.cache_file)
        self.debug("creating cache: %s" % cmd)
        (retval, output) = self.do_elevated(cmd)
        return retval
    
    def prep(self):
        self.state("prep")
        self.log("This may take a while")

        create_cache=0
        if self.config['use_cache']:
            cache_exists = os.path.exists( self.cache_file )
            if cache_exists:
                cache_mtime = os.stat(self.cache_file)[stat.ST_MTIME]
                cache_age_days = (time.time() - cache_mtime) / (60 * 60 * 24)
                if cache_age_days > self.config['max_cache_age_days']:
                    self.config["rebuild_cache"] = True
        
            if cache_exists and not self.config['rebuild_cache']:
                if self.config['clean']:
                    self.unpack()
                cmd = 'update'
            else:
                cmd = '%s' % self.config['chroot_setup_cmd']
                create_cache = 1
        else:
            if self.config['clean']:
                cmd = '%s' % self.config['chroot_setup_cmd']
            else:
                cmd = 'update'
         
        self._prep_install()
        self.yum(cmd)
        self._prep_build()
         
        if create_cache:
            self.pack()

    def yum(self, cmd):
        """use yum to install packages/package groups into the chroot"""
        # mock-helper yum --installroot=rootdir cmd
        basecmd = '%s --installroot %s' % (self.config['yum'], self.rootdir)
        
        self._mountall() # check it again        
        command = '%s %s' % (basecmd, cmd)
        self.debug("yum: command %s" % command)

        (retval, output) = self.do_elevated(command)

        if retval != 0:
            raise YumError, "Error performing yum command: %s" % command
        
        return (retval, output)
        
    def install_build_deps(self, srpm):
        """take an srpm, install it, rebuild it to srpm, 
           return chroot-local path to the resulting srpm"""
        
        self._mountall() # check it again
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
                    raise BuildError, "Cannot find build req %s. Exiting." % errorpkg
            # nothing made us exit, so we continue
            self.yum('install %s' % arg_string)

        return srpm

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

        (retval, output) = self.do_chroot(cmd)
        
        if retval != 0:
            raise BuildError, "Error building package from %s, See build log" % srpmfn
        
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

    def _mount(self, type, device, path):
        "mount a device, given a filesystem type and a path"
        mntpath = os.path.join(self.rootdir, path)
        self._ensure_dir(mntpath)
        self.debug("mounting %s as %s" % (device, mntpath))
        command = '%s -n -t %s %s %s' % (self.config['mount'], type, device, mntpath)
        mf = os.path.join(self.statedir, 'mounted-locations')
        (retval, output) = self.do_elevated(command)
        if retval != 0:
            if output.find('already mounted') == -1: # probably won't work in other LOCALES
                estr = "could not mount %s. Error was: %s" % (path, output)
                error(estr)
                raise RootError, estr
        track = open(mf, 'w+')
        track.write('%s\n' % path)
        track.close()
        
    def _mountall(self):
        """mount proc, sys and devpts into chroot"""

        # if we've already mounted these guys, then just return
        if self._mounted:
            return

        # mount /proc
        self._mount('proc', 'proc', 'proc')

        # mount /dev/pts
        self._mount('devpts', 'dev/pts', 'dev/pts')

        # mount /sys (if we're on a 2.6 kernel)
        if os.uname()[2].find('2.6') == 0:
            self._mount('sysfs', 'sys', 'sys')

        self._mounted = 1

    def _umount(self, path):
        item = '%s/%s' % (self.rootdir, path)
        command = '%s -n %s' % (self.config['umount'], item)
        (retval, output) = self.do_elevated(command)
    
        if retval != 0:
            if output.find('not mounted') == -1: # this probably won't work in other LOCALES
                raise RootError, "could not umount %s error was: %s" % (path, output)

    
    def _umountall(self):
        "undo the results of _mountall (umount proc,sys, and dev/pts)"

        mf = os.path.join(self.statedir, 'mounted-locations')
        if not os.path.exists(mf):
            return
            
        track = open(mf, 'r')
        lines = track.readlines()
        track.close()
        
        for item in lines:
            item = item.strip()
            if len(item) < 1:
                continue
            self._umount(item)
            
        # poof, no more file
        if os.path.exists(mf):
            os.unlink(mf)
        

    def do(self, command):
        """execute given command outside of chroot"""
        
        retval = 0
        msg = "Executing %s" % command
        self.debug(msg)
        self.root_log(msg)

        if hasattr(self, '_root_log'):
            logfile = self._root_log
        else:
            logfile = self.tmplog
        if self.state() == "build":
            logfile = self._build_log

        pipe = os.popen('{ ' + command + '; } 2>&1', 'r')
        output = ""
        for line in pipe:
            logfile.write(line)
            if self.config['debug']:
                print line[:-1]
                sys.stdout.flush()
            logfile.flush()
            output += line
        status = pipe.close()
        if status is None:
            status = 0
        
        if os.WIFEXITED(status):
            retval = os.WEXITSTATUS(status)

        return (retval, output)

    def do_elevated(self, cmd):
        if os.getuid() != self.highuid:
            need_drop = 1
        else:
            need_drop = 0
        try:
            self.elevate()
            (retval, output) = self.do(cmd)
        finally:
            if need_drop: self.drop()
        return (retval, output)

    def do_asuser(self, cmd):
        if os.getuid() != self.lowuid:
            need_elevate = 1
        else:
            need_elevate = 0
        try:
            self.drop()
            (retval, output) = self.do(cmd)
        finally:
            if need_elevate: self.elevate()
        return (retval, output)

    def do_chroot(self, command, fatal = False, exitcode=None):
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
        (ret, output) = self.do_elevated(cmd)
        if (ret != 0) and fatal:
            self.close()
            if exitcode:
                ret = exitcode
            
            error("Non-zero return value %d on executing %s\n" % (ret, cmd))
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

            self.elevate()
            req = rpmUtils.miscutils.formatRequire(n, v, f)
            self.drop()
            reqlist.append(req)
        
        # Extract SRPM name components - still not nice, shouldn't this
        # be somewhere in the "hdr" parameter?
        fname = os.path.split(str(srpm))[1]
        self.elevate()
        name, ver, rel, epoch, arch = rpmUtils.miscutils.splitFilename(fname)
        self.drop()

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
        
        self.elevate()
        ret = rpmUtils.miscutils.unique(reqlist)
        self.drop()
        return ret
    
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
        
        self._mountall()

        # we need stuff
        devices = [('null', 'c', '1', '3', '666'),
                   ('urandom', 'c', '1', '9', '644'),
                   ('random', 'c', '1', '9', '644'),
                   ('full', 'c', '1', '7', '666'),
                   ('ptmx', 'c', '5', '2', '666'),
                   ('tty', 'c', '5', '0', '666'),
                   ('zero', 'c', '1', '5', '666')]

        for (dev, devtype, major, minor, perm) in devices:
            devpath = os.path.join(self.rootdir, 'dev', dev)
            cmd = '%s %s -m %s %s %s %s' % (self.config['mknod'], 
                      devpath, perm, devtype, major, minor)
            if not os.path.exists(devpath):
                (retval, output) = self.do_elevated(cmd)
                if retval != 0:
                    raise RootError, "could not mknod error was: %s" % output

        # link fd to ../proc/self/fd
        devpath = os.path.join(self.rootdir, 'dev/fd')
        if not os.path.exists(devpath):
            os.symlink('../proc/self/fd', devpath)
        
        fd = 0
        for item in ('stdin', 'stdout', 'stderr'):
            devpath =  os.path.join(self.rootdir, 'dev', item)
            if not os.path.exists(devpath):
                fdpath = os.path.join('../proc/self/fd', str(fd))
                os.symlink(fdpath, devpath)
            fd += 1

        for item in [os.path.join(self.rootdir, 'etc', 'mtab'),
                     os.path.join(self.rootdir, 'etc', 'fstab'),
                     os.path.join(self.rootdir, 'var', 'log', 'yum.log')]:
            if not os.path.exists(item):
                fo = open(item, 'w')
                fo.close()
        
        # write in yum.conf into chroot
        if os.path.exists( os.path.join(self.rootdir, 'etc', 'yum.conf')):
            cmd = "chown %s.%s /etc/yum.conf" % (self.config['chrootuid'],
                self.config['chrootgid'])
            self.do_chroot(cmd, fatal = True)
        yumconf = os.path.join(self.rootdir, 'etc', 'yum.conf')
        yumconf_fo = open(yumconf, 'w')
        yumconf_content = self.config['yum.conf']
        yumconf_fo.write(yumconf_content)
    
        # files in /etc that need doing
        filedict = self.config['files']
        for key in filedict:
            # ensure permisssions
            if os.path.exists( "%s%s" % (self.rootdir, key) ):
                cmd = "chown %s.%s %s" % (self.config['chrootuid'],
                    self.config['chrootgid'], "%s" % key)
                self.do_chroot(cmd, fatal = True)

            # write file
            fn = '%s%s' % (self.rootdir, key)
            fo = open(fn, 'w')
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
                self.do_chroot('chown -R %s.%s %s' % (self.config["chrootuid"], self.config["chrootgid"], self.config["chroothome"]), fatal = False)
                # may need a few other chown here if there are other files that have to be edited

        if need_add_user:
            cmd = '/usr/sbin/useradd -m -u %s -d %s %s' % (self.config['chrootuid'], 
                    self.homedir, self.config['chrootuser'])
            self.do_chroot(cmd, fatal = True)

    def _build_dir_setup(self):
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
        
        # rpmmacros default
        macrofile_out = '%s%s/.rpmmacros' % (self.rootdir, self.homedir)
        if not os.path.exists(macrofile_out):
            rpmmacros = open(macrofile_out, 'w')
            rpmmacros.write(self.config['macros'])
            rpmmacros.close()
        
    
    def _prep_build(self):
        """prep the chroot for building packages"""
        self._make_our_user()
        self._build_dir_setup()
        self._mountall() # check it again

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
        init - initialize the chroot, do not build anything"""

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
    parser.add_option("--quiet", action ="store_true", dest="quiet", 
                      default=False, help="quiet down output")
    parser.add_option("--autocache", action ="store_true", dest="use_cache",
                      default=False, help="Turn on build-root caching")
    parser.add_option("--rebuildcache", action ="store_true", dest="rebuild_cache",
                      default=False, help="Force rebuild of build-root cache")
    
    return parser.parse_args()

def setup_default_config_opts(config_opts):
    config_opts['basedir'] = '/var/lib/mock/' # root name is automatically added to this
    config_opts['chroot'] = 'chroot'
    config_opts['mount'] = 'mount'
    config_opts['umount'] = 'umount'
    config_opts['rm'] = 'rm'
    config_opts['mknod'] = 'mknod'
    config_opts['yum'] = 'yum'
    config_opts['runuser'] = '/sbin/runuser'
    config_opts['chroot_setup_cmd'] = 'install buildsys-build'
    config_opts['chrootuser'] = 'mockbuild'
    config_opts['chrootgroup'] = 'mockbuild'
    config_opts['chrootuid'] = 500
    config_opts['chrootgid'] = 500
    config_opts['chroothome'] = '/builddir'
    config_opts['clean'] = True
    config_opts['debug'] = False
    config_opts['quiet'] = False
    config_opts['target_arch'] = 'i386'
    config_opts['files'] = {}
    config_opts['yum.conf'] = ''
    config_opts['macros'] = """
%%_topdir %s/build
%%_rpmfilename   %%%%{NAME}-%%%%{VERSION}-%%%%{RELEASE}.%%%%{ARCH}.rpm
    
""" % config_opts['chroothome']
    
    config_opts['more_buildreqs'] = {}
    config_opts['files']['/etc/resolv.conf'] = "nameserver 192.168.1.1\n"
    config_opts['files']['/etc/hosts'] = "127.0.0.1 localhost localhost.localdomain\n"

    # caching-related config options
    config_opts['rebuild_cache'] = False
    config_opts['use_cache'] = False
    config_opts['pack_cmd'] = "tar"
    config_opts['unpack_cmd'] = "tar"
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
    if options.quiet:
        config_opts['quiet'] = options.quiet
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

        my.close()
        if init:
            print 'Finished initializing root'
        else:
            print 'Finished cleaning root'

def do_run_cmd(config_opts, cmd, env='', raw_chroot=0):
        my = Root(config_opts)
        my.debug("executing: %s" % cmd)
        my._mountall()
        if raw_chroot: 
            cmd = '%s %s %s %s' % (env, config_opts['chroot'], my.rootdir, cmd)
            my.elevate()
            os.system(cmd)
            my.drop()
        else:
            my.do_chroot(cmd, True)
        my.close()
        my.debug('finished: %s' % cmd)
               
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
        os.umask(0022) # set a umask- protects from paranoid whackjobs with an 002 umask
    except Error, e:
        error(e)
        if my:
            my.close()
        sys.exit(e.resultcode)
   
    for srpm in srpms:
        try:
            my.prep()
            my.build(srpm)
        except Error, e:
            error(e)
            if my:
                my.close()
            sys.exit(e.resultcode)
    
    my.close()
    print "Results and/or logs in: %s" % my.resultdir

def main():

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
        if config_path != "/etc/mock" and os.file.exists("/etc/mock/defaults.cfg"):
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
        config_opts['clean'] = config_opts['quiet'] = False
        cmd = ' '.join(args[1:])
        do_run_cmd(config_opts, cmd, raw_chroot=0)
        
    elif args[0] == 'shell':
        # debugging tool for interactive poking around in the chroot
        config_opts['clean'] = config_opts['quiet'] = False
        do_run_cmd(config_opts, "/bin/bash", env='PS1="mock-chroot> "', raw_chroot=1)

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


