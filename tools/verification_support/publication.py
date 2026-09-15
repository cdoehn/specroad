"""Developer verification: publication responsibilities."""

import os
from pathlib import Path
import stat
from .common import CatalogError, json_bytes


def evidence_target(path, root):
    """Allow only an external path or ignored build output, without linked parents."""
    root = Path(root).resolve()
    target = Path(os.path.abspath(path))
    if target == root:
        raise CatalogError("Evidence cannot replace the input root")
    if root in target.parents and (target.relative_to(root).parts[0] != "build"
                                   or len(target.relative_to(root).parts) < 2):
        raise CatalogError("Evidence must not alter source inputs or repository metadata")
    if os.path.lexists(target):
        raise CatalogError("Existing evidence is never overwritten")
    for parent in target.parents:
        if os.path.lexists(parent) and not stat.S_ISDIR(parent.lstat().st_mode):
            raise CatalogError("Evidence output has a linked or non-directory parent")
    return target


def publish_report(path, root, report):
    target = evidence_target(path, root)
    data = json_bytes(report) + b"\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    evidence_target(target, root)
    with target.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
