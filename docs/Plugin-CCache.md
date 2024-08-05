---
layout: default
title: Plugin CCache
---

The ccache plugin is a compiler cache plugin. It is disabled by default and has an upper limit of 4GB of ccache data.

Note: this plugin was enabled by default in mock-1.2.14 and older.

## Configuration

The ccache plugin is enabled by default and has the following values built-in:

    config_opts['plugin_conf']['ccache_enable'] = True
    config_opts['plugin_conf']['ccache_opts']['max_cache_size'] = '4G'
    config_opts['plugin_conf']['ccache_opts']['compress'] = None
    config_opts['plugin_conf']['ccache_opts']['dir'] = "%(cache_topdir)s/%(root)s/ccache/u%(chrootuid)s/"
    config_opts['plugin_conf']['ccache_opts']['hashdir'] = True

To turn on ccache compression, use the following in a config file:

    config_opts['plugin_conf']['ccache_opts']['compress'] = 'on'

The value specified is not important, this just triggers the setting of the CCACHE_COMPRESS environment variable, which is what the ccache program uses to determine if compression of cache elements is desired.

Setting `hashdir` to `False` excludes the build working directory from the hash used to distinguish two
compilations when generating debuginfo. While this allows the compiler cache
to be shared across different package NEVRs, it might cause the debuginfo to be
incorrect.
The option can be used for issue bisecting if running the debugger is
unnecessary. ([issue 1395][]https://github.com/rpm-software-management/mock/issues/1395)
See [ccache documentation](https://ccache.dev/manual/4.10.html#config_hash_dir).
This option is available since Mock 5.7.
