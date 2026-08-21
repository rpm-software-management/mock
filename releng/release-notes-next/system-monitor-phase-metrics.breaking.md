The `system_monitor` plugin replaces `<resultdir>/system_monior.json`
(including the original filename typo) with
`<resultdir>/system_monitor_samples.jsonl`. The output changes from a single
JSON summary to a JSONL stream of memory, swap, CPU and PID-count samples
tagged with the active build phase. Consumers of the old file must be
updated for the new filename, format and schema.

Kernel-tracked memory and swap peaks and information about the process
with the highest observed RSS are no longer reported.
