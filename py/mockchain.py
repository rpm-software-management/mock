#!/usr/bin/python -tt
# by skvidal@fedoraproject.org
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.
# copyright 2012 Red Hat, Inc.

# SUMMARY
# mockchain
# take a mock config and a series of srpms
# rebuild them one at a time
# adding each to a local repo
# so they are available as build deps to next pkg being built

import sys
import subprocess
import os
import optparse
import tempfile
import shutil
from urlgrabber import grabber
import time

import mockbuild.util

# all of the variables below are substituted by the build system
__VERSION__ = "unreleased_version"
SYSCONFDIR = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "..", "etc")
PYTHONDIR = os.path.dirname(os.path.realpath(sys.argv[0]))
PKGPYTHONDIR = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "mockbuild")
MOCKCONFDIR = os.path.join(SYSCONFDIR, "mock")
# end build system subs

mockconfig_path='/etc/mock'

def createrepo(path):
    if os.path.exists(path + '/repodata/repomd.xml'):
        comm = ['/usr/bin/createrepo', '--update', path]
    else:
        comm = ['/usr/bin/createrepo', path]
    cmd = subprocess.Popen(comm,
             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = cmd.communicate()
    return out, err

def parse_args(args):
    parser = optparse.OptionParser('\nmockchain -r mockcfg pkg1 [pkg2] [pkg3]')
    parser.add_option('-r', '--root', default=None, dest='chroot',
            help="chroot config name/base to use in the mock build")
    parser.add_option('-l', '--localrepo', default=None,
            help="local path for the local repo, defaults to making its own")
    parser.add_option('-c', '--continue', default=False, action='store_true',
            dest='cont',
            help="if a pkg fails to build, continue to the next one")
    parser.add_option('-a','--addrepo', default=[], action='append',
            dest='repos',
            help="add these repo baseurls to the chroot's yum config")
    parser.add_option('--recurse', default=False, action='store_true',
            help="if more than one pkg and it fails to build, try to build the rest and come back to it")
    parser.add_option('--log', default=None, dest='logfile',
            help="log to the file named by this option, defaults to not logging")
    parser.add_option('--tmp_prefix', default=None, dest='tmp_prefix',
            help="tmp dir prefix - will default to username-pid if not specified")


    #FIXME?
    # figure out how to pass other args to mock?

    opts, args = parser.parse_args(args)
    if opts.recurse:
        opts.cont = True

    if not opts.chroot:
        print "You must provide an argument to -r for the mock chroot"
        sys.exit(1)


    if len(sys.argv) < 3:
        print "You must specifiy at least 1 package to build"
        sys.exit(1)


    return opts, args

def add_local_repo(infile, destfile, baseurl, repoid=None):
    """take a mock chroot config and add a repo to it's yum.conf
       infile = mock chroot config file
       destfile = where to save out the result
       baseurl = baseurl of repo you wish to add"""
    global config_opts

    try:
        execfile(infile)
        if not repoid:
            repoid=baseurl.split('//')[1].replace('/','_')
        localyumrepo="""
[%s]
name=%s
baseurl=%s
enabled=1
skip_if_unavailable=1
metadata_expire=30
cost=1
""" % (repoid, baseurl, baseurl)

        config_opts['yum.conf'] += localyumrepo
        br_dest = open(destfile, 'w')
        for k,v in config_opts.items():
            br_dest.write("config_opts[%r] = %r\n" % (k, v))
        br_dest.close()
        return True, ''
    except (IOError, OSError):
        return False, "Could not write mock config to %s" % destfile

    return True, ''

def do_build(opts, cfg, pkg):

    # returns 0, cmd, out, err = failure
    # returns 1, cmd, out, err  = success
    # returns 2, None, None, None = already built

    s_pkg = os.path.basename(pkg)
    pdn = s_pkg.replace('.src.rpm', '')
    resdir = '%s/%s' % (opts.local_repo_dir, pdn)
    resdir = os.path.normpath(resdir)
    if not os.path.exists(resdir):
        os.makedirs(resdir)

    success_file = resdir + '/success'
    fail_file = resdir + '/fail'

    if os.path.exists(success_file):
        return 2, None, None, None

    # clean it up if we're starting over :)
    if os.path.exists(fail_file):
        os.unlink(fail_file)

    mockcmd = ['/usr/bin/mock',
               '--configdir', opts.config_path,
               '--resultdir', resdir,
               '--uniqueext', opts.uniqueext,
               '-r', cfg, ]
    print 'building %s' % s_pkg
    mockcmd.append(pkg)
    cmd = subprocess.Popen(mockcmd,
           stdout=subprocess.PIPE,
           stderr=subprocess.PIPE )
    out, err = cmd.communicate()
    if cmd.returncode == 0:
        open(success_file, 'w').write('done\n')
        ret = 1
    else:
        open(fail_file, 'w').write('undone\n')
        ret = 0

    return ret, cmd, out, err


def log(lf, msg):
    if lf:
        now = time.time()
        try:
            open(lf, 'a').write(str(now) + ':' + msg + '\n')
        except (IOError, OSError), e:
            print 'Could not write to logfile %s - %s' % (lf, str(e))
    print msg


config_opts = {}

def main(args):

    global config_opts

    config_opts = mockbuild.util.setup_default_config_opts(os.getgid(), __VERSION__, PKGPYTHONDIR)

    opts, args = parse_args(args)

    # take mock config + list of pkgs
    cfg=opts.chroot
    pkgs=args[1:]
    mockcfg = mockconfig_path + '/' + cfg + '.cfg'

    if not os.path.exists(mockcfg):
        print "could not find config: %s" % mockcfg
        sys.exit(1)


    if not opts.tmp_prefix:
        try:
            opts.tmp_prefix = os.getlogin()
        except OSError, e:
            print "Could not find login name for tmp dir prefix add --tmp_prefix"
            sys.exit(1)
    pid = os.getpid()
    opts.uniqueext = '%s-%s' % (opts.tmp_prefix, pid)


    # create a tempdir for our local info
    if opts.localrepo:
        local_tmp_dir = os.path.abspath(opts.localrepo)
        if not os.path.exists(local_tmp_dir):
            os.makedirs(local_tmp_dir)
    else:
        pre = 'mock-chain-%s-' % opts.uniqueext
        local_tmp_dir = tempfile.mkdtemp(prefix=pre, dir='/var/tmp')

    os.chmod(local_tmp_dir, 0755)

    if opts.logfile:
        opts.logfile = os.path.join(local_tmp_dir, opts.logfile)
        if os.path.exists(opts.logfile):
            os.unlink(opts.logfile)

    log(opts.logfile, "starting logfile: %s" % opts.logfile)
    opts.local_repo_dir = os.path.normpath(local_tmp_dir + '/results/' + cfg + '/')

    if not os.path.exists(opts.local_repo_dir):
        os.makedirs(opts.local_repo_dir, mode=0755)

    local_baseurl="file://%s" % opts.local_repo_dir
    log(opts.logfile, "results dir: %s" % opts.local_repo_dir)
    opts.config_path = os.path.normpath(local_tmp_dir + '/configs/' + cfg + '/')

    if not os.path.exists(opts.config_path):
        os.makedirs(opts.config_path, mode=0755)

    log(opts.logfile, "config dir: %s" % opts.config_path)

    my_mock_config = opts.config_path + '/' + os.path.basename(mockcfg)

    # modify with localrepo
    res, msg = add_local_repo(mockcfg, my_mock_config, local_baseurl, 'local_build_repo')
    if not res:
         log(opts.logfile, "Error: Could not write out local config: %s" % msg)
         sys.exit(1)

    for baseurl in opts.repos:
        res, msg =  add_local_repo(my_mock_config, my_mock_config, baseurl)
        if not res:
            log(opts.logfile, "Error: Could not add: %s to yum config in mock chroot: %s" % (baseurl, msg))
            sys.exit(1)


    # these files needed from the mock.config dir to make mock run
    for fn in ['site-defaults.cfg', 'logging.ini']:
        pth = mockconfig_path + '/' + fn
        shutil.copyfile(pth, opts.config_path + '/' + fn)


    # createrepo on it
    out, err = createrepo(opts.local_repo_dir)
    if err.strip():
        log(opts.logfile, "Error making local repo: %s" % opts.local_repo_dir)
        log(opts.logfile, "Err: %s" % err)
        sys.exit(1)


    download_dir = tempfile.mkdtemp()
    downloaded_pkgs = {}
    built_pkgs = []
    try_again = True
    to_be_built = pkgs
    while try_again:
        failed = []
        for pkg in to_be_built:
            if not pkg.endswith('.rpm'):
                log(opts.logfile, "%s doesn't appear to be an rpm - skipping" % pkg)
                failed.append(pkg)
                continue

            elif pkg.startswith('http://') or pkg.startswith('https://'):
                url = pkg
                cwd = os.getcwd()
                os.chdir(download_dir)
                try:
                    log(opts.logfile, 'Fetching %s' % url)
                    ug = grabber.URLGrabber()
                    fn = ug.urlgrab(url)
                    pkg = download_dir + '/' + fn
                except Exception, e:
                    log(opts.logfile, 'Error Downloading %s: %s' % (url, str(e)))
                    failed.append(url)
                    os.chdir(cwd)
                    continue
                else:
                    os.chdir(cwd)
                    downloaded_pkgs[pkg] = url
            log(opts.logfile, "Start build: %s" % pkg)
            ret, cmd, out, err = do_build(opts, cfg, pkg)
            log(opts.logfile, "End build: %s" % pkg)
            if ret == 0:
                if opts.recurse:
                    failed.append(pkg)
                    log(opts.logfile, "Error building %s, will try again" % os.path.basename(pkg))
                else:
                    log(opts.logfile,"Error building %s" % os.path.basename(pkg))
                    log(opts.logfile,"See logs/results in %s" % opts.local_repo_dir)
                    if not opts.cont:
                        sys.exit(1)

            elif ret == 1:
                log(opts.logfile, "Success building %s" % os.path.basename(pkg))
                built_pkgs.append(pkg)
                # createrepo with the new pkgs
                out, err = createrepo(opts.local_repo_dir)
                if err.strip():
                    log(opts.logfile, "Error making local repo: %s" % opts.local_repo_dir)
                    log(opts.logfile, "Err: %s" % err)
            elif ret == 2:
                log(opts.logfile, "Skipping already built pkg %s" % os.path.basename(pkg))

        if failed:
            if len(failed) != len(to_be_built):
                to_be_built = failed
                try_again = True
                log(opts.logfile, 'Trying to rebuild %s failed pkgs' % len(failed))
            else:
                log(opts.logfile, "Tried twice - following pkgs could not be successfully built:")
                for pkg in failed:
                    msg = pkg
                    if pkg in downloaded_pkgs:
                        msg = downloaded_pkgs[pkg]
                    log(opts.logfile, msg)

                try_again = False
        else:
            try_again = False

    # cleaning up our download dir
    shutil.rmtree(download_dir, ignore_errors=True)

    log(opts.logfile, "Results out to: %s" % opts.local_repo_dir)
    log(opts.logfile, "Pkgs built: %s" % len(built_pkgs))
    log(opts.logfile, "Packages successfully built in this order:")
    for pkg in built_pkgs:
        log(opts.logfile, pkg)

if __name__ == "__main__":
    main(sys.argv)
    sys.exit(0)
