---
layout: default
title: Plugin LVM Root
---

Mock can use LVM as a backend for caching buildroots which is a bit faster than using root_cache and enables efficient snapshotting (copy-on-write). This feature is intended to be used by people who maintain a lot packages and find themselves waiting for mock to install the same set of BuildRequires over and over again.
Mock uses LVM thin provisioning which means that one logical volume (called
thinpool) can hold all thin logical volumes and snapshots used by all
buildroots (you have to set it like that in the config) without each of them
having fixed size. Thinpool is created by mock when it's starts initializing
and after the buildroot is initialized, it creates a postinit snapshot which
will be used as default. Default snapshot means that when you execute clean or
start a new build without `--no-clean` option, mock will rollback to the state in default snapshot. As you install more packages you can create your own snapshots (usually for dependency chains that are common to many of your packages).

## Expected workflow

You have multiple packages that all depend on something with big dependency chain, for example Java packages depend on maven-local, therefore it may be useful to create snapshot that would contain maven-local. With the next steps, you install the package and create the snapshot

    mock --install maven-local
    mock --snapshot mvn

Now there should be two snapshots - the initial one and the one you just created. You can verify it with the list-snapshots command (Note it also has short option `-l`)

    mock --list-snapshots

  Snapshots for fedora-20-x86_64:

      postinit
    * mvn

The new one is marked with an asterisk, which means it will be used as the default snapshot to which `--clean` will rollback whenever you build another package. When you want to rebuild a package that doesn't use maven-local, you can use

    mock --rollback-to postinit

and the initial snapshot will be used for following builds. The mvn snapshot will still exist, so you can get back to it later using

    mock --rollback-to mvn

To get delete a snapshot completely, use

    mock --remove-snapshot mvn

Mock will leave the buildroot volume mounted by default (you can override it in the config), so you can easily access the build directory. When you need to umount it, use

    mock --umount

To getting rid of LVM volumes completely, use

    mock --scrub lvm

This will delete all volumes belonging to the current config and also the thinpool if and only if there are no other volumes left by other configurations.

## Setup

The plugin is distributed as separate subpackage `mock-lvm` because it pulls in additional dependencies which are not available on RHEL6.

You need to specify a volume group which mock will use to create it's thinpool. Therefore you need to have some unoccupied space in your volume group, so you'll probably need to shrink some partition a bit. Mock won't touch anything else in the VG, so don't be afraid to use the VG you have for your system. It won't touch any other logical volumes in the VG that don't belong to it.

## Configuration

    config_opts['plugin_conf']['root_cache_enable'] = False
    config_opts['plugin_conf']['lvm_root_enable'] = True
    config_opts['plugin_conf']['lvm_root_opts'] = {
        'volume_group': 'my-volume-group',
        'size': '8G',
        'pool_name': 'mock',
        'check_size': True,
    }

Explanation: You need to disable root_cache - having two caches with the same contents would just slow you down. You need to specify a size for the thinpool. It can be shared across all mock buildroots so make sure it's big enough. Ideally there will be just one thinpool. Then specify name for the thinpool - all configs which have the same pool_name will share the thinpool, thus being more space-efficient. Make sure the name doesn't clash with existing volumes in your system (you can list existing volumes with lvs command).

Every run, the plugin write usage of data pool and metadata pool.
When utilization is over 75 % then plugin emit warning.
Usage over 90 % is fatal and mock stop with error, but it can be override by

    config_opts['plugin_conf']['lvm_root_opts']['check_size'] = False

However this override is strongly discouraged as LVM2 have known error when thinpool is full.

### Other configuration options

`config_opts['plugin_conf']['lvm_root_opts']['poolmetadatasize']` - specifies separate size of the thinpool metadata. It needs to be big enough, thinpool with overflown metadata will become corrupted. When unspecified, the default value is determined by LVM

`config_opts['plugin_conf']['lvm_root_opts']['umount_root']` -
boolean option specifying whether the buildroot volume should stay mounted after mock exits. Default is `True`

`config_opts['plugin_conf']['lvm_root_opts']['filesystem']` -
filesystem name that will be used for the volume. It will use
`mkfs.$filesystem` binary to create it. Default is `ext4`

`config_opts['plugin_conf']['lvm_root_opts']['mkfs_command']` - the whole command for creating the filesystem that will get the volume path as an argument. When set, overrides above option.

`config_opts['plugin_conf']['lvm_root_opts']['mkfs_args']` - additional arguments passed to mkfs command. Default is empty.

`config_opts['plugin_conf']['lvm_root_opts']['mount_opts']` - will
be passed to `-o` option of mount when mounting the volume. Default is empty.

`config_opts['plugin_conf']['lvm_root_opts']['mount_opts']` - Let user configure mock to wait more patiently for LVM initialization. `lvs' call can be quite expensive, especially when there are hundreds of volumes and multiple parallel mocks waiting for common LVM initialization to complete. (Added in version 1.4.3)

Note: You can not combine Tmpfs plugin and Lvm_root plugin, because it is not possible to mount Logical Volume as tmpfs.
