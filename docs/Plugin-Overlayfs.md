---
layout: default
title: Plugin OverlayFS
---

This plugin implements mock's snapshot functionality using overlayfs. From a user perspective, it works similar to LVM plugin, but unlike LVM plugin, it only needs a directory (not a volume group) for its data (snapshots). Plugin has no additional dependencies, it only requires a kernel with overlayfs support, but this is the case for both current Fedora and RHEL-7.

## Configuration
U can enable overlayfs plugin by adding this line to your configuration:

    config_opts['plugin_conf']['overlayfs_enable'] = True

It is recommended to disable root_cache plugin when overlayfs plugin is enabled. (Plugin does implicit snapshot named "postinit" after init phase similarly to LVM plugin, which makes root cache pointless)

    config_opts['plugin_conf']['root_cache_enable'] = False

Base directory sets directory, where places all its data (snapshots etc.) are placed. Multiple configurations can share base directory (every configuration will have its own directory there).

    config_opts['plugin_conf']['overlayfs_opts']['base_dir'] = "/some/directory"


Enabling touch_rpmd option causes the plugin to implicitly "touch" rpm database files after each mount overcoming issue with rpm/mock, caused by limitations of overlayfs. Option may be useful only when running yum/rpm directly. However, it is not necessary when using package-manager related mock commands (e.g., mock --install). For more details see the section: Limitations of overlayfs (lower).
Default: false

    config_opts['plugin_conf']['overlayfs_opts']['touch_rpmdb'] = True


## Usage
As said earlier, plugins allow you to use mock's snapshot functionality. Snapshots hold the state of (current config's) root fs, which can be recovered later.

To create snapshot run:

    mock --snapshot [name]

You can then return to snapshot created earlier by running (It also makes that snapshot current for clean operation):

    mock --rollback-to [name]

To list snapshots use:

    mock --list-snapshots

Clean operation discards changes done "on top" of current snapshot. ( basically restores current snapshot ). As noted earlier, plugin implicitly creates a snapshot after init phase. So, if no user snapshots are done, plugin behaves more or less as root cache:

    mock --clean # restores current snapshot

To remove all plugin's data associated with configuration (and therefore snapshots), use:

    mock --scrub overlayfs

alternatively, you can remove everything from current configuration:

    mock --scrub all

You can also see more examples of snapshot commands usage in [LVM plugin wiki page](https://rpm-software-management.github.io/mock/Plugin-LvmRoot)
( Difference is, that LVM plugin keeps root mounted, while overlayfs not. )

## Shortly about overlayfs filesystem
Overlayfs is pseudo-filesystem in a kernel, which allows to place multiple directories on each other (as overlays) and combine them to a single filesystem. Upper directory and lower directory(ies) are supplied to mount command as the options. Files from lower files are visible, but all writes happen in a upper layer. Deleted files are represented by special files. For more details see [filesystem's documentation](https://www.kernel.org/doc/Documentation/filesystems/overlayfs.txt) This plugin uses overlayfs to implement snapshots.

## Notes about the implementation of snapshots
To avoid confusion (in some cases), snapshots as displayed by mock (when using this plugin) should be understood more like references/aliases to actual physical snapshots (internally called LAYERS). This means you can have multiple names for a single physical snapshot (LAYER). This also means, you can see multiple snapshots marked as current when listing snapshots (by mock). This can happen because layers are created lazily, so new LAYER is not allocated immediately after creating a snapshot, but prior to mount. So, for example, when 2 snapshots are done, and no mock action, which requires mount, is done in between, they will point to the same LAYER (expected, no changes have been done; same applies for snapshots created after restoring snapshot and after a clean operation). However, a user can still safely delete just one of these. This is possible because LAYERS are reference counted. So you just remove reference (alias), but LAYER (holding actual snapshot's data) is only deleted when no longer referenced. Apart from user-visible references, it may be referenced by other LAYERS (by ones based on it) and by "current state" (special references)). So, it is safe to remove any "snapshot" (as seen by mock), even current one, without having to worry about "breaking" the mock. If you are interested in even more implementation details, see detailed documentation in plugin's [source file](https://github.com/rpm-software-management/mock/blob/devel/mock/py/mockbuild/plugins/overlayfs.py) or maybe even [test file](https://github.com/rpm-software-management/mock/blob/devel/mock/tests/overlayfs_layers_test.py) (where LAYERS are tested).

## Limitations of overlayfs
Overlayfs has known limitations when it comes to POSIX compatibility. This may cause problems with some programs. The problem happens, when a file from the lower layer (directory) is open for writing (forcing overlayfs copy it to upper layer), while the same file is opened read-only. Open file descriptors then point to different files. Rpm/yum are known to be affected by this issue. See:

[yum/rpm bug on RH bugzilla](https://bugzilla.redhat.com/show_bug.cgi?id=1213602)

[docker overlayfs-driver page](https://docs.docker.com/storage/storagedriver/overlayfs-driver/#limitations-on-overlayfs-compatibility)

So, this is not a bug in the plugin. It is caused by nature/design decisions made in overlafs filesystem (and documented). Problem is work-arounded automatically for package manager related operations done using mock (e.g. mock --install). When running yum/rpm manually, an option can be used to overcome the issue automatically (see higher). If you find another program(s) affected by this issue, you should be able to work-around this simply by "touching" problematic files(s) prior to running that program.

    touch /some/file   # using mock --shell or mock --chroot

## Using inside docker
Not tested, but you may need to add additional mount where to place this plugin's base_dir. This is because docker may itself use overlayfs. ( Overlayfs cannot use directories which are part of another overlayfs mount. )
