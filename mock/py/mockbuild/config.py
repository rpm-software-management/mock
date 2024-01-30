# -*- coding: utf-8 -*-
# vim:expandtab:autoindent:tabstop=4:shiftwidth=4:filetype=python:textwidth=0:
# License: GPL2 or later see COPYING

from __future__ import print_function

from ast import literal_eval
from glob import glob
import grp
import logging
import os
import os.path
import pwd
import re
import shlex
import socket
import sys
import warnings

from templated_dictionary import TemplatedDictionary
from . import exception
from . import text
from .constants import MOCKCONFDIR, PKGPYTHONDIR, VERSION
from .file_util import is_in_dir
from .trace_decorator import getLog, traceLog
from .uid import getresuid, getresgid
from .util import set_use_nspawn, setup_operations_timeout

PLUGIN_LIST = ['tmpfs', 'root_cache', 'yum_cache', 'mount', 'bind_mount',
               'ccache', 'selinux', 'package_state', 'chroot_scan',
               'lvm_root', 'compress_logs', 'sign', 'pm_request',
               'hw_info', 'procenv', 'showrc', 'rpkg_preprocessor',
               'rpmautospec']

def nspawn_supported():
    """Detect some situations where the systemd-nspawn chroot code won't work"""
    with open("/proc/1/cmdline", "rb") as f:
        # if PID 1 has a non-0 UID, then we're running in a user namespace
        # without a PID namespace. systemd-nspawn won't work
        if os.fstat(f.fileno()).st_uid != 0:
            return False

        argv0 = f.read().split(b'\0')[0]

        # If PID 1 is not systemd, then we're in a PID namespace, or systemd
        # isn't running on the system: systemd-nspawn won't work.
        return os.path.basename(argv0) == b'systemd'


@traceLog()
def setup_default_config_opts():
    "sets up default configuration."
    config_opts = TemplatedDictionary(alias_spec={'dnf.conf': ['yum.conf', 'dnf5.conf']})
    config_opts['config_paths'] = []
    config_opts['version'] = VERSION
    config_opts['basedir'] = '/var/lib/mock'  # root name is automatically added to this
    config_opts['resultdir'] = '{{basedir}}/{{root}}/result'
    config_opts['rootdir'] = '{{basedir}}/{{root}}/root'
    config_opts['cache_topdir'] = '/var/cache/mock'
    config_opts['clean'] = True
    config_opts['check'] = True
    config_opts['post_install'] = False
    config_opts['chroothome'] = '/builddir'
    config_opts['log_config_file'] = 'logging.ini'
    config_opts['rpmbuild_timeout'] = 0
    config_opts['host_arch'] = os.uname()[-1]
    config_opts['chrootuid'] = os.getuid()
    try:
        config_opts['chrootgid'] = grp.getgrnam("mock")[2]
    except KeyError:
        #  'mock' group doesn't exist, must set in config file
        pass
    config_opts['chrootgroup'] = 'mock'
    config_opts['chrootuser'] = 'mockbuild'
    config_opts['build_log_fmt_name'] = "unadorned"
    config_opts['root_log_fmt_name'] = "detailed"
    config_opts['state_log_fmt_name'] = "state"
    config_opts['online'] = True
    config_opts['isolation'] = None
    config_opts['use_nspawn'] = None
    config_opts['rpmbuild_networking'] = False
    config_opts['nspawn_args'] = ['--capability=cap_ipc_lock']
    config_opts['use_container_host_hostname'] = True

    config_opts['use_bootstrap'] = True
    config_opts['use_bootstrap_image'] = True
    config_opts['bootstrap_image'] = 'fedora:latest'
    config_opts['bootstrap_image_skip_pull'] = False
    config_opts['bootstrap_image_ready'] = False
    config_opts['bootstrap_image_fallback'] = True
    config_opts['bootstrap_image_keep_getting'] = 120

    config_opts['internal_dev_setup'] = True

    # cleanup_on_* only take effect for separate --resultdir
    # config_opts provides fine-grained control. cmdline only has big hammer
    config_opts['cleanup_on_success'] = True
    config_opts['cleanup_on_failure'] = True

    config_opts['exclude_from_homedir_cleanup'] = ['build/SOURCES', '.bash_history',
                                                   '.bashrc']

    config_opts['createrepo_on_rpms'] = False
    config_opts['createrepo_command'] = '/usr/bin/createrepo_c -d -q -x *.src.rpm'  # default command

    config_opts['tar_binary'] = "/bin/tar"
    config_opts['tar'] = "gnutar"

    config_opts['backup_on_clean'] = False
    config_opts['backup_base_dir'] = "{{basedir}}/backup"

    config_opts['redhat_subscription_required'] = False

    config_opts['ssl_ca_bundle_path'] = None

    config_opts['ssl_extra_certs'] = None

    # (global) plugins and plugin configs.
    # ordering constraings: tmpfs must be first.
    #    root_cache next.
    #    after that, any plugins that must create dirs (yum_cache)
    #    any plugins without preinit hooks should be last.
    config_opts['plugins'] = PLUGIN_LIST
    config_opts['plugin_dir'] = os.path.join(PKGPYTHONDIR, "plugins")
    config_opts['plugin_conf'] = {
        'ccache_enable': False,
        'ccache_opts': {
            'max_cache_size': "4G",
            'compress': None,
            'dir': "{{cache_topdir}}/{{root}}/ccache/u{{chrootuid}}/",
            'hashdir': True,
            'debug': False,
            'show_stats': False,
        },
        'yum_cache_enable': True,
        'yum_cache_opts': {
            'max_age_days': 30,
            'max_metadata_age_days': 30,
            'online': True},
        'root_cache_enable': True,
        'root_cache_opts': {
            'age_check': True,
            'max_age_days': 15,
            'dir': "{{cache_topdir}}/{{root}}/root_cache/",
            'compress_program': 'pigz',
            'decompress_program': None,
            'exclude_dirs': ["./proc", "./sys", "./dev", "./tmp/ccache", "./var/cache/yum", "./var/cache/dnf",
                             "./var/log"],
            'extension': '.gz'},
        'bind_mount_enable': True,
        'bind_mount_opts': {
            'dirs': [
                # specify like this:
                # ('/host/path', '/bind/mount/path/in/chroot/' ),
                # ('/another/host/path', '/another/bind/mount/path/in/chroot/'),
            ],
            'create_dirs': False},
        'mount_enable': True,
        'mount_opts': {'dirs': [
            # specify like this:
            # ("/dev/device", "/mount/path/in/chroot/", "vfstype", "mount_options"),
        ]},
        'tmpfs_enable': False,
        'tmpfs_opts': {
            'required_ram_mb': 900,
            'max_fs_size': None,
            'mode': '0755',
            'keep_mounted': False},
        'selinux_enable': True,
        'selinux_opts': {},
        'package_state_enable': True,
        'package_state_opts': {
            'available_pkgs': False,
            'installed_pkgs': True,
        },
        'pm_request_enable': False,
        'pm_request_opts': {},
        'lvm_root_enable': False,
        'lvm_root_opts': {
            'pool_name': 'mockbuild',
        },
        'chroot_scan_enable': False,
        'chroot_scan_opts': {
            'regexes': [
                "^[^k]?core(\\.\\d+)?$", "\\.log$",
            ],
            'only_failed': True,
            'write_tar': False,
        },
        'sign_enable': False,
        'sign_opts': {
            'cmd': 'rpmsign',
            'opts': '--addsign %(rpms)s',
        },
        'hw_info_enable': True,
        'hw_info_opts': {
        },
        'procenv_enable': False,
        'procenv_opts': {
        },
        'showrc_enable': False,
        'showrc_opts': {
        },
        'compress_logs_enable': False,
        'compress_logs_opts': {
            'command': 'gzip',
        },
        'rpkg_preprocessor_enable': False,
        'rpkg_preprocessor_opts': {
            'requires': ['preproc-rpmspec'],
            'cmd': '/usr/bin/preproc-rpmspec %(source_spec)s --output %(target_spec)s',
        },
        'rpmautospec_enable': False,
        'rpmautospec_opts': {
            'requires': ['rpmautospec'],
            'cmd_base': [
                '/usr/bin/rpmautospec',
                'process-distgit',
            ]
        },
    }

    config_opts['environment'] = {
        'TERM': 'vt100',
        'SHELL': '/bin/bash',
        'HOME': '/builddir',
        'HOSTNAME': 'mock',
        'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
        'PROMPT_COMMAND': r'printf "\033]0;<mock-chroot>\007"',
        'PS1': r'<mock-chroot> \s-\v\$ ',
        'LANG': 'C.UTF-8',
    }

    runtime_plugins = [runtime_plugin
                       for (runtime_plugin, _)
                       in [os.path.splitext(os.path.basename(tmp_path))
                           for tmp_path
                           in glob(config_opts['plugin_dir'] + "/*.py")]
                       if runtime_plugin not in config_opts['plugins']]
    for runtime_plugin in sorted(runtime_plugins):
        config_opts['plugins'].append(runtime_plugin)
        config_opts['plugin_conf'][runtime_plugin + "_enable"] = False
        config_opts['plugin_conf'][runtime_plugin + "_opts"] = {}

    # SCM defaults
    config_opts['scm'] = False
    config_opts['scm_opts'] = {
        'method': 'git',
        'cvs_get': 'cvs -d /srv/cvs co SCM_BRN SCM_PKG',
        'git_get': 'git clone SCM_BRN git://localhost/SCM_PKG.git SCM_PKG',
        'svn_get': 'svn co file:///srv/svn/SCM_PKG/SCM_BRN SCM_PKG',
        'distgit_get': 'rpkg clone -a --branch SCM_BRN SCM_PKG SCM_PKG',
        'distgit_src_get': 'rpkg sources',
        'spec': 'SCM_PKG.spec',
        'int_src_dir': None,
        'ext_src_dir': os.devnull,
        'write_tar': False,
        'git_timestamps': False,
        'exclude_vcs': True,
    }

    # dependent on guest OS
    config_opts['use_host_resolv'] = False
    config_opts['chroot_setup_cmd'] = ('groupinstall', 'buildsys-build')
    config_opts['repo_arch'] = None
    config_opts['repo_arch_map'] = {}
    config_opts['target_arch'] = 'i386'
    config_opts['releasever'] = None
    config_opts['rpmbuild_arch'] = None  # <-- None means set automatically from target_arch
    config_opts['dnf_vars'] = {}
    config_opts['yum_builddep_opts'] = []
    config_opts['yum_common_opts'] = []
    config_opts['update_before_build'] = True
    config_opts['priorities.conf'] = '\n[main]\nenabled=0'
    config_opts['rhnplugin.conf'] = '\n[main]\nenabled=0'
    config_opts['subscription-manager.conf'] = ''
    config_opts['more_buildreqs'] = {}
    config_opts['nosync'] = False
    config_opts['nosync_force'] = False
    config_opts['files'] = {}
    config_opts['macros'] = {
        '%_topdir': '%s/build' % config_opts['chroothome'],
        '%_rpmfilename': '%%{NAME}-%%{VERSION}-%%{RELEASE}.%%{ARCH}.rpm',
        # This is actually set in check_arch_combination()
        # '%_platform_multiplier': 1,
    }
    config_opts['hostname'] = None
    config_opts['module_enable'] = []
    config_opts['module_install'] = []
    config_opts['module_setup_commands'] = []
    config_opts['forcearch'] = None

    # Initialize all the bootstrap configuration (bootstrap_ prefixed) we don't
    # want to automatically inherit from the target buildroot configuration.
    config_opts['bootstrap_chroot_additional_packages'] = []
    config_opts['bootstrap_module_enable'] = []
    config_opts['bootstrap_module_install'] = []
    config_opts['bootstrap_module_setup_commands'] = []

    # security config
    config_opts['no_root_shells'] = False
    config_opts['extra_chroot_dirs'] = []

    config_opts['package_manager'] = 'dnf'
    config_opts['package_manager_max_attempts'] = 1
    config_opts['package_manager_attempt_delay'] = 10

    config_opts['dynamic_buildrequires'] = True
    config_opts['dynamic_buildrequires_max_loops'] = 10

    config_opts['external_buildrequires'] = False

    config_opts['dev_loop_count'] = 12

    # configurable commands executables
    config_opts['yum_command'] = '/usr/bin/yum'
    config_opts['system_yum_command'] = '/usr/bin/yum'
    config_opts['yum_install_command'] = 'install yum yum-utils'
    config_opts['yum_builddep_command'] = '/usr/bin/yum-builddep'
    config_opts["yum_avoid_opts"] = {}

    config_opts['dnf_command'] = '/usr/bin/dnf-3'
    config_opts['system_dnf_command'] = '/usr/bin/dnf-3'
    config_opts['dnf_common_opts'] = ['--setopt=deltarpm=False', '--setopt=allow_vendor_change=yes', '--allowerasing']
    config_opts['dnf_install_command'] = 'install python3-dnf python3-dnf-plugins-core'
    config_opts['dnf_disable_plugins'] = ['local', 'spacewalk', 'versionlock']
    config_opts["dnf_avoid_opts"] = {}

    config_opts['dnf5_command'] = '/usr/bin/dnf5'
    config_opts['system_dnf5_command'] = '/usr/bin/dnf5'
    config_opts['dnf5_common_opts'] = ['--setopt=deltarpm=False', '--setopt=allow_vendor_change=yes', '--allowerasing']
    config_opts['dnf5_install_command'] = 'install dnf5 dnf5-plugins'
    config_opts['dnf5_disable_plugins'] = []
    # No --allowerasing with remove, per
    # https://github.com/rpm-software-management/dnf5/issues/729
    config_opts["dnf5_avoid_opts"] = {
        "remove": ["--allowerasing"],
        "repoquery": ["--allowerasing"],
        "makecache": ["--allowerasing"],
        "search": ["--allowerasing"],
        "info": ["--allowerasing"],
    }

    config_opts['microdnf_command'] = '/usr/bin/microdnf'
    # "dnf-install" is special keyword which tells mock to use install but with DNF
    config_opts['microdnf_install_command'] = \
        'dnf-install microdnf dnf dnf-plugins-core'
    config_opts['microdnf_builddep_command'] = '/usr/bin/dnf'
    config_opts['microdnf_builddep_opts'] = []
    config_opts['microdnf_common_opts'] = []
    config_opts['microdnf_avoid_opts'] = {}

    config_opts['rpm_command'] = '/bin/rpm'
    config_opts['rpmbuild_command'] = '/usr/bin/rpmbuild'
    config_opts['user_agent'] = "Mock ({{ root }}; {{ target_arch }})"
    config_opts['opstimeout'] = 0

    config_opts['stderr_line_prefix'] = ""

    # Packages from this option are baked into the root-cache tarball.
    config_opts['chroot_additional_packages'] = []

    # This option is command-line only, packages are always re-installed (ie.
    # not cached in the root-cache tarball).
    config_opts['additional_packages'] = None

    config_opts["no-config"] = {}

    config_opts["seccomp"] = False

    config_opts["copy_host_users"] = []

    # shadow-utils --prefix and --root options do not play well with
    # FreeIPA-provided subids. Using the shadow-utils inside the
    # chroot works around this but this is a niche situation so it is
    # not the default.
    # Upstream issue https://github.com/shadow-maint/shadow/issues/897
    config_opts["use_host_shadow_utils"] = True

    # mapping from target_arch (or forcearch) to arch in /usr/bin/qemu-*-static
    config_opts["qemu_user_static_mapping"] = {
        'aarch64': 'aarch64',
        'armv7hl': 'arm',
        'i386': 'i386',
        'i686': 'i386',
        'ppc64': 'ppc64',
        'ppc64le': 'ppc64le',
        's390x': 's390x',
        'x86_64': 'x86_64',
    }

    config_opts["recursion_limit"] = 5000

    return config_opts


def multiply_platform_multiplier(config_opts):
    """ Define '%_platform_multiplier' macro based on forcearch.
        But respect possible overrides in config.
    """
    if '%_platform_multiplier' not in config_opts["macros"]:
        config_opts["macros"]["%_platform_multiplier"] = 10 if config_opts["forcearch"] else 1

@traceLog()
def set_config_opts_per_cmdline(config_opts, options, args):
    "takes processed cmdline args and sets config options."

    cli_opt_new = {}
    for cli_opt in options.cli_config_opts:
        k, v = cli_opt.split("=", 1)
        # convert string to boolean and int if possible
        if v in ['true', 'True']:
            v = True
        elif v in ['false', 'False']:
            v = False
        elif v in ['none', 'None']:
            v = None
        else:
            try:
                v = int(v)
            except ValueError:
                pass
        if k not in cli_opt_new:
            cli_opt_new[k] = v
        elif isinstance(cli_opt_new[k], list):
            cli_opt_new[k].append(v)
        else:
            if v == '':
                # hack!
                # specify k twice, second v is empty, this make it list with one value
                cli_opt_new[k] = [cli_opt_new[k]]
            else:
                cli_opt_new[k] = [cli_opt_new[k], v]
    config_opts.update(cli_opt_new)

    config_opts['verbose'] = options.verbose
    if 'print_main_output' not in config_opts or config_opts['print_main_output'] is None:
        config_opts['print_main_output'] = config_opts['verbose'] > 0 and sys.stderr.isatty()

    # do some other options and stuff
    if options.arch:
        config_opts['target_arch'] = options.arch
    if options.rpmbuild_arch:
        config_opts['rpmbuild_arch'] = options.rpmbuild_arch
    elif config_opts['rpmbuild_arch'] is None:
        config_opts['rpmbuild_arch'] = config_opts['target_arch']
    if options.forcearch:
        config_opts['forcearch'] = options.forcearch

    if not config_opts['repo_arch']:
        target = config_opts['target_arch']
        config_opts['repo_arch'] = config_opts['repo_arch_map'].get(target, target)

    if not options.clean:
        config_opts['clean'] = options.clean

    if not options.check:
        config_opts['check'] = options.check

    if options.post_install:
        config_opts['post_install'] = options.post_install

    for option in options.rpmwith:
        options.rpmmacros.append("_with_%s --with-%s" %
                                 (option.replace("-", "_"), option))

    for option in options.rpmwithout:
        options.rpmmacros.append("_without_%s --without-%s" %
                                 (option.replace("-", "_"), option))

    for macro in options.rpmmacros:
        try:
            macro = macro.strip()
            k, v = macro.split(" ", 1)
            if not k.startswith('%'):
                k = '%%%s' % k
            config_opts['macros'].update({k: v})
        # pylint: disable=bare-except
        except:
            # pylint: disable=raise-missing-from
            raise exception.BadCmdline(
                "Bad option for '--define' (%s).  Use --define 'macro expr'"
                % macro)

    if options.macrofile:
        config_opts['macrofile'] = os.path.expanduser(options.macrofile)
        if not os.path.isfile(config_opts['macrofile']):
            raise exception.BadCmdline(
                "Input rpm macros file does not exist: %s"
                % options.macrofile)

    if options.resultdir:
        config_opts['resultdir'] = os.path.expanduser(options.resultdir)
    if options.rootdir:
        config_opts['rootdir'] = os.path.expanduser(options.rootdir)
    if options.uniqueext:
        config_opts['unique-ext'] = options.uniqueext
    if options.rpmbuild_timeout is not None:
        config_opts['rpmbuild_timeout'] = options.rpmbuild_timeout
    if options.bootstrapchroot is not None:
        config_opts['use_bootstrap'] = options.bootstrapchroot
    if options.usebootstrapimage is not None:
        config_opts['use_bootstrap_image'] = options.usebootstrapimage
        if options.usebootstrapimage:
            config_opts['use_bootstrap'] = True

    for i in options.disabled_plugins:
        if i not in config_opts['plugins']:
            raise exception.BadCmdline(
                "Bad option for '--disable-plugin=%s'. Expecting one of: %s"
                % (i, config_opts['plugins']))
        config_opts['plugin_conf']['%s_enable' % i] = False
    for i in options.enabled_plugins:
        if i not in config_opts['plugins']:
            raise exception.BadCmdline(
                "Bad option for '--enable-plugin=%s'. Expecting one of: %s"
                % (i, config_opts['plugins']))
        config_opts['plugin_conf']['%s_enable' % i] = True
    for option in options.plugin_opts:
        try:
            p, kv = option.split(":", 1)
            k, v = kv.split("=", 1)
        # pylint: disable=bare-except
        except:
            # pylint: disable=raise-missing-from
            raise exception.BadCmdline(
                "Bad option for '--plugin-option' (%s).  Use --plugin-option 'plugin:key=value'"
                % option)
        if p not in config_opts['plugins']:
            raise exception.BadCmdline(
                "Bad option for '--plugin-option' (%s).  No such plugin: %s"
                % (option, p))
        try:
            v = literal_eval(v)
        # pylint: disable=bare-except
        except:
            pass
        config_opts['plugin_conf'][p + "_opts"].update({k: v})

    use_nspawn = None  # auto-detect by default

    log = logging.getLogger()

    if config_opts['use_nspawn'] in [True, False]:
        log.info("Use of obsoleted configuration option 'use_nspawn'.")
        use_nspawn = config_opts['use_nspawn']

    if config_opts['isolation'] in ['nspawn', 'simple']:
        use_nspawn = config_opts['isolation'] == 'nspawn'
    elif config_opts['isolation'] == 'auto':
        use_nspawn = None  # set auto detection, overrides use_nspawn

    if options.old_chroot:
        use_nspawn = False
        log.error('Option --old-chroot has been deprecated. Use --isolation=simple instead.')
    if options.new_chroot:
        use_nspawn = True
        log.error('Option --new-chroot has been deprecated. Use --isolation=nspawn instead.')

    if options.isolation in ['simple', 'nspawn']:
        use_nspawn = options.isolation == 'nspawn'
    elif options.isolation == 'auto':
        use_nspawn = None  # re-set auto detection
    elif options.isolation is not None:
        raise exception.BadCmdline("Bad option for '--isolation'. Unknown "
                                   "value: %s" % (options.isolation))
    if use_nspawn is None:
        use_nspawn = nspawn_supported()
        getLog().info("systemd-nspawn auto-detected: %s", use_nspawn)

    set_use_nspawn(use_nspawn, config_opts)

    if options.enable_network:
        config_opts['rpmbuild_networking'] = True
        config_opts['use_host_resolv'] = True

    if options.mode in ("rebuild",) and len(args) > 1 and not options.resultdir:
        raise exception.BadCmdline(
            "Must specify --resultdir when building multiple RPMS.")

    if options.mode == "chain" and options.resultdir:
        raise exception.BadCmdline(
            "The --chain mode doesn't support --resultdir, use --localrepo instead")

    if options.cleanup_after is False:
        config_opts['cleanup_on_success'] = False
        config_opts['cleanup_on_failure'] = False

    if options.cleanup_after is True:
        config_opts['cleanup_on_success'] = True
        config_opts['cleanup_on_failure'] = True

    check_config(config_opts)
    # can't cleanup unless resultdir is separate from the root dir
    basechrootdir = os.path.join(config_opts['basedir'], config_opts['root'])
    config_resultdir = text.compat_expand_string(config_opts['resultdir'], config_opts)
    if is_in_dir(config_resultdir, basechrootdir):
        config_opts['cleanup_on_success'] = False
        config_opts['cleanup_on_failure'] = False

    config_opts['cache_alterations'] = options.cache_alterations

    config_opts['online'] = options.online

    if options.pkg_manager:
        config_opts['package_manager'] = options.pkg_manager
    if options.mode == 'yum-cmd':
        config_opts['package_manager'] = 'yum'
    if options.mode == 'dnf-cmd':
        config_opts['package_manager'] = 'dnf'

    if options.short_circuit:
        config_opts['short_circuit'] = options.short_circuit
        config_opts['clean'] = False

    if options.rpmbuild_opts:
        config_opts['rpmbuild_opts'] = options.rpmbuild_opts

    config_opts['enable_disable_repos'] = options.enable_disable_repos

    if options.scm:
        try:
            # pylint: disable=unused-variable,unused-import,import-outside-toplevel
            from . import scm
        except ImportError as e:
            raise exception.BadCmdline(
                "Mock SCM module not installed: %s" % e)

        config_opts['scm'] = options.scm
        for option in options.scm_opts:
            try:
                k, v = option.split("=", 1)
                config_opts['scm_opts'].update({k: v})
            # pylint: disable=bare-except
            except:
                # pylint: disable=raise-missing-from
                raise exception.BadCmdline(
                    "Bad option for '--scm-option' (%s).  Use --scm-option 'key=value'"
                    % option)

    # This option is command-line only (contrary to chroot_additional_packages,
    # which though affects root_cache).
    config_opts["additional_packages"] = options.additional_packages


def check_config(config_opts):
    if 'root' not in config_opts:
        raise exception.ConfigError("Error in configuration "
                                    "- option config_opts['root'] must be present in your config.")


regexp_include = re.compile(r'^\s*include\((.*)\)', re.MULTILINE)


@traceLog()
def include(config_file, search_path, paths):
    if not os.path.isabs(config_file):
        config_file = os.path.join(search_path, config_file)

    if os.path.exists(config_file):
        if config_file in paths:
            getLog().warning("Multiple inclusion of %s, skipping" % config_file)
            return ""

        paths.add(config_file)
        content = open(config_file).read()
        # Search for "include(FILE)" and for each "include(FILE)" replace with
        # content of the FILE, in a perpective of search for includes and replace with his content.
        include_arguments = regexp_include.findall(content)
        if include_arguments is not None:
            for include_argument in include_arguments:
                # pylint: disable=eval-used
                sub_config_file = eval(include_argument)
                sub_content = include(sub_config_file, search_path, paths)
                content = regexp_include.sub(sub_content, content, count=1)
        return content
    else:
        raise exception.ConfigError("Could not find included config file: %s" % config_file)


@traceLog()
def update_config_from_file(config_opts, config_file):
    """
    Parse a given Mock config file with Python interpreter.  Return just the
    'config_opts' global merged with the 'config_opts'.
    """
    config_file = os.path.realpath(config_file)
    included_files = set()
    content = include(config_file, config_opts["config_path"], included_files)

    # TODO: we should avoid doing exec() here long term, and switch to some
    # better form of configuration (like YAML, json, or so?).  But historically
    # the configuration is just a python-syntax file, so as a poor safety
    # measure we disallow this for root (saved set-*IDs checked, too!)
    try:
        exec(content)  # pylint: disable=exec-used
    except Exception as exc:
        raise exception.ConfigError("Config error: {}: {}".format(config_file, str(exc)))

    # this actually allows multiple inclusion of one file, but not in a loop
    new_paths = set(config_opts["config_paths"]) | included_files
    config_opts["config_paths"] = list(new_paths)


@traceLog()
def nice_root_alias_error(name, alias_name, arch, no_configs, log):
    """
    The epel-8 configs (and others in future) will be replaced with more
    specific alternatives.  This is the way to inform user about alternatives.
    """
    any_alternative = False

    if alias_name not in no_configs:
        return any_alternative

    arg_name = "{}-{}".format(alias_name, arch)

    aliases = no_configs[alias_name]["alternatives"]
    order = 0

    for alias_base, alias in aliases.items():
        short_name = "{}-{}".format(alias_base, arch)
        filename = "{}.cfg".format(short_name)
        cfg_path = os.path.join("/etc/mock", filename)
        if not os.path.exists(cfg_path):
            continue
        if not any_alternative:
            log.error("There are those alternatives:")
            any_alternative = True
        order += 1
        pfx = "    "
        log.error("")
        log.error("[{}] {}".format(order, short_name))

        alt_cmd = ['mock'] + [short_name if a == arg_name else shlex.quote(a)
                              for a in sys.argv[1:]]

        log.error("%sUse instead: %s ", pfx, ' '.join(alt_cmd))
        for line in alias["description"]:
            log.error(pfx + line)

        log.error("%sEnable permanently by:", pfx)
        homeconfig = os.path.join(os.path.expanduser('~'), '.config', 'mock')
        if not os.path.exists(homeconfig):
            log.error("%s$ mkdir -p %s", pfx, homeconfig)

        log.error("%s$ ln -s %s %s/%s-%s.cfg", pfx, cfg_path,
                  homeconfig, alias_name, arch)

    return any_alternative


@traceLog()
def do_update_config(log, config_opts, cfg, name, skipError=True):
    if os.path.exists(cfg):
        log.info("Reading configuration from %s", cfg)
        update_config_from_file(config_opts, cfg)
        setup_operations_timeout(config_opts)
        check_macro_definition(config_opts)
        return

    if skipError:
        return

    log.error("Could not find required config file: %s", cfg)

    match = re.match(r"^([\w-]+)-(\w+)-(\w+)$", name)
    no_configs = config_opts.get("no-config")

    if match and no_configs:
        alias = "-".join([match[1], match[2]])
        if nice_root_alias_error(name, alias, match[3], no_configs, log):
            raise exception.ConfigError(
                "Mock config '{}' not found, see errors above.".format(name))

    if name == "default":
        log.error("  Did you forget to specify the chroot to use with '-r'?")
    if "/" in cfg:
        log.error("  If you're trying to specify a path, include the .cfg extension, e.g. -r ./target.cfg")

    raise exception.ConfigError("Non-existing Mock config '{}'".format(name))


def print_description(config_path, config_filename):
    basename_without_ext = parse_config_filename(config_filename)[2]
    try:
        config_opts = load_config(config_path, config_filename)
        description = config_opts.get("description", "")
    except exception.ConfigError:
        description = 'error during parsing the config file'
    print("{} {}".format(basename_without_ext.ljust(34), description))


def parse_config_filename(config_filename):
    """ Accepts filename and returns (dirname, basename, basename_without_ext) """
    basename = os.path.basename(config_filename)
    dirname = os.path.dirname(config_filename)
    basename_without_ext = os.path.splitext(basename)[0]
    return (basename, dirname, basename_without_ext)

def get_global_configs(config_opts):
    """ Return filenames of global configs of chroots"""
    result = []
    for config_filename in glob("{}/*.cfg".format(config_opts['config_path'])):
        if config_filename in ["/etc/mock/chroot-aliases.cfg", "/etc/mock/site-defaults.cfg"]:
            continue
        result.append(config_filename)
    return result


def get_user_config_files(config_opts):
    """ Return filenames of user configs of chroots """
    uid = os.getuid()
    custom_path = os.path.join(os.path.expanduser('~' + pwd.getpwuid(uid)[0]), '.config/mock/*.cfg')
    result = glob(custom_path)
    return result


@traceLog()
def list_configs(config_opts):
    log = logging.getLogger()
    log.disabled = True
    # array to save config paths
    print("{} {}".format("config name".ljust(34), "description"))
    print("Global configs:")
    for config_filename in sorted(get_global_configs(config_opts)):
        print_description(config_opts['config_path'], config_filename)
    user_config_files = get_user_config_files(config_opts)
    if user_config_files:
        print("Custom configs:")
        # ~/.config/mock/CHROOTNAME.cfg
        for config_filename in sorted(user_config_files):
            print_description(config_opts['config_path'], config_filename)
        log.disabled = False


@traceLog()
def simple_load_config(name, config_path=None):
    """ wrapper around load_config() intended by use 3rd party SW """

    for the_id in getresuid() + getresgid():
        if the_id != 0:
            continue
        warnings.warn(
            "Parsing Mock configuration as root is highly discouraged, "
            "see https://rpm-software-management.github.io/mock/#setup"
        )
        break

    if config_path is None:
        config_path = MOCKCONFDIR
    return load_config(config_path, name)


@traceLog()
def load_config(config_path, name):
    log = logging.getLogger()
    config_opts = setup_default_config_opts()

    # array to save config paths
    config_opts['config_path'] = config_path
    config_opts['chroot_name'] = name

    uid = config_opts["chrootuid"]

    # Read in the config files: default, and then user specified
    if name.endswith('.cfg'):
        # If the .cfg is explicitly specified we take the root arg to
        # specify a path, rather than looking it up in the configdir.
        chroot_cfg_path = name
        config_opts['chroot_name'] = os.path.splitext(os.path.basename(name))[0]
    else:
        # ~/.config/mock/CHROOTNAME.cfg
        cfg = os.path.join(os.path.expanduser('~' + pwd.getpwuid(uid)[0]),
                           '.config/mock/{}.cfg'.format(name))
        if os.path.exists(cfg):
            chroot_cfg_path = cfg
        else:
            chroot_cfg_path = '%s/%s.cfg' % (config_path, name)
    config_opts['config_file'] = chroot_cfg_path

    # load the global config files
    for cfg_file in [
        os.path.join(config_path, "site-defaults.cfg"),
        os.path.join(config_path, "chroot-aliases.cfg"),
    ]:
        do_update_config(log, config_opts, cfg_file, name)

    # load the "chroot" specific config (-r option)
    do_update_config(log, config_opts, chroot_cfg_path, name, skipError=False)

    # Read user specific config file
    cfg = os.path.join(os.path.expanduser(
        '~' + pwd.getpwuid(os.getuid())[0]), '.mock/user.cfg')
    do_update_config(log, config_opts, cfg, name)
    cfg = os.path.join(os.path.expanduser(
        '~' + pwd.getpwuid(os.getuid())[0]), '.config/mock.cfg')
    do_update_config(log, config_opts, cfg, name)

    if config_opts['use_container_host_hostname'] and '%_buildhost' not in config_opts['macros']:
        config_opts['macros']['%_buildhost'] = socket.getfqdn()

    # Now when all options are correctly loaded from config files, turn the
    # jinja templating ON.
    config_opts['__jinja_expand'] = True

    # use_bootstrap_container is deprecated option
    if 'use_bootstrap_container' in config_opts:
        log.warning("config_opts['use_bootstrap_container'] is deprecated, "
                    "please use config_opts['use_bootstrap'] instead")
        config_opts['use_bootstrap'] = config_opts['use_bootstrap_container']

    return config_opts


@traceLog()
def check_macro_definition(config_opts):
    for k in list(config_opts['macros']):
        v = config_opts['macros'][k]
        if not k or (not v and (v is not None)) or len(k.split()) != 1:
            raise exception.BadCmdline(
                "Bad macros 'config_opts['macros']['%s'] = ['%s']'" % (k, v))
        if not k.startswith('%'):
            del config_opts['macros'][k]
            k = '%{0}'.format(k)
            config_opts['macros'].update({k: v})
