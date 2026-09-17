"""Semantic configuration projection for model hashes, not policy composition.

Only explicitly classified presentation/operational values are excluded. No
recursive key stripping: strings in normative text or extensions remain data.
The future resolver supplies effective profile/CLI overrides before projection.
"""

from .configuration import ProjectConfiguration
from .errors import ModelError

SOFT_LIMITS = frozenset({
    "model_bytes", "relation_count", "diagnostic_count", "query_result_count",
    "srx_operations", "import_object_count", "merge_conflict_count",
})
SEMANTIC_LIMITS = frozenset({
    "artifact_file_bytes", "trace_depth", "query_default_limit", "xml_depth",
    "json_depth", "srx_depth", "archive_uncompressed_bytes", "srx_nodes",
})


def semantic_configuration(configuration):
    """Return owned semantic data; do not resolve profiles or read the host.

    Known normative defaults (pagination and SRX arithmetic) are materialized.
    Other policy values must be supplied by the effective configuration resolver;
    absence is retained rather than inventing an effective release policy.
    """
    if not isinstance(configuration, ProjectConfiguration):
        raise ModelError("project_configuration_required")
    value = configuration.data
    value.pop("default_locale", None)
    value.pop("generated_path", None)
    transaction = value.pop("transaction_policy", {})
    # auto_recover is operational. Receipt retention is an audit policy.
    value["transaction_policy"] = {"retain_receipts": transaction.get("retain_receipts", True)}
    limits = value.pop("resource_limits", {})
    unknown = limits.keys() - SOFT_LIMITS - SEMANTIC_LIMITS
    if unknown:
        raise ModelError("unclassified_resource_limit", pointer="/resource_limits/" + sorted(unknown)[0])
    value["resource_limits"] = {key: entry for key, entry in limits.items() if key in SEMANTIC_LIMITS}
    value["resource_limits"].setdefault("query_default_limit", 100)
    policy = value.setdefault("srx_policy", {})
    policy.setdefault("numeric_policy_version", "srx-decimal-v1")
    policy.setdefault("decimal_precision", 34)
    return value
