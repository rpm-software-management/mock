Mock now pass --suppress-sync=yes to every systemd-nspawn call (when available
i.e. on RHEL9+). This turns off any form of on-disk file system synchronization
for the container payload. This dramatically improve container runtime performance.
