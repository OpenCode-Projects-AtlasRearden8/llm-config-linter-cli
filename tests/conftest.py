"""Shared helpers: paths to fixtures and helper to collect issues."""
import os
import shutil
import stat

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    return os.path.join(FIXTURES, name)


def private_copy(tmp_path, name):
    """Copy a fixture into tmp_path as a private (0600) file.

    Git stores plain files group/other-readable on checkout, but the
    file-permissions check expects private files - so tests that assert
    a clean run copy fixtures to tmp first.
    """
    dest = tmp_path / name
    shutil.copyfile(fixture(name), dest)
    os.chmod(dest, stat.S_IRUSR | stat.S_IWUSR)
    return str(dest)


def checks(issues, check_name):
    return [i for i in issues if i.check == check_name]


def severities(issues):
    return {i.severity for i in issues}
