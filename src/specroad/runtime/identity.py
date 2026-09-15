"""Project-independent version data. Reading it never scans a project or Git."""

import platform
import re
import sys
import zipimport

from .. import _build
from .._metadata import DECLARED_CPYTHON_MINORS, MINIMUM_PYTHON, SUPPORTED_SCHEMA_VERSIONS, __version__


class BuildMetadataError(ValueError):
    """The trusted distribution contains an unusable build record."""


def version_info():
    from ..cli.results import FORMAT_VERSION
    record = _build.BUILD_METADATA
    build_hash = None
    build_id = None
    algorithm = None
    if record is not None:
        if not isinstance(record, dict) or record.get("format_version") != 1:
            raise BuildMetadataError("Invalid distribution metadata")
        build_hash = record.get("build_sha256")
        if not isinstance(build_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", build_hash):
            raise BuildMetadataError("Invalid distribution hash")
        algorithm = record.get("hash_algorithm")
        if algorithm != "specroad-dev-payload-v1":
            raise BuildMetadataError("Unknown distribution identity algorithm")
        build_id = "dev-" + build_hash[:12]
    return {
        "version_info_format_version": "1.0.0",
        "program_version": __version__,
        "build_id": build_id,
        "build_sha256": build_hash,
        "build_hash_algorithm": algorithm,
        "build_identity_status": "unrecorded" if record is None else "recorded",
        "distribution_kind": "zipapp" if isinstance(__loader__, zipimport.zipimporter) else "module",
        "runtime": {"implementation": sys.implementation.name,
                    "python_version": platform.python_version(),
                    "system": sys.platform, "machine": platform.machine()},
        "python_support": {"minimum_minor": ".".join(map(str, MINIMUM_PYTHON)),
                           "declared_minors": list(DECLARED_CPYTHON_MINORS),
                           "tested_minors": [], "maximum_tested_minor": None,
                           "fully_verified_minors": [], "verification_status": "unrecorded"},
        "supported_schema_versions": list(SUPPORTED_SCHEMA_VERSIONS),
        "supported_output_format_versions": {"json": [FORMAT_VERSION], "sarif": ["2.1.0"]},
    }
