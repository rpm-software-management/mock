A new plugin named `unbreq` has been added. This plugin is able to detect unused
`BuildRequires` based on file accesses during the RPM build. This plugin is
currently experimental and disabled by default.

This plugin can be enabled from configuration this way:

```
config_opts['plugin_conf']['unbreq_enable'] = True
```

The output of the plugin looks like this:

```
INFO: unbreq plugin: BuildRequire bash is needed because file /usr/bin/bash was accessed
INFO: unbreq plugin: BuildRequire diffutils is needed because file /usr/bin/cmp was accessed
INFO: unbreq plugin: BuildRequire gcc-c++ is needed because file /usr/bin/c++ was accessed
INFO: unbreq plugin: BuildRequire make is needed because file /usr/bin/gmake was accessed
INFO: unbreq plugin: BuildRequire rubygem-asciidoctor is needed because file /usr/bin/asciidoctor was accessed
WARNING: unbreq plugin: the following BuildRequires were not used:
        xmlto
        asciidoc
```
