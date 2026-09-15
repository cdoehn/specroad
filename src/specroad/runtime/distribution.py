"""Validation and projection of a trusted, generated distribution record."""

import re
import zipimport


class BuildMetadataError(ValueError):
    """The trusted distribution contains an unusable build record."""


def distribution_identity(record, *, loader):
    build_hash = None
    build_id = None
    algorithm = None
    if record is not None:
        if (type(record) is not dict
                or set(record) != {"format_version", "hash_algorithm", "build_sha256"}
                or type(record.get("format_version")) is not int or record["format_version"] != 1):
            raise BuildMetadataError("Invalid distribution metadata")
        build_hash = record.get("build_sha256")
        if not isinstance(build_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", build_hash):
            raise BuildMetadataError("Invalid distribution hash")
        algorithm = record.get("hash_algorithm")
        if algorithm != "specroad-dev-payload-v1":
            raise BuildMetadataError("Unknown distribution identity algorithm")
        build_id = "dev-" + build_hash[:12]
    return {
        "build_id": build_id,
        "build_sha256": build_hash,
        "build_hash_algorithm": algorithm,
        "build_hash_scope": "core-python-payload-excluding-generated-record" if record is not None else None,
        "release_approved": False,
        "build_identity_status": "unrecorded" if record is None else "recorded",
        "distribution_kind": "zipapp" if isinstance(loader, zipimport.zipimporter) else "module",
    }
