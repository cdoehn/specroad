"""Stable development-verification API; separate from product Evidence/Release.

Only trusted discovered tests execute. Catalogs and JSON evidence are data, not
code. Content digests bind current inputs but do not authenticate an author.
"""

from verification_support.catalog import Case, Catalog, load_catalog, validate_manifest
from verification_support.common import CatalogError, json_bytes, read_object, sha256
from verification_support.evidence import case_evidence, current_evidence_status, make_report, validate_binding
from verification_support.execution import ObservedResult, bind_tests, flatten_suite, observe_suite
from verification_support.identity import platform_identity, source_identity
from verification_support.publication import evidence_target, publish_report

__all__ = (
    "Case", "Catalog", "CatalogError", "ObservedResult", "bind_tests", "case_evidence",
    "current_evidence_status", "evidence_target", "flatten_suite", "json_bytes", "load_catalog",
    "make_report", "observe_suite", "platform_identity", "publish_report", "read_object",
    "sha256", "source_identity", "validate_binding", "validate_manifest",
)
