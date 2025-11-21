import atexit
import shutil
import tempfile
import time

# https://github.com/pytorch/pytorch/issues/166628
# Import pytorch before PyQt6
try:
    import torch  # noqa: F401
except ImportError:
    pass

from dcnum.os_env_st import request_single_threaded


request_single_threaded()

TMPDIR = tempfile.mkdtemp(prefix=time.strftime(
    "chipstream_test_%H.%M_"))

pytest_plugins = []

try:
    import pytestqt  # noqa: F401
except ModuleNotFoundError:
    pass
else:
    pytest_plugins.append("pytest-qt")

try:
    import pytest_click  # noqa: F401
except ModuleNotFoundError:
    pass
else:
    pytest_plugins.append("pytest_click")


def pytest_configure(config):
    """This is run before all tests"""
    # set global temp directory
    tempfile.tempdir = TMPDIR
    atexit.register(shutil.rmtree, TMPDIR, ignore_errors=True)
