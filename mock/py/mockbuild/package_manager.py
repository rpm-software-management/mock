# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import copy
import glob
import os.path
import shutil
import sys
import time
import re
from textwrap import dedent
from configparser import ConfigParser

from distutils.dir_util import copy_tree
from distutils.errors import DistutilsFileError

from . import file_util
from . import util
from .exception import BuildError, Error, YumError
from .trace_decorator import traceLog, getLog
from .mounts import BindMountPoint

fallbacks = {
    'dnf': ['dnf', 'yum'],
    'yum': ['yum', 'dnf'],
    'microdnf': ['microdnf', 'dnf', 'yum'],
}


def package_manager_from_string(name):
    if name == 'yum':
        return Yum
    if name == 'dnf':
        return Dnf
    if name == 'microdnf':
        return MicroDnf
    raise Exception('Unrecognized package manager "{}"'.format(name))


def package_manager_exists_on_host(name, config_opts, bootstrap=False):
    option = '{}_command'.format(name)
    pathname = config_opts[option]
    if not os.path.isfile(pathname):
        if pathname == '/usr/bin/yum':
            # only _exact_ match here, with custom config like
            # /usr/local/bin/yum user must know where yum is
            if os.path.isfile('/usr/bin/yum-deprecated'):
                return True
        return False
    real_pathname = os.path.realpath(pathname)
    # resolve symlinks, and detect that e.g. /bin/yum doesn't point to /bin/dnf
    if name not in real_pathname:
        if not bootstrap:
            getLog().warning("Not using '%s', it is symlink to '%s'", pathname,
                             real_pathname)
        return False
    return True


def package_manager_class_fallback(desired, config_opts, bootstrap):
    getLog().debug("search for '%s' package manager", desired)
    if desired not in fallbacks:
        raise Exception('Unexpected package manager "{}"'.format(desired))

    for manager in fallbacks[desired]:
        if package_manager_exists_on_host(manager, config_opts, bootstrap):
            ret_val = package_manager_from_string(manager)
            if desired == manager:
                return ret_val

            getLog().info("Using '%s' instead of '%s'%s", manager, desired,
                          " for bootstrap chroot" if bootstrap else "")

            if 'dnf_warning' in config_opts and not config_opts['dnf_warning']:
                return ret_val

            if not bootstrap:
                print("""WARNING! WARNING! WARNING!
You are building package for distribution which uses {0}. However your system
does not support {0}. You can continue with {1}, which will likely succeed,
but the installed chroot may look a little different.
  1. Please consider --bootstrap-chroot option, or
  2. install {0} on your host system.
You can suppress this warning when you put
  config_opts['dnf_warning'] = False
in Mock config.""".format(desired.upper(), manager.upper()))
                input("Press Enter to continue.")

            return ret_val

    raise Exception("No package from {} found".format(fallbacks[desired]))


def package_manager_class(config_opts, buildroot, bootstrap_buildroot=None):
    pm = config_opts['package_manager']

    if buildroot.is_bootstrap:
        # pkgmanager _to install_ bootstrap.  we don't care about the package
        # manager too much, so we tolerate cross-pkgmanager installation here
        return package_manager_class_fallback(pm, config_opts, True)

    if bootstrap_buildroot:
        # Installing from bootstrap to destination buildroot, we expect that the
        # desired pkg manager is installed and there's need to warn and do
        # fallbacks.
        return package_manager_from_string(pm)

    # installing from host directly to destination buildroot, this may fail
    # miserably (especially if pm=dnf, and only yum is available).
    return package_manager_class_fallback(pm, config_opts, False)


def package_manager(config_opts, buildroot, plugins, bootstrap_buildroot=None):
    is_bootstrap_image = False
    if buildroot.is_bootstrap and buildroot.use_bootstrap_image:
        is_bootstrap_image = True
    cls = package_manager_class(config_opts, buildroot, bootstrap_buildroot)
    return cls(config_opts, buildroot, plugins, bootstrap_buildroot,
               is_bootstrap_image)


class _PackageManager(object):
    name = None
    command = None
    install_command = None
    builddep_command = None
    resolvedep_command = None
    # When support_installroot is False then command is run in target chroot
    # you must ensure that `command` is available in the chroot
    support_installroot = True

    @traceLog()
    def __init__(self, config, buildroot, plugins, bootstrap_buildroot, is_bootstrap_image):
        self.config = config
        self.plugins = plugins
        self.buildroot = buildroot
        self.init_install_output = ""
        self.bootstrap_buildroot = bootstrap_buildroot
        self.is_bootstrap_image = is_bootstrap_image
        self.pkg_manager_config = ""

    @traceLog()
    def build_invocation(self, *args):
        invocation = []
        common_opts = self.config[self.name + '_common_opts']
        cmd = args[0]
        if cmd == 'builddep':
            args = args[1:]
            invocation += self.builddep_command
            common_opts += self.config[self.name + '_builddep_opts']
        elif cmd == 'resolvedep':
            if self.resolvedep_command:
                args = args[1:]
                invocation = self.resolvedep_command
            else:
                invocation = [self.command]
        else:
            invocation = [self.command]
        if self.support_installroot:
            invocation += ['--installroot', self.buildroot.make_chroot_path('')]
        if cmd in ['upgrade', 'update', 'module']:
            invocation += ['-y']
        releasever = self.config['releasever']
        if releasever:
            invocation += ['--releasever', str(releasever)]
        if not self.config['online']:
            invocation.append('-C')
        if self.config['enable_disable_repos']:
            invocation += self.config['enable_disable_repos']
        invocation += common_opts
        invocation += args
        return invocation

    @traceLog()
    def get_pkg_manager_config(self):
        if 'dnf.conf' in self.config:
            return self.config['dnf.conf']
        else:
            return self.config['yum.conf']

    @traceLog()
    def execute(self, *args, **kwargs):
        self.plugins.call_hooks("preyum")
        pm_umount = False
        if not self.buildroot.mounts.essential_mounted:
            self.buildroot.mounts.mountall_essential()
            pm_umount = True
        # intentionally we do not call bootstrap hook here - it does not have sense
        env = self.config['environment'].copy()
        env.update(util.get_proxy_environment(self.config))
        # installation-time specific homedir
        env['HOME'] = self.buildroot.prepare_installation_time_homedir()
        env['LC_MESSAGES'] = 'C.UTF-8'
        if self.buildroot.nosync_path:
            env['LD_PRELOAD'] = self.buildroot.nosync_path
        invocation = self.build_invocation(*args)
        self.buildroot.root_log.debug(invocation)
        kwargs['printOutput'] = kwargs.get('printOutput', True)
        if not self.config['print_main_output']:
            kwargs.pop('printOutput', None)
        else:
            kwargs['pty'] = kwargs.get('pty', True)
        self.buildroot.nuke_rpm_db()

        error = None
        max_attempts = int(self.config['package_manager_max_attempts'])
        for attempt in range(max(max_attempts, 1)):
            if error:
                sleep_seconds = int(self.config['package_manager_attempt_delay'])
                self.buildroot.root_log.warning(
                    "Dnf command failed, retrying, attempt #%s, sleeping %ss",
                    attempt + 1, sleep_seconds)
                time.sleep(sleep_seconds)

            try:
                # either it does not support --installroot (microdnf) or
                # it is bootstrap image made by container with incomaptible dnf/rpm
                if not self.support_installroot or self.is_bootstrap_image:
                    out = util.do(invocation, env=env,
                                  chrootPath=self.buildroot.make_chroot_path(),
                                  **kwargs)
                elif self.bootstrap_buildroot is None:
                    out = util.do(invocation, env=env,
                                  **kwargs)
                else:
                    out = util.do(invocation, env=env,
                                  chrootPath=self.bootstrap_buildroot.make_chroot_path(),
                                  nspawn_args=self.bootstrap_buildroot.config['nspawn_args'],
                                  **kwargs)
                error = None
                break
            except Error as e:
                error = YumError(str(e))

        if pm_umount:
            self.buildroot.mounts.umountall_essential()

        if error is not None:
            raise error

        self.plugins.call_hooks("postyum")

        # Scriptlets in dnf transaction shouldn't keep leftover processes
        # running in background, but it may happen.
        util.orphansKill(self.buildroot.make_chroot_path(), manual_forced=True)

        # intentionally we do not call bootstrap hook here - it does not have sense
        return out

    @traceLog()
    # pylint: disable=unused-argument
    def install(self, *args, **kwargs):
        return self.execute('install', *args)

    # pylint: disable=unused-argument
    @traceLog()
    def remove(self, *args, **kwargs):
        return self.execute('remove', *args)

    # pylint: disable=unused-argument
    @traceLog()
    def update(self, *args, **kwargs):
        return self.execute('update', *args)

    # pylint: disable=unused-argument
    @traceLog()
    def builddep(self, *args, **kwargs):
        try:
            result = self.execute('builddep', returnOutput=1, *args)
        except (FileNotFoundError) as error:
            er = str(error)
            if "builddep" in er:
                print(error)
                print("""
Error:      Neither dnf-utils nor yum-utils are installed. Dnf-utils or yum-utils are needed to complete this action.
            To install dnf-utils use:
            $ dnf install dnf-utils
            or yum-utils:
            $ yum install yum-utils""")
                sys.exit(120)
            else:
                raise
        return result

    @traceLog()
    def copy_distribution_gpg_keys(self):
        # Copy the files from the host to avoid invoking package manager
        # or rebuilding the cached bootstrap chroot.
        keys_path = "/usr/share/distribution-gpg-keys"
        dest_path = os.path.dirname(keys_path)
        chroot_path = self.buildroot.make_chroot_path(dest_path)
        file_util.mkdirIfAbsent(chroot_path)
        self.buildroot.root_log.debug("Copying %s to the bootstrap chroot" % keys_path)
        cmd = ["cp", "-a", keys_path, chroot_path]
        util.do(cmd)

    @traceLog()
    def copy_gpg_keys(self):
        pki_dir = self.buildroot.make_chroot_path('etc', 'pki', 'mock')
        file_util.mkdirIfAbsent(pki_dir)
        for pki_file in glob.glob("/etc/pki/mock/RPM-GPG-KEY-*"):
            shutil.copy(pki_file, pki_dir)

    @traceLog()
    def copy_certs(self):
        cert_path = "/etc/pki/ca-trust"
        pki_dir = self.buildroot.make_chroot_path(cert_path)
        try:
            copy_tree(cert_path, pki_dir)
        except DistutilsFileError:
            warning = "Couldn't copy certs from host, %s doesn't exist or is not readable"
            self.buildroot.root_log.debug(warning, cert_path)

        bundle_path = self.config['ssl_ca_bundle_path']
        if bundle_path:
            self.buildroot.root_log.debug('copying CA bundle into chroot')
            host_bundle = os.path.realpath('/etc/pki/tls/certs/ca-bundle.crt')
            chroot_bundle_path = self.buildroot.make_chroot_path(bundle_path)
            chroot_bundle_dir = os.path.dirname(chroot_bundle_path)
            try:
                os.makedirs(chroot_bundle_dir)
            except FileExistsError:
                pass  # for repeated attempts

            try:
                shutil.copy(host_bundle, chroot_bundle_path)
            except FileNotFoundError:
                # when mock is not run on Fedora or EL
                self.buildroot.root_log.debug("ca bundle not found on host")

    @traceLog()
    def copy_extra_certs(self):
        extra_certs = self.config['ssl_extra_certs']
        if extra_certs:
            self.buildroot.root_log.debug('copying extra certificates into chroot')
            for cert_src, cert_dest in zip(extra_certs[::2], extra_certs[1::2]):
                host_cert_src = os.path.realpath(cert_src)
                chroot_cert_dest = self.buildroot.make_chroot_path(cert_dest)
                chroot_cert_dir = os.path.dirname(chroot_cert_dest)
                file_util.mkdirIfAbsent(chroot_cert_dir)
                try:
                    shutil.copy(host_cert_src, chroot_cert_dest)
                except FileNotFoundError:
                    # when mock is not run on Fedora or EL
                    self.buildroot.root_log.debug("extra certificates not found on host")


    def initialize(self):
        self.copy_gpg_keys()
        self.copy_certs()
        if self.buildroot.is_bootstrap:
            self.copy_distribution_gpg_keys()
            self.copy_extra_certs()
        self.initialize_config()

        try:
            self._bind_mount_repos_to_bootstrap()
        except Exception as e:
            getLog().warning(e)

    def expand_url_vars(self, string):
        """
        Expand DNF variables like $baseurl to proper values in string, and
        return it.
        """
        expand = {
            "basearch": self.config["target_arch"] or '<undef>',
            "releasever": self.config["releasever"] or '<undef>',
        }

        if 'dnf_vars' in self.config:
            for key in self.config['dnf_vars']:
                expand[key] = self.config['dnf_vars'][key]

        for key, value in expand.items():
            # replace both $key and ${key}
            # dnf allows braced variables
            string = string.replace('$' + key, value)
            string = string.replace('${' + key + '}', value)

        return string

    def _bind_mount_repos_to_bootstrap(self):
        if not self.buildroot.is_bootstrap:
            return

        parse = {
            "baseurl": (True, re.compile("[ \t\n,]")),
            "mirrorlist": (False, None),
            "metalink": (False, None),
        }

        # in dnf, the last occurence of the same option beats the previous
        config = ConfigParser(strict=False)
        config.read_string(self.pkg_manager_config)

        # don't bindmount the same paths multiple times
        tried = set()

        for section in config.sections():
            for option in parse:
                directory, split_re = parse[option]

                if option not in config[section]:
                    continue

                raw = config[section][option]
                items = split_re.split(raw) if split_re else [raw]

                for value in items:
                    value = value.strip()
                    if not value:
                        continue

                    # triple slash, we only accept absolute pathnames
                    if value.startswith('file:///'):
                        srcpath = value[7:]
                    elif value.startswith('/'):
                        srcpath = value
                    else:
                        continue

                    srcpath = self.expand_url_vars(srcpath)

                    if srcpath in tried:
                        continue

                    tried.add(srcpath)

                    if directory and not os.path.isdir(srcpath):
                        continue

                    if not os.path.exists(srcpath):
                        continue

                    bindpath = self.buildroot.make_chroot_path(srcpath)
                    bind_mount_point = BindMountPoint(srcpath=srcpath,
                                                      bindpath=bindpath)

                    # we need to use user mounts as essential mounts are used
                    # only for installing into bootstrap chroot
                    self.buildroot.mounts.add_user_mount(bind_mount_point)

    def initialize_config(self):
        # there may be configs we get from container image
        file_util.rmtree(self.buildroot.make_chroot_path('etc', 'yum.repos.d'))

    def _check_command(self):
        """ Check if main command exists """
        if not os.path.exists(self.command):
            raise Exception("""Command {0} is not available. Either install package containing this command
or run mock with --yum or --dnf to overwrite config value. However this may
lead to different dependency solving!""".format(self.command))


def check_yum_config(config, log):
    if '\nreposdir' not in config:
        log.warning(dedent("""\
                reposdir option is not set in yum config. That means Yum/DNF
                will use system-wide repos. To suppress that behavior, put
                reposdir=/dev/null to your yum.conf in mock config.
                """))


class Yum(_PackageManager):
    name = 'yum'
    support_installroot = True

    def __init__(self, config, buildroot, plugins, bootstrap_buildroot, is_bootstrap_image):
        super(Yum, self).__init__(config, buildroot, plugins, bootstrap_buildroot, is_bootstrap_image)
        self.pm = config['package_manager']
        self.command = config['yum_command']
        self.install_command = config['yum_install_command']
        self.builddep_command = [config['yum_builddep_command']]
        if bootstrap_buildroot is not None:
            # we are in bootstrap so use configured names
            yum_deprecated_path = config['yum_command']
            yum_builddep_deprecated_path = config['yum_builddep_command']
            yum_deprecated_path = bootstrap_buildroot.make_chroot_path(yum_deprecated_path)
            yum_builddep_deprecated_path = bootstrap_buildroot.make_chroot_path(yum_builddep_deprecated_path)
        else:
            # we are building bootstrap or do not use bootstrap at all
            yum_deprecated_path = '/usr/bin/yum-deprecated'
            yum_builddep_deprecated_path = '/usr/bin/yum-builddep-deprecated'
            if os.path.exists(yum_deprecated_path):
                yum_repoquery_command = '/usr/bin/repoquery'
                if os.path.exists(yum_repoquery_command + '-deprecated'):
                    yum_repoquery_command = yum_repoquery_command + '-deprecated'
                self.command = '/usr/bin/yum-deprecated'
                self.resolvedep_command = [
                    yum_repoquery_command, '--resolve', '--requires',
                    '--config', self.buildroot.make_chroot_path('etc', 'yum', 'yum.conf')]
            if os.path.exists(yum_builddep_deprecated_path):
                self.builddep_command = ['/usr/bin/yum-builddep-deprecated']
        # the command in bootstrap may not exists yet
        if bootstrap_buildroot is None:
            self._check_command()

    @traceLog()
    def _write_plugin_conf(self, name):
        """ Write 'name' file into pluginconf.d """
        conf_path = self.buildroot.make_chroot_path('etc', 'yum', 'pluginconf.d', name)
        with open(conf_path, 'w+') as conf_file:
            conf_file.write(self.config[name])

    @traceLog()
    def initialize_config(self):
        super(Yum, self).initialize_config()
        # use yum plugin conf from chroot as needed
        pluginconf_dir = self.buildroot.make_chroot_path('etc', 'yum', 'pluginconf.d')
        file_util.mkdirIfAbsent(pluginconf_dir)
        config_content = self.get_pkg_manager_config().replace(
            "plugins=1", dedent("""\
                           plugins=1
                           pluginconfpath={0}""".format(pluginconf_dir)))

        self.pkg_manager_config = config_content
        check_yum_config(config_content, self.buildroot.root_log)

        # write in yum.conf into chroot
        # always truncate and overwrite (w+)
        self.buildroot.root_log.debug('configure yum')
        yumconf_path = os.path.join('etc', 'yum', 'yum.conf')
        # we need dnf too in case that yum is not installed and /usr/bin/yum points in fact to dnf
        dnfconf_path = os.path.join('etc', 'dnf', 'dnf.conf')
        for conf_path in (yumconf_path, dnfconf_path):
            chroot_conf_path = self.buildroot.make_chroot_path(conf_path)
            with open(chroot_conf_path, 'w+') as conf_file:
                conf_file.write(config_content)
            if os.path.exists(conf_path):
                shutil.copystat(conf_path, chroot_conf_path)

        # write in yum plugins into chroot
        self.buildroot.root_log.debug('configure yum priorities')
        self._write_plugin_conf('priorities.conf')
        self.buildroot.root_log.debug('configure yum rhnplugin')
        self._write_plugin_conf('rhnplugin.conf')
        if self.config['subscription-manager.conf']:
            self.buildroot.root_log.debug('configure RHSM rhnplugin')
            self._write_plugin_conf('subscription-manager.conf')
            pem_dir = self.buildroot.make_chroot_path('etc', 'pki', 'entitlement')
            file_util.mkdirIfAbsent(pem_dir)
            for pem_file in glob.glob("/etc/pki/entitlement/*.pem"):
                shutil.copy(pem_file, pem_dir)
            consumer_dir = self.buildroot.make_chroot_path('etc', 'pki', 'consumer')
            file_util.mkdirIfAbsent(consumer_dir)
            for consumer_file in glob.glob("/etc/pki/consumer/*.pem"):
                shutil.copy(consumer_file, consumer_dir)
            shutil.copy('/etc/rhsm/rhsm.conf',
                        self.buildroot.make_chroot_path('etc', 'rhsm'))
            self.execute('repolist')

    def install(self, *pkgs, **kwargs):
        check = kwargs.pop('check', False)
        if check:
            out = self.execute('resolvedep', *pkgs, returnOutput=True,
                               printOutput=False, pty=False)
            _check_missing(out)
        out = super(Yum, self).install(*pkgs, **kwargs)
        if check:
            _check_missing(out)


def _check_missing(output):
    for i, line in enumerate(output.split('\n')):
        for msg in ('no package found for', 'no packages found for',
                    'missing dependency', 'error:'):
            if msg in line.lower():
                raise BuildError('\n'.join(output.split('\n')[i:]))


class Dnf(_PackageManager):
    name = 'dnf'
    support_installroot = True

    def __init__(self, config, buildroot, plugins, bootstrap_buildroot, is_bootstrap_image):
        super(Dnf, self).__init__(config, buildroot, plugins, bootstrap_buildroot, is_bootstrap_image)
        self.pm = config['package_manager']
        self.command = config['dnf_command']
        self.install_command = config['dnf_install_command']
        self.builddep_command = [self.command, 'builddep']
        # the command in bootstrap may not exists yet
        if bootstrap_buildroot is None:
            self._check_command()
        self.resolvedep_command = [self.command, 'repoquery', '--resolve', '--requires']

    def initialize_vars(self):
        self.buildroot.root_log.debug('configure DNF vars')
        var_path = self.buildroot.make_chroot_path('etc/dnf/vars/')
        for key in self.config['dnf_vars'].keys():
            with open(os.path.join(var_path, key), 'w+') as conf_file:
                conf_file.write(self.config['dnf_vars'][key])

    def _get_disabled_plugins(self):
        if 'dnf_disable_plugins' in self.config:
            disabled_plugins = self.config['dnf_disable_plugins']
        else:
            disabled_plugins = []
        return ["--disableplugin={}".format(x) for x in disabled_plugins]

    @traceLog()
    def build_invocation(self, *args):
        if 'dnf_builddep_opts' not in self.config:
            self.config['dnf_builddep_opts'] = self.config['yum_builddep_opts']
        if 'dnf_common_opts' not in self.config:
            self.config['dnf_common_opts'] = self.config['yum_common_opts'] + \
                                             ['--setopt=deltarpm=False', '--allowerasing']
        self.config['dnf_common_opts'].extend(self._get_disabled_plugins())
        if 'forcearch' in self.config and '--forcearch' not in self.config['dnf_common_opts'] \
           and self.config['forcearch']:
            self.config['dnf_common_opts'].extend(['--forcearch', self.config['forcearch']])
        return super(Dnf, self).build_invocation(*args)

    @traceLog()
    def initialize_config(self):
        super(Dnf, self).initialize_config()
        config_content = self.get_pkg_manager_config()
        self.pkg_manager_config = config_content
        check_yum_config(config_content, self.buildroot.root_log)
        file_util.mkdirIfAbsent(self.buildroot.make_chroot_path('etc', 'dnf'))
        dnfconf_path = self.buildroot.make_chroot_path('etc', 'dnf', 'dnf.conf')
        with open(dnfconf_path, 'w+') as dnfconf_file:
            dnfconf_file.write(config_content)
        self.initialize_vars()

    def builddep(self, *pkgs, **kwargs):
        try:
            super(Dnf, self).builddep(*pkgs, **kwargs)
        except Error as e:
            # pylint: disable=unused-variable
            for i, line in enumerate(e.msg.split('\n')):
                if 'no such command: builddep' in line.lower():
                    raise BuildError("builddep command missing.\nPlease install package dnf-plugins-core.")
            raise


class MicroDnf(Dnf):
    name = 'microdnf'
    support_installroot = False

    def __init__(self, config, buildroot, plugins, bootstrap_buildroot, is_bootstrap_image):
        super(MicroDnf, self).__init__(config, buildroot, plugins, bootstrap_buildroot, is_bootstrap_image)
        self.command = config['microdnf_command']
        self.install_command = config['microdnf_install_command']
        self.builddep_command = [config['microdnf_builddep_command'], 'builddep']
        self.saved_releasever = config['releasever']
        self.config['releasever'] = None

    def _check_command(self):
        """ Check if main command exists """
        super(MicroDnf, self)._check_command()
        if not os.path.exists(self.config['dnf_command']):
            raise Exception("""Command {0} is not available. Either install package containing this command
or run mock with --yum or --dnf to overwrite config value. However this may
lead to different dependency solving!""".format(self.config['dnf_command']))

    @traceLog()
    def execute(self, *args, **kwargs):
        args_copy = list(copy.copy(args))
        cmd = args_copy[0]
        if cmd not in ['update', 'remove', 'install']:
            self.command = self.config['dnf_command']
            self.support_installroot = True
            self.config['releasever'] = self.saved_releasever
        # else it is builddep or resolvedep and we keep command == config['microdnf_command']
        if cmd == "dnf-install":
            cmd = args_copy[0] = "install"
        result = super(MicroDnf, self).execute(*args_copy, **kwargs)
        # restore original value
        self.command = self.config['microdnf_command']
        self.support_installroot = False
        self.config['releasever'] = None
        return result
