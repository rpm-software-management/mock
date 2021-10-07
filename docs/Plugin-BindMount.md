---
layout: default
title: Plugin BindMount
---

This plugin enables setting up bind mountpoints inside the chroot. It is enabled by default but has no paths setup for bind mounts.


## Configuration

In your config file insert the following lines:

    config_opts['plugin_conf']['bind_mount_enable'] = True
    config_opts['plugin_conf']['bind_mount_opts']['dirs'].append(('/host/path', '/bind/mount/path/in/chroot/' ))

The `/host/path` is the path to a directory on the host that will be the source of a bind-mount, while the `/bind/mount/path/in/chroot` is the path where it will be mounted inside the chroot.

If you want the bind mounts to be available to all configurations, edit [the configuration file](Home#generate-custom-config-file).

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

***

Set options from command line
```
mock '--plugin-option=bind_mount:dirs=[("/host/dir", "/mount/path/in/chroot/")]' --init
```

:warning: Note that command line arguments override configs (not append them).

:notebook: Since version  mock-1.4.10 and newer you can bind mount even single files.
