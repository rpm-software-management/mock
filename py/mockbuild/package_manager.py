import glob
import os.path
import shutil
import platform

from six.moves import input
from textwrap import dedent

from . import util
from .exception import BuildError, Error, YumError
from .trace_decorator import traceLog

def PackageManager(config_opts, chroot, plugins):
    pm = config_opts.get('package_manager', 'yum')
    if pm == 'yum':
        return Yum(config_opts, chroot, plugins)
    elif pm == 'dnf':
        (distribution, version) = platform.dist()[0:2]
        if distribution in ['redhat', 'centos']:
            version = int(version.split('.')[0])
            if version < 8:
                if  'dnf_warning' in config_opts and config_opts['dnf_warning']:
                    print("""WARNING! WARNING! WARNING!
You are building package for distribution which use DNF. However your system
does not support DNF. You can continue with YUM, which will likely succeed,
but the result may be little different.
You can suppress this warning when you put
  config_opts['dnf_warning'] = False
in Mock config.""")
                    input("Press Enter to continue.")
                return Yum(config_opts, chroot, plugins)
        return Dnf(config_opts, chroot, plugins)
    else:
        #TODO specific exception type
        raise Exception('Unrecognized package manager')


class _PackageManager(object):
    name = None
    command = None
    builddep_command = None
    resolvedep_command = None

    @traceLog()
    def __init__(self, config, buildroot, plugins):
        self.config = config
        self.plugins = plugins
        self.buildroot = buildroot

    @traceLog()
    def build_invocation(self, *args):
        invocation = []
        common_opts = []
        cmd = args[0]
        if cmd == 'builddep':
            args = args[1:]
            invocation += self.builddep_command
            common_opts = self.config[self.name + '_builddep_opts']
        elif cmd == 'resolvedep':
            if self.resolvedep_command:
                args = args[1:]
                invocation = self.resolvedep_command
            else:
                invocation = [self.command]
                common_opts = self.config[self.name + '_common_opts']
        else:
            invocation = [self.command]
            common_opts = self.config[self.name + '_common_opts']
        invocation += ['--installroot', self.buildroot.make_chroot_path('')]
        if cmd == 'upgrade' or cmd == 'update':
            invocation += ['-y']
        releasever = self.config['releasever']
        if releasever:
            invocation += ['--releasever', releasever]
        if not self.config['online']:
            invocation.append('-C')
        if self.config['enable_disable_repos']:
            invocation += self.config['enable_disable_repos']
        invocation += common_opts
        invocation += args
        return invocation

    @traceLog()
    def execute(self, *args, **kwargs):
        self.plugins.call_hooks("preyum")
        env = self.config['environment'].copy()
        env.update(util.get_proxy_environment(self.config))
        env['LC_MESSAGES'] = 'C'
        if self.buildroot.nosync_path:
            env['LD_PRELOAD'] = self.buildroot.nosync_path
        invocation = self.build_invocation(*args)
        self.buildroot.root_log.debug(invocation)
        kwargs['printOutput'] = kwargs.get('printOutput', True)
        if not self.config['print_main_output']:
            kwargs.pop('printOutput', None)
        else:
            kwargs['pty'] = kwargs.get('pty', True)
        self.buildroot._nuke_rpm_db()
        try:
            out = util.do(invocation, env=env, **kwargs)
        except Error as e:
            raise YumError(str(e))
        self.plugins.call_hooks("postyum")
        return out

    @traceLog()
    def install(self, *args, **kwargs):
        return self.execute('install', *args)

    @traceLog()
    def remove(self, *args, **kwargs):
        return self.execute('remove', *args)

    @traceLog()
    def update(self, *args, **kwargs):
        return self.execute('update', *args)

    @traceLog()
    def builddep(self, *args, **kwargs):
        return self.execute('builddep', returnOutput=1, *args)

    @traceLog()
    def copy_gpg_keys(self):
        pki_dir = self.buildroot.make_chroot_path('etc', 'pki', 'mock')
        util.mkdirIfAbsent(pki_dir)
        for pki_file in glob.glob("/etc/pki/mock/RPM-GPG-KEY-*"):
            shutil.copy(pki_file, pki_dir)

    def initialize(self):
        self.copy_gpg_keys()
        self.initialize_config()

    def initialize_config(self):
        raise NotImplementedError()

    def replace_in_config(self, config_content):
        """ expand resultdir in the yum.conf segment of the mock
        configuration file.
        """
        return config_content.replace("%(resultdir)s",\
                self.config['resultdir'] % self.config)

    def _check_command(self):
        """ Check if main command exists """
        if not os.path.exists(self.command):
            raise Exception("""Command {0} is not available. Either install package containing this command
or run mock with --yum or --dnf to overwrite config value. However this may
lead to different dependency solving!""".format(self.command))


def check_yum_config(config, log):
    if '\nreposdir' not in config:
        log.warn(dedent("""\
                reposdir option is not set in yum config. That means Yum/DNF
                will use system-wide repos. To suppress that behavior, put
                reposdir=/dev/null to your yum.conf in mock config.
                """))

class Yum(_PackageManager):
    name = 'yum'

    def __init__(self, config, buildroot, plugins):
        super(Yum, self).__init__(config, buildroot, plugins)
        self.command = config['yum_command']
        self.builddep_command = [config['yum_builddep_command']]
        self._check_command()
        if os.path.exists('/usr/bin/yum-deprecated'):
            self.resolvedep_command = ['repoquery', '--resolve', '--requires',
                '--config', self.buildroot.make_chroot_path('etc', 'yum', 'yum.conf')]

    @traceLog()
    def _write_plugin_conf(self, name):
        """ Write 'name' file into pluginconf.d """
        conf_path = self.buildroot.make_chroot_path('etc', 'yum', 'pluginconf.d', name)
        with open(conf_path, 'w+') as conf_file:
            conf_file.write(self.config[name])

    @traceLog()
    def initialize_config(self):
        # use yum plugin conf from chroot as needed
        pluginconf_dir = self.buildroot.make_chroot_path('etc', 'yum', 'pluginconf.d')
        util.mkdirIfAbsent(pluginconf_dir)
        config_content = self.config['yum.conf']\
                          .replace("plugins=1",
                           dedent("""\
                           plugins=1
                           pluginconfpath={0}""".format(pluginconf_dir)))
        config_content = self.replace_in_config(config_content)

        check_yum_config(config_content, self.buildroot.root_log)

        # write in yum.conf into chroot
        # always truncate and overwrite (w+)
        self.buildroot.root_log.debug('configure yum')
        yumconf_path = self.buildroot.make_chroot_path('etc', 'yum', 'yum.conf')
        with open(yumconf_path, 'w+') as yumconf_file:
            yumconf_file.write(config_content)

        # write in yum plugins into chroot
        self.buildroot.root_log.debug('configure yum priorities')
        self._write_plugin_conf('priorities.conf')
        self.buildroot.root_log.debug('configure yum rhnplugin')
        self._write_plugin_conf('rhnplugin.conf')
        if self.config['subscription-manager.conf']:
            self.buildroot.root_log.debug('configure RHSM rhnplugin')
            self._write_plugin_conf('subscription-manager.conf')
            pem_dir = self.buildroot.make_chroot_path('etc', 'pki', 'entitlement')
            util.mkdirIfAbsent(pem_dir)
            for pem_file in glob.glob("/etc/pki/entitlement/*.pem"):
                shutil.copy(pem_file, pem_dir)
            consumer_dir = self.buildroot.make_chroot_path('etc', 'pki', 'consumer')
            util.mkdirIfAbsent(consumer_dir)
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

    def __init__(self, config, buildroot, plugins):
        super(Dnf, self).__init__(config, buildroot, plugins)
        self.command = config['dnf_command']
        self.builddep_command = [self.command, 'builddep']
        self._check_command()
        self.resolvedep_command = ['repoquery', '--resolve', '--requires']

    @traceLog()
    def build_invocation(self, *args):
        if not 'dnf_builddep_opts' in self.config:
            self.config['dnf_builddep_opts'] = self.config['yum_builddep_opts']
        if not 'dnf_common_opts' in self.config:
            self.config['dnf_common_opts'] = self.config['yum_common_opts'] + ['--setopt=deltarpm=false']
        return super(Dnf, self).build_invocation(*args)

    @traceLog()
    def initialize_config(self):
        if 'dnf.conf' in self.config:
            config_content = self.config['dnf.conf']
        else:
            config_content = self.config['yum.conf']
        config_content = self.replace_in_config(config_content)

        check_yum_config(config_content, self.buildroot.root_log)
        util.mkdirIfAbsent(self.buildroot.make_chroot_path('etc', 'dnf'))
        dnfconf_path = self.buildroot.make_chroot_path('etc', 'dnf', 'dnf.conf')
        with open(dnfconf_path, 'w+') as dnfconf_file:
            dnfconf_file.write(config_content)

    def builddep(self, *pkgs, **kwargs):
        try:
            out = super(Dnf, self).builddep(*pkgs, **kwargs)
        except Error as e:
            for i, line in enumerate(e.msg.split('\n')):
                if 'no such command: builddep' in line.lower():
                    raise BuildError("builddep command missing.\nPlease install package dnf-plugins-core.")
            raise
