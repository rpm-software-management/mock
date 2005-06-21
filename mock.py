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
import commands
import rpmUtils
import rpm
import glob
import shutil
import types
import grp

from optparse import OptionParser

__VERSION__ = '0.3'

def error(msg):
    print >> sys.stderr, msg


class Locked(Exception): pass
class ReturnValue(Exception): pass
class Error(Exception): pass



class Root:
    """base root object"""
    def __init__(self, config):
        self._state = 'unstarted'
        self.tmplog = []
        self.config = config
        self.basedir = '%s/%s' % (config['basedir'], config['root'])
        self.target_arch = config['target_arch']
        self.rootdir = os.path.join(self.basedir, 'root')
        self.statedir = os.path.join(self.basedir, 'state')
        self.homedir = self.config['chroothome']
        self.builddir = os.path.join(self.homedir, 'build')
        if not self.config.has_key('resultdir'):
            self.resultdir = os.path.join(self.basedir, 'result')
        else:
            self.resultdir = self.config['resultdir']
        
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
        cfgout.write('rootdir = %s' % self.rootdir)
        cfgout.write('resultdir = %s' % self.resultdir)
        cfgout.write('statedir = %s' % self.statedir)
        cfgout.close()

        
    
    def build_log(self, content):
        if type(content) is types.ListType:
            for line in content:
                self._build_log.write('%s\n' % line)
        elif type(content) is types.StringType:
            self._build_log.write('%s\n' % content)
        else:
            # wtf?
            pass
        self._build_log.flush()

    def root_log(self, content):
            
        # do this so if the log dir isn't ready yet we can still get those logs
        self.tmplog.append(content)
        
        if not hasattr(self, '_root_log'):
            return
        
        for content in self.tmplog:
            if type(content) is types.ListType:
                for line in content:
                    self._root_log.write('%s\n' % line)
            elif type(content) is types.StringType:
                self._root_log.write('%s\n' % content)
            else:
                # wtf?
                pass
            
            self._root_log.flush()
        self.tmplog = [] # zero out the logs

    def debug(self, msg):
        if self.config['debug']:
            print "DEBUG: %s" % msg
    
    def clean(self):
        """clean out chroot with extreme prejudice :)"""
        self.root_log('Cleaning Root')
        if os.path.exists('%s/%s' % (self.rootdir, 'proc')):
            self._umount('proc')
        if os.path.exists('%s/%s' % (self.rootdir, 'dev/pts')):
            self._umount('dev/pts')
            
        cmd = '%s -rfv %s' % (self.config['rm'], self.basedir)
        (retval, output) = self.do(cmd)

        if retval != 0:
            error("Errors cleaning out chroot: %s" % output)
            if os.path.exists(self.rootdir) or os.path.exists(self.statedir):
                raise Error, "Failed to clean basedir, exiting"


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
    
    def prep(self):
        self.state('Starting Prep')
        self._prep_install()
        if self.config['clean']:
            cmd = 'groupinstall %s' % self.config['buildgroup']
        else:
            cmd = 'update'

        self.yum(cmd)
        self._prep_build()
        self.state('Finished Prep')
        

    def yum(self, cmd):
        """use yum to install packages/package groups into the chroot"""
        # mach-helper yum --installroot=rootdir cmd
        basecmd = '%s --installroot %s' % (self.config['yum'], self.rootdir)
        
        self._mount() # check it again        
        command = '%s %s' % (basecmd, cmd)
        self.debug("yum: command %s" % command)
        self.state("yum: command %s" % command)
        
        self.root_log(command)
        (retval, output) = self.do(command)
        self.root_log(output)

        if retval != 0:
            raise Error, "Error peforming yum command: %s" % command
        
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
        self.root_log(cmd)
        self.state("Running: %s" % cmd)
        (retval, output) = self.do_chroot(cmd)
        
        self.root_log(output)
        
        if retval != 0:
            msg = "Error installing srpm: %s" % srpmfn
            self.root_log(msg)
            raise Error, msg
        
        specdir = os.path.join(bd_out, 'SPECS')
        specs = glob.glob('%s/*.spec' % specdir)
        if len(specs) < 1:
            msg =  "No Spec file found in srpm: %s" % srpmfn
            self.root_log(msg)
            raise Error, msg

        spec = specs[0] # if there's more than one then someone is an idiot
    
        chrootspec = spec.replace(self.rootdir, '') # get rid of rootdir prefix
        # grab the .spec file from the specdir
        # run rpmbuild -bs --nodeps specfile
        cmd = "%s -c 'rpmbuild -bs --target %s --nodeps %s' %s" % (self.config['runuser'], 
                    self.target_arch, chrootspec, self.config['chrootuser'])
        
        self.state("Running: %s" % cmd)
        (retval, output) = self.do_chroot(cmd)
        self.root_log(output)
        if retval != 0:
            raise Error, "Error building srpm from installed spec. See Root log."
            
        srpmdir = os.path.join(bd_out, 'SRPMS')
        srpms = glob.glob('%s/*.src.rpm' % srpmdir)
        if len(srpms) < 1:
            msg = "No srpm created from specfile from srpm: %s" % srpmfn
            self.root_log(msg)
            raise Error, msg
        
        srpm = srpms[0] # if there's more than one then something is weird
        
        ts = rpmUtils.transaction.initReadOnlyTransaction(root=self.rootdir)
        hdr = rpmUtils.miscutils.hdrFromPackage(ts, srpm)
        
        self.state("Getting buildreqs")
        # get text buildreqs
        buildreqs = self._text_requires_from_hdr(hdr)
        arg_string = ""
        for item in buildreqs:
            
            arg_string = arg_string + " " + "'%s'" % item

        # everything exists, okay, install them all.
        # pass build reqs (as strings) to installer
        if arg_string != "":
            (retval, output) = self.yum('resolvedep %s' % arg_string)
            self.root_log(output)
            for line in output.split('\n'):
                if line.find('No Package Found for') != -1:
                    errorpkg = line.replace('No Package Found for', '')
                    raise Error, "Cannot find build req %s. Exiting." % errorpkg
            # nothing made us exit, so we continue
            self.yum('install %s' % arg_string)

        return srpm

    def build(self, srpm):
        """build an srpm into binary rpms, capture log"""
        
        # take srpm, pass to install_build_deps() to rebuild it to a valid srpm
        # and do build deps
        srpm_out = self.install_build_deps(srpm)
        srpm_in = srpm_out.replace(self.rootdir, '')
        
        srpmfn = os.path.basename(srpm_in)
        self.state("Starting Build of %s" % srpmfn)
        # run with --nodeps b/c of the check above we know we have our build
        # deps satisfied.
        cmd = "%s -c 'rpmbuild --rebuild  --target %s --nodeps %s' %s" % (
             self.config['runuser'], self.target_arch, srpm_in, 
             self.config['chrootuser'])
        
        self.root_log(cmd)
        
        (retval, output) = self.do_chroot(cmd)
        
        self.build_log(output)
        
        if retval != 0:
            raise Error, "Error building package from %s, See build log" % srpmfn
        
        bd_out = self.rootdir + self.builddir 
        rpms = glob.glob(bd_out + '/RPMS/*.rpm')
        srpms = glob.glob(bd_out + '/SRPMS/*.rpm')
        packages = rpms + srpms
        
        self.root_log("Copying packages to result dir")
        for item in packages:
            shutil.copy2(item, self.resultdir)
        


    def close(self):
        """unmount things and clean up a bit"""
        self.root_log("Ending")
        self._umount_by_file()
        self._root_log.close()
        self._build_log.close()
        self.state("Closed")
        
        
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

        # make the procdir if we don't have it
        # mount up proc
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
                self.root_log(output)
                error("could not mount proc error was: %s" % output)
        
        # devpts
        # 
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
                self.root_log(output)
                raise Error, "could not mount /dev/pts error was: %s" % output
        

    def _umount(self, path):
    
        item = '%s/%s' % (self.rootdir, path)
        command = '%s %s' % (self.config['umount'], item)
        (retval, output) = self.do(command)
    
        if retval != 0:
            if output.find('not mounted') == -1: # this probably won't work in other LOCALES
                self.root_log(output)
                raise Error, "could not umount %s error was: %s" % (path, output)

    
    def _umount_by_file(self):
                
        mf = os.path.join(self.statedir, 'mounted-locations')
        if not os.path.exists(mf):
            return
            
        track = open(mf, 'r')
        lines = track.readlines()
        track.close()
        
        for item in lines:
            item = item.replace('\n','')
            if len(item.strip()) < 1:
                continue
            
            self._umount(item)
            
        # poof, no more file
        if os.path.exists(mf):
            os.unlink(mf)
        

    def do(self, command):
        """execute given command outside of chroot"""
        
        self.debug("Executing %s" % command)
        (status, output) = commands.getstatusoutput(command)

        if os.WIFEXITED(status):
            retval = os.WEXITSTATUS(status)

        return (retval, output)

    def do_chroot(self, command, fatal = False):
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
        (ret, output) = self.do(cmd)
        if (ret != 0) and fatal:
            self.close()
            error("Non-zero return value %d on executing %s\n" % (ret, cmd))
            sys.exit(ret)
        
        return (ret, output)

    def _text_requires_from_hdr(self, hdr):
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
        
        return rpmUtils.miscutils.unique(reqlist)
    
    def _prep_install(self):
        """prep chroot for installation"""
        # make chroot dir
        # make /dev, mount /proc
        #
        self.state("Preparing Root")
        for item in [self.basedir, self.rootdir, self.statedir, self.resultdir,
                     os.path.join(self.rootdir, 'var/lib/rpm'),
                     os.path.join(self.rootdir, 'var/log'),
                     os.path.join(self.rootdir, 'dev'),
                     os.path.join(self.rootdir, 'etc/rpm'),
                     os.path.join(self.rootdir, 'tmp'),
                     os.path.join(self.rootdir, 'var/tmp'),
                     os.path.join(self.rootdir, 'etc/yum.repos.d')]:
            self._ensure_dir(item)
        
        self._mount()

        # we need stuff
        self.state("making /dev devices")
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
                (retval, output) = self.do(cmd)
                if retval != 0:
                    self.root_log(output)
                    raise Error, "could not mknod error was: %s" % output

        # link fd to ../proc/self/fd
        devpath = os.path.join(self.rootdir, 'dev/fd')
        if not os.path.exists(devpath):
            os.symlink('../proc/self/fd', devpath)
        
        self.state("making misc files of use")
        for item in [os.path.join(self.rootdir, 'etc', 'mtab'),
                     os.path.join(self.rootdir, 'etc', 'fstab'),
                     os.path.join(self.rootdir, 'var', 'log', 'yum.log')]:
            fo = open(item, 'w')
            fo.close()
        
        self.state("making yum.conf")
        # write in yum.conf into chroot
        yumconf = os.path.join(self.rootdir, 'etc', 'yum.conf')
        yumconf_fo = open(yumconf, 'w')
        yumconf_content = self.config['yum.conf']
        yumconf_fo.write(yumconf_content)
    
        # files in /etc that need doing
        filedict = self.config['files']
        for key in filedict:
            fn = '%s%s' % (self.rootdir, key)
            fo = open(fn, 'w')
            fo.write(filedict[key])
            fo.close()

    def _make_our_user(self):
        self.state("Creating user for builds")
        # should check if the user exists first
        # make the buildusers/groups
        if not os.path.exists(self.rootdir + self.homedir):
            if not os.path.exists(os.path.join(self.rootdir, 'usr/sbin/useradd')):
                raise Error, "Could not find useradd in chroot, maybe the install failed?"
            cmd = '/usr/sbin/useradd -u %s -d %s %s' % (self.config['chrootuid'], 
                    self.homedir, self.config['chrootuser'])
            self.do_chroot(cmd, fatal = True)

    def _build_dir_setup(self):
        self.state("Setting up builddir")
        # purge the builddir, if it exists
        bd_out = '%s%s' % (self.rootdir, self.builddir)
        if os.path.exists(bd_out):
            cmd = 'rm -rf %s' % self.builddir
            self.do_chroot(cmd, fatal=True)
    
        # create dir structure
        for subdir in ('RPMS', 'SRPMS', 'SOURCES', 'SPECS', 'BUILD', 'originals'):
            cmd = "mkdir -p %s/%s" % (self.builddir, subdir)
            self.do_chroot(cmd, fatal = True)
            cmd = "chown %s.%s %s/%s" % (self.config['chrootuser'], 
               self.config['chrootgroup'], self.builddir, subdir)
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
        self._mount() # check it again
        
        # FIXME - do we need this still?
        # create /boot/kernel.h with a warning
        #self.do_chroot ("mkdir -p /boot", fatal = True)
        #self.do_chroot ("echo '#ifndef __BOOT_KERNEL_H_' > /boot/kernel.h", fatal = True)
        #self.do_chroot ("echo '#define __BOOT_KERNEL_H_' >> /boot/kernel.h", fatal = True)
        #self.do_chroot ("echo '#error This is a kernel.h generated by mach, including this indicates a build error !' >> /boot/kernel.h", fatal = True)
        #self.do_chroot ("echo '#endif /* __BOOT_KERNEL_H_ */' >> /boot/kernel.h", fatal = True)
        
def command_parse():
    """return options and args from parsing the command line"""
    
    usage = "usage: mock [options] /path/to/srpm"
    parser = OptionParser(usage=usage, version=__VERSION__)
    parser.add_option("-r", action="store", type="string", dest="chroot",
                      default='default', 
                      help="chroot name/config file name default: %default")
    parser.add_option("--no-clean", action ="store_true", dest="dirty", 
             help="do not clean chroot before building")
    parser.add_option("--arch", action ="store", dest="arch", 
             default=None, help="target build arch")
    parser.add_option("--debug", action ="store_true", dest="debug", 
             default=False, help="Output copious debugging information")
    parser.add_option("--resultdir", action="store", type="string", 
             default=None, help="path for resulting files to be put")
    parser.add_option("--statedir", action="store", type="string", default=None,
            help="path for state dirresulting files to be put")

    return parser.parse_args()
    
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
        
    # config path
    config_path='/etc/mock'
    
    # defaults
    config_opts = {}
    config_opts['basedir'] = '/var/lib/mach/roots/' # root name is automatically added to this
    config_opts['chroot'] = '/usr/sbin/mach-helper chroot'
    config_opts['mount'] = '/usr/sbin/mach-helper mount'
    config_opts['umount'] = '/usr/sbin/mach-helper umount'
    config_opts['rm'] = '/usr/sbin/mach-helper rm'
    config_opts['mknod'] = '/usr/sbin/mach-helper mknod'
    config_opts['yum'] = '/usr/sbin/mach-helper yum'
    config_opts['runuser'] = '/sbin/runuser'
    config_opts['buildgroup'] = 'build'
    config_opts['chrootuser'] = 'mockbuild'
    config_opts['chrootgroup'] = 'mockbuild'
    config_opts['chrootuid'] = 500
    config_opts['chrootgid'] = 500
    config_opts['chroothome'] = '/builddir'
    config_opts['clean'] = True
    config_opts['debug'] = False    
    config_opts['target_arch'] = 'i386'
    config_opts['files'] = {}
    config_opts['yum.conf'] = ''
    config_opts['macros'] = """
%%_topdir %s/build
%%_rpmfilename   %%%%{NAME}-%%%%{VERSION}-%%%%{RELEASE}.%%%%{ARCH}.rpm
    
""" % config_opts['chroothome']
    
    config_opts['files']['/etc/resolv.conf'] = "nameserver 192.168.1.1\n"
    config_opts['files']['/etc/hosts'] = "127.0.0.1 localhost localhost.localdomain\n"
    
    # cli option parsing
    (options, args) = command_parse()
    
    if len(args) < 1:
        error("No srpm specified - nothing to do")
        sys.exit(50)
        
    
    srpm = args[0] # we only take one and I don't care. :)
    ts = rpmUtils.transaction.initReadOnlyTransaction()
    try:
        hdr = rpmUtils.miscutils.hdrFromPackage(ts, srpm)
    except rpmUtils.RpmUtilsError, e:
        error("Specified srpm %s cannot be found/opened" % srpm)
        sys.exit(50)

    if hdr[rpm.RPMTAG_SOURCEPACKAGE] != 1:
        error("Specified srpm isn't a srpm!  Can't go on")
        sys.exit(50)
    
    
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
    
    # do some other options and stuff
    if options.arch:
        config_opts['target_arch'] = options.arch
    
    if options.dirty:
        config_opts['clean'] = False
    else:
        config_opts['clean'] = True
        
    config_opts['debug'] = options.debug
    
    if options.resultdir:
        config_opts['resultdir'] = options.resultdir

    if options.statedir:
        config_opts['statedir'] = options.resultdir


    try:
        my = Root(config_opts)
        my.prep()
        my.build(srpm)
    except Error, e:
        print e
        my.close()
        sys.exit(100)

    my.close()
    print "Results and/or logs in: %s" % my.resultdir


if __name__ == '__main__':
    main()



