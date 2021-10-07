---
layout: default
title: Feature DNF
---
## DNF

This is default package manager for mock. You can enforce it (e.g. in older Mock) using>

```
config_opts['package_manager'] = 'dnf'
```

## YUM

Yum is still used in RHEL 7 and olders. You can enable it using

```
config_opts['package_manager'] = 'yum'
```

## MicroDNF

MicroDNF is written in C and does not need Python. It is present in minimal OCI containers. It can be enabled using:

```
config_opts['package_manager'] = 'microdnf'
```

However, MicroDNF still [does not have `buildep` command](https://github.com/rpm-software-management/microdnf/issues/82). The current implementation still installs DNF (using microdnf) and use DNF to query the build deps.

You can use following options in the config:
```
config_opts['microdnf_command'] = '/usr/bin/microdnf'
# "dnf-install" is special keyword which tells mock to use install but with DNF
config_opts['microdnf_install_command'] = 'dnf-install microdnf dnf dnf-plugins-core distribution-gpg-keys'
config_opts['microdnf_builddep_command'] = '/usr/bin/dnf'
config_opts['microdnf_builddep_opts'] = []
config_opts['microdnf_common_opts'] = []
```
