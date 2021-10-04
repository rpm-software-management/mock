---
layout: default
title: Plugin HwInfo
---

This plugin allows prints your basic hardware information, which may help identify problems or reproduced the build.

It print information about CPU, memory (including swap) and storage (only of volume where chroot will be stored).
The information is stored in file hw_info.log in results directory.

## Configuration

You can enable the plugin using this settings:

    config_opts['plugin_conf']['hw_info_enable'] = True
    config_opts['plugin_conf']['hw_info_opts'] = {}

Available since version 1.3.4.

This plugin is enabled by default.
