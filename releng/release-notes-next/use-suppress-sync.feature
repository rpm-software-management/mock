Mock now pass --suppress-sync=yes to every systemd-nspawn call (when available
i.e., on RHEL9+). This turns off any form of on-disk file system synchronization
for the container payload.

This feature sets a new default for:

    config_opts['nspawn_args'] = ['--capability=cap_ipc_lock', '--suppress-sync=yes']

This dramatically improves container runtime performance - up to 16 % for big packages.
It does not have an impact on building small packages.

The only drawback is that in case of a hard shutdown (power outage) during the build, some changes in the buildroot can be lost.
As buildroot is supposed to be ephemeral and reconstructed for every build, we enabled this by default.
If you want to disable this feature, you can put in your config:

    config_opts['nspawn_args'] = ['--capability=cap_ipc_lock']
