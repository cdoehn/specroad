"""Existing PRoot-safe portable source fixtures, kept out of the product."""

from pathlib import Path
import importlib.util
import os
import stat

ROOT = Path(__file__).resolve().parents[2]


def build_distribution(output, source=None):
    spec = importlib.util.spec_from_file_location("specroad_dev_build", ROOT / "tools/build_core.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder.build_core(source or ROOT / "src", output)


def copy_source_fixture(destination: Path, *, source_root: Path | None = None) -> Path:
    """Copy only package bytes; do not inherit host metadata or local src siblings.

    Inspect fresh lstat metadata, not cached DirEntry type hints. In a virtual
    filesystem these may disagree, for example for emulated hardlinks. Actual
    symlinks and special files are still rejected, never followed or ignored.
    Validate and read the package before creating any destination entries.
    """
    source_root = ROOT / "src" if source_root is None else Path(source_root)
    if not stat.S_ISDIR(source_root.lstat().st_mode):
        raise ValueError(f"Source fixture root is not a regular directory: {source_root!s}")
    package = source_root / "specroad"
    payload = {}
    directories = []

    def collect_directory(source: Path, relative: Path) -> None:
        if not stat.S_ISDIR(source.lstat().st_mode):
            raise ValueError(f"Source fixture directory is not regular: {source!s}")
        directories.append(relative)
        # Enumeration supplies names only. Every type decision uses fresh lstat.
        with os.scandir(source) as entries:
            names = sorted(entry.name for entry in entries)
        for name in names:
            source_path = source / name
            target_relative = relative / name
            mode = source_path.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ValueError(f"Unexpected symlink in source fixture: {source_path!s}")
            if stat.S_ISDIR(mode):
                if name != "__pycache__":
                    collect_directory(source_path, target_relative)
            elif stat.S_ISREG(mode):
                # Explicit reads, no copytree/copyfile/copystat or fast-copy path.
                with source_path.open("rb") as incoming:
                    payload[target_relative] = incoming.read()
            else:
                raise ValueError(f"Unexpected special source fixture entry: {source_path!s}")

    collect_directory(package, Path("specroad"))
    destination = Path(destination)
    destination.mkdir()  # Exclusive: an existing target is never overwritten.
    for relative in directories:
        (destination / relative).mkdir()
    for relative, data in payload.items():
        with (destination / relative).open("xb") as outgoing:
            outgoing.write(data)
    return destination


def files_under(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


