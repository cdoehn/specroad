"""Owned temporary fixtures and non-following observation of filesystem effects."""

from contextlib import contextmanager
from pathlib import Path, PurePosixPath
import os
import stat
import tempfile


def _fixture_path(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\0" in name:
        raise ValueError("Invalid fixture path")
    if any(part in ("", ".", "..") for part in name.split("/")):
        raise ValueError("Fixture path must be strictly relative")
    path = PurePosixPath(name)
    if path.is_absolute():
        raise ValueError("Fixture path must be relative")
    return path


@contextmanager
def temporary_project(files=None, *, parent=None):
    """Private byte fixture, not a claim to implement the future init command."""
    files = {"specroad.json": b"{}\n"} if files is None else dict(files)
    checked = []
    for name, data in files.items():
        relative = _fixture_path(name)
        if type(data) is not bytes:
            raise TypeError("Fixture contents must be bytes")
        checked.append((relative, data))
    paths = {str(relative).casefold() for relative, _ in checked}
    if len(paths) != len(checked):
        raise ValueError("Case-colliding fixture paths")
    for relative, _ in checked:
        if any(str(ancestor).casefold() in paths for ancestor in relative.parents if str(ancestor) != "."):
            raise ValueError("Fixture file is also a directory")
    with tempfile.TemporaryDirectory(prefix="specroad-test-", dir=parent) as directory:
        root = Path(directory)
        for relative, data in checked:
            target = root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
        yield root


def tree_state(root):
    """Observe file effects, including empty directories and links, without following links."""
    root = Path(root)
    result = {}

    def visit(directory):
        with os.scandir(directory) as entries:
            names = sorted(entry.name for entry in entries)
        for name in names:
            path = directory / name
            relative = path.relative_to(root).as_posix()
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                result[relative] = ("symlink", os.readlink(path))
            elif stat.S_ISDIR(mode):
                result[relative] = ("directory", None)
                visit(path)
            elif stat.S_ISREG(mode):
                result[relative] = ("file", path.read_bytes())
            else:
                raise ValueError("Special entry in test fixture")
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise ValueError("Fixture root must be a real directory")
    visit(root)
    return result


