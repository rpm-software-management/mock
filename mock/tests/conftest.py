"""Common pytest fixtures."""

import pytest


pytest_version_tuple = tuple(int(piece) for piece in pytest.__version__.split("."))
if pytest_version_tuple < (3, 9):
    # Old versions of pytest don’t have the tmp_path fixture, fill it in here.
    from pathlib import Path

    @pytest.fixture
    def tmp_path(tmpdir):
        """Return temporary directory path object."""
        return Path(tmpdir)
