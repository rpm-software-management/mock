---
layout: default
title: Plugin ProcEnv
---

This plugin allows prints your build time environment, which may help identify problems or reproduced the build.

It prints information about the entire software build environment, any capabilities, and much more.
The information is stored in file procenv.log in the results directory.
It calls `procenv` command and stores its output.

## Configuration

You can enable the plugin using this settings:

    config_opts['plugin_conf']['procenv_enable'] = True
    config_opts['plugin_conf']['procenv_opts'] = {}

Available since version 1.4.18.

This plugin is DISABLED by default.
