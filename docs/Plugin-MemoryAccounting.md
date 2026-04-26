---
layout: default
title: Plugin MemoryAccounting
---

This plugin activates memory usage accounting during the build phase and
dumps a json file 'memory_accounting.json' with the collected statitics in the
result dir

Currently dumped statistics include total maximum memory usage for the build
and the process with maximum memory RSS

The plugin requires the use for systemd-nspawn as build container runner

## Configuration

The module is disabled by default and needs to be activated by:

    config_opts['plugin_conf']['memory_accounting_enable'] = True

The following sub-options may be specified:

    # the interval between statistics collection runs , default 2
    config_opts['plugin_conf']['memory_accounting_opts']['interval'] = 10
