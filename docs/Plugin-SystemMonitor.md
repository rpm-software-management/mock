---
layout: default
title: Plugin SystemMonitor
---

This plugin continuously samples resource usage (memory and CPU)
throughout the whole build using the kernel's cgroup v2 controllers.
Every sample is tagged with the build phase that was active at the time
it was taken, so the collected data can later be broken down per-phase
(e.g. "how much memory did dependency resolution need" vs. "how much
memory did the actual build need").

The plugin requires cgroup v2 and `systemd-nspawn` as the build container
runner.

## Output

This plugin writes its data as a single file in the result dir:

* `system_monitor_samples.jsonl` - one raw sample per line, appended as
  soon as it is collected.

Each line of `system_monitor_samples.jsonl` is a JSON object with:

* `phase` - the build phase active when this sample was taken (e.g.
  `chroot_init`, `resolving_deps`, `build`, `check`)
* `t` - wall-clock timestamp (seconds since the epoch) when the sample
  was taken
* `rss_bytes`, `swap_bytes` - memory (RSS) and swap usage at this instant
  (`memory.current`/`memory.swap.current`), not a delta
* `cpu_usage_delta_usec`, `cpu_user_delta_usec`, `cpu_system_delta_usec` -
  CPU time consumed since the previous sample, in microseconds
* `pids` - number of processes/threads in the monitored cgroups at this
  instant

## Configuration

The module is disabled by default and needs to be activated by:

```python
config_opts['plugin_conf']['system_monitor_enable'] = True
```

The following sub-option may be specified:

```python
# the interval between statistics collection runs in seconds, default 5
config_opts['plugin_conf']['system_monitor_opts']['interval'] = 5
```

## Accuracy notes

* Monitoring relies on the current process' own cgroup plus a dedicated
  `systemd-nspawn` slice. If `systemd-nspawn` does not support the
  `--slice` option, the plugin disables itself entirely.
