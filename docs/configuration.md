---
layout: default
title: Mock configuration
---

## Mock configuration files

Syntactically, Mock configuration files are just Python files.  But you should
be rather conservative and use just the `config_opts[]` dictionary because we'd
like to [change the format in the future](https://github.com/rpm-software-management/mock/issues/1060).

Mock RPM package self-documents all the available options, take a look at this
file:

    $ rpm -qd mock | grep site-defaults
    /usr/share/doc/mock/site-defaults.cfg

Mock configuration files can be logically divided into *generic* (used for every
executed Mock command) and *chroot* configuration (used only if the
corresponding chroot is selected, see below).

Both the *generic* and *chroot* configuration can be done on either
*system* level (`/etc/mock` directory) or on *user* level (files in
`$HOME/.config` directory).


### Selecting a chroot config

For example to initialize a Fedora Rawhide x86_64 chroot (using
`/etc/mock/fedora-rawhide-x86_64.cfg` file), and switch into the chroot, one can
do:

    $ mock -r fedora-rawhide-x86_64 --shell

Note we are not using the `.cfg` suffix in the `-r` option in this case.  This
way the *user* level `$HOME/.config` files are searched for the corresponding
`.cfg` file first, and since nothing is found, then the *system* level file is
found in `/etc/mock` (and used).

One can though use a config pathname with the `-r` option, too.  But the
pathname must represent an existing file (accessible from the current working
directory):

    $ mock -r ./subdir/existing-config-file.cfg --shell
    $ mock -r /etc/mock/fedora-35-x86_64.cfg

### Generic configuration changes

Typically the file `$HOME/.config/mock.cfg` should be used for *generic*
configuration changes for a single user.  If a *system* Mock behavior change
is desired (for all system users), then use `/etc/mock/site-defaults.cfg`.

The `site-defaults.cfg` is typically empty by default, but contains a basic
documentation and a valid link to a **complete configuration documentation**.
That documentation typically is `/usr/share/doc/mock/site-defaults.cfg`
(location may vary depending on your host system conventions).


### Chroot configuration changes

There are `/etc/mock/<buildroot>.cfg` files for various build chroots that
contain various compatibility settings related to the target distribution
(location of RPM repositories, if DNF or YUM should be used, working directory
to be used, and so on).

These system files are shipped via the `mock-core-configs` (or other), and users
are discouraged from changing these (change would break the automatic update of
such file with an updated version of the package).  It is safer to install an
*override* configuration file:

    $ cat $HOME/.config/mock/fedora-35-x86_64.cfg
    # include the default configuration
    include("/etc/mock/fedora-35-x86_64.cfg")
    # install make into the minimal build chroot
    config_opts['chroot_additional_packages'] = 'make'

You may also copy and edit an existing configuration file into a new one:

    $ cp /etc/mock/fedora-rawhide-x86_64.cfg ~/.config/mock/foo.cfg

If Koji is already using a config you need, then you can use the Koji client
tool for generating the file:

    $ koji mock-config --tag f21-build --arch=aarch64 f21 > ~/.config/mock/foo.cfg

Similar functionality has the Copr client tool:

    $ copr mock-config @copr/copr-dev fedora-21-x86_64 > ~/.config/mock/foo.cfg

When your file `foo.cfg` is installed, you can just do `mock -r foo [...]`.

### Order of loading the files

The order of reading and evaluating configuration files in Mock is the following:

1. `/etc/mock/site-defaults.cfg`
1. `/etc/mock/<buildroot>.cfg` or `~/.config/mock/<buildroot>.cfg`
1. `~/.mock/user.cfg`
1. `~/.config/mock.cfg` (since `mock-1.2.15`)

I.e. the value set in the later configuration file overrides the value set by
previously loaded files.
