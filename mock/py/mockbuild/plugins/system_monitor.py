# License: GPL2 or later see COPYING
"""
Track various system statistics during the build phase.
- Report maximum allocated memory in total and for the "biggest" process

The plugin requires systemd-nspawn as build container runner
"""

import threading
import time
import os
import json

from mockbuild.trace_decorator import getLog
from mockbuild.util import get_machinectl_uuid, _safe_check_output

requires_api_version = "1.1"
run_in_bootstrap = False

def init(plugins, conf, buildroot):
    SystemMonitor(plugins, conf, buildroot)

class SystemMonitor():

    def get_top_process_info(self, scope_path):
        """Finds the process in the cgroup with the highest RSS.

        Args:
            scope_path (str): Path to the cgroup scope directory.

        Returns:
            tuple[str, int]: A tuple containing the command line of the top process
                and its RSS in bytes.
        """
        procs_path = os.path.join(scope_path, "cgroup.procs")
        max_rss = 0
        top_cmdline = ""

        try:
            if not os.path.exists(procs_path):
                return "unknown", 0
            with open(procs_path, 'r') as f:
                pids = f.read().split()

            for pid in pids:
                try:
                    with open(f"/proc/{pid}/statm", 'r') as sm:
                        data = sm.read().split()
                        if not data: continue
                        # RSS in pages * 4096 bytes
                        rss_bytes = int(data[1]) * os.sysconf('SC_PAGE_SIZE')

                    if rss_bytes > max_rss:
                        max_rss = rss_bytes
                        with open(f"/proc/{pid}/cmdline", 'r') as cmd:
                            top_cmdline = cmd.read().replace('\0', ' ').strip()
                        if not top_cmdline:
                            top_cmdline = f"{pid}"

                except (FileNotFoundError, ProcessLookupError, IndexError):
                    continue
        except Exception as e:
            getLog().error("SYSMON: Error: %s", e)

        return top_cmdline, max_rss

    def sysmon_thread(self, buildroot, interval):
        current_peak = 0

        # wait for nspawn to start
        time.sleep(5)
        machine_id = get_machinectl_uuid(buildroot.make_chroot_path())
        if machine_id == None:
            getLog().error("SYSMON: Failed to get nspawn container machine_id")
            return

        # The unit name depends on systemd version
        ustr = _safe_check_output(["/bin/machinectl", "show", "--property=Unit", f"{machine_id}"])
        if isinstance(ustr, bytes):
            ustr = ustr.decode("utf-8")
        machine_id_unit = ustr.rstrip().split('=')[1]
        scope_dir = f"/sys/fs/cgroup/machine.slice/{machine_id_unit}"
        peak_file = os.path.join(scope_dir, "memory.peak")

        while not self.sysmon_stop_event.is_set():
            max_status = "Current"
            pid_status = "Current"

            try:
                if os.path.exists(peak_file):
                    with open(peak_file, 'r') as f:
                        current_peak = int(f.read().strip())

                if current_peak > self.max_memory_peak:
                    max_status = "NEW"
                    self.max_memory_peak = current_peak

                cmd, rss = self.get_top_process_info(f"{scope_dir}/payload")
                if rss > self.top_rss:
                    pid_status = "NEW"
                    self.top_rss = rss
                    self.top_rss_cmd = cmd

                if f"{max_status}{pid_status}" != "CurrentCurrent":
                    getLog().debug(
                        "SYSMON: %s PEAK %.2f MiB | SYSMON: %s Top Process: RSS:%.2f MiB [%s]",
                        max_status, self.max_memory_peak / 1048576, pid_status, self.top_rss / 1048576, self.top_rss_cmd
                    )
            except (IOError, ValueError):
                getLog().debug("SYSMON: memory.peak missing %s", scope_dir)

            if self.sysmon_stop_event.wait(timeout=interval):
                break

    def _on_pre_build(self):
        # Inject nspawn args
        nspawn_args = self.config.get('nspawn_args', [])
        prop = '--property=MemoryAccounting=on'
        if prop not in nspawn_args:
            nspawn_args.append(prop)
            self.config['nspawn_args'] = nspawn_args

        # Start thread
        interval = self.memory_accounting_opts.get('interval', 2)
        self.sysmon_stop_event.clear()
        self.sysmon_timer_thread = threading.Thread(target=self.sysmon_thread, args=(self.buildroot, interval), daemon=True)
        self.sysmon_timer_thread.start()

        getLog().debug("SYSMON: Monitoring thread started via callback.")

    def _on_post_build(self):
        self.sysmon_stop_event.set()
        self.sysmon_timer_thread.join()
        getLog().info(
            "SYSMON: Total Memory Peak %.2f MiB | Top process: RSS:%.2f MiB [%s]",
            self.max_memory_peak / 1048576, self.top_rss / 1048576, self.top_rss_cmd
        )
        out_file = self.buildroot.resultdir + '/system_monior.json'
        with open(out_file, 'w') as f:
            json.dump({"total_max_memory" : self.max_memory_peak, "top_process_memory" : self.top_rss, "top_process_cmdline" : self.top_rss_cmd}, f)

    def __init__(self, plugins, conf, buildroot):
        self.max_memory_peak = 0
        self.top_rss = 0
        self.top_rss_cmd = ""
        self.sysmon_timer_thread = None
        self.sysmon_stop_event = threading.Event()
        self.buildroot = buildroot
        self.memory_accounting_opts = conf
        self.config = buildroot.config

        if self.config.get('use_nspawn', True):
            getLog().warning("SYSMON: build is not using nspawn. Statistics will not be available")
            return

        getLog().info("SYSMON: Starting system monitor")
        plugins.add_hook("prebuild", self._on_pre_build)
        plugins.add_hook("postbuild", self._on_post_build)
