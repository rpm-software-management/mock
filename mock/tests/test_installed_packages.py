"""
Test the "installed_packages.py" file
"""

from mockbuild.installed_packages import _subprocess_executor


def test_the_default_executor():
    """
    The expected executor output is just stderr
    """
    assert "stdout\n" == _subprocess_executor([
        "/bin/sh", "-c", "echo stdout ; echo >&2 stderr"
    ])
