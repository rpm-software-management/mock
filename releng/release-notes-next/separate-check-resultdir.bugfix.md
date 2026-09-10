Fix `separate_check` builds with a separate `--resultdir`.  A resultdir
outside of the chroot directory enables `cleanup_on_success`, and that in turn
made Mock run `rpmbuild` without `--noclean`.  The `%clean` stage then removed
the build directory before the separate `%check` phase could run, so
`rpmbuild -bk --short-circuit` failed with `rpmbuild.env: No such file or
directory` ([issue#1808][]).  Mock now always runs `rpmbuild` with `--noclean`
and does its own cleanup, so the build directory survives for the separate
`%check` phase.
