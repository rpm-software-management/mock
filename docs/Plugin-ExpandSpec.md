---
layout: default
title: Plugin ExpandSpec
---

This plugin expands specfile and save the output to `expanded-spec.txt` in result directory in `postdeps` hook.

It uses to expand the specfile
```bash
/usr/bin/rpmspec --parse <spec>
```

## Configuration

You can enable the plugin using this settings:
```python
config_opts['plugin_conf']['expand_spec_enable'] = True
```

To add extra options in `rpmspec` command, use:
```python
config_opts['plugin_conf']['expand_spec_opts']['rpmspec_opts'] = ['--verbose', '-d', 'foo bar']
```

Available since version 6.7.

This plugin is DISABLED by default.
