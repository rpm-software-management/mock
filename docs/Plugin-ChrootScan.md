---
layout: default
title: Plugin Chroot Scan
---

The chroot_scan plugin is used to grab files of interest after a build attempt and copy them to the 'result directory' before the chroot is cleaned and data lost.

## Configuration

The chroot_scan plugin is disabled by default. To enable it and to add files to the detection logic, add this code to configure file:

    config_opts['plugin_conf']['chroot_scan_enable'] = True
    config_opts['plugin_conf']['chroot_scan_opts'] = {
        'regexes': [ "core(\.\d+)?", "\.log$",],
        'only_failed': True,
    }

The above logic turns on the chroot_scan plugin and adds corefiles and log files to the scan plugin. When the 'postbuild' hook is run by mock, the chroot_scan will look through the chroot for files that match the regular expressions in it's list and any matching file will be copied to the mock result directory for the config file. Again if you want this to be enabled across all configs, edit the `/etc/mock/site-defaults.cfg` file.

When `only_failed` is set to False, then those files are always copied. When it is set to True (default when plugin enabled), then those files are only copied when build failed.

`only_failed` option is available since mock-1.2.8
