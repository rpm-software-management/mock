"""
Executing commands in Mock's behave test suite.
"""

from contextlib import contextmanager
import io
import shlex
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
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        ) as process:
            stdout, stderr = process.communicate()
            print(f"Exit code: {process.returncode} in: {quoted_cmd(cmd)}")
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
        raise RuntimeError(f"Command failed with return code {retcode}: "
                           f"{quoted_cmd(cmd)}\n{stderr}")
    return stdout, stderr
