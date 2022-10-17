---
layout: default
title: Release Notes - Mock v3.3
---

Released on 2022-10-17.

## Mock v3.3 bugfixes:

The fix for `--list-chroots` and `simple_load_config()` from
[v3.1](Release-Notes-3.2) disallowed running Mock under the `root` user.  Since
this is still a common practice [issue#990][], we relaxed the rule and we only
raise a warning if `simple_load_config()` is executed by `root`.

[issue#990]: https://github.com/rpm-software-management/mock/issues/990
