"""Test the standalone mock-system-monitor-collector script."""

# _write()/_populate_cgroup() below are intentionally duplicated from
# tests/plugins/test_system_monitor.py, not worth sharing via
# conftest.py.
# pylint: disable=duplicate-code

import importlib.util
import os

_SPEC = importlib.util.spec_from_file_location(
    "mock_system_monitor_collector",
    os.path.join(os.path.dirname(__file__), "..", "py", "mock-system-monitor-collector.py"),
)
collector = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(collector)

GiB = 1024 ** 3


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


def test_multi_delta_since_last_read(tmp_path):
    """ Test that cpu.stat deltas are computed since the last read, not absolute values. """
    # pylint: disable=protected-access
    cgroup_dir = tmp_path / "cg"
    cgroup_dir.mkdir()
    _write(str(cgroup_dir), "cpu.stat", "usage_usec 1000000\nuser_usec 900000\nsystem_usec 100000\n")

    state = {}
    fields = ["usage_usec", "user_usec", "system_usec"]
    # the first read has no prior value to diff against, so it seeds `state`
    # and reports a zero delta
    first = collector._multi_delta_over_dirs(
        [str(cgroup_dir)], "cpu.stat", collector._read_stat_fields, state, fields)
    assert first == {"usage_usec": 0, "user_usec": 0, "system_usec": 0}

    _write(str(cgroup_dir), "cpu.stat", "usage_usec 1500000\nuser_usec 1350000\nsystem_usec 150000\n")
    second = collector._multi_delta_over_dirs(
        [str(cgroup_dir)], "cpu.stat", collector._read_stat_fields, state, fields)
    assert second == {"usage_usec": 500000, "user_usec": 450000, "system_usec": 50000}


def test_active_dirs_filters_missing_extra_dirs(tmp_path):
    """ Test that only the first dir is kept unconditionally; extras only while they exist. """
    cgroup_dir = tmp_path / "cg"
    cgroup_dir.mkdir()
    slice_dir = tmp_path / "slice"

    assert collector._active_dirs([str(cgroup_dir), str(slice_dir)]) == [str(cgroup_dir)]  # pylint: disable=protected-access

    slice_dir.mkdir()
    assert collector._active_dirs([str(cgroup_dir), str(slice_dir)]) == [  # pylint: disable=protected-access
        str(cgroup_dir), str(slice_dir)]


def test_take_sample_schema(tmp_path):
    """ Test that _take_sample() wires the helpers together into the expected sample shape. """
    cgroup_dir = tmp_path / "cg"
    cgroup_dir.mkdir()
    _populate_cgroup(str(cgroup_dir))

    state = {}
    # first tick has no prior state to diff cpu.stat against, so its delta is 0
    collector._take_sample([str(cgroup_dir)], state)  # pylint: disable=protected-access

    _write(str(cgroup_dir), "cpu.stat", "usage_usec 1500000\nuser_usec 1350000\nsystem_usec 150000\n")
    sample = collector._take_sample([str(cgroup_dir)], state)  # pylint: disable=protected-access

    assert sample["rss_bytes"] == 1 * GiB
    assert sample["swap_bytes"] == 0
    assert sample["cpu_usage_delta_usec"] == 500000
    assert sample["cpu_user_delta_usec"] == 450000
    assert sample["cpu_system_delta_usec"] == 50000
    assert sample["pids"] == 5
    assert "t" in sample
