---
layout: default
title: Feature modularity support
---
## Modularity support

* There is a support for Fedora Modularity. You can add to config:

```
config_opts['module_enable'] = ['list', 'of', 'modules']
config_opts['module_install'] = ['module1/profile', 'module2/profile']
```

This will call `dnf module enable list of modules` and `dnf module install module1/profile module2/profile` during the init phase. If you want to use this feature you have to have DNF which support modularity (Fedora 28+).

You can find more in this comprehensive blogpost - [Modularity Features in Mock](http://frostyx.cz/posts/modularity-features-in-mock).

This has been added in Mock 1.4.2.
