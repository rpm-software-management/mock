Hermetic build [now|PR#1712] provides access to buildroot repo in
`/hermetic_repo` directory. Normal behaviour for package maintainers is to
expect that `/var/cache/{dnf|yum}` is populated by these packages. Anyway, in
case of "offline" repo which is used by hermetic builds, `dnf4` doesn't
populate that directory, while `dnf5` yes (with `keepcache=1`). Providing also
`/hermetic_repo` in every case would make looking for buildroot packages a bit
easier.
