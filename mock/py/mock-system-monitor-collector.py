#!/usr/bin/python3
# License: GPL2 or later see COPYING
"""
Standalone resource-usage collector for mock's system_monitor plugin.

Periodically reads a set of cgroup v2 files under given cgroup directories
and sends them to STDOUT as JSONL.

See https://docs.kernel.org/admin-guide/cgroup-v2.html for the cgroup v2
file formats and semantics used below.
"""

# pylint: disable=invalid-name

import argparse
import json
import os
import sys
import time

# Cgroup parser helpers, check the docs above for the file formats.
# OSError/ValueError are swallowed; a file may not exist on this
# distro/kernel or vanish mid-sample.


def _read_int(path):
    try:
        with open(path, 'r', encoding="utf-8") as f:
            text = f.read().strip()
            if text in ("", "max"):
                return 0

            return int(text)
    except (OSError, ValueError):
        return 0


def _read_stat_fields(path, fields):
    result = dict.fromkeys(fields, 0)
    try:
        with open(path, 'r', encoding="utf-8") as file:
            for line in file:
                parts = line.split()
                if len(parts) == 2 and parts[0] in result:
                    # example: usage_usec 4000000
                    result[parts[0]] = int(parts[1])
    except (OSError, ValueError):
        pass

    return result


def _sum_over_dirs(dirs, filename, reader, *args):
    return sum(reader(os.path.join(d, filename), *args) for d in dirs)


def _multi_delta_over_dirs(dirs, filename, reader, state, fields):
    # sum across dirs how much each of `fields` increased since the last
    # time each individual directory was read
    totals = dict.fromkeys(fields, 0)
    for d in dirs:
        current = reader(os.path.join(d, filename), fields)
        for field in fields:
            key = (filename, field, d)
            previous = state.get(key, current[field])
            totals[field] += max(current[field] - previous, 0)
            state[key] = current[field]

    return totals


def _active_dirs(dirs):
    # Keep the first dir unconditionally (the caller's own cgroup), and any
    # further dirs only while they currently exist.
    #
    # cgroup v2 aggregates cumulative values recursively across the whole
    # subtree, even after a descendant is gone, so summing just these
    # top-level dirs is enough. A further dir (e.g. a named nspawn slice) can
    # appear and disappear during the build, so this is re-evaluated every
    # tick rather than cached.
    if not dirs:
        return []

    return [dirs[0]] + [d for d in dirs[1:] if os.path.isdir(d)]


def _take_sample(dirs, state):
    now = time.time()
    active_dirs = _active_dirs(dirs)

    cpu = _multi_delta_over_dirs(active_dirs, "cpu.stat", _read_stat_fields, state,
                                  ["usage_usec", "user_usec", "system_usec"])

    return {
        "t": now,
        "rss_bytes": _sum_over_dirs(active_dirs, "memory.current", _read_int),
        "swap_bytes": _sum_over_dirs(active_dirs, "memory.swap.current", _read_int),
        "cpu_usage_delta_usec": cpu["usage_usec"],
        "cpu_user_delta_usec": cpu["user_usec"],
        "cpu_system_delta_usec": cpu["system_usec"],
        "pids": _sum_over_dirs(active_dirs, "pids.current", _read_int),
    }


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        description="Periodically sample cgroup v2 resource usage and print "
                     "one JSONL sample per line to STDOUT.",
    )
    parser.add_argument("--interval", type=float, required=True,
                         help="seconds to sleep between samples")
    parser.add_argument("--cgroup", dest="cgroups", metavar="PATH",
                         action="append", required=True,
                         help="cgroup directory to sample; may be given more than once")
    return parser.parse_args(argv)


def main(argv=None):
    """ Entry point: parse args, then sample forever until killed or the pipe closes. """
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    state = {}

    while True:
        try:
            sample = _take_sample(args.cgroups, state)
            print(json.dumps(sample), flush=True)
        except BrokenPipeError:
            # the parent went away without terminating us - nothing left to do
            break
        except (OSError, ValueError):
            # a bad tick shouldn't stop the whole collector
            pass

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
