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
from __future__ import print_function
"""
    usage:
           mock [options] {--init|--clean|--scrub=[all,chroot,cache,root-cache,c-cache,yum-cache,lvm]}
           mock [options] [--rebuild] /path/to/srpm(s)
           mock [options] --buildsrpm {--spec /path/to/spec --sources /path/to/src|--scm-enable [--scm-option key=value]}
           mock [options] {--shell|--chroot} <cmd>
           mock [options] --installdeps {SRPM|RPM}
           mock [options] --install PACKAGE
           mock [options] --copyin path [..path] destination
           mock [options] --copyout path [..path] destination
           mock [options] --scm-enable [--scm-option key=value]
           mock [options] --dnf-cmd arguments
           mock [options] --yum-cmd arguments
"""

# library imports
import grp
import logging
import logging.config
import os
import os.path
import pwd
import sys
import time
from optparse import OptionParser
from textwrap import dedent

try:
    import configparser
except ImportError:
    import ConfigParser as configparser

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
from mockbuild.trace_decorator import traceLog
import mockbuild.backend
import mockbuild.uid

from mockbuild import util
from mockbuild.backend import Commands
from mockbuild.state import State
from mockbuild.plugin import Plugins
from mockbuild.buildroot import Buildroot
from mockbuild.exception import BadCmdline

def scrub_callback(option, opt, value, parser):
    parser.values.scrub.append(value)
    parser.values.mode = "clean"

def repo_callback(optobj, opt, value, parser):
    '''Callback for the enablerepo and disablerepo option.

    Combines the values given for these options while preserving order
    from command line.
    '''
    dest = eval('parser.values.%s' % optobj.dest)
    dest.extend((opt, value))

def command_parse():
    """return options and args from parsing the command line"""
    plugins = util.PLUGIN_LIST
    parser = OptionParser(usage=__doc__, version=__VERSION__)

    # modes (basic commands)
    parser.add_option("--rebuild", action="store_const", const="rebuild",
                      dest="mode", default='__default__',
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
    scrub_choices = ('chroot', 'cache', 'root-cache', 'c-cache', 'yum-cache', 'lvm', 'all')
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
    parser.add_option("-i", "--install", action="store_const", const="install",
                      dest="mode",
                      help="install packages using package manager")
    parser.add_option("--update", action="store_const", const="update",
                      dest="mode",
                      help="update installed packages using package manager")
    parser.add_option("--remove", action="store_const", const="remove",
                      dest="mode",
                      help="remove packages using package manager")
    parser.add_option("--orphanskill", action="store_const", const="orphanskill",
                      dest="mode",
                      help="Kill all processes using specified buildroot.")

    parser.add_option("--copyin", action="store_const", const="copyin",
                      dest="mode",
                      help="Copy file(s) into the specified chroot")

    parser.add_option("--copyout", action="store_const", const="copyout",
                      dest="mode",
                      help="Copy file(s) from the specified chroot")

    parser.add_option("--pm-cmd", action="store_const", const="pm-cmd",
                      dest="mode",
                      help="Execute package management command (with yum or dnf)")

    parser.add_option("--yum-cmd", action="store_const", const="yum-cmd",
                      dest="mode",
                      help="Execute package management command with yum")

    parser.add_option("--dnf-cmd", action="store_const", const="dnf-cmd",
                      dest="mode",
                      help="Execute package management command with dnf")

    parser.add_option("--snapshot", action="store_const", const="snapshot",
                      dest="mode",
                      help="Create a new LVM snapshot with given name")

    parser.add_option("--remove-snapshot", action="store_const", const="remove_snapshot",
                      dest="mode",
                      help="Remove LVM snapshot with given name")

    parser.add_option("--rollback-to", action="store_const", const="rollback-to",
                      dest="mode",
                      help="Rollback to given snapshot")

    parser.add_option("--umount", action="store_const", const="umount",
                      dest="mode", help="Umount the buildroot if it's "
                      "mounted from separate device (LVM)")

    # options
    parser.add_option("-r", "--root", action="store", type="string", dest="chroot",
                      help="chroot config file name or path. Taken as a path if it ends "
                           "in .cfg, otherwise looked up in the configdir. default: %default",
                      default='default')

    parser.add_option("--offline", action="store_false", dest="online",
                      default=True,
                      help="activate 'offline' mode.")

    parser.add_option("-n", "--no-clean", action ="store_false", dest="clean",
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
    parser.add_option("--nocheck", action ="store_false", dest="check",
                      default=True, help="pass --nocheck to rpmbuild to skip 'make check' tests")
    parser.add_option("--arch", action ="store", dest="arch",
                      default=None, help="Sets kernel personality().")
    parser.add_option("--target", action ="store", dest="rpmbuild_arch",
                      default=None, help="passed to rpmbuild as --target")
    parser.add_option("-D", "--define", action="append", dest="rpmmacros",
                      default=[], type="string", metavar="'MACRO EXPR'",
                      help="define an rpm macro (may be used more than once)")
    parser.add_option("--macro-file", action="store", type="string", dest="macrofile",
                      default=[], help="Use pre-defined rpm macro file")
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
    parser.add_option("--short-circuit", action="store", type='choice',
                      choices=['prep', 'install', 'build', 'binary'],
                      help="Pass short-circuit option to rpmbuild to skip already "
                      "complete stages. Warning: produced packages are unusable. "
                      "Implies --no-clean. Valid options: build, install, binary")
    parser.add_option("--rpmbuild-opts", action="store",
                      help="Pass additional options to rpmbuild")
    parser.add_option("--enablerepo", action="callback", type="string", dest="enable_disable_repos", default=[],
                      help="Pass enablerepo option to yum/dnf", metavar='[repo]',
                      callback=repo_callback)
    parser.add_option("--disablerepo", action="callback", type="string", dest="enable_disable_repos", default=[],
                      help="Pass disablerepo option to yum/dnf", metavar='[repo]',
                      callback=repo_callback)
    parser.add_option("--old-chroot", action="store_true", dest="old_chroot",
                      default=False,
                      help="use old chroot instead of systemd-nspawn.")
    parser.add_option("--new-chroot", action="store_true", dest="new_chroot",
                      default=False,
                      help="use new chroot (systemd-nspawn).")

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
                        % repr(plugins))
    parser.add_option("--disable-plugin", action="append",
                      dest="disabled_plugins", type="string", default=[],
                      help="Disable plugin. Currently-available plugins: %s"
                           % repr(plugins))
    parser.add_option("--plugin-option", action="append", dest="plugin_opts",
                      default=[], type="string",
                      metavar="PLUGIN:KEY=VALUE",
                      help="define an plugin option (may be used more than once)")

    parser.add_option("-p", "--print-root-path", help="print path to chroot root",
                      dest="printrootpath", action="store_true",
                      default=False)

    parser.add_option("-l", "--list-snapshots",
                      help="list LVM snapshots associated with buildroot",
                      dest="list_snapshots", action="store_true",
                      default=False)

    # SCM options
    parser.add_option("--scm-enable", help="build from SCM repository",
                      dest="scm", action="store_true",
                      default=None)
    parser.add_option("--scm-option", action="append", dest="scm_opts",
                      default=[], type="string",
                      help="define an SCM option (may be used more than once)")

    # Package management options
    parser.add_option("--yum", help="use yum as package manager",
                      dest="pkg_manager", action="store_const", const="yum")
    parser.add_option("--dnf", help="use dnf as package manager",
                      dest="pkg_manager", action="store_const", const="dnf")

    (options, args) = parser.parse_args()

    if options.mode == '__default__':
        # handle old-style commands
        if len(args) and args[0] in ('chroot', 'shell',
                'rebuild', 'install', 'installdeps', 'remove', 'init', 'clean'):
            options.mode = args[0]
            args = args[1:]
        else:
            options.mode = 'rebuild'

    # explicitly disallow multiple targets in --target argument
    if options.rpmbuild_arch:
        if options.rpmbuild_arch.find(',') != -1:
                   raise mockbuild.exception.BadCmdline("--target option accepts only one arch. Invalid: %s" % options.rpmbuild_arch)

    if options.mode == 'buildsrpm' and not (options.spec and options.sources):
        if not options.scm:
            raise mockbuild.exception.BadCmdline("Must specify both --spec and --sources with --buildsrpm")
    if options.spec:
        options.spec = os.path.expanduser(options.spec)
    if options.sources:
        options.sources = os.path.expanduser(options.sources)
    if options.old_chroot:
        util.USE_NSPAWN = False
    if options.new_chroot:
        util.USE_NSPAWN = True

    return (options, args)

@traceLog()
def load_config(config_path, name, uidManager):
    config_opts = util.setup_default_config_opts(uidManager.unprivUid,
            __VERSION__, PKGPYTHONDIR)

    # array to save config paths
    config_opts['config_paths'] = []
    config_opts['chroot_name'] = name

    # Read in the config files: default, and then user specified
    if name.endswith('.cfg'):
        # If the .cfg is explicitly specified we take the root arg to
        # specify a path, rather than looking it up in the configdir.
        chroot_cfg_path = name
    else:
        chroot_cfg_path = '%s/%s.cfg' % (config_path, name)
    for cfg in (os.path.join(config_path, 'site-defaults.cfg'),
                chroot_cfg_path):
        if os.path.exists(cfg):
            config_opts['config_paths'].append(cfg)
            util.update_config_from_file(config_opts, cfg, uidManager)
        else:
            log.error("Could not find required config file: %s" % cfg)
            if name == "default":
                log.error("  Did you forget to specify the chroot to use with '-r'?")
            if "/" in cfg:
                log.error("  If you're trying to specify a path, include the .cfg extension, e.g. -r ./target.cfg")
            sys.exit(1)

    # Read user specific config file
    cfg = os.path.join(os.path.expanduser('~' + pwd.getpwuid(os.getuid())[0]),
            '.mock/user.cfg')
    if os.path.exists(cfg):
        config_opts['config_paths'].append(cfg)
        util.update_config_from_file(config_opts, cfg, uidManager)

    # default /etc/hosts contents
    if (not config_opts['use_host_resolv']
        and 'etc/hosts' not in config_opts['files']):
        config_opts['files']['etc/hosts'] = dedent('''\
            127.0.0.1 localhost localhost.localdomain
            ::1       localhost localhost.localdomain localhost6 localhost6.localdomain6
            ''')

    return config_opts

@traceLog()
def setup_logging(log_ini, config_opts, options):
    if not os.path.exists(log_ini):
        log.error("Could not find required logging config file: %s" % log_ini)
        sys.exit(50)
    try:
        if not os.path.exists(log_ini):
            raise IOError("Could not find log config file %s" % log_ini)
        log_cfg = configparser.ConfigParser()
        logging.config.fileConfig(log_ini)
        log_cfg.read(log_ini)
    except (IOError, OSError, configparser.NoSectionError) as exc:
        log.error("Log config file(%s) not correctly configured: %s" % (log_ini, exc))
        sys.exit(50)

    try:
        # set up logging format strings
        config_opts['build_log_fmt_str'] = log_cfg.get("formatter_%s" % config_opts['build_log_fmt_name'], "format", raw=1)
        config_opts['root_log_fmt_str'] = log_cfg.get("formatter_%s" % config_opts['root_log_fmt_name'], "format", raw=1)
        config_opts['state_log_fmt_str'] = log_cfg.get("formatter_%s" % config_opts['state_log_fmt_name'], "format", raw=1)
    except configparser.NoSectionError as exc:
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
    logging.getLogger("trace").propagate = 0
    if options.trace:
        logging.getLogger("trace").propagate = 1

@traceLog()
def setup_uid_manager(mockgid):
    unprivUid = os.getuid()
    unprivGid = os.getgid()

    # sudo
    if os.environ.get("SUDO_UID") is not None:
        unprivUid = int(os.environ['SUDO_UID'])
        os.setgroups((mockgid,))
        unprivGid = int(os.environ['SUDO_GID'])

    # consolehelper
    if os.environ.get("USERHELPER_UID") is not None:
        unprivUid = int(os.environ['USERHELPER_UID'])
        os.setgroups((mockgid,))
        unprivGid = pwd.getpwuid(unprivUid)[3]

    uidManager = mockbuild.uid.UidManager(unprivUid, unprivGid)
    return uidManager


@traceLog()
def check_arch_combination(target_arch, config_opts):
    try:
        legal = config_opts['legal_host_arches']
    except KeyError:
        return
    host_arch = os.uname()[-1]
    if host_arch not in legal:
        raise mockbuild.exception.InvalidArchitecture(
            "Cannot build target {0} on arch {1}, because it is not listed in legal_host_arches {2}".format(target_arch, host_arch, legal))

@traceLog()
def rebuild_generic(items, commands, buildroot, config_opts, cmd, post=None, clean=True):
    start = time.time()
    try:
        for item in items:
            log.info("Start(%s)  Config(%s)" % (item, buildroot.shared_root_name))
            if clean:
                commands.clean()
            commands.init(prebuild=not config_opts.get('short_circuit'))
            ret = cmd(item)
            elapsed = time.time() - start
            log.info("Done(%s) Config(%s) %d minutes %d seconds"
                % (item, config_opts['chroot_name'], elapsed // 60, elapsed % 60))
            log.info("Results and/or logs in: %s" % buildroot.resultdir)

        if config_opts["cleanup_on_success"]:
            log.info("Cleaning up build root ('cleanup_on_success=True')")
            commands.clean()
        if post:
            post()
        return ret

    except (Exception, KeyboardInterrupt):
        elapsed = time.time() - start
        log.error("Exception(%s) Config(%s) %d minutes %d seconds"
            % (item, buildroot.shared_root_name, elapsed // 60, elapsed % 60))
        log.info("Results and/or logs in: %s" % buildroot.resultdir)
        if config_opts["cleanup_on_failure"]:
            log.info("Cleaning up build root ('cleanup_on_failure=True')")
            commands.clean()
        raise

@traceLog()
def do_rebuild(config_opts, commands, buildroot, srpms):
    "rebuilds a list of srpms using provided chroot"
    if len(srpms) < 1:
        log.critical("No package specified to rebuild command.")
        sys.exit(50)

    util.checkSrpmHeaders(srpms)
    clean = config_opts['clean'] and not config_opts['scm']

    def build(srpm):
        commands.build(srpm, timeout=config_opts['rpmbuild_timeout'],
                       check=config_opts['check'])

    def createrepo_on_rpms():
        if config_opts["createrepo_on_rpms"]:
            log.info("Running createrepo on binary rpms in resultdir")
            buildroot.uid_manager.dropPrivsTemp()
            cmd = config_opts["createrepo_command"].split()
            cmd.append(buildroot.resultdir)
            util.do(cmd)
            buildroot.uid_manager.restorePrivs()

    rebuild_generic(srpms, commands, buildroot, config_opts, cmd=build,
                    post=createrepo_on_rpms, clean=clean)

@traceLog()
def do_buildsrpm(config_opts, commands, buildroot, options, args):
    # verify the input command line arguments actually exist
    if not os.path.isfile(options.spec):
        raise BadCmdline("Input specfile does not exist: %s" % options.spec)
    if not os.path.isdir(options.sources):
        raise BadCmdline("Input sources directory does not exist: %s" % options.sources)
    clean = config_opts['clean']

    def cmd(spec):
        commands.buildsrpm(spec=spec, sources=options.sources,
                           timeout=config_opts['rpmbuild_timeout'])
    return rebuild_generic([options.spec], commands, buildroot, config_opts,
                           cmd=cmd, post=None, clean=clean)

@traceLog()
def rootcheck():
    "verify mock was started correctly (either by sudo or consolehelper)"
    # if we're root due to sudo or consolehelper, we're ok
    # if not raise an exception and bail
    if os.getuid() == 0 and not (os.environ.get("SUDO_UID") or os.environ.get("USERHELPER_UID")):
        raise RuntimeError("mock will not run from the root account (needs an unprivileged uid so it can drop privs)")

@traceLog()
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

@traceLog()
def unshare_namespace():
    base_unshare_flags = util.CLONE_NEWNS
    extended_unshare_flags = base_unshare_flags | util.CLONE_NEWIPC \
                             | util.CLONE_NEWUTS
    try:
        util.unshare(extended_unshare_flags)
    except mockbuild.exception.UnshareFailed as e:
        log.debug("unshare(%d) failed, falling back to unshare(%d)" \
                  % (extended_unshare_flags, base_unshare_flags))
        try:
            util.unshare(base_unshare_flags)
        except mockbuild.exception.UnshareFailed as e:
            log.error("Namespace unshare failed.")
            sys.exit(e.resultcode)

@traceLog()
def main():
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

    mockgid = grp.getgrnam('mock').gr_gid
    uidManager = setup_uid_manager(mockgid)

    # go unpriv only when root to make --help etc work for non-mock users
    if os.geteuid() == 0:
        uidManager.dropPrivsTemp()

    (options, args) = command_parse()

    if options.printrootpath or options.list_snapshots:
        options.verbose = 0

    # config path -- can be overridden on cmdline
    config_path = MOCKCONFDIR
    if options.configdir:
        config_path = options.configdir

    config_opts = load_config(config_path, options.chroot, uidManager)

    # cmdline options override config options
    util.set_config_opts_per_cmdline(config_opts, options, args)

    # allow a different mock group to be specified
    if config_opts['chrootgid'] != mockgid:
        uidManager.restorePrivs()
        os.setgroups((mockgid, config_opts['chrootgid']))
        uidManager.dropPrivsTemp()

    # verify that our unprivileged uid is in the mock group
    groupcheck(uidManager.unprivGid, config_opts['chrootgid'])

    # configure logging
    log_ini = os.path.join(config_path, config_opts["log_config_file"])
    setup_logging(log_ini, config_opts, options)

    # verify that we're not trying to build an arch that we can't
    check_arch_combination(config_opts['rpmbuild_arch'], config_opts)

    # security cleanup (don't need/want this in the chroot)
    if 'SSH_AUTH_SOCK' in os.environ:
        del os.environ['SSH_AUTH_SOCK']

    # elevate privs
    uidManager._becomeUser(0, 0)

    # do whatever we're here to do
    py_version = '{0}.{1}.{2}'.format(*sys.version_info[:3])
    log.info("mock.py version %s starting (python version = %s)..." %
                (__VERSION__, py_version))
    state = State()
    plugins = Plugins(config_opts, state)
    buildroot = Buildroot(config_opts, uidManager, state, plugins)
    commands = Commands(config_opts, uidManager, plugins, state, buildroot)

    state.start("run")

    if options.printrootpath:
        print(buildroot.make_chroot_path(''))
        sys.exit(0)

    if options.list_snapshots:
        plugins.call_hooks('list_snapshots', required=True)
        sys.exit(0)

    # dump configuration to log
    log.debug("mock final configuration:")
    for k, v in list(config_opts.items()):
        log.debug("    %s:  %s" % (k, v))

    os.umask(0o02)
    os.environ["HOME"] = buildroot.homedir

    # New namespace starting from here
    unshare_namespace()

    # set personality (ie. setarch)
    if config_opts['internal_setarch']:
        util.condPersonality(config_opts['target_arch'])

    try:
        run_command(options, args, config_opts, commands, buildroot, state)
    finally:
        buildroot.finalize()

@traceLog()
def run_command(options, args, config_opts, commands, buildroot, state):
    #TODO separate this
    # Fetch and prepare sources from SCM
    if config_opts['scm']:
        scmWorker = mockbuild.scm.scmWorker(log, config_opts['scm_opts'], config_opts['macros'])
        scmWorker.get_sources()
        (options.sources, options.spec) = scmWorker.prepare_sources()

    if options.mode == 'init':
        if config_opts['clean']:
            commands.clean()
        commands.init()

    elif options.mode == 'clean':
        if len(options.scrub) == 0:
            commands.clean()
        else:
            commands.scrub(options.scrub)

    elif options.mode == 'shell':
        if len(args):
            cmd = ' '.join(args)
        else:
            cmd = None
        commands.init(do_log=False)
        sys.exit(commands.shell(options, cmd))

    elif options.mode == 'chroot':
        if not os.path.exists(buildroot.make_chroot_path()):
            raise mockbuild.exception.ChrootNotInitialized("chroot %s not initialized!" % buildroot.make_chroot_path())
        if len(args) == 0:
            log.critical("You must specify a command to run with --chroot")
            sys.exit(50)
        commands.init(do_log=False)
        commands.chroot(args, options)

    elif options.mode == 'installdeps':
        if len(args) == 0:
            log.critical("You must specify an SRPM file with --installdeps")
            sys.exit(50)

        util.checkSrpmHeaders(args, plainRpmOk=1)
        commands.init()
        commands.installSrpmDeps(*args)

    elif options.mode == 'install':
        if len(args) == 0:
            log.critical("You must specify a package list to install.")
            sys.exit(50)

        commands.init()
        commands.install(*args)

    elif options.mode == 'update':
        commands.init()
        commands.update()

    elif options.mode == 'remove':
        if len(args) == 0:
            log.critical("You must specify a package list to remove.")
            sys.exit(50)
        commands.init()
        commands.remove(*args)

    elif options.mode == 'rebuild':
        if config_opts['scm']:
            srpm = do_buildsrpm(config_opts, commands, buildroot, options, args)
            if srpm:
                args.append(srpm)
            scmWorker.clean()
        do_rebuild(config_opts, commands, buildroot, args)

    elif options.mode == 'buildsrpm':
        do_buildsrpm(config_opts, commands, buildroot, options, args)

    elif options.mode == 'orphanskill':
        util.orphansKill(buildroot.make_chroot_path())

    elif options.mode == 'copyin':
        commands.init()
        #uidManager.dropPrivsForever()
        if len(args) < 2:
            log.critical("Must have source and destinations for copyin")
            sys.exit(50)
        dest = buildroot.make_chroot_path(args[-1])
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

    elif options.mode == 'copyout':
        commands.init()
        buildroot.uid_manager.dropPrivsTemp()
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
            src = buildroot.make_chroot_path(f)
            log.info("copying %s to %s" % (src, dest))
            if os.path.isdir(src):
                shutil.copytree(src, dest, symlinks=True)
            else:
                if os.path.islink(src):
                    linkto = os.readlink(src)
                    os.symlink(linkto, dst)
                else:
                    shutil.copy(src, dest)
        buildroot.uid_manager.restorePrivs()

    elif options.mode in ('pm-cmd', 'yum-cmd', 'dnf-cmd'):
        log.info('Running {0} {1}'.format(buildroot.pkg_manager.command,
                                          ' '.join(args)))
        commands.init()
        buildroot.pkg_manager.execute(*args)
    elif options.mode == 'snapshot':
        if len(args) < 1:
            log.critical("Requires a snapshot name")
            sys.exit(50)
        buildroot.plugins.call_hooks('make_snapshot', args[0], required=True)
    elif options.mode == 'rollback-to':
        if len(args) < 1:
            log.critical("Requires a snapshot name")
            sys.exit(50)
        buildroot.plugins.call_hooks('rollback_to', args[0], required=True)
    elif options.mode == 'remove_snapshot':
        if len(args) < 1:
            log.critical("Requires a snapshot name")
            sys.exit(50)
        buildroot.plugins.call_hooks('remove_snapshot', args[0], required=True)
    elif options.mode == 'umount':
        buildroot.plugins.call_hooks('umount_root')

    buildroot._nuke_rpm_db()
    state.finish("run")
    state.alldone()
    buildroot.finalize()

if __name__ == '__main__':
    # fix for python 2.4 logging module bug:
    logging.raiseExceptions = 0

    exitStatus = 0

    try:
        main()

    except (SystemExit,):
        raise

    except (OSError,) as e:
        if e.errno == 1:
            print()
            log.error("%s" % str(e))
            print()
            log.error("The most common cause for this error is trying to run /usr/sbin/mock as an unprivileged user.")
            log.error("Check your path to make sure that /usr/bin/ is listed before /usr/sbin, or manually run /usr/bin/mock to see if that fixes this problem.")
            print()
        else:
            raise

    except (KeyboardInterrupt,):
        exitStatus = 7
        log.error("Exiting on user interrupt, <CTRL>-C")

    except (mockbuild.exception.ResultDirNotAccessible,) as exc:
        exitStatus = exc.resultcode
        log.error(str(exc))

    except (mockbuild.exception.BadCmdline, mockbuild.exception.BuildRootLocked) as exc:
        exitStatus = exc.resultcode
        log.error(str(exc))

    except (mockbuild.exception.Error) as exc:
        exitStatus = exc.resultcode
        log.error(str(exc))

    except (Exception,) as exc:
        exitStatus = 1
        log.exception(exc)

    logging.shutdown()
    sys.exit(exitStatus)
