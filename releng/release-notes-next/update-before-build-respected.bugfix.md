The `config_opts['update_before_build'] = False` option is now respected
during build dependency installation with dnf5. Previously, `dnf5 builddep`
would upgrade already-installed packages even when this option was disabled,
as reported in [issue#1420][]. When dnf5 is the package manager, Mock now
excludes installed packages during `builddep`/`install`, preventing unwanted
upgrades.
