---
layout: default
title: Plugin SystemMonitor
---

This plugin activates per-interval collection of various statistics
based on the kernels cgroupv2 controllers during the build phase and
dumps a json file 'systemd-monitor.json' with the collected statitics
in the result dir

Currently dumped statistics include total maximum memory usage for the build
and the process with maximum memory RSS

The plugin requires the use for systemd-nspawn as build container runner

## Configuration

The module is disabled by default and needs to be activated by:

    config_opts['plugin_conf']['system_monitor_enable'] = True

The following sub-options may be specified:

    # the interval between statistics collection runs , default 2
    config_opts['plugin_conf']['system_monitor_opts']['interval'] = 10
