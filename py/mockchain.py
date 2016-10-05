#!/usr/bin/python -tt
# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

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
from __future__ import print_function

import cgi
# pylint: disable=deprecated-module
import optparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import requests
# pylint: disable=import-error
from six.moves.urllib_parse import urlsplit

import mockbuild.util

# all of the variables below are substituted by the build system
__VERSION__ = "unreleased_version"
SYSCONFDIR = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "..", "etc")
PYTHONDIR = os.path.dirname(os.path.realpath(sys.argv[0]))
PKGPYTHONDIR = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "mockbuild")
MOCKCONFDIR = os.path.join(SYSCONFDIR, "mock")
# end build system subs

mockconfig_path = '/etc/mock'


def createrepo(path):
    if os.path.exists(path + '/repodata/repomd.xml'):
        comm = ['/usr/bin/createrepo_c', '--update', path]
    else:
        comm = ['/usr/bin/createrepo_c', path]
    cmd = subprocess.Popen(
        comm, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = cmd.communicate()
    return out, err


def parse_args(args):
    parser = optparse.OptionParser('\nmockchain -r mockcfg pkg1 [pkg2] [pkg3]')
    parser.add_option(
        '-r', '--root', default=None, dest='chroot',
        metavar="CONFIG",
        help="chroot config name/base to use in the mock build")
    parser.add_option(
        '-l', '--localrepo', default=None,
        help="local path for the local repo, defaults to making its own")
    parser.add_option(
        '-c', '--continue', default=False, action='store_true',
        dest='cont',
        help="if a pkg fails to build, continue to the next one")
    parser.add_option(
        '-a', '--addrepo', default=[], action='append',
        dest='repos',
        help="add these repo baseurls to the chroot's yum config")
    parser.add_option(
        '--recurse', default=False, action='store_true',
        help="if more than one pkg and it fails to build, try to build the rest and come back to it")
    parser.add_option(
        '--log', default=None, dest='logfile',
        help="log to the file named by this option, defaults to not logging")
    parser.add_option(
        '--tmp_prefix', default=None, dest='tmp_prefix',
        help="tmp dir prefix - will default to username-pid if not specified")
    parser.add_option(
        '-m', '--mock-option', default=[], action='append',
        dest='mock_option',
        help="option to pass directly to mock")

    opts, args = parser.parse_args(args)
    if opts.recurse:
        opts.cont = True

    if not opts.chroot:
        print("You must provide an argument to -r for the mock chroot")
        sys.exit(1)

    if len(sys.argv) < 3:
        print("You must specify at least 1 package to build")
        sys.exit(1)

    return opts, args


REPOS_ID = []


def generate_repo_id(baseurl):
    """ generate repository id for yum.conf out of baseurl """
    repoid = "/".join(baseurl.split('//')[1:]).replace('/', '_')
    repoid = re.sub(r'[^a-zA-Z0-9_]', '', repoid)
    suffix = ''
    i = 1
    while repoid + suffix in REPOS_ID:
        suffix = str(i)
        i += 1
    repoid = repoid + suffix
    REPOS_ID.append(repoid)
    return repoid


def add_local_repo(infile, destfile, baseurl, repoid=None):
    """take a mock chroot config and add a repo to it's yum.conf
       infile = mock chroot config file
       destfile = where to save out the result
       baseurl = baseurl of repo you wish to add"""
    global config_opts

    try:
        with open(infile) as f:
            code = compile(f.read(), infile, 'exec')
        # pylint: disable=exec-used
        exec(code)
        if not repoid:
            repoid = generate_repo_id(baseurl)
        else:
            REPOS_ID.append(repoid)
        localyumrepo = """
[%s]
name=%s
baseurl=%s
enabled=1
skip_if_unavailable=1
metadata_expire=0
cost=1
""" % (repoid, baseurl, baseurl)

        config_opts['yum.conf'] += localyumrepo
        with open(destfile, 'w') as br_dest:
            for k, v in list(config_opts.items()):
                br_dest.write("config_opts[%r] = %r\n" % (k, v))
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
    # heuristic here, if user pass for mock "-d foo", but we must be care to leave
    # "-d'foo bar'" or "--define='foo bar'" as is
    compiled_re_1 = re.compile(r'^(-\S)\s+(.+)')
    compiled_re_2 = re.compile(r'^(--[^ =])[ =](\.+)')
    for option in opts.mock_option:
        r_match = compiled_re_1.match(option)
        if r_match:
            mockcmd.extend([r_match.group(1), r_match.group(2)])
        else:
            r_match = compiled_re_2.match(option)
            if r_match:
                mockcmd.extend([r_match.group(1), r_match.group(2)])
            else:
                mockcmd.append(option)

    print('building %s' % s_pkg)
    mockcmd.append(pkg)
    cmd = subprocess.Popen(
        mockcmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = cmd.communicate()
    if cmd.returncode == 0:
        with open(success_file, 'w') as f:
            f.write('done\n')
        ret = 1
    else:
        if (isinstance(err, bytes)):
            err = err.decode("utf-8")
        sys.stderr.write(err)
        with open(fail_file, 'w') as f:
            f.write('undone\n')
        ret = 0

    return ret, cmd, out, err


def log(lf, msg):
    if lf:
        now = time.time()
        try:
            with open(lf, 'a') as f:
                f.write(str(now) + ':' + msg + '\n')
        except (IOError, OSError) as e:
            print('Could not write to logfile %s - %s' % (lf, str(e)))
    print(msg)


config_opts = {}


def main(args):
    opts, args = parse_args(args)
    # take mock config + list of pkgs
    cfg = opts.chroot
    pkgs = args[1:]

    global config_opts
    config_opts = mockbuild.util.load_config(mockconfig_path, cfg, None, __VERSION__, PKGPYTHONDIR)

    if not opts.tmp_prefix:
        try:
            opts.tmp_prefix = os.getlogin()
        except OSError as e:
            print("Could not find login name for tmp dir prefix add --tmp_prefix")
            sys.exit(1)
    pid = os.getpid()
    opts.uniqueext = '%s-%s' % (opts.tmp_prefix, pid)

    # create a tempdir for our local info
    if opts.localrepo:
        local_tmp_dir = os.path.abspath(opts.localrepo)
        if not os.path.exists(local_tmp_dir):
            os.makedirs(local_tmp_dir)
            os.chmod(local_tmp_dir, 0o755)
    else:
        pre = 'mock-chain-%s-' % opts.uniqueext
        local_tmp_dir = tempfile.mkdtemp(prefix=pre, dir='/var/tmp')
        os.chmod(local_tmp_dir, 0o755)

    if opts.logfile:
        opts.logfile = os.path.join(local_tmp_dir, opts.logfile)
        if os.path.exists(opts.logfile):
            os.unlink(opts.logfile)

    log(opts.logfile, "starting logfile: %s" % opts.logfile)
    opts.local_repo_dir = os.path.normpath(local_tmp_dir + '/results/' + config_opts['chroot_name'] + '/')

    if not os.path.exists(opts.local_repo_dir):
        os.makedirs(opts.local_repo_dir, mode=0o755)

    local_baseurl = "file://%s" % opts.local_repo_dir
    log(opts.logfile, "results dir: %s" % opts.local_repo_dir)
    opts.config_path = os.path.normpath(local_tmp_dir + '/configs/' + config_opts['chroot_name'] + '/')

    if not os.path.exists(opts.config_path):
        os.makedirs(opts.config_path, mode=0o755)

    log(opts.logfile, "config dir: %s" % opts.config_path)

    my_mock_config = os.path.join(opts.config_path, "{0}.cfg".format(config_opts['chroot_name']))

    # modify with localrepo
    res, msg = add_local_repo(config_opts['config_file'], my_mock_config, local_baseurl, 'local_build_repo')
    if not res:
        log(opts.logfile, "Error: Could not write out local config: %s" % msg)
        sys.exit(1)

    for baseurl in opts.repos:
        res, msg = add_local_repo(my_mock_config, my_mock_config, baseurl)
        if not res:
            log(opts.logfile, "Error: Could not add: %s to yum config in mock chroot: %s" % (baseurl, msg))
            sys.exit(1)

    # these files needed from the mock.config dir to make mock run
    for fn in ['site-defaults.cfg', 'logging.ini']:
        pth = mockconfig_path + '/' + fn
        shutil.copyfile(pth, opts.config_path + '/' + fn)

    # createrepo on it
    err = createrepo(opts.local_repo_dir)[1]
    if err.strip():
        log(opts.logfile, "Error making local repo: %s" % opts.local_repo_dir)
        log(opts.logfile, "Err: %s" % err)
        sys.exit(1)

    download_dir = tempfile.mkdtemp()
    downloaded_pkgs = {}
    built_pkgs = []
    try_again = True
    to_be_built = pkgs
    return_code = 0
    num_of_tries = 0
    while try_again:
        num_of_tries += 1
        failed = []
        for pkg in to_be_built:
            if not pkg.endswith('.rpm'):
                log(opts.logfile, "%s doesn't appear to be an rpm - skipping" % pkg)
                failed.append(pkg)
                continue

            elif pkg.startswith('http://') or pkg.startswith('https://') or pkg.startswith('ftp://'):
                url = pkg
                try:
                    log(opts.logfile, 'Fetching %s' % url)
                    r = requests.get(url)
                    # pylint: disable=no-member
                    if r.status_code == requests.codes.ok:
                        fn = urlsplit(r.url).path.rsplit('/', 1)[1]
                        if 'content-disposition' in r.headers:
                            _, params = cgi.parse_header(r.headers['content-disposition'])
                            if 'filename' in params and params['filename']:
                                fn = params['filename']
                        pkg = download_dir + '/' + fn
                        with open(pkg, 'wb') as fd:
                            for chunk in r.iter_content(4096):
                                fd.write(chunk)
                except Exception as e:
                    log(opts.logfile, 'Error Downloading %s: %s' % (url, str(e)))
                    failed.append(url)
                    continue
                else:
                    downloaded_pkgs[pkg] = url
            log(opts.logfile, "Start build: %s" % pkg)
            ret = do_build(opts, config_opts['chroot_name'], pkg)[0]
            log(opts.logfile, "End build: %s" % pkg)
            if ret == 0:
                failed.append(pkg)
                log(opts.logfile, "Error building %s." % os.path.basename(pkg))
                if opts.recurse:
                    log(opts.logfile, "Will try to build again (if some other package will succeed).")
                else:
                    log(opts.logfile, "See logs/results in %s" % opts.local_repo_dir)
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

        if failed and opts.recurse:
            if len(failed) != len(to_be_built):
                to_be_built = failed
                try_again = True
                log(opts.logfile, 'Some package succeeded, some failed.')
                log(opts.logfile, 'Trying to rebuild %s failed pkgs, because --recurse is set.' % len(failed))
            else:
                log(opts.logfile, "Tried %s times - following pkgs could not be successfully built:" % num_of_tries)
                for pkg in failed:
                    msg = pkg
                    if pkg in downloaded_pkgs:
                        msg = downloaded_pkgs[pkg]
                    log(opts.logfile, msg)
                try_again = False
        else:
            try_again = False
            if failed:
                return_code = 2

    # cleaning up our download dir
    shutil.rmtree(download_dir, ignore_errors=True)

    log(opts.logfile, "Results out to: %s" % opts.local_repo_dir)
    log(opts.logfile, "Pkgs built: %s" % len(built_pkgs))
    if built_pkgs:
        if failed:
            if len(built_pkgs):
                log(opts.logfile, "Some packages successfully built in this order:")
        else:
            log(opts.logfile, "Packages successfully built in this order:")
        for pkg in built_pkgs:
            log(opts.logfile, pkg)
    return return_code

if __name__ == "__main__":
    sys.exit(main(sys.argv))
