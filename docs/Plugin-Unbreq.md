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
INFO: enabled unbreq plugin(prebuild)
...
INFO: enabled unbreq plugin(postbuild)
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

## Issues
* Currently does not work with `--isolation=simple`

## How it works
The tool marks a timestamp before executing the build.
After executing the build, the relevant files have their access time compared to the saved timestamp.

1. The tool runs `dnf --assumeno remove ${BuildRequire}` for each field in the SRPM file to get the list of RPMs that would be removed along with the `BuildRequire`.
2. Then the tool checks the files owned by all the RPMs, if they were accessed during the build.
3. If no, then the `BuildRequire` is added to the list of removable fields.
   In the next iteration the `dnf` query is executed with the next `BuildRequire` field together with all the fields that can be removed.

Available since version 6.4.
