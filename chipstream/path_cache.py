import pathlib


class PathCache:
    def __init__(self, cache_path):
        """Cache paths in a text file"""
        self.cache_path = cache_path
        self.cache_path.touch()
        cached = self.cache_path.read_text().split("\n")
        self.paths = [pathlib.Path(pp) for pp in cached if pp.strip()]

    def __getitem__(self, item):
        return self.paths[item]

    def __iter__(self):
        return iter(self.paths)

    def __len__(self):
        return len(self.paths)

    def add_path(self, path):
        """Add a path to the cache"""
        self.paths.append(path)
        with self.cache_path.open("a") as fp:
            fp.write(f"{path}\n")

    def cleanup(self):
        """Remove non-existent paths from the cache"""
        self.cache_path.unlink(missing_ok=True)
        temp_paths = self.paths[:]
        self.paths.clear()
        for path in temp_paths:
            if path.exists():
                self.add_path(path)
