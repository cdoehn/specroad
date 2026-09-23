"""Independent test oracle for the development distribution's byte identity.

Keep the expected resource inventory test-owned: importing the builder's
allowlist or hash function here would let the same omission validate itself.
These are shipped data files, not documentation or presentation snapshots.
"""
from hashlib import sha256
import json
from pathlib import Path


PROFILE_RESOURCES = (
    "profile_data/profiles.json",
    "profile_data/core.json",
    "profile_data/software-de.json",
    "profile_data/software-en.json",
)
LANGUAGE_RESOURCES = (
    "language_data/registry.txt",
    "language_data/snapshot.json",
    "language_data/packages.json",
    "language_data/minimum_corpus.json",
    "language_data/packages/de.json",
    "language_data/packages/en.json",
    "language_data/packages/hi.json",
    "language_data/packages/id.json",
    "language_data/packages/pt.json",
    "language_data/packages/es.json",
    "language_data/packages/ru.json",
    "language_data/packages/ja.json",
    "language_data/packages/zh-Hans.json",
)
SHIPPED_RESOURCES = PROFILE_RESOURCES + LANGUAGE_RESOURCES


def reference_payload(package: Path, launcher: bytes) -> dict[str, bytes]:
    """Expected source bytes, excluding generated records and cache entries.

    A missing required data file fails explicitly; it is not silently filtered
    out of the expected inventory. Absolute paths and filesystem times never
    enter the byte contract. Relative delivered names do.
    """
    package = Path(package)
    result = {}
    for path in package.rglob("*.py"):
        relative = path.relative_to(package)
        if "__pycache__" in relative.parts or relative.as_posix() == "_build.py":
            continue
        result["specroad/" + relative.as_posix()] = path.read_bytes()
    for relative in SHIPPED_RESOURCES:
        result["specroad/" + relative] = (package / relative).read_bytes()
    result["__main__.py"] = launcher
    return result


def reference_digest(payload: dict[str, bytes]) -> str:
    """Reproduce the published hash domain without the production implementation."""
    manifest = {name: sha256(data).hexdigest() for name, data in payload.items()}
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True).encode("utf-8")
    return sha256(b"specroad-dev-payload-v1\0" + canonical).hexdigest()
