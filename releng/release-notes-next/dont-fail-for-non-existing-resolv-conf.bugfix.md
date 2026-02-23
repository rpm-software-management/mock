Mock no longer fails if `resolv.conf` is missing on the host.  While builds
requiring network access (--enable-networking) will still fail later, Mock will
no longer crash with a FileNotFoundError during the initialization phase.
