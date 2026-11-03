"""Bounded ZIP hints for discovery; only native PatchHarbor Core validates.

Hints neither extract ZIP contents nor certify identity, validity or freshness.
"""
from pathlib import Path
import stat
import zipfile
from .local import decode_object

# A result manifest records one entry per tracked file. A 64 KiB cap drops
# otherwise valid results from normal-size SpecRoad repositories. Bounded at
# 32 MiB for cheap discovery; the native PatchHarbor Core still decides trust.
MAX_RESULT_HINT_BYTES = 32 * 1024 * 1024
MAX_PATCH_HINT_BYTES = 64 * 1024


def signature(path: Path):
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_size > 256 * 1024 * 1024:
        raise ValueError
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def hint(path: Path) -> dict | None:
    # This never executes/extracts content, and is NEVER a validity proof.
    try:
        signature(path)
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > 100000:
                return None
            for name, kind in (("manifest.json", "result"), ("patch.json", "patch")):
                members = [item for item in entries if item.filename == name]
                limit = MAX_RESULT_HINT_BYTES if kind == "result" else MAX_PATCH_HINT_BYTES
                if len(members) != 1 or not 0 < members[0].file_size <= limit:
                    continue
                # Never decompress more than the discovery budget. This is a
                # hint only; full ZIP/manifest validity is checked by Core.
                with archive.open(members[0], "r") as stream:
                    payload = stream.read(limit + 1)
                if len(payload) != members[0].file_size:
                    continue
                value = decode_object(payload)
                expected = "patch-harbor-result-bundle" if kind == "result" else "patch-harbor"
                if value.get("marker") == expected:
                    return {"kind": kind, "path": str(path), "manifest": value}
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile, RuntimeError, RecursionError, NotImplementedError, OverflowError):
        pass
    return None
