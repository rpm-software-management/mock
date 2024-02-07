On newer build hosts (Fedora 44+ and EL 11+), Mock uses the
[`useradd --root` option][issue#1285] instead of `--prefix` to better isolate it
from the host system.  Specifically, this correctly resolves
[subuid/subgid issues][issue#1354] (previously, we had to work around this
problem by using in-chroot shadow-utils).
