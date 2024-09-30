""" helpers for Copr BDD tests """

from contextlib import contextmanager
import io
from pathlib import Path
import shlex
import os
import subprocess
import sys


@contextmanager
def no_output():
    """
    Suppress stdout/stderr when it is not captured by behave
    https://github.com/behave/behave/issues/863
    """
    real_out = sys.stdout, sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    yield
    sys.stdout, sys.stderr = real_out


def quoted_cmd(cmd):
    """ shell quoted cmd array as string """
    return " ".join(shlex.quote(arg) for arg in cmd)


def run(cmd):
    """
    Return exitcode, stdout, stderr.  It's bad there's no such thing in behave
    directly.
    """
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        stdout, stderr = process.communicate()
        print(f"Command exit status {process.returncode} in: {quoted_cmd(cmd)}")
        if stdout:
            print("stdout:")
            print(stdout)
        if stderr:
            print("stderr:")
            print(stderr)
        return process.returncode, stdout, stderr
    except (FileNotFoundError, PermissionError) as e:
        print(f"Error running command {quoted_cmd(cmd)}: {e}")
        return -1, "", str(e)


def run_check(cmd):
    """ run, but check nonzero exit status """
    retcode, stdout, stderr = run(cmd)
    if retcode != 0:
        raise Exception(f"Command failed with return code {retcode}: {quoted_cmd(cmd)}\n{stderr}")
    return stdout, stderr


class Mock:
    """ /bin/mock wrapper """
    def __init__(self, context):
        self.context = context
        self.common_opts = []

        # The chroot being used (e.g. fedora-rawhide-x86_64).  If None is used,
        # it is automatically set to the default.cfg target.
        self.chroot = context.chroot

        # The -r/--root option being used.  Sometimes it is convenient to use a
        # custom config file that includes `fedora-rawhide-x86_64`
        # configuration without overriding the `config_opts["root"]" opt.
        # None means "no option used".
        self.chroot_opt = None

        # Sometimes we use multiple chroots.  Clean them all.
        self.more_cleanups = []

        context.mock_runs = {
            "init": [],
            "rebuild": [],
            "calculate-build-deps": [],
        }

    @property
    def basecmd(self):
        """ return the pre-configured mock base command """
        cmd = ["mock"]
        if self.chroot_opt:
            cmd += ["-r", self.chroot_opt]
        if self.context.uniqueext_used:
            cmd += ["--uniqueext", self.context.uniqueext]
        for repo in self.context.add_repos:
            cmd += ["-a", repo]
        if self.common_opts:
            cmd += self.common_opts
        if self.context.next_mock_options:
            cmd += self.context.next_mock_options
            self.context.next_mock_options = []
        return cmd

    def init(self):
        """ initialize chroot """
        out, err = run_check(self.basecmd + ["--init"])
        self.context.mock_runs['init'] += [{
            "status": 0,
            "out": out,
            "err": err,
        }]
        return out, err

    def rebuild(self, srpms):
        """ Rebuild source RPM(s) """

        chrootspec = []
        if self.context.custom_config:
            config_file = Path(self.context.workdir) / "custom.cfg"
            with config_file.open("w") as fd:
                fd.write(f"include('{self.chroot}.cfg')\n")
                fd.write(self.context.custom_config)
            chrootspec = ["-r", str(config_file)]

        out, err = run_check(self.basecmd + chrootspec + ["--rebuild"] + srpms)
        self.context.mock_runs['rebuild'] += [{
            "status": 0,
            "out": out,
            "err": err,
            "srpms": srpms,
        }]

    def calculate_deps(self, srpm, chroot):
        """
        Call Mock with --calculate-build-dependencies and produce lockfile
        """
        call = self.basecmd + ["-r", chroot]
        self.more_cleanups += [call]
        out, err = run_check(call + ["--calculate-build-dependencies", srpm])
        self.chroot = chroot
        self.context.mock_runs["calculate-build-deps"].append({
            "status": 0,
            "out": out,
            "err": err,
            "srpm": srpm,
            "chroot": chroot,
            "lockfile": os.path.join(self.resultdir, "buildroot_lock.json")
        })

    def hermetic_build(self):
        """
        From the previous calculate_deps() run, perform hermetic build
        """
        mock_calc = self.context.mock_runs["calculate-build-deps"][-1]
        out, err = run_check(self.basecmd + [
            "--hermetic-build", mock_calc["lockfile"], self.context.local_repo,
            mock_calc["srpm"]
        ])
        self.context.mock_runs["rebuild"].append({
            "status": 0,
            "out": out,
            "err": err,
        })
        # We built into a hermetic-build.cfg!
        self.chroot = "hermetic-build"
        self.chroot_opt = "hermetic-build"

    def clean(self):
        """ Clean chroot, but keep dnf/yum caches """
        args = ["--scrub=bootstrap", "--scrub=root-cache", "--scrub=chroot"]
        run_check(self.basecmd + args)
        for call in self.more_cleanups:
            run_check(call + args)

    @property
    def resultdir(self):
        """ Where the results are stored """
        resultdir = "/var/lib/mock/" + self.chroot
        if self.context.uniqueext_used:
            resultdir += "-" + self.context.uniqueext
        return resultdir + "/result"


def assert_is_subset(set_a, set_b):
    """ assert that SET_A is subset of SET_B """
    if set_a.issubset(set_b):
        return
    raise AssertionError("Set {} is not a subset of {}".format(set_a, set_b))
