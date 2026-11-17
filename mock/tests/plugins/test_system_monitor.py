"""Test the system_monitor plugin."""

import json
import os
import sys
import time
from unittest import mock

from mockbuild.plugins import system_monitor as sysmon

GiB = 1024 ** 3

COLLECTOR_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "..", "py", "mock-system-monitor-collector.py")


def _write(directory, filename, content):
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _populate_cgroup(cgroup_dir):
    _write(cgroup_dir, "memory.current", str(1 * GiB))
    _write(cgroup_dir, "memory.swap.current", "0")
    _write(cgroup_dir, "cpu.stat", "usage_usec 1000000\nuser_usec 900000\nsystem_usec 100000\n")
    _write(cgroup_dir, "pids.current", "5")


def _make_buildroot(tmp_path):
    buildroot = mock.Mock()
    buildroot.resultdir = str(tmp_path)
    buildroot.config = {"nspawn_args": []}
    return buildroot


def _wait_for_phase_sample(samples_path, phase, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if samples_path.exists():
            with open(samples_path, encoding="utf-8") as f:
                if any(json.loads(line)["phase"] == phase for line in f if line.strip()):
                    return
        time.sleep(0.01)
    raise AssertionError(f"no sample collected for phase {phase!r} within {timeout}s")


def test_plugin_enabled_writes_results(tmp_path):
    """ Test that the plugin writes results when enabled. """
    cgroup_dir = tmp_path / "cg"
    cgroup_dir.mkdir()
    _populate_cgroup(str(cgroup_dir))

    plugins = mock.Mock()
    buildroot = _make_buildroot(tmp_path)

    with mock.patch.object(sysmon, "_setup_cgroup", return_value=str(cgroup_dir)), \
            mock.patch.object(sysmon.util, "systemd_nspawn_help_output", return_value="--slice"), \
            mock.patch.object(sysmon, "_COLLECTOR_ARGV", [sys.executable, COLLECTOR_SCRIPT]):
        sysmon.SystemMonitor(plugins, {"interval": 0.01}, buildroot)

    # a dedicated --slice=... is injected so containers from other,
    # concurrent nspawn/mock instances on the same host aren't summed in
    assert any(arg.startswith("--slice=") for arg in buildroot.config["nspawn_args"])

    hooks = dict((call[0][0], call[0][1]) for call in plugins.add_hook.call_args_list)
    assert set(hooks) == {
        "preinit", "earlyprebuild", "postdeps", "precheck", "postbuild", "initfailed",
    }

    samples_path = tmp_path / "system_monitor_samples.jsonl"

    hooks["preinit"]()
    hooks["earlyprebuild"]()
    hooks["postdeps"]()
    # wait for at least one real sample in each phase instead of a fixed
    # sleep, so this isn't flaky under a loaded/throttled CPU. Each sample
    # is streamed straight to samples.jsonl as it is collected, so we can
    # poll the file directly even before the build finishes.
    _wait_for_phase_sample(samples_path, "build")
    hooks["precheck"]()
    _wait_for_phase_sample(samples_path, "check")
    hooks["postbuild"]()
    # finalize must be idempotent - initfailed firing afterwards must not raise
    hooks["initfailed"]()

    assert samples_path.exists()

    with open(samples_path, encoding="utf-8") as f:
        samples = [json.loads(line) for line in f]

    assert samples
    phases = {s["phase"] for s in samples}
    assert {"build", "check"} <= phases
    assert all(s["rss_bytes"] == 1 * GiB for s in samples)
