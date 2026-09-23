"""Closed project configuration and the initial shared path contract.

Policy values remain declarations: loading never executes an adapter or resolves
an online registry. The specific policy engines belong to later plan steps.
"""

from dataclasses import dataclass
from datetime import date
import json
import math
import re

from ..security import SafetyViolation, check_project_declarations
from .errors import ModelError
from .numbers import number_from_token
from .metadata import validate_extensions
from .paths import PathClass, artifact_path, classify_path, project_path, _under

from .versions import SCHEMA_VERSION
REQUIRED_FIELDS = frozenset({
    "schema_version", "project_id", "project_name", "id_prefix", "default_locale",
    "managed_paths", "profiles", "generated_path", "validation_policy",
})
OPTIONAL_FIELDS = frozenset({
    "transaction_policy", "resource_limits", "language_policy", "language_packages",
    "analyzer_policy", "srx_policy", "language_registry", "extensions",
})


def _json_values(value, pointer=""):
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        try:
            number_from_token(str(value), pointer=pointer)
        except ValueError as error:
            if isinstance(error, ModelError):
                raise
            raise ModelError("unsupported_number", pointer=pointer) from error
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ModelError("nonfinite_number", pointer=pointer)
        return
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeError as error:
            raise ModelError("invalid_unicode", pointer=pointer) from error
        return
    if type(value) is list:
        for index, item in enumerate(value):
            _json_values(item, pointer + "/" + str(index))
        return
    if type(value) is dict:
        for key, item in value.items():
            if not isinstance(key, str):
                raise ModelError("nonstring_key", pointer=pointer)
            _json_values(key, pointer)
            _json_values(item, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
        return
    raise ModelError("non_json_value", pointer=pointer)


def _text(value, pointer):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ModelError("invalid_text", pointer=pointer)



def _closed_object(value, allowed, pointer):
    extra = value.keys() - set(allowed)
    if extra:
        raise ModelError("unknown_field", pointer=pointer + "/" + sorted(extra)[0])


def _policy_shapes(data):
    validation = data["validation_policy"]
    _closed_object(validation, ("fail_on", "minimum_human_proposal_approvals", "required_relation_review"), "/validation_policy")
    if "fail_on" in validation and validation["fail_on"] not in ("info", "warning", "error"):
        raise ModelError("invalid_policy_value", pointer="/validation_policy/fail_on")
    approvals = validation.get("minimum_human_proposal_approvals", 1)
    if type(approvals) is not int or approvals < 1:
        raise ModelError("invalid_policy_value", pointer="/validation_policy/minimum_human_proposal_approvals")
    if "required_relation_review" in validation and validation["required_relation_review"] != "current":
        raise ModelError("invalid_policy_value", pointer="/validation_policy/required_relation_review")
    transaction = data.get("transaction_policy", {})
    _closed_object(transaction, ("auto_recover", "retain_receipts"), "/transaction_policy")
    if any(type(value) is not bool for value in transaction.values()):
        raise ModelError("invalid_policy_value", pointer="/transaction_policy")
    # Retention has a normative audit role; a declaration cannot disable it.
    if transaction.get("retain_receipts", True) is not True:
        raise ModelError("receipt_retention_required", pointer="/transaction_policy/retain_receipts")
    precision = data.get("srx_policy", {})
    _closed_object(precision, ("numeric_policy_version", "decimal_precision"), "/srx_policy")
    if precision.get("numeric_policy_version", "srx-decimal-v1") != "srx-decimal-v1":
        raise ModelError("invalid_policy_value", pointer="/srx_policy/numeric_policy_version")
    digits = precision.get("decimal_precision", 34)
    if type(digits) is not int or not 1 <= digits <= 1000:
        raise ModelError("invalid_policy_value", pointer="/srx_policy/decimal_precision")
    if "language_policy" in data:
        from .language_policy import resolve_language_policy, LanguagePolicyError
        try:
            resolve_language_policy(data["language_policy"])
        except ModelError as error:
            raise LanguagePolicyError(error.reason, pointer="/language_policy" + error.pointer) from error
    for key, value in data.get("resource_limits", {}).items():
        if type(value) is not int or value < 0:
            raise ModelError("invalid_policy_value", pointer="/resource_limits/" + key)
    from ._language_package_parser import parse_package_key
    for value in data.get("language_packages", ()):
        parse_package_key(value)
    for field in ("profiles", "language_packages"):
        for value in data.get(field, ()):
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*@[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?(?:\+[A-Za-z0-9.-]+)?", value):
                raise ModelError("unversioned_resource", pointer="/" + field)


def validate_configuration(data):
    if type(data) is not dict:
        raise ModelError("object_required")
    _json_values(data)
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise ModelError("missing_field", pointer="/" + sorted(missing)[0])
    unknown = data.keys() - REQUIRED_FIELDS - OPTIONAL_FIELDS
    if unknown:
        raise ModelError("unknown_field", pointer="/" + sorted(unknown)[0])
    if data["schema_version"] != SCHEMA_VERSION:
        raise ModelError("unsupported_schema_version", pointer="/schema_version", highest_supported=SCHEMA_VERSION)
    for field in ("project_id", "project_name", "default_locale"):
        _text(data[field], "/" + field)
    if not isinstance(data["id_prefix"], str) or not re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", data["id_prefix"]):
        raise ModelError("invalid_id_prefix", pointer="/id_prefix")
    for field in ("profiles", "managed_paths", "language_packages"):
        if field not in data:
            continue
        if type(data[field]) is not list:
            raise ModelError("array_required", pointer="/" + field)
        for index, value in enumerate(data[field]):
            _text(value, "/" + field + "/" + str(index))
        if len(set(data[field])) != len(data[field]):
            raise ModelError("duplicate_value", pointer="/" + field)
    for field in ("validation_policy", "transaction_policy", "resource_limits", "language_policy",
                  "analyzer_policy", "srx_policy", "language_registry", "extensions"):
        if field in data and type(data[field]) is not dict:
            raise ModelError("object_required", pointer="/" + field)
    _policy_shapes(data)
    generated = project_path(data["generated_path"])
    roots = [project_path(path) for path in data["managed_paths"]]
    protected = ("specroad.json", "spec", "profiles", "rules", "mappings", "attachments", "archive", ".specroad")
    if any(_under(generated.casefold(), path) or _under(path, generated.casefold()) for path in protected):
        raise ModelError("overlapping_path_classes", pointer="/generated_path")
    for path in roots:
        folded = path.casefold()
        if (_under(folded, ".specroad") or _under(folded, "specroad.json")
                or _under(folded, generated.casefold()) or _under(generated.casefold(), folded)):
            raise ModelError("overlapping_path_classes", pointer="/managed_paths")
    if len({path.casefold() for path in roots}) != len(roots):
        raise ModelError("duplicate_path", pointer="/managed_paths")
    registry = data.get("language_registry")
    if registry is not None:
        fields = {"registry_id", "registry_version", "path", "sha256"}
        if set(registry) != fields or registry["registry_id"] != "iana-language-subtags":
            raise ModelError("invalid_registry_binding", pointer="/language_registry")
        if not isinstance(registry["registry_version"], str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", registry["registry_version"]):
            raise ModelError("invalid_registry_binding", pointer="/language_registry/registry_version")
        try:
            date.fromisoformat(registry["registry_version"])
        except ValueError as error:
            raise ModelError("invalid_registry_binding", pointer="/language_registry/registry_version") from error
        if not isinstance(registry["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", registry["sha256"]):
            raise ModelError("invalid_registry_binding", pointer="/language_registry/sha256")
        reference = project_path(registry["path"])
        if not reference.startswith("profiles/language-data/") or not any(_under(reference, path) for path in roots):
            raise ModelError("invalid_registry_binding", pointer="/language_registry/path")
    if "extensions" in data:
        validate_extensions(data["extensions"])
    try:
        check_project_declarations(data)
    except SafetyViolation as error:
        raise ModelError("unsafe_project_declaration") from error
    from .configuration_schema import configuration_json_schema
    from ._schema import validate_builtin
    validate_builtin(data, configuration_json_schema())


@dataclass(frozen=True, init=False)
class ProjectConfiguration:
    """Owned immutable bytes; each data access returns an independent value tree."""
    _encoded: bytes

    def __init__(self, value):
        try:
            validate_configuration(value)
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        except RecursionError as error:
            raise ModelError("nesting_not_supported") from error
        object.__setattr__(self, "_encoded", encoded)

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def id_prefix(self):
        return self.data["id_prefix"]

    @property
    def project_id(self):
        return self.data["project_id"]

    @property
    def managed_paths(self):
        return tuple(self.data["managed_paths"])

    @property
    def generated_path(self):
        return self.data["generated_path"]
