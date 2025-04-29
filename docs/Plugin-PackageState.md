---
layout: default
title: Plugin PackageState
---

This plugin optionally dumps additional metadata files into the result dir:
* A list of all available pkgs + repos + other data. This file is named `available_pkgs.log`. This file is not created if you run mock with `--offline` option.
* A list of all installed pkgs + repos + other data. This file is name `installed_pkgs.log`.

Format of `installed_pkgs.log` file is:

    %{nevra} %{buildtime} %{size} %{pkgid} installed

## Configuration

The Package_state plugin is enabled by default.

    # in version 1.2.18 and older the default was False
    config_opts['plugin_conf']['package_state_enable'] = True

The following sub-options may be turned off/on:
```python
config_opts['plugin_conf']['package_state_opts'] = {}
config_opts['plugin_conf']['package_state_opts']['available_pkgs'] = False
config_opts['plugin_conf']['package_state_opts']['installed_pkgs'] = True
```
