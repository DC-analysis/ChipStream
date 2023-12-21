import atexit
import shutil
import tempfile
import time


TMPDIR = tempfile.mkdtemp(prefix=time.strftime(
    "chipstream_test_%H.%M_"))

pytest_plugins = ["pytest-qt"]


def pytest_configure(config):
    """This is run before all tests"""
    # set global temp directory
    tempfile.tempdir = TMPDIR
    atexit.register(shutil.rmtree, TMPDIR, ignore_errors=True)
