#!/usr/bin/python -tt
# vim:tw=0:ts=4:sw=4:et:
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

import os
import os.path
import sys
import grp

from optparse import OptionParser

# all of the variables below are substituted by the build system
__VERSION__="0.8.0"
SYSCONFDIR="/usr/local/etc"
PYTHONDIR="/usr/local/lib/python2.5/site-packages"
PKGPYTHONDIR="/usr/local/lib/python2.5/site-packages/mock"
MOCKCONFDIR= SYSCONFDIR + "/mock"

sys.path.insert(0,PYTHONDIR)

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
    # global
    config_opts['basedir'] = '/var/lib/mock/' # root name is automatically added to this
    config_opts['clean'] = True
    config_opts['debug'] = False
    config_opts['verbose'] = False
    import grp
    config_opts['chrootuser'] = 'mockbuild'
    config_opts['chrootgroup'] = 'mockbuild'
    config_opts['chrootuid'] = os.geteuid()
    config_opts['chrootgid'] = grp.getgrnam("mock")[2]
    config_opts['chroothome'] = '/builddir'
    config_opts['log_config_file'] = 'logging.conf'

    # (global) caching-related config options
    config_opts['rebuild_cache'] = False
    config_opts['use_cache'] = True
    config_opts['pack_cmd'] = "tar xvjf"
    config_opts['unpack_cmd'] = "tar cvjf"
    config_opts['cache_ext'] = ".tar.gz"
    config_opts['cache_topdir'] = "root-cache"
    config_opts['max_cache_age_days'] = 15

    # commands
    config_opts['chroot'] = '/usr/sbin/chroot'
    config_opts['mount'] = '/bin/mount'
    config_opts['umount'] = '/usr/umount'
    config_opts['rpmbuild_timeout'] = 0

    # dependent on guest OS
    config_opts['use_host_resolv'] = True
    config_opts['runuser'] = '/sbin/runuser'
    config_opts['chroot_setup_cmd'] = 'install buildsys-build'
    config_opts['target_arch'] = 'i386'
    config_opts['files'] = {}
    config_opts['yum.conf'] = ''
    config_opts['macros'] = {'%%_topdir': '%s/build' % config_opts['chroothome'],
                             '%%_rpmfilename': '%%%%{NAME}-%%%%{VERSION}-%%%%{RELEASE}.%%%%{ARCH}.rpm'}

    config_opts['more_buildreqs'] = {}
    config_opts['files']['etc/hosts'] = "127.0.0.1 localhost localhost.localdomain\n"


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
    config_path=MOCKCONFDIR
    if options.configdir:
        config_path = options.configdir

    # Read in the default values which can be overwritten
    # with the more specific config being loaded below.
    for cfg in ( os.path.join(config_path, 'defaults.cfg'), '%s/%s.cfg' % (config_path, options.chroot)):
        if os.path.exists(cfg):
            execfile(cfg)
        else:
            error("Could not find required config file: %s" % cfg)
            sys.exit(1)
    
    # cmdline options override config options
    set_config_opts_per_cmdline(config_opts, options)

    import logging.config
    logging.config.fileConfig(os.path.join(config_path, options["log_config_file"]))

    # do whatever we're here to do
    if args[0] == 'clean':
        pass
    elif args[0] == 'init':
        pass
    elif args[0] == 'chroot':
        pass
    elif args[0] == 'shell':
        pass
    elif args[0] == 'installdeps':
        pass
    elif args[0] == 'rebuild':
        pass
    else:
        pass


if __name__ == '__main__':
    main()


