---
layout: default
title: Plugin Unbreq
---

Detector of unused `BuildRequires` of RPM builds.

# Usage

> [!Note]
> The current implementation requires that the mock chroot is **not** on a filesystem mounted with the `noatime` option.
> You may need to remount the relevant directory with options `strictatime,lazytime`.

Enable it upon `mock` execution via a flag:
```
mock --enable-plugin=unbreq ...
```

In logs you should see messages like:
```
INFO: enabled unbreq plugin(...)
```

If Unbreq detects an unneeded `BuildRequire` it prints a message like:
```
WARNING: unbreq plugin: the following BuildRequires were not used:
...
```

## Configuration
The configuration options for this plugin are listed below.

Configuration via the `.cfg` file is done this way:
```
config_opts['plugin_conf']['unbreq_opts']['${OPTION}'] = ${VALUE}
```

Configuration from the command line is done this way:
```
--plugin-option='unbreq:${OPTION}=${VALUE}'
```

### Configuration options
* **`exclude_accessed_files`** - *`List[str]`*
  * A list of regular expressions that are used to ignore file accesses of certain files.

    *Example*: `xmvn` always reads all files inside `/usr/share/maven-metadata/`.
    The exclusion filter `^/usr/share/maven-metadata/` excludes these files from the listing.

## How it works

### Before the build
The tool reads the `BuildRequires` of the SRPM files (usually only one) in their standard location.
This step is executed after resolving dynamic `BuildRequires` and this tool is able to recognize them.

It also marks a timestamp before executing the build for use as reference.

Depending of the detected filesystem mount options, if `relatime` options is detected, then all the files owned by all the installed dependencies have their access times and modify times set to `0`, to make it possible to detect further file accesses during the build.

### After the build
After executing the build, the relevant files have their access time compared to the saved timestamp.

Each `BuildRequire` field may cause the installation of multiple packages.
These are obtained by iteratively executing `dnf --assumeno remove ${BuildRequires}`.

If any of the files owned by any of the package in this set was accessed, then this `BuildRequires` field can not be removed.

Each iteration of the `remove` query will also include all the `BuildRequires` fields for which were shown to be unnecessary.
This is because the removal of multiple packages at once can produce a different result than removing them separately.

### Output
The output of the tool is logged in the build log at the end of the build.

Available since version 6.4.
