---
layout: default
title: Plugin Showrc
---

This plugin dumps all the build time RPM macros (via `rpm --showrc`) into result directory as `showrc.log` file, which may help identify problems of (or reproduce) the build.

It prints information about all defined RPM macros.

## Configuration

You can enable the plugin using this settings:

    config_opts['plugin_conf']['showrc_enable'] = True

Available since version 2.5.

This plugin is DISABLED by default.
