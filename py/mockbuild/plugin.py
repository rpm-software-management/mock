# -*- coding: utf-8 -*-
# vim: noai:ts=4:sw=4:expandtab

import imp

from .exception import Error
from .trace_decorator import traceLog

current_api_version = '1.1'


class Plugins(object):
    @traceLog()
    def __init__(self, config, state):
        self.config = config
        self._hooks = {}
        self.state = state

        self.already_initialized = False

        self.plugins = config['plugins']
        self.plugin_conf = config['plugin_conf']
        self.plugin_dir = config['plugin_dir']

    def __repr__(self):
        return "<mockbuild.plugin.Plugins: state={0}, _hooks={1}, already_initialized={2}".format(
            self.state, self._hooks, self.already_initialized)

    @traceLog()
    def init_plugins(self, buildroot):
        if self.already_initialized:
            return
        self.already_initialized = True
        for key in list(self.plugin_conf.keys()):
            if key.endswith('_opts'):
                self.plugin_conf[key]['basedir'] = buildroot.basedir
                self.plugin_conf[key]['cache_topdir'] = buildroot.cache_topdir
                self.plugin_conf[key]['cachedir'] = buildroot.cachedir
                self.plugin_conf[key]['root'] = buildroot.shared_root_name
                self.plugin_conf[key]['resultdir'] = buildroot.resultdir

        self.state.start("init plugins")
        # Import plugins  (simplified copy of what yum does). Can add yum
        # features later when we prove we need them.
        for plugin in self.plugins:
            if self.plugin_conf.get("{0}_enable".format(plugin)):
                try:
                    fp, pathname, description = imp.find_module(plugin, [self.plugin_dir])
                except ImportError:
                    buildroot.root_log.warning(
                        "{0} plugin is enabled in configuration but is not installed".format(plugin))
                    continue
                try:
                    module = imp.load_module(plugin, fp, pathname, description)
                finally:
                    fp.close()

                if not hasattr(module, 'requires_api_version'):
                    raise Error('Plugin "%s" doesn\'t specify required API version' % plugin)
                requested_api_version = module.requires_api_version
                if requested_api_version != current_api_version:
                    raise Error('Plugin version mismatch - requested = %s, current = %s'
                                % (requested_api_version, current_api_version))

                module.init(self, self.plugin_conf["{0}_opts".format(plugin)], buildroot)
        self.state.finish("init plugins")

    @traceLog()
    def call_hooks(self, stage, *args, **kwargs):
        required = kwargs.get('required', False)
        if 'required' in kwargs:
            del kwargs['required']
        hooks = self._hooks.get(stage, [])
        if required and not hooks:
            raise Error(
                "Feature {0} is not provided by any of enabled plugins".format(stage))
        for hook in hooks:
            hook(*args, **kwargs)

    @traceLog()
    def add_hook(self, stage, function):
        hooks = self._hooks.get(stage, [])
        if function not in hooks:
            hooks.append(function)
            self._hooks[stage] = hooks
