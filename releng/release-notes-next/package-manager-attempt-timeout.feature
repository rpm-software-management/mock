A new `package_manager_attempt_timeout` config option limits how long a
single package manager command (e.g. a DNF transaction) may take.  When the
limit is exceeded, the command is killed and the action is retried up to
`package_manager_max_attempts` times, ideally against a different mirror.
This helps when the package manager gets stuck, e.g. on a very slow or dead
mirror ([issue#1278][]).  The option is disabled (`0`) by default.
