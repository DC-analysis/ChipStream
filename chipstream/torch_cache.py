"""Persistent cache directory for compiled PyTorch models

The "inductor" backend of PyTorch (used by dcnum for segmentation with
exported models) caches compiled code in ``TORCHINDUCTOR_CACHE_DIR``.
By default, this is a directory in the temporary directory of the system,
which may be cleared between runs. With a persistent cache, compiling a
model takes a fraction of the time when ChipStream is started again.

Note that PyTorch fails hard if this directory cannot be created or is
not writable (``torch.compile`` raises a ``PermissionError``). Therefore,
the variable is only set if the directory is writable.
"""
import logging
import os
import pathlib
import sys
import uuid


logger = logging.getLogger(__name__)


def get_user_cache_dir() -> pathlib.Path:
    """Return the per-user cache directory of ChipStream

    This is the same directory that the GUI uses (Qt's
    ``QStandardPaths.CacheLocation`` with the organization name
    "DC-Analysis" and the application name "ChipStream").
    """
    home = pathlib.Path.home()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local"
        return pathlib.Path(base) / "DC-Analysis" / "ChipStream" / "cache"
    elif sys.platform == "darwin":
        return home / "Library" / "Caches" / "DC-Analysis" / "ChipStream"
    else:
        base = os.environ.get("XDG_CACHE_HOME") or home / ".cache"
        return pathlib.Path(base) / "DC-Analysis" / "ChipStream"


def is_directory_writable(path: pathlib.Path) -> bool:
    """Create `path` if necessary and check whether we can write to it"""
    path = pathlib.Path(path)
    test_file = path / f".write-test_{uuid.uuid4()}.tmp~"
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file.touch()
    except OSError:
        return False
    finally:
        try:
            test_file.unlink(missing_ok=True)
        except OSError:
            pass
    return True


def setup_torch_inductor_cache_dir() -> pathlib.Path | None:
    """Set ``TORCHINDUCTOR_CACHE_DIR`` to a persistent cache directory

    The environment variable is set in :data:`os.environ`, so that the
    worker processes spawned by dcnum inherit it. A value that is already
    set (e.g. by the user) is not changed. If the cache directory is not
    writable, the variable is not set (PyTorch then uses its default
    directory) and a warning is logged.

    Returns the cache directory that PyTorch will use or None if
    PyTorch uses its default directory.
    """
    name = "TORCHINDUCTOR_CACHE_DIR"
    if os.environ.get(name):
        return pathlib.Path(os.environ[name])
    path = get_user_cache_dir() / "torchinductor"
    if is_directory_writable(path):
        os.environ[name] = str(path)
        return path
    else:
        logger.warning(f"Cannot write to '{path}', not setting {name} "
                       f"(compiled PyTorch models are not cached "
                       f"persistently)")
        return None
