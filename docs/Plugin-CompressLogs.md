---
layout: default
title: Plugin Compress Logs
---

This plugin compresses logs created by Mock in the result directory (build.log,
hw_info.log, installed_pkgs.log, root.log and state.log).

This plugin is **disabled** by default.


## Configuration

To compress your logs with XZ, you can put this into the
[configuration](configuration):
```python
config_opts['plugin_conf']['compress_logs_enable'] = True
config_opts['plugin_conf']['compress_logs_opts']['command'] = "/usr/bin/xz -9"
```
This plugin is available since mock-1.2.1.
