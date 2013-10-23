#!/usr/bin/python -tt
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# Originally written by Seth Vidal
# Sections taken from Mach by Thomas Vander Stichele
# Major reorganization and adaptation by Michael Brown
# Copyright (C) 2007 Michael E Brown <mebrown@michaels-house.net>
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.
"""
    usage:
           mock [options] {--init|--clean|--scrub=[all,chroot,cache,root-cache,c-cache,yum-cache]}
           mock [options] [--rebuild] /path/to/srpm(s)
           mock [options] --buildsrpm {--spec /path/to/spec --sources /path/to/src|--scm-enable [--scm-option key=value]}
           mock [options] {--shell|--chroot} <cmd>
           mock [options] --installdeps {SRPM|RPM}
           mock [options] --install PACKAGE
           mock [options] --copyin path [..path] destination
           mock [options] --copyout path [..path] destination
           mock [options] --scm-enable [--scm-option key=value]
"""

# library imports
import ConfigParser
import grp
import logging
import logging.config
import os
import os.path
import pwd
import sys
import time
from optparse import OptionParser
from glob import glob

# all of the variables below are substituted by the build system
__VERSION__ = "unreleased_version"
SYSCONFDIR = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "..", "etc")
PYTHONDIR = os.path.dirname(os.path.realpath(sys.argv[0]))
PKGPYTHONDIR = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "mockbuild")
MOCKCONFDIR = os.path.join(SYSCONFDIR, "mock")
# end build system subs

# import all mockbuild.* modules after this.
sys.path.insert(0, PYTHONDIR)

# set up basic logging until config file can be read
FORMAT = "%(levelname)s: %(message)s"
logging.basicConfig(format=FORMAT, level=logging.WARNING)
log = logging.getLogger()

# our imports
import mockbuild.exception
from mockbuild.trace_decorator import traceLog, decorate
import mockbuild.backend
import mockbuild.uid
import mockbuild.util

def scrub_callback(option, opt, value, parser):
    parser.values.scrub.append(value)
    parser.values.mode = "clean"

def command_parse(config_opts):
    """return options and args from parsing the command line"""
    parser = OptionParser(usage=__doc__, version=__VERSION__)

    # modes (basic commands)
    parser.add_option("--rebuild", action="store_const", const="rebuild",
                      dest="mode", default='rebuild',
                      help="rebuild the specified SRPM(s)")
    parser.add_option("--buildsrpm", action="store_const", const="buildsrpm",
                      dest="mode",
                      help="Build a SRPM from spec (--spec ...) and sources (--sources ...) or from SCM")
    parser.add_option("--shell", action="store_const",
                      const="shell", dest="mode",
                      help="run the specified command interactively within the chroot."
                           " Default command: /bin/sh")
    parser.add_option("--chroot", action="store_const",
                      const="chroot", dest="mode",
                      help="run the specified command noninteractively within the chroot.")
    parser.add_option("--clean", action="store_const", const="clean",
                      dest="mode",
                      help="completely remove the specified chroot")
    scrub_choices = ('chroot', 'cache', 'root-cache', 'c-cache', 'yum-cache', 'all')
    scrub_metavar = "[all|chroot|cache|root-cache|c-cache|yum-cache]"
    parser.add_option("--scrub", action="callback", type="choice", default=[],
                      choices=scrub_choices, metavar=scrub_metavar,
                      callback=scrub_callback,
                      help="completely remove the specified chroot or cache dir or all of the chroot and cache")
    parser.add_option("--init", action="store_const", const="init", dest="mode",
                      help="initialize the chroot, do not build anything")
    parser.add_option("--installdeps", action="store_const", const="installdeps",
                      dest="mode",
                      help="install build dependencies for a specified SRPM")
    parser.add_option("--install", action="store_const", const="install",
                      dest="mode",
                      help="install packages using yum")
    parser.add_option("--update", action="store_const", const="update",
                      dest="mode",
                      help="update installed packages using yum")
    parser.add_option("--remove", action="store_const", const="remove",
                      dest="mode",
                      help="remove packages using yum")
    parser.add_option("--orphanskill", action="store_const", const="orphanskill",
                      dest="mode",
                      help="Kill all processes using specified buildroot.")

    parser.add_option("--copyin", action="store_const", const="copyin",
                      dest="mode",
                      help="Copy file(s) into the specified chroot")

    parser.add_option("--copyout", action="store_const", const="copyout",
                      dest="mode",
                      help="Copy file(s) from the specified chroot")

    # options
    parser.add_option("-r", "--root", action="store", type="string", dest="chroot",
                      help="chroot name/config file name default: %default",
                      default='default')

    parser.add_option("--offline", action="store_false", dest="online",
                      default=True,
                      help="activate 'offline' mode.")

    parser.add_option("--no-clean", action ="store_false", dest="clean",
                      help="do not clean chroot before building", default=True)
    parser.add_option("--cleanup-after", action ="store_true",
                      dest="cleanup_after", default=None,
                      help="Clean chroot after building. Use with --resultdir."
                           " Only active for 'rebuild'.")
    parser.add_option("--no-cleanup-after", action ="store_false",
                      dest="cleanup_after", default=None,
                      help="Dont clean chroot after building. If automatic"
                           " cleanup is enabled, use this to disable.", )
    parser.add_option("--cache-alterations", action="store_true",
                      dest="cache_alterations", default=False,
                      help="Rebuild the root cache after making alterations to the chroot"
                           " (i.e. --install). Only useful when using tmpfs plugin.")
    parser.add_option("--arch", action ="store", dest="arch",
                      default=None, help="Sets kernel personality().")
    parser.add_option("--target", action ="store", dest="rpmbuild_arch",
                      default=None, help="passed to rpmbuild as --target")
    parser.add_option("-D", "--define", action="append", dest="rpmmacros",
                      default=[], type="string", metavar="'MACRO EXPR'",
                      help="define an rpm macro (may be used more than once)")
    parser.add_option("--with", action="append", dest="rpmwith",
                      default=[], type="string", metavar="option",
                      help="enable configure option for build (may be used more than once)")
    parser.add_option("--without", action="append", dest="rpmwithout",
                      default=[], type="string", metavar="option",
                      help="disable configure option for build (may be used more than once)")
    parser.add_option("--resultdir", action="store", type="string",
                      default=None, help="path for resulting files to be put")
    parser.add_option("--uniqueext", action="store", type="string",
                      default=None,
                      help="Arbitrary, unique extension to append to buildroot"
                           " directory name")
    parser.add_option("--configdir", action="store", dest="configdir",
                      default=None,
                      help="Change where config files are found")
    parser.add_option("--rpmbuild_timeout", action="store",
                      dest="rpmbuild_timeout", type="int", default=None,
                      help="Fail build if rpmbuild takes longer than 'timeout'"
                           " seconds ")
    parser.add_option("--unpriv", action="store_true", default=False,
                      help="Drop privileges before running command when using --chroot")
    parser.add_option("--cwd", action="store", default=None,
                      metavar="DIR",
                      help="Change to the specified directory (relative to the chroot)"
                           " before running command when using --chroot")

    parser.add_option("--spec", action="store",
                      help="Specifies spec file to use to build an SRPM (used only with --buildsrpm)")
    parser.add_option("--sources", action="store",
                      help="Specifies sources (either a single file or a directory of files)"
                      "to use to build an SRPM (used only with --buildsrpm)")

    # verbosity
    parser.add_option("-v", "--verbose", action="store_const", const=2,
                      dest="verbose", default=1, help="verbose build")
    parser.add_option("-q", "--quiet", action="store_const", const=0,
                      dest="verbose", help="quiet build")
    parser.add_option("--trace", action="store_true", default=False,
                      dest="trace", help="Enable internal mock tracing output.")

    # plugins
    parser.add_option("--enable-plugin", action="append",
                      dest="enabled_plugins", type="string", default=[],
                      help="Enable plugin. Currently-available plugins: %s"
                        % repr(config_opts['plugins']))
    parser.add_option("--disable-plugin", action="append",
                      dest="disabled_plugins", type="string", default=[],
                      help="Disable plugin. Currently-available plugins: %s"
                           % repr(config_opts['plugins']))
    parser.add_option("--plugin-option", action="append", dest="plugin_opts",
                      default=[], type="string",
                      metavar="PLUGIN:KEY=VALUE",
                      help="define an plugin option (may be used more than once)")

    parser.add_option("--print-root-path", help="print path to chroot root",
                      dest="printrootpath", action="store_true",
                      default=False)

    # SCM options
    parser.add_option("--scm-enable", help="build from SCM repository",
                      dest="scm", action="store_true",
                      default=None)
    parser.add_option("--scm-option", action="append", dest="scm_opts",
                      default=[], type="string",
                      help="define an SCM option (may be used more than once)")

    (options, args) = parser.parse_args()

    # handle old-style commands
    if len(args) and args[0] in ('chroot', 'shell',
            'rebuild', 'install', 'installdeps', 'remove', 'init', 'clean'):
        options.mode = args[0]
        args = args[1:]

    # explicitly disallow multiple targets in --target argument
    if options.rpmbuild_arch:
        if options.rpmbuild_arch.find(',') != -1:
                   raise mockbuild.exception.BadCmdline, "--target option accepts only one arch. Invalid: %s" % options.rpmbuild_arch

    if options.mode == 'buildsrpm' and not (options.spec and options.sources):
        if not options.scm:
            raise mockbuild.exception.BadCmdline, "Must specify both --spec and --sources with --buildsrpm"
    if options.spec:
        options.spec = os.path.expanduser(options.spec)
    if options.sources:
        options.sources = os.path.expanduser(options.sources)

    return (options, args)

decorate(traceLog())
def check_arch_combination(target_arch, config_opts):
    try:
        legal = config_opts['legal_host_arches']
    except KeyError:
        return
    host_arch = os.uname()[-1]
    if host_arch not in legal:
        raise mockbuild.exception.InvalidArchitecture(
            "Cannot build target %s on arch %s" % (target_arch, host_arch))

decorate(traceLog())
def do_rebuild(config_opts, chroot, srpms):
    "rebuilds a list of srpms using provided chroot"
    if len(srpms) < 1:
        log.critical("No package specified to rebuild command.")
        sys.exit(50)

    # check that everything is kosher. Raises exception on error
    for hdr in mockbuild.util.yieldSrpmHeaders(srpms):
        pass

    start = time.time()
    try:
        for srpm in srpms:
            start = time.time()
            log.info("Start(%s)  Config(%s)" % (srpm, chroot.sharedRootName))
            if config_opts['clean'] and chroot.state() != "clean" \
                    and not config_opts['scm']:
                chroot.clean()
            chroot.init()
            chroot.build(srpm, timeout=config_opts['rpmbuild_timeout'])
            elapsed = time.time() - start
            log.info("Done(%s) Config(%s) %d minutes %d seconds"
                % (srpm, config_opts['chroot_name'], elapsed//60, elapsed%60))
            log.info("Results and/or logs in: %s" % chroot.resultdir)

        if config_opts["cleanup_on_success"]:
            log.info("Cleaning up build root ('clean_on_success=True')")
            chroot.clean()

        if config_opts["createrepo_on_rpms"]:
            log.info("Running createrepo on binary rpms in resultdir")
            chroot.uidManager.dropPrivsTemp()
            cmd = config_opts["createrepo_command"].split()
            cmd.append(chroot.resultdir)
            mockbuild.util.do(cmd)
            chroot.uidManager.restorePrivs()

    except (Exception, KeyboardInterrupt):
        elapsed = time.time() - start
        log.error("Exception(%s) Config(%s) %d minutes %d seconds"
            % (srpm, chroot.sharedRootName, elapsed//60, elapsed%60))
        log.info("Results and/or logs in: %s" % chroot.resultdir)
        if config_opts["cleanup_on_failure"]:
            log.info("Cleaning up build root ('clean_on_failure=True')")
            chroot.clean()
        raise

def do_buildsrpm(config_opts, chroot, options, args):
    # verify the input command line arguments actually exist
    if not os.path.isfile(options.spec):
        raise mockbuild.exception.BadCmdline, \
            "input specfile does not exist: %s" % options.spec
    if not os.path.isdir(options.sources):
        raise mockbuild.exception.BadCmdline, \
            "input sources directory does not exist: %s" % options.sources
    start = time.time()
    try:
        log.info("Start(%s)  Config(%s)" % (os.path.basename(options.spec), chroot.sharedRootName))
        if config_opts['clean'] and chroot.state() != "clean":
            chroot.clean()
        chroot.init()

        srpm = chroot.buildsrpm(spec=options.spec, sources=options.sources, timeout=config_opts['rpmbuild_timeout'])
        elapsed = time.time() - start
        log.info("Done(%s) Config(%s) %d minutes %d seconds"
            % (os.path.basename(options.spec), config_opts['chroot_name'], elapsed//60, elapsed%60))
        log.info("Results and/or logs in: %s" % chroot.resultdir)

        if config_opts["cleanup_on_success"]:
            log.info("Cleaning up build root ('clean_on_success=True')")
            chroot.clean()

        return srpm

    except (Exception, KeyboardInterrupt):
        elapsed = time.time() - start
        log.error("Exception(%s) Config(%s) %d minutes %d seconds"
            % (os.path.basename(options.spec), chroot.sharedRootName, elapsed//60, elapsed%60))
        log.info("Results and/or logs in: %s" % chroot.resultdir)
        if config_opts["cleanup_on_failure"]:
            log.info("Cleaning up build root ('clean_on_failure=True')")
            chroot.clean()
        raise

def rootcheck():
    "verify mock was started correctly (either by sudo or consolehelper)"
    # if we're root due to sudo or consolehelper, we're ok
    # if not raise an exception and bail
    if os.getuid() == 0 and not (os.environ.get("SUDO_UID") or os.environ.get("USERHELPER_UID")):
        raise RuntimeError, "mock will not run from the root account (needs an unprivileged uid so it can drop privs)"

def groupcheck(unprivGid, tgtGid):
    "verify that the user running mock is part of the correct group"
    # verify that we're in the correct group (so all our uid/gid manipulations work)
    inmockgrp = False
    members = []
    for gid in os.getgroups() + [unprivGid]:
        name = grp.getgrgid(gid).gr_name
        if gid == tgtGid:
            inmockgrp = True
            break
        members.append(name)
    if not inmockgrp:
        name = grp.getgrgid(tgtGid).gr_name
        raise RuntimeError("Must be member of '%s' group to run mock! (%s)" %
                           (name, ", ".join(members)))

def main(ret):
    "Main executable entry point."

    # initial sanity check for correct invocation method
    rootcheck()

    # drop unprivileged to parse args, etc.
    #   uidManager saves current real uid/gid which are unprivileged (callers)
    #   due to suid helper, our current effective uid is 0
    #   also supports being run by sudo
    #
    #   setuid wrapper has real uid = unpriv,  effective uid = 0
    #   sudo sets real/effective = 0, and sets env vars
    #   setuid wrapper clears environment, so there wont be any conflict between these two

    # old setuid wrapper
    unprivUid = os.getuid()
    unprivGid = os.getgid()

    mockgid = grp.getgrnam('mock').gr_gid

    # sudo
    if os.environ.get("SUDO_UID") is not None:
        unprivUid = int(os.environ['SUDO_UID'])
        username = os.environ.get("SUDO_USER")
        os.setgroups((mockgid,))
        unprivGid = int(os.environ['SUDO_GID'])

    # consolehelper
    if os.environ.get("USERHELPER_UID") is not None:
        unprivUid = int(os.environ['USERHELPER_UID'])
        username = pwd.getpwuid(unprivUid)[0]
        os.setgroups((mockgid,))
        unprivGid = pwd.getpwuid(unprivUid)[3]

    uidManager = mockbuild.uid.uidManager(unprivUid, unprivGid)
    # go unpriv only when root to make --help etc work for non-mock users
    if os.geteuid() == 0:
        uidManager.dropPrivsTemp()

    # defaults
    config_opts = mockbuild.util.setup_default_config_opts(unprivUid, __VERSION__, PKGPYTHONDIR)

    (options, args) = command_parse(config_opts)

    if options.printrootpath:
        options.verbose = 0

    # config path -- can be overridden on cmdline
    config_path = MOCKCONFDIR
    if options.configdir:
        config_path = options.configdir

    # array to save config paths
    config_opts['config_paths'] = []

    # Read in the config files: default, and then user specified
    for cfg in ( os.path.join(config_path, 'site-defaults.cfg'), '%s/%s.cfg' % (config_path, options.chroot)):
        if os.path.exists(cfg):
            config_opts['config_paths'].append(cfg)
            execfile(cfg)
        else:
            log.error("Could not find required config file: %s" % cfg)
            if options.chroot == "default": log.error("  Did you forget to specify the chroot to use with '-r'?")
            sys.exit(1)

    # Read user specific config file
    cfg = os.path.join(os.path.expanduser('~' + pwd.getpwuid(os.getuid())[0]), '.mock/user.cfg')
    if os.path.exists(cfg):
        config_opts['config_paths'].append(cfg)
        execfile(cfg)

    # allow a different mock group to be specified
    if config_opts['chrootgid'] != mockgid:
        uidManager.restorePrivs()
        os.setgroups((mockgid, config_opts['chrootgid']))
        uidManager.dropPrivsTemp()

    # verify that our unprivileged uid is in the mock group
    groupcheck(unprivGid, config_opts['chrootgid'])

    # configure logging
    config_opts['chroot_name'] = options.chroot
    log_ini = os.path.join(config_path, config_opts["log_config_file"])
    if not os.path.exists(log_ini):
        log.error("Could not find required logging config file: %s" % log_ini)
        sys.exit(50)
    try:
        if not os.path.exists(log_ini): raise IOError, "Could not find log config file %s" % log_ini
        log_cfg = ConfigParser.ConfigParser()
        logging.config.fileConfig(log_ini)
        log_cfg.read(log_ini)
    except (IOError, OSError, ConfigParser.NoSectionError), exc:
        log.error("Log config file(%s) not correctly configured: %s" % (log_ini, exc))
        sys.exit(50)

    try:
        # set up logging format strings
        config_opts['build_log_fmt_str'] = log_cfg.get("formatter_%s" % config_opts['build_log_fmt_name'], "format", raw=1)
        config_opts['root_log_fmt_str'] = log_cfg.get("formatter_%s" % config_opts['root_log_fmt_name'], "format", raw=1)
        config_opts['state_log_fmt_str'] = log_cfg.get("formatter_%s" % config_opts['state_log_fmt_name'], "format", raw=1)
    except ConfigParser.NoSectionError, exc:
        log.error("Log config file (%s) missing required section: %s" % (log_ini, exc))
        sys.exit(50)

    # set logging verbosity
    if options.verbose == 0:
        log.handlers[0].setLevel(logging.WARNING)
        tmplog = logging.getLogger("mockbuild.Root.state")
        if tmplog.handlers:
            tmplog.handlers[0].setLevel(logging.WARNING)
    elif options.verbose == 1:
        log.handlers[0].setLevel(logging.INFO)
    elif options.verbose == 2:
        log.handlers[0].setLevel(logging.DEBUG)
        logging.getLogger("mockbuild.Root.build").propagate = 1
        logging.getLogger("mockbuild").propagate = 1

    # enable tracing if requested
    logging.getLogger("trace").propagate=0
    if options.trace:
        logging.getLogger("trace").propagate=1

    # cmdline options override config options
    #set_config_opts_per_cmdline(config_opts, options, args)
    mockbuild.util.set_config_opts_per_cmdline(config_opts, options, args)

    # verify that we're not trying to build an arch that we can't
    check_arch_combination(config_opts['rpmbuild_arch'], config_opts)

    # default /etc/hosts contents
    if not config_opts['use_host_resolv'] and not config_opts['files'].has_key('etc/hosts'):
        config_opts['files']['etc/hosts'] = '''
127.0.0.1 localhost localhost.localdomain
::1       localhost localhost.localdomain localhost6 localhost6.localdomain6
'''

    # Fetch and prepare sources from SCM
    if config_opts['scm']:
        scmWorker = mockbuild.scm.scmWorker(log, config_opts['scm_opts'])
        scmWorker.get_sources()
        (options.sources, options.spec) = scmWorker.prepare_sources()

    # security cleanup (don't need/want this in the chroot)
    if os.environ.has_key('SSH_AUTH_SOCK'):
        del os.environ['SSH_AUTH_SOCK']

    # elevate privs
    uidManager._becomeUser(0, 0)

    # do whatever we're here to do
    log.info("mock.py version %s starting..." % __VERSION__)
    chroot = mockbuild.backend.Root(config_opts, uidManager)

    chroot.start("run")

    if options.printrootpath:
        print chroot.makeChrootPath('')
        sys.exit(0)

    # dump configuration to log
    log.debug("mock final configuration:")
    for k, v in config_opts.items():
        log.debug("    %s:  %s" % (k, v))

    ret["chroot"] = chroot
    ret["config_opts"] = config_opts
    os.umask(002)
    os.environ["HOME"] = chroot.homedir

    # New namespace starting from here
    base_unshare_flags = mockbuild.util.CLONE_NEWNS
    extended_unshare_flags = base_unshare_flags|mockbuild.util.CLONE_NEWIPC|mockbuild.util.CLONE_NEWUTS
    try:
        mockbuild.util.unshare(extended_unshare_flags)
    except mockbuild.exception.UnshareFailed, e:
        log.debug("unshare(%d) failed, falling back to unshare(%d)" % (extended_unshare_flags, base_unshare_flags))
        try:
            mockbuild.util.unshare(base_unshare_flags)
        except mockbuild.exception.UnshareFailed, e:
            log.error("Namespace unshare failed.")
            sys.exit(e.resultcode)

    # set personality (ie. setarch)
    if config_opts['internal_setarch']:
        mockbuild.util.condPersonality(config_opts['target_arch'])

    if options.mode == 'init':
        if config_opts['clean']:
            chroot.clean()
        chroot.init()

    elif options.mode == 'clean':
        if len(options.scrub) == 0:
            chroot.clean()
        else:
            chroot.scrub(options.scrub)

    elif options.mode == 'shell':
        if not os.path.exists(chroot.makeChrootPath()):
            raise mockbuild.exception.ChrootNotInitialized, \
                "chroot %s not initialized!" % chroot.makeChrootPath()
        if len(args):
            cmd = ' '.join(args)
        else:
            cmd = None
        sys.exit(chroot.shell(options, cmd))

    elif options.mode == 'chroot':
        if not os.path.exists(chroot.makeChrootPath()):
            raise mockbuild.exception.ChrootNotInitialized, \
                "chroot %s not initialized!" % chroot.makeChrootPath()
        if len(args) == 0:
            log.critical("You must specify a command to run with --chroot")
            sys.exit(50)
        chroot.chroot(args, options)

    elif options.mode == 'installdeps':
        if len(args) == 0:
            log.critical("You must specify an SRPM file with --installdeps")
            sys.exit(50)

        for hdr in mockbuild.util.yieldSrpmHeaders(args, plainRpmOk=1):
            pass
        chroot.tryLockBuildRoot()
        try:
            chroot._mountall()
            chroot.installSrpmDeps(*args)
        finally:
            chroot._umountall()
        chroot.unlockBuildRoot()

    elif options.mode == 'install':
        if len(args) == 0:
            log.critical("You must specify a package list to install.")
            sys.exit(50)

        chroot._resetLogging()
        chroot.tryLockBuildRoot()
        chroot.yumInstall(*args)
        chroot.unlockBuildRoot()

    elif options.mode == 'update':
        chroot._resetLogging()
        chroot.tryLockBuildRoot()
        chroot.yumUpdate()
        chroot.unlockBuildRoot()

    elif options.mode == 'remove':
        if len(args) == 0:
            log.critical("You must specify a package list to remove.")
            sys.exit(50)

        chroot._resetLogging()
        chroot.tryLockBuildRoot()
        chroot.yumRemove(*args)
        chroot.unlockBuildRoot()

    elif options.mode == 'rebuild':
        if config_opts['scm']:
            srpm = do_buildsrpm(config_opts, chroot, options, args)
            if srpm:
                args.append(srpm)
            scmWorker.clean()
        do_rebuild(config_opts, chroot, args)

    elif options.mode == 'buildsrpm':
        do_buildsrpm(config_opts, chroot, options, args)

    elif options.mode == 'orphanskill':
        mockbuild.util.orphansKill(chroot.makeChrootPath())
    elif options.mode == 'copyin':
        chroot.tryLockBuildRoot()
        chroot._resetLogging()
        #uidManager.dropPrivsForever()
        if len(args) < 2:
            log.critical("Must have source and destinations for copyin")
            sys.exit(50)
        dest = chroot.makeChrootPath(args[-1])
        if len(args) > 2 and not os.path.isdir(dest):
            log.critical("multiple source files and %s is not a directory!" % dest)
            sys.exit(50)
        args = args[:-1]
        import shutil
        for src in args:
            log.info("copying %s to %s" % (src, dest))
            if os.path.isdir(src):
                shutil.copytree(src, dest)
            else:
                shutil.copy(src, dest)
        chroot.unlockBuildRoot()

    elif options.mode == 'copyout':
        chroot.tryLockBuildRoot()
        chroot._resetLogging()
        uidManager.dropPrivsForever()
        if len(args) < 2:
            log.critical("Must have source and destinations for copyout")
            sys.exit(50)
        dest = args[-1]
        if len(args) > 2 and not os.path.isdir(dest):
            log.critical("multiple source files and %s is not a directory!" % dest)
            sys.exit(50)
        args = args[:-1]
        import shutil
        for f in args:
            src = chroot.makeChrootPath(f)
            log.info("copying %s to %s" % (src, dest))
            if os.path.isdir(src):
                shutil.copytree(src, dest)
            else:
                shutil.copy(src, dest)
        chroot.unlockBuildRoot()

    chroot._nuke_rpm_db()
    chroot.finish("run")
    chroot.alldone()

if __name__ == '__main__':
    # fix for python 2.4 logging module bug:
    logging.raiseExceptions = 0

    exitStatus = 0
    killOrphans = 1

    try:
        # sneaky way to ensure that we get passed back parameter even if
        # we hit an exception.
        retParams = {}
        main(retParams)
        exitStatus = retParams.get("exitStatus", exitStatus)

    except (SystemExit,):
        raise

    except (OSError,), e:
        if e.errno == 1:
            print
            log.error("%s" % str(e))
            print
            log.error("The most common cause for this error is trying to run /usr/sbin/mock as an unprivileged user.")
            log.error("Check your path to make sure that /usr/bin/ is listed before /usr/sbin, or manually run /usr/bin/mock to see if that fixes this problem.")
            print
        else:
            raise

    except (KeyboardInterrupt,):
        exitStatus = 7
        log.error("Exiting on user interrupt, <CTRL>-C")

    except (mockbuild.exception.ResultDirNotAccessible,), exc:
        exitStatus = exc.resultcode
        log.error(str(exc))
        killOrphans = 0

    except (mockbuild.exception.BadCmdline, mockbuild.exception.BuildRootLocked), exc:
        exitStatus = exc.resultcode
        log.error(str(exc))
        killOrphans = 0

    except (mockbuild.exception.Error), exc:
        exitStatus = exc.resultcode
        log.error(str(exc))

    except (Exception,), exc:
        exitStatus = 1
        log.exception(exc)

    if killOrphans and retParams:
        mockbuild.util.orphansKill(retParams["chroot"].makeChrootPath())

    logging.shutdown()
    sys.exit(exitStatus)
