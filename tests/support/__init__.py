"""Test-only deterministic fixtures. Not installed in the SpecRoad Core."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
import hashlib
import os
import stat
import subprocess
import sys
import tempfile

SOURCE = Path(__file__).resolve().parents[2] / "src"


class ManualClock:
    """Explicitly injected clock; never patches real time or sleeps."""

    def __init__(self, start=None):
        self._start = datetime(2020, 1, 1, tzinfo=timezone.utc) if start is None else start
        if not isinstance(self._start, datetime) or self._start.utcoffset() is None:
            raise ValueError("An aware datetime is required")
        self._elapsed = 0

    def monotonic_ns(self):
        return self._elapsed

    def utc_now(self):
        return self._start.astimezone(timezone.utc) + timedelta(microseconds=self._elapsed // 1000)

    def advance(self, nanoseconds):
        if type(nanoseconds) is not int or nanoseconds < 0:
            raise ValueError("Clock movement must be a non-negative integer")
        candidate = self._elapsed + nanoseconds
        # Reject overflow before changing the observable clock state.
        self._start.astimezone(timezone.utc) + timedelta(microseconds=candidate // 1000)
        self._elapsed = candidate


class ByteSequence:
    """Finite injected entropy, deliberately unsuitable for production IDs."""

    def __init__(self, chunks):
        self._chunks = tuple(chunks)
        if any(type(chunk) is not bytes for chunk in self._chunks):
            raise TypeError("Entropy fixtures require bytes")
        self._position = 0

    def __call__(self, count):
        if type(count) is not int or count <= 0:
            raise ValueError("Entropy request must be a positive integer")
        if self._position >= len(self._chunks):
            raise RuntimeError("Entropy fixture exhausted")
        chunk = self._chunks[self._position]
        if len(chunk) != count:
            raise ValueError("Unexpected entropy request size")
        self._position += 1
        return chunk


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


def run_python(arguments, cwd, *, python=None, capture=False):
    """Run trusted Python with closed stdin and no shell or harness timeout."""
    environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR")
                   if key in os.environ}
    environment["PATH"] = ""
    return subprocess.run(
        [str(python or sys.executable), *arguments], cwd=cwd, env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )


def run_core(body, cwd, *, python=None, expose_cwd=False, capture=False):
    prefix = "import sys;sys.path.insert(0," + repr(str(SOURCE)) + ");\n"
    if expose_cwd:
        prefix += "sys.path.append(" + repr(str(cwd)) + ");\n"
    return run_python(["-I", "-S", "-B", "-c", prefix + body], cwd,
                      python=python, capture=capture)


def run_cli(arguments, cwd, *, capture=False):
    body = "from specroad.cli import main;sys.exit(main(" + repr(list(arguments)) + "))"
    return run_core(body, cwd, capture=capture)
