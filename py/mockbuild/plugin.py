import imp

from mockbuild.exception import Error
from mockbuild.trace_decorator import traceLog

class Plugins(object):
    @traceLog()
    def __init__(self, config, state):
        self.config = config
        self._hooks = {}
        self.state = state

        self.plugins = config['plugins']
        self.plugin_conf = config['plugin_conf']
        self.plugin_dir = config['plugin_dir']

    @traceLog()
    def init_plugins(self, buildroot):
        for key in list(self.plugin_conf.keys()):
            if key.endswith('_opts'):
                self.plugin_conf[key]['basedir'] = buildroot.basedir
                self.plugin_conf[key]['cache_topdir'] = buildroot.cache_topdir
                self.plugin_conf[key]['cachedir'] = buildroot.cachedir
                self.plugin_conf[key]['root'] = buildroot.shared_root_name

        self.state.start("init plugins")
        # Import plugins  (simplified copy of what yum does). Can add yum
        # features later when we prove we need them.
        for plugin in self.plugins:
            if self.plugin_conf.get("{0}_enable".format(plugin)):
                fp, pathname, description = imp.find_module(plugin, [self.plugin_dir])
                try:
                    module = imp.load_module(plugin, fp, pathname, description)
                finally:
                    fp.close()

                if not hasattr(module, 'requires_api_version'):
                    raise Error('Plugin "%s" doesn\'t specify required API version' % plugin)

                module.init(self, self.plugin_conf["{0}_opts".format(plugin)], buildroot)
        self.state.finish("init plugins")

    @traceLog()
    def call_hooks(self, stage, *args, **kwargs):
        hooks = self._hooks.get(stage, [])
        for hook in hooks:
            hook(*args, **kwargs)

    @traceLog()
    def add_hook(self, stage, function):
        hooks = self._hooks.get(stage, [])
        if function not in hooks:
            hooks.append(function)
            self._hooks[stage] = hooks
