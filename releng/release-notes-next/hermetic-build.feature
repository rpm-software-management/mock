Support for [hermetic builds](feature-hermetic-builds) has been
[implemented][PR#1393].  This update introduces two new command-line options:
`--calculate-build-deps` and `--hermetic-build`, along with the new
`mock-hermetic-repo(1)` utility.

Additionally, this change introduces a new [`buildroot_lock`
plugin](Plugin-BuildrootLock), which generates a new artifact in the buildroot—a
buildroot *lockfile*.  Users can enable this plugin explicitly by setting
`config_opts["plugin_conf"]["buildroot_lock_enable"] = True`.
