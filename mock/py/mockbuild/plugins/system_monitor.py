# License: GPL2 or later see COPYING
"""
Sample resource usage continuously throughout the whole build,
tagging each sample with the build phase active at the time, and
stream the raw samples into the result dir.

The actual sampling happens in a separate `mock-system-monitor-collector`
process (see mock-system-monitor-collector.py). This plugin only figures out
which cgroups to monitor plus is creating named nspawn slice.
"""

import json
import os
import subprocess
import threading

from mockbuild import util
from mockbuild.trace_decorator import getLog

requires_api_version = "1.1"
# TODO: would be nice to have monitoring for bootstrap as well
run_in_bootstrap = False

_COLLECTOR_ARGV = ["mock-system-monitor-collector"]


def init(plugins, conf, buildroot):
    """ Plugin entry point """
    SystemMonitor(plugins, conf, buildroot)


def _own_cgroup_path():
    # return the cgroupfs path of the current process cgroup as
    # absolute path (no self-reference). This is where mock itself
    # is running: builddeps, chroot init, ...
    try:
        with open("/proc/self/cgroup", 'r', encoding="utf-8") as file:
            for line in file:
                # example line: 0::/some/path
                if line.startswith("0::"):
                    relative = line.strip().split(":", 2)[2]
                    return "/sys/fs/cgroup" + relative
    except OSError as e:
        getLog().debug("SYSMON: could not read own cgroup: %s", e)

    return None


def _setup_cgroup():
    cgroup_path = _own_cgroup_path()
    if not cgroup_path or not os.path.isdir(cgroup_path):
        return None

    return cgroup_path


def _inject_nspawn_slice(config, slice_name):
    # without a dedicated slice, the actual build (running inside
    # the nspawn container) would be invisible to us - monitoring
    # only mock's own cgroup would be misleading, not useful.
    # This is where the building happens.
    if '--slice' not in util.systemd_nspawn_help_output():
        return False

    nspawn_args = config.get('nspawn_args', [])
    slice_arg = f'--slice={slice_name}'
    if slice_arg not in nspawn_args:
        nspawn_args.append(slice_arg)
        config['nspawn_args'] = nspawn_args

    return True


def _parse_sample_line(line):
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        getLog().debug("SYSMON: could not parse collector output line: %r", line)
        return None


class SystemMonitor:  # pylint: disable=too-few-public-methods
    """ Main plugin class. """

    def __init__(self, plugins, conf, buildroot):
        self.buildroot = buildroot
        self.opts = conf
        self.interval = self.opts.get('interval', 5)
        self._proc = None
        self._thread = None
        self._samples_path = None
        self._current_phase = "startup"

        cgroup_path = _setup_cgroup()
        if not cgroup_path:
            getLog().warning("SYSMON: could not determine own cgroup, "
                              "resource monitoring disabled")
            return

        slice_name = f"mocksysmon{os.getpid()}.slice"
        if not _inject_nspawn_slice(buildroot.config, slice_name):
            getLog().warning("SYSMON: systemd-nspawn does not support --slice, "
                              "resource monitoring disabled")
            return

        if not self._prepare_samples_file(buildroot.resultdir):
            return

        cgroup_dirs = [cgroup_path, os.path.join("/sys/fs/cgroup", slice_name)]
        self._start_collector(cgroup_dirs, self.interval)

        # needed for phase tagging in samples
        plugins.add_hook("preinit", lambda: self._set_phase("chroot_init"))
        plugins.add_hook("earlyprebuild", lambda: self._set_phase("resolving_deps"))
        plugins.add_hook("postdeps", lambda: self._set_phase("build"))
        # only produces check phase when `separate_check` is enabled
        # otherwise %check run inside the run_build() so we get
        # everything under build phase
        plugins.add_hook("precheck", lambda: self._set_phase("check"))

        plugins.add_hook("postbuild", self._finalize)
        plugins.add_hook("initfailed", self._finalize)

        getLog().info("SYSMON: monitoring cgroups ready at %s", cgroup_dirs)

    def _prepare_samples_file(self, resultdir):
        try:
            self._samples_path = os.path.join(resultdir, "system_monitor_samples.jsonl")
            # start each build with a fresh, empty file - later samples are
            # appended to it one by one as they arrive
            with open(self._samples_path, 'w', encoding="utf-8"):
                pass

            return True
        except OSError:
            getLog().warning("SYSMON: failed to create results file", exc_info=True)
            return False

    def _start_collector(self, cgroup_dirs, interval):
        cmd = list(_COLLECTOR_ARGV) + ["--interval", str(interval)]
        for cgroup_dir in cgroup_dirs:
            cmd += ["--cgroup", cgroup_dir]

        self._proc = subprocess.Popen(  # pylint: disable=consider-using-with
            cmd, stdout=subprocess.PIPE, universal_newlines=True)
        self._thread = threading.Thread(target=self._read_samples, daemon=True)
        self._thread.start()

    def _read_samples(self):
        # runs in the background reader thread; ends naturally once the
        # collector process exits and its stdout hits EOF
        for line in self._proc.stdout:
            sample = _parse_sample_line(line)
            if sample is None:
                continue

            sample["phase"] = self._current_phase
            try:
                with open(self._samples_path, 'a', encoding="utf-8") as f:
                    f.write(json.dumps(sample) + "\n")
            except OSError:
                getLog().warning("SYSMON: failed to write sample", exc_info=True)

    def _set_phase(self, name):
        getLog().debug("SYSMON: switching to phase '%s'", name)
        self._current_phase = name

    def _finalize(self):
        if self._proc is None:
            return

        proc = self._proc
        self._proc = None
        proc.terminate()
        self._thread.join(timeout=5)
        proc.wait()
