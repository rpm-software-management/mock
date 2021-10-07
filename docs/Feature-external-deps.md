---
layout: default
title: Feature external dependencies
---
## External dependencies

It can happen that you need some library that is not packaged. PyPI has ten times more modules than Fedora has packages. The same for Rubygems.org, Crates.io...

External dependencies allow you to install a package using the native package manager. I.e. not dnf or rpm, but rather using `pip`, `gem`, etc.

Right now it is possible to do that only for BuildRequires. Run-time requires will need more co-operation with DNF and rpm.

This feature is by default disabled. It can be enabled using:

```
config_opts['external_buildrequires'] = True
```

## Modules

### PyPI

`BuildRequires: external:pypi:foo` - this will run `pip3 --install foo`

### Crate

`BuildRequires: external:crate:foo` - this will run `cargo install foo`

### Others

Do you miss other languages here? [File an issue](https://github.com/rpm-software-management/mock/issues) and let us know which language you want to add. There are two requirements. The native package manager needs to be available in Fedora. And the manager has to have `--root` or something similar which let you allow to install the files in the different root path. That is because we run this tool in bootstrap chroot.

## How it works

When we find the `external::` prefix in BuildRequires then Mock install the native package manager in bootstrap buildroot. E.g., for `external:pypi:foo` mock will install `pip3` and run `pip3 install --root MOCK_CHROOT foo`.

To satisfy rpm dependencies Mock calls `create-fake-rpm` and creates a fake rpm package that provides `external:pypi:foo` and installs it in chroot.

All this is logged in `root.log` and usually start with the line `Installing dependencies to satisfy external:*`

As of now, this feature requires [bootstrap chroot](Feature-bootstrap) enabled and requires `create-fake-rpm` to be present (package) in the target chroot.

Available since 2.7
