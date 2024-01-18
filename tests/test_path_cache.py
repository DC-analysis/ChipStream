import pathlib

from chipstream import path_cache


def test_path_cache_simple(tmp_path):
    cf = tmp_path / "cache.txt"
    pc = path_cache.PathCache(cf)
    assert cf.exists()
    path = pathlib.Path("foo/bar.txt")
    pc.add_path(path)
    pc.add_path("hans.txt")
    assert path in pc
    assert str(path) in cf.read_text()
    assert pc[0] == path
    assert len(pc) == 2


def test_path_cache_cleanup(tmp_path):
    cf = tmp_path / "cache.txt"
    path1 = tmp_path / "foo.txt"
    path2 = tmp_path / "bar.txt"
    path2.touch()
    pc = path_cache.PathCache(cf)
    pc.add_path(path1)
    pc.add_path(path2)
    assert len(pc) == 2
    assert str(path1) in cf.read_text()
    assert str(path2) in cf.read_text()
    pc.cleanup()
    assert len(pc) == 1
    assert str(path1) not in cf.read_text()
    assert str(path2) in cf.read_text()
