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

To turn on ccache compression, use the following in a config file:

    config_opts['plugin_conf']['ccache_opts']['compress'] = 'on'

The value specified is not important, this just triggers the setting of the CCACHE_COMPRESS environment variable, which is what the ccache program uses to determine if compression of cache elements is desired.
