""" helpers for Copr BDD tests """

from contextlib import contextmanager
import io
import pipes
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
    return " ".join(pipes.quote(arg) for arg in cmd)


def run(cmd):
    """
    Return exitcode, stdout, stderr.  It's bad there's no such thing in behave
    directly.
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    stdout, stderr = process.communicate()
    print("Command exit status {} in: {}".format(
        process.returncode,
        quoted_cmd(cmd),
    ))
    if stdout:
        print("stdout:")
        print(stdout)
    if stderr:
        print("stderr:")
        print(stderr)
    return process.returncode, stdout, stderr


def run_check(cmd):
    """ run, but check nonzero exit status """
    retcode, stdout, stderr = run(cmd)
    assert not retcode
    return stdout, stderr


class Mock:
    """ /bin/mock wrapper """
    def __init__(self, context):
        self.context = context
        context.mock_runs = {
            "init": [],
            "rebuild": [],
        }

    @property
    def basecmd(self):
        """ return the pre-configured mock base command """
        cmd = ["mock"]
        if self.context.chroot_used:
            cmd += ["--chroot", self.context.chroot]
        if self.context.uniqueext_used:
            cmd += ["--uniqueext", self.context.uniqueext]
        for repo in self.context.add_repos:
            cmd += ["-a", repo]
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
        out, err = run_check(self.basecmd + ["--rebuild"] + srpms)
        self.context.mock_runs['rebuild'] += [{
            "status": 0,
            "out": out,
            "err": err,
            "srpms": srpms,
        }]

    def clean(self):
        """ Clean chroot, but keep dnf/yum caches """
        run_check(self.basecmd + [
            "--scrub=bootstrap", "--scrub=root-cache", "--scrub=chroot",
        ])

    @property
    def resultdir(self):
        """ Where the results are stored """
        resultdir = "/var/lib/mock/" + self.context.chroot
        if self.context.uniqueext_used:
            resultdir += "-" + self.context.uniqueext
        return resultdir + "/result"


def assert_is_subset(set_a, set_b):
    """ assert that SET_A is subset of SET_B """
    if set_a.issubset(set_b):
        return
    raise AssertionError("Set {} is not a subset of {}".format(set_a, set_b))
