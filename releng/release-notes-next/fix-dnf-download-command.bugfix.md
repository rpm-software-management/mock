The dnf `download` command does not accept the `--allowerasing` argument
in dnf5. This invalid argument is now excluded when invoking dnf `download`
operations using `--dnf-cmd` or `--pm-cmd`.
