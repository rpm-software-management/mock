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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
"""
    usage:
           mock [options] {--init|--clean}
           mock [options] [--rebuild] /path/to/srpm(s)
           mock [options] {--shell|--chroot} <cmd>
           mock [options] --installdeps {SRPM|RPM}
           mock [options] --install PACKAGE
           mock [options] --copyin path [..path] destination
           mock [options] --copyout path [..path] destination
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

# all of the variables below are substituted by the build system
__VERSION__ = "unreleased_version"
SYSCONFDIR = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "..", "etc")
PYTHONDIR = os.path.dirname(os.path.realpath(sys.argv[0]))
PKGPYTHONDIR = os.path.join(os.path.dirname(os.path.realpath(sys.argv[0])), "mock")
MOCKCONFDIR = os.path.join(SYSCONFDIR, "mock")
# end build system subs

# import all mock.* modules after this.
sys.path.insert(0, PYTHONDIR)

# set up basic logging until config file can be read
FORMAT = "%(levelname)s: %(message)s"
logging.basicConfig(format=FORMAT, level=logging.WARNING)
log = logging.getLogger()

# our imports
import mock.exception
from mock.trace_decorator import traceLog, decorate
import mock.backend
import mock.uid
import mock.util

def command_parse(config_opts):
    """return options and args from parsing the command line"""
    parser = OptionParser(usage=__doc__, version=__VERSION__)

    # modes (basic commands)
    parser.add_option("--rebuild", action="store_const", const="rebuild",
                      dest="mode", default='rebuild',
                      help="rebuild the specified SRPM(s)")
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
    parser.add_option("--target", "--arch", action ="store", dest="arch",
                      default=None, help="target build arch")
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

    # verbosity
    parser.add_option("-v", "--verbose", action="store_const", const=2,
                      dest="verbose", default=1, help="verbose build")
    parser.add_option("-q", "--quiet", action="store_const", const=0,
                      dest="verbose", help="quiet build")
    parser.add_option("--trace", action="store_true", default=False,
                      dest="trace", help="TODO: document me")

    # plugins
    parser.add_option("--enable-plugin", action="append",
                      dest="enabled_plugins", type="string", default=[],
                      help="Enable plugin. Currently-available plugins: %s"
                        % repr(config_opts['plugins']))
    parser.add_option("--disable-plugin", action="append",
                      dest="disabled_plugins", type="string", default=[],
                      help="Disable plugin. Currently-available plugins: %s"
                           % repr(config_opts['plugins']))

    (options, args) = parser.parse_args()
    if len(args) and args[0] in ('chroot', 'shell',
            'rebuild', 'install', 'installdeps', 'init', 'clean'):
        options.mode = args[0]
        args = args[1:]

    return (options, args)

decorate(traceLog())
def setup_default_config_opts(config_opts, unprivUid):
    "sets up default configuration."
    # global
    config_opts['basedir'] = '/var/lib/mock/' # root name is automatically added to this
    config_opts['resultdir'] = '%(basedir)s/%(root)s/result'
    config_opts['cache_topdir'] = '/var/lib/mock/cache'
    config_opts['clean'] = True
    config_opts['chroothome'] = '/builddir'
    config_opts['log_config_file'] = 'logging.ini'
    config_opts['rpmbuild_timeout'] = 0
    config_opts['chrootuid'] = unprivUid
    try:
        config_opts['chrootgid'] = grp.getgrnam("mock")[2]
    except KeyError:
        #  'mock' group doesnt exist, must set in config file
        pass
    config_opts['build_log_fmt_name'] = "unadorned"
    config_opts['root_log_fmt_name']  = "detailed"
    config_opts['state_log_fmt_name'] = "state"
    config_opts['online'] = True

    config_opts['internal_dev_setup'] = True
    config_opts['internal_setarch'] = True

    # cleanup_on_* only take effect for separate --resultdir
    # config_opts provides fine-grained control. cmdline only has big hammer
    config_opts['cleanup_on_success'] = 1
    config_opts['cleanup_on_failure'] = 1

    # (global) plugins and plugin configs
    config_opts['plugins'] = ('ccache', 'yum_cache', 'root_cache', 'bind_mount')
    config_opts['plugin_dir'] = os.path.join(PKGPYTHONDIR, "plugins")
    config_opts['plugin_conf'] = {
            'ccache_enable': True,
            'ccache_opts': {
                'max_cache_size': "4G",
                'dir': "%(cache_topdir)s/%(root)s/ccache/"},
            'yum_cache_enable': True,
            'yum_cache_opts': {
                'max_age_days': 30,
                'max_metadata_age_days': 30,
                'dir': "%(cache_topdir)s/%(root)s/yum_cache/",
                'online': True,},
            'root_cache_enable': True,
            'root_cache_opts': {
                'max_age_days': 15,
                'dir': "%(cache_topdir)s/%(root)s/root_cache/"},
            'bind_mount_enable': True,
            'bind_mount_opts': {'dirs': [
                # specify like this:
                # ('/host/path', '/bind/mount/path/in/chroot/' ),
                # ('/another/host/path', '/another/bind/mount/path/in/chroot/'),
                ]},
            }

    # dependent on guest OS
    config_opts['useradd'] = \
        '/usr/sbin/useradd -o -m -u %(uid)s -g %(gid)s -d %(home)s -n %(user)s'
    config_opts['use_host_resolv'] = True
    config_opts['chroot_setup_cmd'] = 'install buildsys-build'
    config_opts['target_arch'] = 'i386'
    config_opts['yum.conf'] = ''
    config_opts['more_buildreqs'] = {}
    config_opts['files'] = {}
    config_opts['files']['etc/hosts'] = "127.0.0.1 localhost localhost.localdomain\n"
    config_opts['macros'] = {
        '%_topdir': '%s/build' % config_opts['chroothome'],
        '%_rpmfilename': '%%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm',
        }

decorate(traceLog())
def set_config_opts_per_cmdline(config_opts, options, args):
    "takes processed cmdline args and sets config options."
    # do some other options and stuff
    if options.arch:
        config_opts['target_arch'] = options.arch
    if not options.clean:
        config_opts['clean'] = options.clean

    for option in options.rpmwith:
        options.rpmmacros.append("_with_%s 1" % option)

    for option in options.rpmwithout:
        options.rpmmacros.append("_without_%s 1" % option)

    for macro in options.rpmmacros:
        try:
            k, v = macro.split(" ", 1)
            if not k.startswith('%'):
                k = '%%%s' % k
            config_opts['macros'].update({k: v})
        except:
            raise mock.exception.BadCmdline(
                "Bad option for '--define' (%s).  Use --define 'macro expr'"
                % macro)

    if options.resultdir:
        config_opts['resultdir'] = os.path.expanduser(options.resultdir)
    if options.uniqueext:
        config_opts['unique-ext'] = options.uniqueext
    if options.rpmbuild_timeout is not None:
        config_opts['rpmbuild_timeout'] = options.rpmbuild_timeout

    for i in options.disabled_plugins:
        if i not in config_opts['plugins']:
            raise mock.exception.BadCmdline(
                "Bad option for '--disable-plugins=%s'. Expecting one of: %s"
                % (i, config_opts['plugins']))
        config_opts['plugin_conf']['%s_enable' % i] = False
    for i in options.enabled_plugins:
        if i not in config_opts['plugins']:
            raise mock.exception.BadCmdline(
                "Bad option for '--enable-plugins=%s'. Expecting one of: %s"
                % (i, config_opts['plugins']))
        config_opts['plugin_conf']['%s_enable' % i] = True

    if options.cleanup_after and not options.resultdir:
        raise mock.exception.BadCmdline(
            "Must specify --resultdir when using --cleanup-after")

    if options.mode in ("rebuild",) and len(args) > 1 and not options.resultdir:
        raise mock.exception.BadCmdline(
            "Must specify --resultdir when building multiple RPMS.")

    if options.cleanup_after == False:
        config_opts['cleanup_on_success'] = False
        config_opts['cleanup_on_failure'] = False

    if options.cleanup_after == True:
        config_opts['cleanup_on_success'] = True
        config_opts['cleanup_on_failure'] = True

    # cant cleanup unless separate resultdir
    if not options.resultdir:
        config_opts['cleanup_on_success'] = False
        config_opts['cleanup_on_failure'] = False

    config_opts['online'] = options.online

decorate(traceLog())
def do_rebuild(config_opts, chroot, srpms):
    "rebuilds a list of srpms using provided chroot"
    if len(srpms) < 1:
        log.critical("No package specified to rebuild command.")
        sys.exit(50)

    # check that everything is kosher. Raises exception on error
    for hdr in mock.util.yieldSrpmHeaders(srpms):
        pass

    start = time.time()
    try:
        for srpm in srpms:
            start = time.time()
            log.info("Start(%s)  Config(%s)" % (srpm, chroot.sharedRootName))
            if config_opts['clean'] and chroot.state() != "clean":
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
    except (Exception, KeyboardInterrupt):
        elapsed = time.time() - start
        log.error("Exception(%s) Config(%s) %d minutes %d seconds"
            % (srpm, chroot.sharedRootName, elapsed//60, elapsed%60))
        log.info("Results and/or logs in: %s" % chroot.resultdir)
        if config_opts["cleanup_on_failure"]:
            log.info("Cleaning up build root ('clean_on_failure=True')")
            chroot.clean()
        raise

def main(ret):
    "Main executable entry point."
    # drop unprivleged to parse args, etc.
    #   uidManager saves current real uid/gid which are unpriviledged (callers)
    #   due to suid helper, our current effective uid is 0
    #   also supports being run by sudo
    #
    #   setuid wrapper has real uid = unpriv,  effective uid = 0
    #   sudo sets real/effective = 0, and sets env vars
    #   setuid wrapper clears environment, so there wont be any conflict between these two

    # old setuid wrapper
    unprivUid = os.getuid()
    unprivGid = os.getgid()

    # sudo
    if os.environ.get("SUDO_UID") is not None:
        unprivUid = int(os.environ['SUDO_UID'])
        username = os.environ.get("SUDO_USER")
        groups = [ g[2] for g in grp.getgrall() if username in g[3]]
        os.setgroups(groups)
        unprivGid = int(os.environ['SUDO_GID'])

    # consolehelper
    if os.environ.get("USERHELPER_UID") is not None:
        unprivUid = int(os.environ['USERHELPER_UID'])
        username = pwd.getpwuid(unprivUid)[0]
        groups = [ g[2] for g in grp.getgrall() if username in g[3]]
        os.setgroups(groups)
        unprivGid = pwd.getpwuid(unprivUid)[3]

    uidManager = mock.uid.uidManager(unprivUid, unprivGid)
    uidManager._becomeUser(unprivUid, unprivGid)
    del(os.environ["HOME"])

    # defaults
    config_opts = {}
    setup_default_config_opts(config_opts, unprivUid)
    (options, args) = command_parse(config_opts)

    # config path -- can be overridden on cmdline
    config_path = MOCKCONFDIR
    if options.configdir:
        config_path = options.configdir

    # Read in the config files: default, and then user specified
    for cfg in ( os.path.join(config_path, 'defaults.cfg'), '%s/%s.cfg' % (config_path, options.chroot)):
        if os.path.exists(cfg):
            execfile(cfg)
        else:
            log.error("Could not find required config file: %s" % cfg)
            if options.chroot == "default": log.error("  Did you forget to specify the chroot to use with '-r'?")
            sys.exit(1)

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

    if options.verbose == 0:
        log.handlers[0].setLevel(logging.WARNING)
        logging.getLogger("mock.Root.state").handlers[0].setLevel(logging.WARNING)
    elif options.verbose == 1:
        log.handlers[0].setLevel(logging.INFO)
    elif options.verbose == 2:
        log.handlers[0].setLevel(logging.DEBUG)
        logging.getLogger("mock.Root.build").propagate = 1
        logging.getLogger("mock").propagate = 1

    logging.getLogger("trace").propagate=0
    if options.trace:
        logging.getLogger("trace").propagate=1

    # cmdline options override config options
    set_config_opts_per_cmdline(config_opts, options, args)

    # elevate privs
    uidManager._becomeUser(0, 0)

    # do whatever we're here to do
    log.info("mock.py version %s starting..." % __VERSION__)
    chroot = mock.backend.Root(config_opts, uidManager)

    # dump configuration to log
    log.debug("mock final configuration:")
    for k, v in config_opts.items():
        log.debug("    %s:  %s" % (k, v))

    ret["chroot"] = chroot
    ret["config_opts"] = config_opts
    os.umask(002)

    # New namespace starting from here
    try:
        mock.util.unshare(mock.util.CLONE_NEWNS)
    except:
        log.info("Namespace unshare failed.")

    if options.mode == 'init':
        if config_opts['clean']:
            chroot.clean()
        chroot.init()

    elif options.mode == 'clean':
        chroot.clean()

    elif options.mode == 'shell':
        chroot.tryLockBuildRoot()
        try:
            chroot._mountall()
            if config_opts['internal_setarch']:
                mock.util.condPersonality(config_opts['target_arch'])
            cmd = ' '.join(args)
            status = os.system("PS1='mock-chroot> ' /usr/sbin/chroot %s %s" % (chroot.rootdir, cmd))
            ret['exitStatus'] = os.WEXITSTATUS(status)

        finally:
            chroot._umountall()

    elif options.mode == 'chroot':
        if len(args) == 0:
            log.critical("You must specify a command to run")
            sys.exit(50)
        elif len(args) == 1:
            args = args[0]

        log.info("Running in chroot: %s" % args)
        chroot.tryLockBuildRoot()
        chroot._resetLogging()
        chroot.doChroot(args)

    elif options.mode == 'installdeps':
        if len(args) == 0:
            log.critical("You must specify an SRPM file.")
            sys.exit(50)

        for hdr in mock.util.yieldSrpmHeaders(args, plainRpmOk=1):
            pass
        chroot.tryLockBuildRoot()
        try:
            chroot._mountall()
            chroot.installSrpmDeps(*args)
        finally:
            chroot._umountall()

    elif options.mode == 'install':
        if len(args) == 0:
            log.critical("You must specify a package list to install.")
            sys.exit(50)

        chroot.tryLockBuildRoot()
        chroot.yumInstall(*args)

    elif options.mode == 'update':
        chroot.yumUpdate()

    elif options.mode == 'rebuild':
        do_rebuild(config_opts, chroot, args)

    elif options.mode == 'orphanskill':
        mock.util.orphansKill(chroot.rootdir)
    elif options.mode == 'copyin':
        chroot.tryLockBuildRoot()
        chroot._resetLogging()
        uidManager.dropPrivsForever()
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
            log.debug("copying %s to %s" % (src, dest))
            if os.path.isdir(src):
                shutil.copytree(src, dest)
            else:
                shutil.copy(src, dest)
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
            log.debug("copying %s to %s" % (src, dest))
            if os.path.isdir(src):
                shutil.copytree(src, dest)
            else:
                shutil.copy(src, dest)

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

    except (KeyboardInterrupt,):
        exitStatus = 7
        log.error("Exiting on user interrupt, <CTRL>-C")

    except (mock.exception.BadCmdline), exc:
        exitStatus = exc.resultcode
        log.error(str(exc))
        killOrphans = 0

    except (mock.exception.BuildRootLocked), exc:
        exitStatus = exc.resultcode
        log.error(str(exc))
        killOrphans = 0

    except (mock.exception.Error), exc:
        exitStatus = exc.resultcode
        log.error(str(exc))

    except (Exception,), exc:
        exitStatus = 1
        log.exception(exc)

    if killOrphans and retParams:
        mock.util.orphansKill(retParams["chroot"].rootdir)

    logging.shutdown()
    sys.exit(exitStatus)



