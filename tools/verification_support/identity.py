"""Developer verification: identity responsibilities."""

import os
from pathlib import Path
import platform
import stat
import sys
from .common import CatalogError, json_bytes, sha256


def source_identity(root):
    """Hash verification inputs, including progress that controls resource gates."""
    root = Path(root)
    entries = {}
    def visit(path):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            entries[path.relative_to(root).as_posix()] = sha256(path.read_bytes())
        elif stat.S_ISDIR(mode):
            with os.scandir(path) as scan:
                names = sorted(entry.name for entry in scan)
            for name in names:
                if name == "__pycache__" or name.endswith((".pyc", ".pyo", ".egg-info")):
                    continue
                visit(path / name)
        else:
            raise CatalogError("Linked or special source input")
    # Limit the source tree to the package, not local editable-install siblings.
    for relative in ("src/specroad", "tests", "tools", "verification", "pyproject.toml"):
        visit(root / relative)
    # Public review code, module data and evidence are also test inputs.
    if os.path.lexists(root / "reviews"):
        visit(root / "reviews")
    # The pytest bootstrap participates in the current test-input identity.
    # Small legacy fixtures without it remain valid input trees.
    if os.path.lexists(root / "conftest.py"):
        visit(root / "conftest.py")
    # The final resource obligation reads this machine progress. Bind it like
    # other executable-policy inputs; unrelated documentation remains excluded.
    if os.path.lexists(root / "verification/resource_measurement_policy.json"):
        visit(root / "docs/implementation/SpecRoad_Implementierungsplan.md")
    return sha256(json_bytes(entries))


def platform_identity():
    return {"implementation": sys.implementation.name, "python": platform.python_version(),
            "system": platform.system(), "machine": platform.machine()}


