The `system_monitor` plugin now samples resource usage for the whole build
instead of only reporting a single peak snapshot, and tags every sample
with the active build phase. Extended statistics: CPU, memory. Logged into
`<resultdir>/system_monitor_samples.jsonl`.
