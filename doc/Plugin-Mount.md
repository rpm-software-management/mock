---
layout: default
title: Plugin Mount
---

This plugin allows you to mount directories into chroot. The mount plugin is enabled by default, but has no configured directories to mount.

## Configuration

You can disable this plugin by:

    config_opts['plugin_conf']['mount_enable'] = False

you can configure this plugin by:

    config_opts['plugin_conf']['mount_enable'] = True
    config_opts['plugin_conf']['mount_opts']['dirs'].append(("/dev/device", "/mount/path/in/chroot/", "vfstype", "mount_options"))

A real life example:

    config_opts['plugin_conf']['mount_opts']['dirs'].append(("server.example.com:/exports/data", "/mnt/data", "nfs", "rw,hard,intr,nosuid,nodev,noatime,tcp"))

### `/builddir/` cleanup

**WARNING!** The build user's homedir (`/builddir`)  is partially cleaned up even when `--no-clean` is
specified in order to prevent garbage from previous builds from altering
successive builds. Mock can be configured to exclude certain files/directories
from this. Default is `SOURCES` directory to support nosrc rpms:

    config_opts['exclude_from_homedir_cleanup'] = ['build/SOURCES']

Paths are relative to build user's homedir.

So if you do something like this:

	config_opts['plugin_conf']['bind_mount_opts']['dirs'].append((os.path.expanduser('~/MyProject'), '/builddir/MyProject' ))

Then you SHOULD do:

    config_opts['exclude_from_homedir_cleanup'] = ['build/SOURCES', 'MyProject']

otherwise your `~/MyProject` will be wiped out!
Other option is to not mount it under `/builddir`, but somewhere else (`/opt`, `/mnt`...).



