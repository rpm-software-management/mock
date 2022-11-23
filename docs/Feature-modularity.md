---
layout: default
title: Feature modularity support
---
## Modularity support

There is support for Fedora and RHEL Modularity. This requires `dnf`, not merely
`yum`. It is available for RHEL >= 8 and its clones, and built into
all supported releases of Fedora. 

The new modularity format was added with release 2.4 and uses
`module_setup_commands`. Each command can be specified multiple times,
and mock respects the order of the commands when executing them.

* Artificial example:
   * Disable any potentially enabled postgresql module stream.
   * Enable _specific_ postgresql and ruby module streams.
   * Install the development nodejs profile and (4) disable it immediately.

```
config_opts['module_setup_commands'] = [
    ('disable', 'postgresql'),
    ('enable',  'postgresql:12, ruby:2.6'),
    ('install', 'nodejs:13/development'),
    ('disable', 'nodejs'),
    ]
```

Modules can also be specified on the command line using:
```
--config-opts=module_setup_commands.module_install=postgresql:13
```

The obsolete, less flexible, but still available  modularity syntax was added in Mock 1.4.2.

```
config_opts['module_enable'] = ['list', 'of', 'modules']
config_opts['module_install'] = ['module1/profile', 'module2/profile']
```

This would call these steps during the init phase.
* `dnf module enable list of modules`
* `dnf module install module1/profile module2/profile`

You can find more about this obsolete format in this comprehensive blogpost.
* [Modularity Features in Mock](http://frostyx.cz/posts/modularity-features-in-mock).
