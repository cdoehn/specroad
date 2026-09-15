"""Project-independent version data. Reading it never scans a project or Git."""

import platform
import sys

from .. import _build
from .._metadata import DECLARED_CPYTHON_MINORS, MINIMUM_PYTHON, SUPPORTED_SCHEMA_VERSIONS, __version__


from .distribution import BuildMetadataError, distribution_identity


def version_info():
    """A fresh semantic result, independent of all presentation settings."""
    from ..cli.results import FORMAT_VERSION
    return {
        "version_info_format_version": "1.0.0",
        "program_version": __version__,
        **distribution_identity(_build.BUILD_METADATA, loader=__loader__),
        "runtime": {"implementation": sys.implementation.name,
                    "python_version": platform.python_version(),
                    "system": sys.platform, "machine": platform.machine()},
        "python_support": {"minimum_minor": ".".join(map(str, MINIMUM_PYTHON)),
                           "declared_minors": list(DECLARED_CPYTHON_MINORS),
                           "maximum_declared_minor": DECLARED_CPYTHON_MINORS[-1],
                           "tested_minors": [], "maximum_tested_minor": None,
                           "fully_verified_minors": [], "verification_status": "unrecorded", "evidence_refs": []},
        "supported_schema_versions": list(SUPPORTED_SCHEMA_VERSIONS),
        "supported_output_format_versions": {"json": [FORMAT_VERSION], "sarif": ["2.1.0"]},
    }
