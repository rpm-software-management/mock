#!/usr/bin/python3 -tt
# -*- coding: utf-8 -*-
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

# pylint: disable=pointless-string-statement,wrong-import-position
"""
       mock [options] {--init|--clean|--scrub=[all,chroot,cache,root-cache,c-cache,yum-cache,dnf-cache,lvm,overlayfs]}
       mock [options] [--rebuild] /path/to/srpm(s)
       mock [options] [--chain] /path/to/srpm(s)
       mock [options] --buildsrpm {--spec /path/to/spec --sources /path/to/src|
       --scm-enable [--scm-option key=value]}
       mock [options] {--shell|--chroot} <cmd>
       mock [options] --installdeps {SRPM|RPM}
       mock [options] --install PACKAGE
       mock [options] --copyin path [..path] destination
       mock [options] --copyout path [..path] destination
       mock [options] --scm-enable [--scm-option key=value]
       mock [options] --dnf-cmd arguments
       mock [options] --yum-cmd arguments
"""

from __future__ import print_function

# library imports
import argparse
import configparser
import errno
import glob
import grp
import logging
import logging.config

from pprint import pformat
import os
import os.path
import signal
import pwd
import shutil
import sys
import time
import copy

# pylint: disable=import-error
from functools import partial
from mockbuild import config
from mockbuild import util
from mockbuild.file_downloader import FileDownloader
from mockbuild.mounts import BindMountPoint, FileSystemMountPoint

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
# pylint: disable=wrong-import-position

import mockbuild.backend
from mockbuild.backend import Commands
from mockbuild.buildroot import Buildroot
import mockbuild.exception
from mockbuild.plugin import Plugins
import mockbuild.rebuild
from mockbuild.state import State
from mockbuild.trace_decorator import traceLog
import mockbuild.uid

signal_names = {1: "SIGHUP",
                13: "SIGPIPE",
                15: "SIGTERM"
                }

# This line is replaced by spec file %install section.
_MOCK_NVR = None


class RepoCallback(argparse.Action):
    """ Parse --enablerepo/--disablerepo options """
    def __call__(self, parser, namespace, value, option_string=None):
        if not hasattr(namespace, self.dest):
            setattr(namespace, self.dest, [])
        options = getattr(namespace, self.dest)
        options.extend((option_string, value))


def command_parse():
    """return options and args from parsing the command line"""
    plugins = config.PLUGIN_LIST
    parser = argparse.ArgumentParser(usage=__doc__)

    parser.add_argument('--version', action='version', version=__VERSION__)

    # hack from optparse=>argparse migration time, use add_argument if possible
    parser.add_option = parser.add_argument

    # modes (basic commands)
    parser.add_option("--rebuild", action="store_const", const="rebuild",
                      dest="mode", default='__default__',
                      help="rebuild the specified SRPM(s)")
    parser.add_option("--chain", action="store_const", const="chain",
                      dest="mode",
                      help="build multiple RPMs in chain loop")
    parser.add_option("--buildsrpm", action="store_const", const="buildsrpm",
                      dest="mode",
                      help="Build a SRPM from spec (--spec ...) and sources"
                           "(--sources ...) or from SCM")
    parser.add_option("--debug-config", action="store_const", const="debugconfig",
                      dest="mode",
                      help="Prints all options in config_opts")
    parser.add_option("--debug-config-expanded", action="store_const", const="debugconfigexpand",
                      dest="mode",
                      help="Prints all options in config_opts with jinja template values already expanded")
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
    scrub_choices = ('chroot', 'cache', 'root-cache', 'c-cache', 'yum-cache',
                     'dnf-cache', 'lvm', 'overlayfs', 'bootstrap', 'all')
    scrub_metavar = "[all|chroot|cache|root-cache|c-cache|yum-cache|dnf-cache]"
    parser.add_option("--scrub", action='append', choices=scrub_choices, default=[],
                      metavar=scrub_metavar,
                      help="completely remove the specified chroot "
                           "or cache dir or all of the chroot and cache")
    parser.add_option("--init", action="store_const", const="init", dest="mode",
                      help="initialize the chroot, do not build anything")
    parser.add_option("--installdeps", action="store_const", const="installdeps",
                      dest="mode",
                      help="install build dependencies for a specified SRPM or SPEC file")
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
                      help="Create a new LVM/overlayfs snapshot with given name")

    parser.add_option("--remove-snapshot", action="store_const", const="remove_snapshot",
                      dest="mode",
                      help="Remove LVM/overlayfs snapshot with given name")

    parser.add_option("--rollback-to", action="store_const", const="rollback-to",
                      dest="mode",
                      help="Rollback to given snapshot")

    parser.add_option("--umount", action="store_const", const="umount",
                      dest="mode", help="Umount the buildroot if it's "
                                        "mounted from separate device (LVM/overlayfs)")
    parser.add_option("--mount", action="store_const", const="mount",
                      dest="mode", help="Mount the buildroot if it's "
                                        "mounted from separate device (LVM/overlayfs)")
    # chain
    parser.add_option('--localrepo', default=None,
                      help=("local path for the local repo, defaults to making "
                            "its own (--chain mode only)"))
    parser.add_option('-c', '--continue', default=False, action='store_true',
                      dest='cont',
                      help="if a pkg fails to build, continue to the next one")
    parser.add_option('-a', '--addrepo', default=[], action='append',
                      dest='repos',
                      help="add these repo baseurls to the chroot's yum config")
    parser.add_option('--recurse', default=False, action='store_true',
                      help="if more than one pkg and it fails to build, try to build the rest and come back to it")
    parser.add_option('--tmp_prefix', default=None, dest='tmp_prefix',
                      help="tmp dir prefix - will default to username-pid if not specified")
    # options
    parser.add_option("-r", "--root", action="store", type=str, dest="chroot",
                      help="chroot config file name or path. Taken as a path if it ends "
                           "in .cfg, otherwise looked up in the configdir.  default: %%default",
                      metavar="CONFIG",
                      default='default')

    parser.add_option("--offline", action="store_false", dest="online",
                      default=True,
                      help="activate 'offline' mode.")

    parser.add_option("-n", "--no-clean", action="store_false", dest="clean",
                      help="do not clean chroot before building", default=True)
    parser.add_option("--cleanup-after", action="store_true",
                      dest="cleanup_after", default=None,
                      help="Clean chroot after building. Use with --resultdir."
                           " Only active for 'rebuild'.")
    parser.add_option("-N", "--no-cleanup-after", action="store_false",
                      dest="cleanup_after", default=None,
                      help="Don't clean chroot after building. If automatic"
                           " cleanup is enabled, use this to disable.", )
    parser.add_option("--cache-alterations", action="store_true",
                      dest="cache_alterations", default=False,
                      help="Rebuild the root cache after making alterations to the chroot"
                           " (i.e. --install). Only useful when using tmpfs plugin.")
    parser.add_option("--nocheck", action="store_false", dest="check",
                      default=True, help="pass --nocheck to rpmbuild to skip 'make check' tests")
    parser.add_option("--arch", action="store", dest="arch",
                      default=None, help="Sets kernel personality().")
    parser.add_option("--forcearch", action="store", dest="forcearch",
                      default=None, help="Force architecture to DNF (pass --forcearch to DNF).")
    parser.add_option("--target", action="store", dest="rpmbuild_arch",
                      default=None, help="passed to rpmbuild as --target")
    parser.add_option("-D", "--define", action="append", dest="rpmmacros",
                      default=[], type=str, metavar="'MACRO EXPR'",
                      help="define an rpm macro (may be used more than once)")
    parser.add_option("--macro-file", action="store", type=str, dest="macrofile",
                      default=[], help="Use pre-defined rpm macro file")
    parser.add_option("--with", action="append", dest="rpmwith",
                      default=[], type=str, metavar="option",
                      help="enable configure option for build (may be used more than once)")
    parser.add_option("--without", action="append", dest="rpmwithout",
                      default=[], type=str, metavar="option",
                      help="disable configure option for build (may be used more than once)")
    parser.add_option("--resultdir", action="store", type=str,
                      default=None, help="path for resulting files to be put")
    parser.add_option("--rootdir", action="store", type=str,
                      default=None, help="Path for where the chroot should be built")
    parser.add_option("--uniqueext", action="store", type=str,
                      default=None,
                      help="Arbitrary, unique extension to append to buildroot"
                           " directory name")
    parser.add_option("--configdir", action="store", dest="configdir",
                      default=None,
                      help="Change where config files are found")
    parser.add_option("--config-opts", action="append", dest="cli_config_opts",
                      default=[], help="Override configuration option.")
    parser.add_option("--rpmbuild_timeout", action="store",
                      dest="rpmbuild_timeout", type=int, default=None,
                      help="Fail build if rpmbuild takes longer than 'timeout'"
                           " seconds ")
    parser.add_option("--unpriv", action="store_true", default=False,
                      help="Drop privileges before running command when using --chroot")
    parser.add_option("--cwd", action="store", default=None,
                      metavar="DIR",
                      help="Change to the specified directory (relative to the chroot)"
                           " before running command when using --chroot")

    parser.add_option("--spec", action="store",
                      help="Specifies spec file to use to build an SRPM")
    parser.add_option("--sources", action="store",
                      help="Specifies sources (either a single file or a directory of files)"
                           "to use to build an SRPM (used only with --buildsrpm)")
    parser.add_option("--symlink-dereference", action="store_true", dest="symlink_dereference",
                      default=False, help="Follow symlinks in sources (used only with --buildsrpm)")

    parser.add_option("--short-circuit",
                      choices=['prep', 'install', 'build', 'binary'],
                      help="Pass short-circuit option to rpmbuild to skip already "
                           "complete stages. Warning: produced packages are unusable. "
                           "Implies --no-clean. Valid options: build, install, binary")
    parser.add_option("--rpmbuild-opts", action="store",
                      help="Pass additional options to rpmbuild")
    parser.add_option("--enablerepo", action=RepoCallback, type=str,
                      dest="enable_disable_repos", default=[],
                      help="Pass enablerepo option to yum/dnf", metavar='[repo]')
    parser.add_option("--disablerepo", action=RepoCallback, type=str,
                      dest="enable_disable_repos", default=[],
                      help="Pass disablerepo option to yum/dnf", metavar='[repo]')
    parser.add_option("--old-chroot", action="store_true", dest="old_chroot",
                      default=False,
                      help="Obsoleted. Use --isolation=simple")
    parser.add_option("--new-chroot", action="store_true", dest="new_chroot",
                      default=False,
                      help="Obsoleted. Use --isolation=nspawn")
    parser.add_option("--isolation", action="store", dest="isolation",
                      help="what level of isolation to use. Valid option: simple, nspawn")
    parser.add_option("--enable-network", action="store_true", dest="enable_network",
                      default=False,
                      help="enable networking.")
    parser.add_option("--postinstall", action="store_true", dest="post_install",
                      default=False, help="Try to install built packages in "
                                          "the same buildroot right after build")

    # verbosity
    parser.add_option("-v", "--verbose", action="store_const", const=2,
                      dest="verbose", default=1, help="verbose build")
    parser.add_option("-q", "--quiet", action="store_const", const=0,
                      dest="verbose", help="quiet build")
    parser.add_option("--trace", action="store_true", default=False,
                      dest="trace", help="Enable internal mock tracing output.")

    # plugins
    parser.add_option("--enable-plugin", action="append",
                      dest="enabled_plugins", type=str, default=[],
                      help="Enable plugin. Currently-available plugins: %s"
                      % repr(plugins))
    parser.add_option("--disable-plugin", action="append",
                      dest="disabled_plugins", type=str, default=[],
                      help="Disable plugin. Currently-available plugins: %s"
                      % repr(plugins))
    parser.add_option("--plugin-option", action="append", dest="plugin_opts",
                      default=[], type=str,
                      metavar="PLUGIN:KEY=VALUE",
                      help="define an plugin option (may be used more than once)")

    parser.add_option("-p", "--print-root-path", help="print path to chroot root",
                      dest="printrootpath", action="store_true",
                      default=False)

    parser.add_option("-l", "--list-snapshots",
                      help="list LVM/overlayfs snapshots associated with buildroot",
                      dest="list_snapshots", action="store_true",
                      default=False)

    # SCM options
    parser.add_option("--scm-enable", help="build from SCM repository",
                      dest="scm", action="store_true",
                      default=None)
    parser.add_option("--scm-option", action="append", dest="scm_opts",
                      default=[], type=str,
                      help="define an SCM option (may be used more than once)")

    # Package management options
    parser.add_option("--yum", help="use yum as package manager",
                      dest="pkg_manager", action="store_const", const="yum")
    parser.add_option("--dnf", help="use dnf as package manager",
                      dest="pkg_manager", action="store_const", const="dnf")

    # Bootstrap options
    parser.add_option('--bootstrap-chroot', dest='bootstrapchroot', action='store_true',
                      help="build in two stages, using chroot rpm for creating the build chroot",
                      default=None)
    parser.add_option('--no-bootstrap-chroot', dest='bootstrapchroot', action='store_false',
                      help="build in a single stage, using system rpm for creating the build chroot",
                      default=None)

    parser.add_option('--use-bootstrap-image', dest='usebootstrapimage', action='store_true',
                      help="create bootstrap chroot from container image (turns "
                           "--bootstrap-chroot on)", default=None)
    parser.add_option('--no-bootstrap-image', dest='usebootstrapimage', action='store_false',
                      help="don't create bootstrap chroot from container image", default=None)

    parser.add_option('--additional-package', action='append', default=[],
                      type=str, dest="additional_packages",
                      help=("Additional package to install into the buildroot before "
                            "the build is done.  Can be specified multiple times."))

    (options, args) = parser.parse_known_args()

    if options.mode == '__default__':
        # handle old-style commands
        if len(args) and args[0] in ('chroot', 'shell', 'rebuild', 'install',
                                     'installdeps', 'remove', 'init', 'clean'):
            options.mode = args[0]
            args = args[1:]
        else:
            options.mode = 'rebuild'

    # Optparse.parse_args() eats '--' argument, while argparse doesn't.  Do it manually.
    if args and args[0] == '--':
        args = args[1:]

    if options.scrub:
        options.mode = 'clean'

    # explicitly disallow multiple targets in --target argument
    if options.rpmbuild_arch:
        if options.rpmbuild_arch.find(',') != -1:
            raise mockbuild.exception.BadCmdline("--target option accepts only "
                                                 "one arch. Invalid: %s" % options.rpmbuild_arch)

    if options.mode == 'buildsrpm' and not (options.spec):
        if not options.scm:
            raise mockbuild.exception.BadCmdline("Must specify both --spec and "
                                                 "--sources with --buildsrpm")

    if options.recurse:
        # --recurse implies --continue
        options.cont = True

    if options.localrepo and options.mode != 'chain':
        raise mockbuild.exception.BadCmdline(
            "The --localrepo option works only with --chain")

    if options.recurse and options.mode != 'chain':
        raise mockbuild.exception.BadCmdline(
            "Only --chain mode supports --recurse build algorithm")

    if options.cont and options.mode != 'chain':
        raise mockbuild.exception.BadCmdline(
            "Only --chain mode supports --continue build algorithm")

    if options.spec:
        options.spec = os.path.expanduser(options.spec)
    if options.sources:
        options.sources = os.path.expanduser(options.sources)

    if options.additional_packages and options.mode != 'rebuild':
        raise mockbuild.exception.BadCmdline(
            "The --additional-package option requires the --rebuild mode")

    return (options, args)


def handle_signals(buildroot, number, frame):

    log.info("\nReceived signal %s activating orphansKill", signal_names[number])
    util.orphansKill(buildroot.make_chroot_path())
    sys.exit(128 + number)


@traceLog()
def setup_logging(config_path, config_opts, options):
    log_ini = os.path.join(config_path, config_opts["log_config_file"])

    try:
        if not os.path.exists(log_ini):
            if os.path.normpath('/etc/mock') != os.path.normpath(config_path):
                log.warning("Could not find required logging config file: %s. Using default...",
                            log_ini)
                log_ini = os.path.join("/etc/mock", config_opts["log_config_file"])
                if not os.path.exists(log_ini):
                    raise IOError("Could not find log config file %s" % log_ini)
            else:
                raise IOError("Could not find log config file %s" % log_ini)
    except IOError as exc:
        log.error(exc)
        sys.exit(50)

    try:
        log_cfg = configparser.ConfigParser()
        logging.config.fileConfig(log_ini)
        log_cfg.read(log_ini)
    except (IOError, OSError, configparser.NoSectionError) as exc:
        log.error("Log config file(%s) not correctly configured: %s", log_ini, exc)
        sys.exit(50)

    try:
        # set up logging format strings
        config_opts['build_log_fmt_str'] = log_cfg.get("formatter_%s" % config_opts['build_log_fmt_name'],
                                                       "format", raw=1)
        config_opts['root_log_fmt_str'] = log_cfg.get("formatter_%s" % config_opts['root_log_fmt_name'],
                                                      "format", raw=1)
        config_opts['state_log_fmt_str'] = log_cfg.get("formatter_%s" % config_opts['state_log_fmt_name'],
                                                       "format", raw=1)
    except configparser.NoSectionError as exc:
        log.error("Log config file (%s) missing required section: %s", log_ini, exc)
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

    logging.getLogger("mockbuild").mock_stderr_line_prefix = ""
    if config_opts['stderr_line_prefix'] != "":
        logging.getLogger("mockbuild").mock_stderr_line_prefix = config_opts['stderr_line_prefix']


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
        unprivName = pwd.getpwuid(unprivUid).pw_name
        secondary_groups = [g.gr_gid for g in grp.getgrall() if unprivName in g.gr_mem]
        os.setgroups([mockgid] + secondary_groups)
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
    if (host_arch not in legal) and not config_opts['forcearch']:
        log.info("Unable to build arch %s natively on arch %s. Setting forcearch to use software emulation.",
                 target_arch, host_arch)
        config_opts['forcearch'] = target_arch

    config.multiply_platform_multiplier(config_opts)
    if config_opts['forcearch']:
        binary = '/usr/bin/qemu-x86_64-static'
        if not os.path.exists(binary):
            # qemu-user-static is required, but seems to be missing
            if util.is_host_rh_family():
                # fail asap on RH systems
                raise RuntimeError('the --forcearch feature requires the '
                                   'qemu-user-static.rpm package to be installed')
            # on other systems we are not sure where the qemu-user-static
            # binaries are installed.  Notify the user verbosely, but do our
            # best and continue!
            log.warning("missing %s mock will likely fail ...", binary)
            time.sleep(5)

@traceLog()
def do_debugconfig(config_opts, uidManager, expand=False):
    jinja_expand = config_opts['__jinja_expand']
    defaults = config.load_defaults(uidManager, __VERSION__, PKGPYTHONDIR)
    defaults['__jinja_expand'] = expand
    config_opts['__jinja_expand'] = expand
    for key in sorted(config_opts):
        if key == '__jinja_expand':
            value = jinja_expand
        else:
            value = config_opts[key]
        if (key in defaults) and (key in config_opts) and (config_opts[key] != defaults[key]) or \
           (key not in defaults):
            print("config_opts['{}'] = {}".format(key, pformat(value)))
    config_opts['__jinja_expand'] = jinja_expand

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


def running_in_docker():
    """ Returns True if we are running inside of Docker container """
    # Docker container has different cgroup than PID 1 of host.
    # And have "docker" in that tree.
    with open('/proc/self/cgroup') as f:
        for line in f:
            items = line.split(':')
            if 'docker' in items[2]:
                return True
    return False


@traceLog()
def unshare_namespace(config_opts):
    base_unshare_flags = util.CLONE_NEWNS
    # IPC ns is unshared later
    extended_unshare_flags = base_unshare_flags | util.CLONE_NEWUTS
    try:
        util.unshare(extended_unshare_flags)
    except mockbuild.exception.UnshareFailed as e:
        log.debug("unshare(%d) failed, falling back to unshare(%d)",
                  extended_unshare_flags, base_unshare_flags)
        try:
            util.unshare(base_unshare_flags)
        except mockbuild.exception.UnshareFailed as e:
            log.error("Namespace unshare failed.")
            if running_in_docker() and not ('docker_unshare_warning' in config_opts and
                                            config_opts['docker_unshare_warning']):
                log.error("It seems we are running inside of Docker. Let skip unsharing.")
                log.error("You should *not* run anything but Mock in this container. You have been warned!")
                time.sleep(5)
            else:
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

    config_opts = config.load_config(config_path, options.chroot, uidManager, __VERSION__, PKGPYTHONDIR)

    # cmdline options override config options
    config.set_config_opts_per_cmdline(config_opts, options, args)

    util.subscription_redhat_init(config_opts)

    # allow a different mock group to be specified
    if config_opts['chrootgid'] != mockgid:
        uidManager.restorePrivs()
        os.setgroups((mockgid, config_opts['chrootgid']))
        uidManager.dropPrivsTemp()

    # verify that our unprivileged uid is in the mock group
    groupcheck(uidManager.unprivGid, config_opts['chrootgid'])

    # configure logging
    setup_logging(config_path, config_opts, options)

    # verify that we're not trying to build an arch that we can't
    check_arch_combination(config_opts['rpmbuild_arch'], config_opts)

    # security cleanup (don't need/want this in the chroot)
    if 'SSH_AUTH_SOCK' in os.environ:
        del os.environ['SSH_AUTH_SOCK']

    # elevate privs
    uidManager.become_user_without_push(0, 0)

    # do whatever we're here to do
    py_version = '{0}.{1}.{2}'.format(*sys.version_info[:3])
    log.info("mock.py version %s starting (python version = %s%s)...",
             __VERSION__, py_version,
             "" if not _MOCK_NVR else ", NVR = " + _MOCK_NVR)
    state = State()
    plugins = Plugins(config_opts, state)

    # When scrubbing all, we also want to scrub a bootstrap chroot
    if options.scrub:
        config_opts['use_bootstrap'] = True

    # outer buildroot to bootstrap the installation - based on main config with some differences
    bootstrap_buildroot = None
    if config_opts['use_bootstrap']:
        # first take a copy of the config so we can make some modifications
        bootstrap_buildroot_config = config_opts.copy()
        # copy plugins configuration so we get a separate deep copy
        bootstrap_buildroot_config['plugin_conf'] = \
            copy.deepcopy(config_opts['plugin_conf'])  # pylint: disable=no-member
        # add '-bootstrap' to the end of the root name
        bootstrap_buildroot_config['root'] = bootstrap_buildroot_config['root'] + '-bootstrap'
        # don't share root cache tarball
        bootstrap_buildroot_config['plugin_conf']['root_cache_opts']['dir'] = \
            "{{cache_topdir}}/" + bootstrap_buildroot_config['root'] + "/root_cache/"
        # we don't want to affect the bootstrap.config['nspawn_args'] array, deep copy
        bootstrap_buildroot_config['nspawn_args'] = config_opts.get('nspawn_args', []).copy()

        # allow bootstrap buildroot to access the network for getting packages
        bootstrap_buildroot_config['rpmbuild_networking'] = True
        bootstrap_buildroot_config['use_host_resolv'] = True
        util.setup_host_resolv(bootstrap_buildroot_config)

        # use system_*_command for bootstrapping
        bootstrap_buildroot_config['yum_command'] = bootstrap_buildroot_config['system_yum_command']
        bootstrap_buildroot_config['dnf_command'] = bootstrap_buildroot_config['system_dnf_command']

        # disable updating bootstrap chroot
        bootstrap_buildroot_config['update_before_build'] = False

        bootstrap_buildroot_state = State(bootstrap=True)
        bootstrap_plugins = Plugins(bootstrap_buildroot_config, bootstrap_buildroot_state)
        bootstrap_buildroot = Buildroot(bootstrap_buildroot_config,
                                        uidManager, bootstrap_buildroot_state, bootstrap_plugins,
                                        is_bootstrap=True)
        # this bit of config is needed after we have created the bootstrap buildroot since we need to
        # query pkg_manager to know which manager is in use
        bootstrap_buildroot.config['chroot_setup_cmd'] = bootstrap_buildroot.pkg_manager.install_command
        # override configs for bootstrap_*
        for k in bootstrap_buildroot.config.copy():
            if "bootstrap_" + k in bootstrap_buildroot.config:
                bootstrap_buildroot.config[k] = bootstrap_buildroot_config["bootstrap_" + k]
                del bootstrap_buildroot.config["bootstrap_" + k]

        if config_opts['redhat_subscription_required']:
            key_dir = '/etc/pki/entitlement'
            chroot_dir = bootstrap_buildroot.make_chroot_path(key_dir)
            mount_point = BindMountPoint(srcpath=key_dir, bindpath=chroot_dir)
            bootstrap_buildroot.mounts.add(mount_point)

    # this changes config_opts['nspawn_args'], so do it after initializing
    # bootstrap chroot to not inherit the changes there
    util.setup_host_resolv(config_opts)

    buildroot = Buildroot(config_opts, uidManager, state, plugins, bootstrap_buildroot)

    for baseurl in options.repos:
        util.add_local_repo(config_opts, baseurl,
                            bootstrap=bootstrap_buildroot)

    if bootstrap_buildroot is not None:
        # add the extra bind mount to the outer chroot
        inner_mount = bootstrap_buildroot.make_chroot_path(buildroot.make_chroot_path())

        # Hide re-mounted chroot from host by private tmpfs.
        buildroot.mounts.managed_mounts.append(
            FileSystemMountPoint(filetype='tmpfs',
                                 device='hide_root_in_bootstrap',
                                 path=inner_mount,
                                 options="private"))
        buildroot.mounts.managed_mounts.append(
            BindMountPoint(buildroot.make_chroot_path(), inner_mount,
                           recursive=True, options="private"))

    signal.signal(signal.SIGTERM, partial(handle_signals, buildroot))
    signal.signal(signal.SIGPIPE, partial(handle_signals, buildroot))
    signal.signal(signal.SIGHUP, partial(handle_signals, buildroot))

    # postprocess option arguments for bootstrap
    if options.mode in ['installdeps', 'install']:
        args = [buildroot.file_on_cmdline(arg) for arg in args]

    log.info("Signal handler active")
    commands = Commands(config_opts, uidManager, plugins, state, buildroot, bootstrap_buildroot)

    if config_opts['use_bootstrap']:
        bootstrap_buildroot.config['chroot_setup_cmd'] = buildroot.pkg_manager.install_command

    state.start("run")

    if options.printrootpath:
        print(buildroot.make_chroot_path(''))
        sys.exit(0)

    if options.list_snapshots:
        plugins.call_hooks('list_snapshots', required=True)
        if bootstrap_buildroot is not None:
            bootstrap_buildroot.plugins.call_hooks('list_snapshots', required=True)
        sys.exit(0)

    # dump configuration to log
    log.debug("mock final configuration:")
    for k, v in list(config_opts.items()):
        log.debug("    %s:  %s", k, v)

    os.umask(0o02)
    os.environ["HOME"] = buildroot.homedir

    # New namespace starting from here
    unshare_namespace(config_opts)

    if config_opts['hostname']:
        util.sethostname(config_opts['hostname'])

    # set personality (ie. setarch)
    util.condPersonality(config_opts['target_arch'])

    result = 0
    try:
        result = run_command(options, args, config_opts, commands, buildroot, state)
    finally:
        buildroot.finalize()
        if bootstrap_buildroot is not None:
            bootstrap_buildroot.finalize()
    return result


@traceLog()
def run_command(options, args, config_opts, commands, buildroot, state):
    result = 0
    # TODO separate this
    # Fetch and prepare sources from SCM
    if config_opts['scm']:
        try:
            # pylint: disable=import-outside-toplevel
            from mockbuild import scm
        except ImportError as e:
            raise mockbuild.exception.BadCmdline(
                "Mock SCM module not installed: %s. You should install package mock-scm." % e)
        scmWorker = scm.scmWorker(log, config_opts, config_opts['macros'])
        with buildroot.uid_manager:
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

    elif options.mode == 'chain':
        if len(args) == 0:
            log.critical("You must specify an SRPM file with --chain")
            return 50
        commands.init(do_log=True)
        result = commands.chain(args, options, buildroot)

    elif options.mode == 'shell':
        if len(args):
            cmd = args
        else:
            cmd = None
        commands.init(do_log=False)
        return commands.shell(options, cmd)

    elif options.mode == 'chroot':
        if len(args) == 0:
            log.critical("You must specify a command to run with --chroot")
            return 50
        commands.init(do_log=True)
        return commands.chroot(args, options)

    elif options.mode == 'installdeps':
        if len(args) == 0:
            log.critical("You must specify an SRPM file with --installdeps")
            return 50
        commands.init()
        rpms = []
        for file in args:
            if os.path.splitext(file)[1] == ".spec":
                commands.installSpecDeps(file)
            else:
                rpms.append(file)
        if rpms:
            util.checkSrpmHeaders(rpms, plainRpmOk=1)
            commands.installSrpmDeps(*rpms)

    elif options.mode == 'install':
        if len(args) == 0:
            log.critical("You must specify a package list to install.")
            return 50

        commands.init()
        commands.install_external(args)
        buildroot.install(*args)

    elif options.mode == 'update':
        commands.init()
        buildroot.pkg_manager.execute('update', *args)

    elif options.mode == 'remove':
        if len(args) == 0:
            log.critical("You must specify a package list to remove.")
            return 50
        commands.init()
        buildroot.remove(*args)

    elif options.mode == 'rebuild':
        if config_opts['scm'] or (options.spec and options.sources):
            srpm = mockbuild.rebuild.do_buildsrpm(config_opts, commands, buildroot, options, args)
            if srpm:
                args.append(srpm)
            if config_opts['scm']:
                scmWorker.clean()
                options.spec = None
                options.sources = None
            else:
                config_opts['clean'] = False

        try:
            srpms = []
            for srpm_location in args:
                with buildroot.uid_manager:
                    srpm = FileDownloader.get(srpm_location)
                if not srpm:
                    raise mockbuild.exception.BadCmdline(
                        "Invalid {} source RPM".format(srpm_location))
                srpms.append(srpm)
            mockbuild.rebuild.do_rebuild(config_opts, commands, buildroot, options, srpms)
        finally:
            FileDownloader.cleanup()

    elif options.mode == 'buildsrpm':
        mockbuild.rebuild.do_buildsrpm(config_opts, commands, buildroot, options, args)

    elif options.mode == 'debugconfig':
        do_debugconfig(config_opts, buildroot.uid_manager)

    elif options.mode == 'debugconfigexpand':
        do_debugconfig(config_opts, buildroot.uid_manager, True)

    elif options.mode == 'orphanskill':
        util.orphansKill(buildroot.make_chroot_path())

    elif options.mode == 'copyin':
        commands.init()
        if len(args) < 2:
            log.critical("Must have source and destinations for copyin")
            return 50
        dest = buildroot.make_chroot_path(args[-1])
        if len(args) > 2 and not os.path.isdir(dest):
            log.critical("multiple source files and %s is not a directory!", dest)
            return 50
        args = args[:-1]
        for src in args:
            if not os.path.lexists(src):
                log.critical("No such file or directory: %s", src)
                return 50
            log.info("copying %s to %s", src, dest)
            if os.path.isdir(src):
                dest2 = dest
                if os.path.exists(dest2):
                    path_suffix = os.path.split(src)[1]
                    dest2 = os.path.join(dest2, path_suffix)
                    if os.path.exists(dest2):
                        log.critical("Destination %s already exists!", dest2)
                        return 50
                shutil.copytree(src, dest2)
            else:
                shutil.copy(src, dest)
        buildroot.chown_home_dir()

    elif options.mode == 'copyout':
        commands.init()
        with buildroot.uid_manager:
            if len(args) < 2:
                log.critical("Must have source and destinations for copyout")
                return 50
            dest = args[-1]
            sources = []
            for arg in args[:-1]:
                matches = glob.glob(buildroot.make_chroot_path(arg.replace('~', buildroot.homedir)))
                if not matches:
                    log.critical("%s not found", arg)
                    return 50
                sources += matches
            if len(sources) > 1 and not os.path.isdir(dest):
                log.critical("multiple source files and %s is not a directory!", dest)
                return 50
            for src in sources:
                log.info("copying %s to %s", src, dest)
                if os.path.isdir(src):
                    shutil.copytree(src, dest, symlinks=True)
                else:
                    if os.path.islink(src):
                        linkto = os.readlink(src)
                        os.symlink(linkto, dest)
                    else:
                        shutil.copy(src, dest)

    elif options.mode in ('pm-cmd', 'yum-cmd', 'dnf-cmd'):
        log.info('Running %s %s', buildroot.pkg_manager.command, ' '.join(args))
        commands.init()
        buildroot.pkg_manager.execute(*args)
    elif options.mode == 'snapshot':
        if len(args) < 1:
            log.critical("Requires a snapshot name")
            return 50
        buildroot.plugins.call_hooks('make_snapshot', args[0], required=True)
        if buildroot.bootstrap_buildroot is not None:
            buildroot.bootstrap_buildroot.plugins.call_hooks('make_snapshot', args[0], required=True)
    elif options.mode == 'rollback-to':
        if len(args) < 1:
            log.critical("Requires a snapshot name")
            return 50
        buildroot.plugins.call_hooks('rollback_to', args[0], required=True)
        if buildroot.bootstrap_buildroot is not None:
            buildroot.bootstrap_buildroot.plugins.call_hooks('rollback_to', args[0], required=True)
    elif options.mode == 'remove_snapshot':
        if len(args) < 1:
            log.critical("Requires a snapshot name")
            return 50
        buildroot.plugins.call_hooks('remove_snapshot', args[0], required=True)
        if buildroot.bootstrap_buildroot is not None:
            buildroot.bootstrap_buildroot.plugins.call_hooks('remove_snapshot', args[0], required=True)
    elif options.mode == 'umount':
        buildroot.plugins.call_hooks('umount_root')
        if buildroot.bootstrap_buildroot is not None:
            buildroot.bootstrap_buildroot.plugins.call_hooks('umount_root')
    elif options.mode == 'mount':
        buildroot.plugins.call_hooks('mount_root')
        if buildroot.bootstrap_buildroot is not None:
            buildroot.bootstrap_buildroot.plugins.call_hooks('mount_root')

    buildroot.nuke_rpm_db()
    state.finish("run")
    state.alldone()
    return result


if __name__ == '__main__':
    # TODO: this was documented as "fix for python 2.4 logging module bug:"
    # TODO: ...but it is apparently still needed; without it there are various
    # TODO:    exceptions from trace_decorator like:
    # TODO:    TypeError: not enough arguments for format string
    logging.raiseExceptions = 0

    exitStatus = 0


    try:
        exitStatus = main()

    except (SystemExit,):
        raise # pylint: disable=try-except-raise

    except (OSError,) as e:
        if e.errno == errno.EPERM:
            print()
            log.error("%s", e)
            print()
            log.error("The most common cause for this error is trying to run "
                      "/usr/libexec/mock/mock as an unprivileged user.")
            log.error("You should not run /usr/libexec/mock/mock directly.")
            print()
            exitStatus = 2
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

    except (Exception,) as exc:  # pylint: disable=broad-except
        exitStatus = 1
        log.exception(exc)

    logging.shutdown()
    sys.exit(exitStatus)
