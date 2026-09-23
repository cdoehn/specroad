"""Closed language-policy-v1 values; defaults are explicit derived data only.

Loading/validation never updates saved configuration or requirement bytes.
The complete container-selection/mixing operation belongs to a later layer.
"""
from dataclasses import dataclass
from .canonical import canonical_json_bytes, canonical_json_sha256
from .errors import ModelError
from .language_tags import parse_language_tag, LanguageTagError
from ._language_package_parser import range_matches, LanguagePackageError
from ..storage.json_syntax import parse_json_object

POLICY_VERSION = "language-policy-v1"
ACTIONS = ("allow", "warning", "error")
COMPARISONS = ("primary_language", "exact_tag")


class LanguagePolicyError(ModelError):
    exit_code = 3


def default_language_policy():
    return {"version": POLICY_VERSION, "default_language": "de-DE", "allowed_ranges": ["*"],
            "disallowed_language": "error", "unverified_registry": "warning", "unspecified_language": "error",
            "mixed_languages": {"comparison": "primary_language", "project": "allow",
                                "document": "warning", "section": "warning"}}


def _fail(reason, at=""):
    raise LanguagePolicyError(reason, pointer=at)


def _closed(value, keys, at):
    if type(value) is not dict:
        _fail("language_policy_object_required", at)
    for key in value:
        if type(key) is not str:
            _fail("language_policy_string_key_required", at)
        if key not in keys:
            _fail("language_policy_unknown_field", at + "/" + key.replace("~", "~0").replace("/", "~1"))


def resolve_language_policy(value):
    """Materialize only omitted fields. Explicit null/empty/invalid is not omitted."""
    defaults = default_language_policy()
    _closed(value, defaults, "")
    # Copy trusted primitive data first: never invoke user-defined conversions.
    data = parse_json_object(canonical_json_bytes(value))
    result = {**defaults, **data}
    if type(result["version"]) is not str or result["version"] != POLICY_VERSION:
        _fail("language_policy_version", "/version")
    try:
        parse_language_tag(result["default_language"])
    except LanguageTagError as error:
        raise LanguagePolicyError("language_policy_default_tag", pointer="/default_language") from error
    ranges = result["allowed_ranges"]
    if type(ranges) is not list:
        _fail("language_policy_ranges_required", "/allowed_ranges")
    for i, item in enumerate(ranges):
        try:
            # Range grammar, NOT tag/registry grammar; empty allow-list is valid.
            range_matches(item, "en")
        except LanguagePackageError as error:
            raise LanguagePolicyError("language_policy_invalid_range", pointer="/allowed_ranges/" + str(i)) from error
    for field in ("disallowed_language", "unverified_registry", "unspecified_language"):
        if type(result[field]) is not str or result[field] not in ACTIONS:
            _fail("language_policy_action", "/" + field)
    mixed = result["mixed_languages"]
    _closed(mixed, defaults["mixed_languages"], "/mixed_languages")
    mixed = {**defaults["mixed_languages"], **mixed}
    if type(mixed["comparison"]) is not str or mixed["comparison"] not in COMPARISONS:
        _fail("language_policy_comparison", "/mixed_languages/comparison")
    for field in ("project", "document", "section"):
        if type(mixed[field]) is not str or mixed[field] not in ACTIONS:
            _fail("language_policy_action", "/mixed_languages/" + field)
    result["mixed_languages"] = mixed
    return result


@dataclass(frozen=True, init=False)
class LanguagePolicy:
    _encoded: bytes

    def __init__(self, value):
        object.__setattr__(self, "_encoded", canonical_json_bytes(resolve_language_policy(value)))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)


def language_policy_schema():
    defaults = default_language_policy()
    action = {"enum": list(ACTIONS)}
    properties = {"version": {"const": POLICY_VERSION, "default": POLICY_VERSION},
        "default_language": {"type": "string", "minLength": 1, "default": "de-DE"},
        "allowed_ranges": {"type": "array", "items": {"type": "string",
            "pattern": r"^(?:[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*|\*)(?![\s\S])"}, "default": ["*"]},
        "mixed_languages": {"type": "object", "additionalProperties": False,
            "properties": {"comparison": {"enum": list(COMPARISONS), "default": "primary_language"},
                **{k: {**action, "default": defaults["mixed_languages"][k]} for k in ("project", "document", "section")}},
            "default": defaults["mixed_languages"]}}
    for key in ("disallowed_language", "unverified_registry", "unspecified_language"):
        properties[key] = {**action, "default": defaults[key]}
    return {"type": "object", "properties": properties, "additionalProperties": False,
            "default": defaults}
