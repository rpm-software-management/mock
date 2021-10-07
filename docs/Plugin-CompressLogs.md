---
layout: default
title: Plugin Compress Logs
---

This plugin compress logs created by mock (build.log, root.log and state.log). This plugin is disabled by default.

## Configuration

In file `/etc/mock/site-defaults.cfg` put this configuration:

    config_opts['plugin_conf']['compress_logs_enable'] = False
    config_opts['plugin_conf']['compress_logs_opts'] = {}
    config_opts['plugin_conf']['compress_logs_opts']['command'] = "/usr/bin/xz -9"

This plugin is available since mock-1.2.1.
