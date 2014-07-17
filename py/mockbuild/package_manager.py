from mockbuild import util

def PackageManager(config_opts, chroot):
    pm = config_opts.get('package_manager', 'yum')
    if pm == 'yum':
        return Yum(config_opts, chroot)
    elif pm == 'dnf':
        return Dnf(config_opts, chroot)
    else:
        #TODO specific exception type
        raise Exception('Unrecognized package manager')


class _PackageManager(object):
    command = None

    def __init__(self, config, buildroot):
        self.config = config
        self.buildroot = buildroot

    def build_invocation(self, *args):
        if args[0] == 'builddep':
            args = args[1:]
            invocation = [self.command + '-builddep']
            common_opts = self.config[self.command + '_builddep_opts']
        else:
            invocation = [self.command]
            common_opts = self.config[self.command + '_common_opts']
        invocation += ['--installroot', self.buildroot.makeChrootPath()]
        releasever = self.config['releasever']
        if releasever:
            invocation += ['--releasever', releasever]
        if not self.config['online']:
            invocation.append('-C')
        invocation += common_opts
        invocation += args
        return invocation

    def execute(self, *args, **kwargs):
        self.buildroot._callHooks("preyum")
        env = self.config['environment'].copy()
        env.update(util.get_proxy_environment(self.config))
        env['LC_MESSAGES'] = 'C'
        invocation = self.build_invocation(*args)
        self.buildroot.root_log.debug(invocation)
        # log?
        self.buildroot._nuke_rpm_db()
        out = util.do(invocation, env=env, **kwargs)
        self.buildroot._callHooks("postyum")
        return out

    def install(self, *args):
        return self.execute('install', *args)

    def remove(self, *args):
        return self.execute('remove', *args)

    def update(self, *args):
        return self.execute('update', *args)

class Yum(_PackageManager):
    command = 'yum'

class Dnf(_PackageManager):
    command = 'dnf'
