The `uidManager` is now reloaded with `chrootuid`/`chrootgid` from
config after the configuration is loaded.  Previously, privilege
dropping always used the calling user's identity, ignoring the
configured chroot user ([#1731][]).
