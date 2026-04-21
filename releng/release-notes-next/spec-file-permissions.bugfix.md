The `--spec` option now works with spec files that have restrictive
permissions (e.g. `0600`).  Previously, `shutil.copy2()` preserved the
source permissions inside the chroot, making the file unreadable by the
`mockbuild` user ([#1300][]).
