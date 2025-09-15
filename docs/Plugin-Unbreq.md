---
layout: default
title: Plugin Unbreq
---

Detector of unused `BuildRequires` of RPM builds.

# Usage

> [!Note]
> The current implementation requires that the mock chroot is not on a filesystem mounted with the `noatime` option.
> You may need to remount the relevant directory with options `strictatime,lazytime`.

To run it, install the Python script into the system `mock` plugin directory.
Then enable it upon `mock` execution via a flag:

```
mock --enable-plugin=unbreq ...
```

In logs you should see messages like:

```
INFO: enabled unbreq plugin(prebuild)
```

If Unbreq detects an unneeded `BuildRequire` it prints a message like:

```
WARNING: unbreq plugin: the following BuildRequires were not used:
...
```

## Configuration
The mock plugin reads these mock configuration fields for `config_opts`:

`['plugin_conf']['unbreq_opts']['exclude_accessed_files']` : `List[String]` ::
A list of regular expressions which are used to ignore file accesses of certain files.
+
Example: `xmvn` always reads all files inside `/usr/share/maven-metadata/`, the exclusion filter `^/usr/share/maven-metadata/` excludes these files from the listing.
+
The command line syntax is: `--plugin-option='unbreq:exclude_accessed_files=[${python_regexes...}]'`
