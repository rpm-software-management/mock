import os
import shutil
import stat
import errno
from pathlib import Path
import subprocess
from unittest.mock import patch
import pytest

from mockbuild import file_util


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary base directory for testing."""
    d = tmp_path / "test_rmtree_root"
    d.mkdir()
    return d


def create_dir_structure(base: Path, structure: dict):
    """Helper to create nested dir/file structure from dict."""
    for name, contents in structure.items():
        path = base / name
        if isinstance(contents, dict):  # Directory
            path.mkdir()
            create_dir_structure(path, contents)
        else:  # File
            path.write_text(contents)


def set_immutable(path: Path, immutable: bool):
    """Use chattr to set or unset immutable flag."""
    flag = "+i" if immutable else "-i"
    return subprocess.run(["chattr", flag, str(path)], check=True, capture_output=True, text=True)


def chattr_works_or_skip(path: Path):
    if not hasattr(chattr_works_or_skip, "has_chattr"):
        try:
            result = subprocess.run(["chattr", "-V"], capture_output=True, text=True)
            chattr_works_or_skip.has_chattr = "chattr" in result.stderr
        except (FileNotFoundError, OSError):
            chattr_works_or_skip.has_chattr = False

    if not chattr_works_or_skip.has_chattr:
        pytest.skip("chattr not available on this system")

    try:
        set_immutable(path, True)
        set_immutable(path, False)
    except subprocess.CalledProcessError as e:
        pytest.skip(e.stderr)


class TestRmtree:
    """Integration-style tests for file_util.rmtree using real files and directories"""

    def test_rmtree_regular_directory(self, temp_dir):
        """Delete a directory with files and subdirectories."""
        struct = {
            "file1.txt": "hello",
            "subdir": {
                "file2.txt": "world",
                "nested": {}
            }
        }
        create_dir_structure(temp_dir, struct)
        os.symlink("file1.txt", str(temp_dir / "link"))

        file_util.rmtree(str(temp_dir))

        assert not temp_dir.exists()

    def test_rmtree_nonexistent_directory(self, temp_dir):
        """Should not raise if directory does not exist (ENOENT)."""
        path = temp_dir / "missing"
        # Simulate ENOENT
        with pytest.raises(FileNotFoundError):
            os.listdir(str(path))
        file_util.rmtree(str(path))  # Should not raise

    def test_rmtree_with_exclude(self, temp_dir):
        """Files in exclude list should remain."""
        struct = {
            "keep.txt": "preserve me",
            "delete.txt": "remove me",
            "subdir": {
                "keep_sub.txt": "keep",
                "del.txt": "delete"
            },
            "keepdir": {"a": "1"},
            "deletedir": {"b": "2"},
        }
        create_dir_structure(temp_dir, struct)

        exclude_paths = [
            str(temp_dir / "keep.txt"),
            str(temp_dir / "subdir" / "keep_sub.txt"),
            str(temp_dir / "keepdir"),
        ]
        file_util.rmtree(str(temp_dir), exclude=exclude_paths)

        # Excluded files should still exist
        assert (temp_dir / "keep.txt").exists()
        assert (temp_dir / "subdir" / "keep_sub.txt").exists()
        assert (temp_dir / "keepdir").exists()
        assert (temp_dir / "keepdir" / "a").exists()

        # Others should be gone
        assert not (temp_dir / "delete.txt").exists()
        assert not (temp_dir / "subdir" / "del.txt").exists()
        assert not (temp_dir / "deletedir").exists()
        assert not (temp_dir / "deletedir" / "b").exists()

    def test_rmtree_top_level_excluded(self, temp_dir):
        """If the root is excluded, nothing should happen."""
        (temp_dir / "file.txt").write_text("data")

        file_util.rmtree(str(temp_dir), exclude=(str(temp_dir),))

        # Should not be deleted
        assert temp_dir.exists()
        assert (temp_dir / "file.txt").exists()

    def test_rmtree_immutable_file_with_selinux_flag(self, temp_dir):
        """When selinux=True, try chattr -R -i on immutable files."""
        chattr_works_or_skip(temp_dir)

        file_path = temp_dir / "locked.txt"
        file_path.write_text("I am immutable")

        # Make it immutable
        set_immutable(temp_dir, True)

        try:
            # Confirm immutability blocks deletion
            with pytest.raises(OSError):
                os.rmdir(str(temp_dir))

            # Now try rmtree with selinux=True
            file_util.rmtree(str(temp_dir), selinux=True)

            # Should succeed after chattr -i
            assert not temp_dir.exists()
        finally:
            # Cleanup: remove immutable flag if still set
            if temp_dir.exists():
                set_immutable(temp_dir, False)

    def test_rmtree_immutable_file_without_selinux_fails(self, temp_dir):
        """Without selinux=True, immutable files should cause failure."""
        chattr_works_or_skip(temp_dir)

        file_path = temp_dir / "locked.txt"
        file_path.write_text("I am immutable")

        set_immutable(temp_dir, True)

        try:
            with pytest.raises(OSError):
                file_util.rmtree(str(temp_dir), selinux=False)
        finally:
            if temp_dir.exists():
                set_immutable(temp_dir, False)

    def test_rmtree_readonly_file(self, temp_dir):
        """Test handling of read-only files (no write permission)."""
        file_path = temp_dir / "readonly.txt"
        file_path.write_text("read only")

        # Remove write permissions
        os.chmod(str(file_path), stat.S_IREAD)

        # Should still be removable by owner
        file_util.rmtree(str(temp_dir))

        assert not temp_dir.exists()

    def test_rmtree_directory_with_readonly_dir(self, temp_dir):
        """Read-only directory should still be removable after content is gone."""
        struct = {
            "readonly_empty_dir": {},
            "readonly_dir": {
                "file.txt": "some data",
            }
        }
        create_dir_structure(temp_dir, struct)
        readonly_dir = temp_dir / "readonly_dir"
        readonly_empty_dir = temp_dir / "readonly_empty_dir"

        # Remove write permission on dirs
        os.chmod(str(readonly_empty_dir), stat.S_IREAD | stat.S_IEXEC)
        os.chmod(str(readonly_dir), stat.S_IREAD | stat.S_IEXEC)

        # 'root' could delete readonly dir
        if os.geteuid() != 0:
            with pytest.raises(OSError, match="Permission denied"):
                file_util.rmtree(str(temp_dir))
            assert (readonly_dir / "file.txt").exists()

            # Return write permission on readonly_dir
            os.chmod(str(readonly_dir), stat.S_IREAD | stat.S_IWRITE | stat.S_IEXEC)

        file_util.rmtree(str(temp_dir))

        assert not temp_dir.exists()

    def test_rmtree_symlink_itself(self, temp_dir):
        """If the path is a symlink, should raise OSError."""
        real_dir = temp_dir / "real"
        link = temp_dir / "link"
        real_dir.mkdir()
        os.symlink(real_dir, link)

        with pytest.raises(OSError, match="Cannot call rmtree on a symbolic link"):
            file_util.rmtree(str(link))

        # Real dir should still exist
        assert real_dir.exists()

    def test_rmtree_on_broken_symlink(self, temp_dir):
        """Even broken symlinks should raise."""
        link = temp_dir / "broken"
        os.symlink("/nonexistent/target", str(link))

        with pytest.raises(OSError, match="Cannot call rmtree on a symbolic link"):
            file_util.rmtree(str(link))

    def test_rmtree_error_retry_simulated(self, temp_dir):
        """Simulate delayed deletion."""
        (temp_dir / "file.txt").write_text("will be deleted late")

        # Monkey-patch os.remove to fail first few times
        original_remove = os.remove
        retries = 10 * 2 + 2

        def fake_remove(path):
            nonlocal retries
            if path == str(temp_dir / "file.txt") and retries:
                retries -= 1
                if retries < 12:
                    raise OSError(errno.EBUSY, "tst EBUSY", path)
                return
            original_remove(path)

        with patch("os.remove", fake_remove):
            # Patch time.sleep to avoid long waits during retry
            with patch("time.sleep"):
                with pytest.raises(OSError, match="Directory not empty"):
                    file_util.rmtree(str(temp_dir))
                with pytest.raises(OSError, match="tst EBUSY"):
                    file_util.rmtree(str(temp_dir))
                file_util.rmtree(str(temp_dir))

            assert not temp_dir.exists()

    def test_rmtree_long_path(self, temp_dir):
        """Check for directory tree deeper than PATH_MAX."""
        PATH_MAX = os.pathconf(temp_dir, "PC_PATH_MAX")
        if PATH_MAX < 3:
            pytest.skip(f"to short PATH_MAX: {PATH_MAX}")
        NAME_MAX = os.pathconf(temp_dir, "PC_NAME_MAX")
        if NAME_MAX < 1:
            pytest.skip(f"to short NAME_MAX: {NAME_MAX}")

        dir_name = "d" * NAME_MAX

        # Create a deep directory tree
        def create_dir_tree(current, min_length):
            current_fd = os.open(str(current), os.O_RDONLY)
            while len(str(current)) <= min_length:
                current = current / dir_name
                os.mkdir(dir_name, dir_fd=current_fd)
                new_fd = os.open(dir_name, os.O_RDONLY, dir_fd=current_fd)
                os.close(current_fd)
                current_fd = new_fd
            with os.fdopen(os.open("file.txt", os.O_WRONLY | os.O_CREAT, dir_fd=current_fd), "w") as fd:
                fd.write("data")
            os.close(current_fd)
        try:
            create_dir_tree(temp_dir, PATH_MAX)
            file_util.rmtree(str(temp_dir))
            assert not temp_dir.exists()

            temp_dir.mkdir()
            create_dir_tree(temp_dir, PATH_MAX * 3)
            file_util.rmtree(str(temp_dir))
            assert not temp_dir.exists()
        finally:
            if temp_dir.exists():
                shutil.rmtree(str(temp_dir))

    def test_rmtree_symlink_out(self, temp_dir):
        """Check if symlink targets are save."""
        (temp_dir / "to rm").mkdir()

        (temp_dir / "keepdir empty").mkdir()
        (temp_dir / "keepdir").mkdir()
        (temp_dir / "file.txt").write_text("top")
        (temp_dir / "keepdir" / "file.txt").write_text("sub")

        (temp_dir / "to rm" / "link to 'empty' dir").symlink_to("../keepdir empty")
        (temp_dir / "to rm" / "link to dir").symlink_to("../keepdir")
        (temp_dir / "to rm" / "link to dir abs").symlink_to(str(temp_dir / "keepdir"))
        (temp_dir / "to rm" / "link to file").symlink_to("../file.txt")
        (temp_dir / "to rm" / "link to file abs").symlink_to(str(temp_dir / "keepdir" / "file.txt"))

        file_util.rmtree(str(temp_dir / "to rm"))

        assert not (temp_dir / "to rm").exists()

        assert (temp_dir / "file.txt").exists()
        assert (temp_dir / "keepdir empty").exists()
        assert (temp_dir / "keepdir").exists()
        assert (temp_dir / "keepdir" / "file.txt").exists()
