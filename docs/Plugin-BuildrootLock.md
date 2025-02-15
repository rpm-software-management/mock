---
layout: default
title: Plugin buildroot_lock
---

buildroot_lock Plugin
=====================

This plugin generates an additional build artifact—the buildroot *lockfile*
(`buildroot_lock.json` file in the result directory).

The *lockfile* describes both the list of buildroot sources (e.g., a list of
installed RPMs, bootstrap image info, etc.) and a set of Mock configuration
options.  Using this information, Mock can later reproduce the buildroot
preparation (see the [Hermetic Builds feature page](feature-hermetic-builds)).

This plugin is **disabled** by default but is automatically enabled with the
`--calculate-build-dependencies` option.  You can enable it (for all builds) by
this configuration snippet:

```python
config_opts['plugin_conf']['buildroot_lock_enable'] = True
```

**Note:** This plugin does not work with the `--offline` option.


Format of the *buildroot_lock.json* file
----------------------------------------

The file `buildroot_lock.json` is a JSON file.  List of JSON Schema files is
installed together with the Mock RPM package:

    rpm -ql mock | grep schema
    /usr/share/doc/mock/buildroot-lock-schema-1.0.0.json
    /usr/share/doc/mock/buildroot-lock-schema-1.1.0.json

Currently, we do not provide a compatibility promise.  Only the exact same
version of Mock that produced the file is guaranteed to read and process it.
For more information, see [Hermetic Builds](feature-hermetic-builds).

Also, in the future we plan to switch to a standardized tooling so we operate
with a standardized format, too.  For more info see the [DNF5 feature
request][discussion], [rpm-lockfile-prototype][] and [libpkgmanifest][].

[discussion]: https://github.com/rpm-software-management/dnf5/issues/833
[rpm-lockfile-prototype]: https://github.com/konflux-ci/rpm-lockfile-prototype
[libpkgmanifest]: https://github.com/rpm-software-management/libpkgmanifest
