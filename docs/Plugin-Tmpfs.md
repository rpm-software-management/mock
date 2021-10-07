---
layout: default
title: Plugin TmpFS
---

The tmpfs plugin allows you to mount a tmpfs on the chroot dir. This plugin is disabled by default.

## Configuration

You can enable the plugin using this settings:

    config_opts['plugin_conf']['tmpfs_enable'] = True
    config_opts['plugin_conf']['tmpfs_opts'] = {}
    config_opts['plugin_conf']['tmpfs_opts']['required_ram_mb'] = 1024
    config_opts['plugin_conf']['tmpfs_opts']['max_fs_size'] = '768m'
    config_opts['plugin_conf']['tmpfs_opts']['mode'] = '0755'
    config_opts['plugin_conf']['tmpfs_opts']['keep_mounted'] = False

* `required_ram_mb` - If system has less memory than this value, the Tmpfs plugin is disabled and a warning is omitted, but `mock` will continue.
* `max_fs_size` - this is passed to `mount.tmpfs` as `-o size=X`
* `mode` - this is passed to to `mount.tmpfs` as `-o mode=X`
* `keep_mounted` - when set to `True`, the `buildroot` is not unmounted when mock exits (which will destroy it's content). Additionally when mock is starting and it detects the tmpfs from a previous run, it will reuse it.

:warning: You can not combine **Tmpfs plugin** and **Lvm_root plugin**, because it is not possible to mount Logical Volume as tmpfs.
