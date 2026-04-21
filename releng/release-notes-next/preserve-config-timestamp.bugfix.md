Mock now preserves the timestamp of `dnf.conf` and `yum.conf` inside the
chroot when their content has not changed.  Previously, every mock invocation
rewrote these files unconditionally, which — combined with DNF's default
`check_config_file_age=True` — caused repository metadata to be re-downloaded
even when it was still valid ([issue#216][]).

[issue#216]: https://github.com/rpm-software-management/mock/issues/216
