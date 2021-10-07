---
layout: default
title: Plugin Hooks
---

When you develop a new plugin, you can register your hook with:

    plugins.add_hook("HOOK_NAME", self.your_method)

Where `HOOK_NAME` is one of:

* clean
* earlyprebuild - This is called during the very early stage of building RPM or SRPM. It is called even before SRPM is rebuilt or build dependencies have been installed.
* initfailed
* list_snapshots
* make_snapshot
* mount_root - This hook is intended for plugins which mount the chroot directory. This is called just before 'preinit' when only chroot directory exists. Result directory does not exist yet.
* postbuild - This hook is called just after RPM or SRPM have been build (with or without success).
* postchroot - This hook is called just after exiting from command in `mock chroot` command. This action is currently being used by `root_cache` plugin.
* postclean - This hook is called when the content of the chroot has been deleted. It is called after `umount_root`.  E.g., `lvm_root` use this to delete the LVM volume.
* postinit - Chroot have been initialized and it is ready for installing SRPM dependencies. E.g., root_cache plugin now packs the chroot and put it in a cache. This action is currently being used by `bind_mount`, `lvm_root`, `mount`, `root_cache` plugins.
* postshell - This hook is called just after exiting from the shell in `mock shell` command. This action is currently being used by `root_cache` plugin.
* postupdate - Mock attempts to cache buildroot contents, but tries to automatically update the packages inside the buildroot in subsequent executions (so up2date packages are used during build). This hook is called anytime such udpdate is successul and any package is updated inside the buildroot.  Any plugin taking care of the buildroot caches can then react and update the cache to avoid re-updating in the subsequent mock runs.
* postumount - This hook is called when everything in chroot finished or has been killed. All inner mounts have been umounted. E.g., tmpfs plugin uses this to umount tmpfs chroot. This action is currently being used by `lvm_root`, `tmpfs` plugins.
* postyum - This hook is called after any packager manager action is executed. This is e.g., used by the `package_state` plugin to list all available packages. This action is currently being used by `package_state`, `root_cache`, `selinux`, `yum_cache` plugins.
* prebuild - This hook is called after BuildRequires have been installed, but before RPM builds. This is not called for SRPM rebuilds.
* prechroot - This hook is called just before executing a command when `mock chroot` command has been used. This action is currently being used by `root_cache` plugin.
* preinit - Only chroot and result_dir directories exist. There may be no other content. No binary. Not even base directories. Root_cache plugin uses this hook to populate the content of chroot_from cache. HW_info gather information about hardware and store it in result_dir. This action is currently being used by `ccache`, `hw_info`, `root_cache`, `yum_cache` plugins.
* preshell - This hook is called just before giving a prompt to a user when `mock shell` command has been used. This action is currently being used by `pm_request`, `root_cache` plugins.
* preyum - This hook is called before any packager manager action is executed. This is, e.g., used by `root_cache` plugin when `--cache-alterations` option is used. This action is currently being used by `root_cache`, `selinux`, `yum_cache`.
* process_logs - Called once the build log files (root.log, build.log, ...) are completed so they can be processed (e.g. compressed by the `compress_logs` plugin).
* remove_snapshot
* rollback_to
* scrub

You can get inspired by existing [plugins](https://github.com/rpm-software-management/mock/tree/master/mock/py/mockbuild/plugins).
