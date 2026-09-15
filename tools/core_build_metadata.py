"""Pure build-record generation. Input Python modules remain inert bytes."""

import hashlib
import json
from pathlib import Path


def build_record_source(payload, archive_main):
    # Content identity excludes its derived record, timestamps and absolute paths.
    # Input modules are data: never import or execute the caller-supplied tree.
    manifest = {path.as_posix(): hashlib.sha256(data).hexdigest()
                for path, data in payload.items() if path != Path("specroad/_build.py")}
    manifest["__main__.py"] = hashlib.sha256(archive_main.encode("utf-8")).hexdigest()
    identity_bytes = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    record = {"format_version": 1, "hash_algorithm": "specroad-dev-payload-v1",
              "build_sha256": hashlib.sha256(b"specroad-dev-payload-v1\0" + identity_bytes).hexdigest()}
    return ("\"\"\"Generated development payload identity; not release evidence.\"\"\"\n"
                                           + "BUILD_METADATA = " + repr(record) + "\n").encode("utf-8")
