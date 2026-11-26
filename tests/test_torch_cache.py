import logging
import os
import pathlib
import sys

import pytest

from chipstream import torch_cache


ENV_NAME = "TORCHINDUCTOR_CACHE_DIR"


def test_setup_sets_writable_directory(monkeypatch, tmp_path):
    monkeypatch.delenv(ENV_NAME, raising=False)
    cache = tmp_path / "user" / "cache"
    monkeypatch.setattr(torch_cache, "get_user_cache_dir", lambda: cache)
    path = torch_cache.setup_torch_inductor_cache_dir()
    assert path == cache / "torchinductor"
    assert path.is_dir()
    assert os.environ[ENV_NAME] == str(path)
    # the write test file is removed again
    assert not list(path.iterdir())


def test_setup_keeps_existing_variable(monkeypatch, tmp_path):
    monkeypatch.setenv(ENV_NAME, str(tmp_path / "user-defined"))
    monkeypatch.setattr(torch_cache, "get_user_cache_dir",
                        lambda: tmp_path / "cache")
    path = torch_cache.setup_torch_inductor_cache_dir()
    assert path == tmp_path / "user-defined"
    assert os.environ[ENV_NAME] == str(tmp_path / "user-defined")
    assert not (tmp_path / "cache").exists()


def test_setup_unwritable_directory(monkeypatch, tmp_path, caplog):
    monkeypatch.delenv(ENV_NAME, raising=False)
    monkeypatch.setattr(torch_cache, "get_user_cache_dir",
                        lambda: tmp_path / "cache")
    monkeypatch.setattr(torch_cache, "is_directory_writable",
                        lambda path: False)
    with caplog.at_level(logging.WARNING, logger="chipstream.torch_cache"):
        path = torch_cache.setup_torch_inductor_cache_dir()
    assert path is None
    assert ENV_NAME not in os.environ
    assert "Cannot write to" in caplog.text


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0,
                    reason="read-only permissions only work on POSIX "
                           "for non-root users")
def test_is_directory_writable(tmp_path):
    assert torch_cache.is_directory_writable(tmp_path / "a" / "b")
    read_only = tmp_path / "read-only"
    read_only.mkdir()
    read_only.chmod(0o555)
    try:
        assert not torch_cache.is_directory_writable(read_only)
        assert not torch_cache.is_directory_writable(read_only / "sub")
    finally:
        read_only.chmod(0o755)


def test_is_directory_writable_file(tmp_path):
    path = tmp_path / "file"
    path.touch()
    assert not torch_cache.is_directory_writable(path)


@pytest.mark.parametrize("platform,env,expected", [
    ("win32", {"LOCALAPPDATA": "C:/Users/me/AppData/Local"},
     "C:/Users/me/AppData/Local/DC-Analysis/ChipStream/cache"),
    ("linux", {"XDG_CACHE_HOME": "/xdg/cache"},
     "/xdg/cache/DC-Analysis/ChipStream"),
    ("linux", {}, "~/.cache/DC-Analysis/ChipStream"),
    ("darwin", {}, "~/Library/Caches/DC-Analysis/ChipStream"),
])
def test_get_user_cache_dir(monkeypatch, platform, env, expected):
    monkeypatch.setattr(sys, "platform", platform)
    for key in ["LOCALAPPDATA", "XDG_CACHE_HOME"]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    expected = pathlib.Path(expected.replace("~", str(pathlib.Path.home())))
    assert torch_cache.get_user_cache_dir() == expected
