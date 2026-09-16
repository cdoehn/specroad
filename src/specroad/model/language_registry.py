"""Bound, immutable offline IANA snapshot and language-subtag assessments.

Registry knowledge is not an allowlist, linguistic validation, or a write gate.
No online sources, system locales, environment variables, or detector are used.
"""

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from types import MappingProxyType
import re

from .errors import ModelError
from .language_tags import LanguageTagError, VALIDATOR_VERSION, parse_language_tag


class LanguageRegistryError(ModelError):
    exit_code = 3


@dataclass(frozen=True)
class RegistryRecord:
    kind: str
    value: str
    fields: tuple

    def values(self, name):
        return tuple(value for key, value in self.fields if key == name)


@dataclass(frozen=True)
class LanguageAssessment:
    original: str
    canonical: str | None
    registry_state: str
    syntax_valid: bool
    reasons: tuple
    unknown_subtags: tuple
    deprecated: tuple
    preferred_values: tuple
    unspecified: bool
    registry_version: str
    registry_sha256: str
    validator_version: str = VALIDATOR_VERSION
    registration_scope: str = "language_subtags_only"
    linguistic_validation: bool = False

    def as_dict(self):
        return {"original": self.original, "canonical": self.canonical,
                "syntax_valid": self.syntax_valid, "registry_state": self.registry_state,
                "reasons": list(self.reasons), "unknown_subtags": list(self.unknown_subtags),
                "deprecated": list(self.deprecated),
                "preferred_values": [{"subtag": key, "value": value} for key, value in self.preferred_values],
                "unspecified": self.unspecified, "registry_id": "iana-language-subtags",
                "registry_version": self.registry_version, "registry_sha256": self.registry_sha256,
                "validator_version": self.validator_version, "registration_scope": self.registration_scope,
                "linguistic_validation": False}


def _registry_records(raw):
    if type(raw) is not bytes or raw.startswith(b"\xef\xbb\xbf"):
        raise LanguageRegistryError("invalid_registry_encoding")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as error:
        raise LanguageRegistryError("invalid_registry_encoding") from error
    if "\x00" in text or "\r" in text.replace("\r\n", ""):
        raise LanguageRegistryError("invalid_registry_encoding")
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[-1:] == [""]: lines.pop()
    if not lines or not re.fullmatch(r"File-Date: [0-9]{4}-[0-9]{2}-[0-9]{2}", lines[0]):
        raise LanguageRegistryError("invalid_registry_date")
    version = lines[0].split(": ", 1)[1]
    try:
        date.fromisoformat(version)
    except ValueError as error:
        raise LanguageRegistryError("invalid_registry_date") from error
    groups = []; current = []
    if len(lines) < 3 or lines[1] != "%%":
        raise LanguageRegistryError("invalid_registry_records")
    for line in lines[2:]:
        if line == "%%":
            if not current: raise LanguageRegistryError("empty_registry_record")
            groups.append(current); current = []
        elif line.startswith((" ", "\t")):
            if not current: raise LanguageRegistryError("orphan_registry_continuation")
            key, value = current[-1]; current[-1] = (key, value + " " + line.lstrip())
        else:
            match = re.fullmatch(r"([A-Za-z][A-Za-z0-9-]*): (.+)", line)
            if not match: raise LanguageRegistryError("invalid_registry_field")
            current.append(match.groups())
    if not current: raise LanguageRegistryError("empty_registry_record")
    groups.append(current)
    records = {}
    for group in groups:
        fields = {}
        for key, value in group: fields.setdefault(key, []).append(value)
        for key in ("Type", "Added"):
            if len(fields.get(key, ())) != 1: raise LanguageRegistryError("invalid_registry_record")
        if not fields.get("Description"): raise LanguageRegistryError("invalid_registry_record")
        kind = fields["Type"][0]
        if kind not in {"language", "extlang", "script", "region", "variant", "grandfathered", "redundant"}:
            raise LanguageRegistryError("unsupported_registry_record")
        field = "Tag" if kind in {"grandfathered", "redundant"} else "Subtag"
        if len(fields.get(field, ())) != 1 or ("Subtag" if field == "Tag" else "Tag") in fields:
            raise LanguageRegistryError("invalid_registry_record")
        for key in ("Added", "Deprecated"):
            if len(fields.get(key, ())) > 1: raise LanguageRegistryError("invalid_registry_record")
            for value in fields.get(key, ()):
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                    raise LanguageRegistryError("invalid_registry_date")
                try: date.fromisoformat(value)
                except ValueError as error: raise LanguageRegistryError("invalid_registry_date") from error
        for key in ("Preferred-Value", "Suppress-Script", "Scope", "Macrolanguage"):
            if len(fields.get(key, ())) > 1: raise LanguageRegistryError("invalid_registry_record")
        value = fields[field][0]
        if not value.isascii() or not re.fullmatch(r"[A-Za-z0-9-]+(?:\.\.[A-Za-z0-9]+)?", value):
            raise LanguageRegistryError("invalid_registry_subtag")
        grammar = {
            "language": r"[A-Za-z]{2,8}", "extlang": r"[A-Za-z]{3}",
            "script": r"[A-Za-z]{4}", "region": r"[A-Za-z]{2}|[0-9]{3}",
            "variant": r"[A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}",
        }
        if ".." not in value:
            if kind in grammar and not re.fullmatch(grammar[kind], value):
                raise LanguageRegistryError("invalid_registry_subtag")
            if kind in {"grandfathered", "redundant"}:
                try:
                    parsed = parse_language_tag(value)
                except LanguageTagError as error:
                    raise LanguageRegistryError("invalid_registry_tag") from error
                if parsed.grandfathered != (kind == "grandfathered"):
                    raise LanguageRegistryError("invalid_registry_tag_kind")
        elif (kind, value.lower()) not in {
            ("language", "qaa..qtz"), ("script", "qaaa..qabx"),
            ("region", "qm..qz"), ("region", "xa..xz"),
        }:
            raise LanguageRegistryError("invalid_registry_range")
        identity = kind, value.lower()
        if identity in records: raise LanguageRegistryError("duplicate_registry_record")
        if ".." in value:
            start, end = value.lower().split("..")
            if len(start) != len(end) or start > end or kind not in {"language", "script", "region"}:
                raise LanguageRegistryError("invalid_registry_range")
        records[identity] = RegistryRecord(kind, value, tuple(group))
    for (kind, token), record in records.items():
        if ".." in token:
            start, end = token.split("..")
            if any(k == kind and ".." not in v and len(v) == len(start) and start <= v <= end
                   for k, v in records):
                raise LanguageRegistryError("overlapping_registry_entries")
        if kind == "extlang" and (len(record.values("Prefix")) != 1
                                  or not re.fullmatch(r"[A-Za-z]{2,3}", record.values("Prefix")[0])):
            raise LanguageRegistryError("invalid_registry_prefix")
    return version, MappingProxyType(records)


@dataclass(frozen=True, init=False)
class LanguageRegistry:
    source_bytes: bytes
    version: str
    sha256: str
    _records: object

    def __init__(self, raw, *, expected_sha256, expected_version):
        if type(expected_sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
            raise LanguageRegistryError("invalid_registry_binding")
        if type(raw) is not bytes or sha256(raw).hexdigest() != expected_sha256:
            raise LanguageRegistryError("registry_hash_mismatch")
        version, records = _registry_records(raw)
        if version != expected_version:
            raise LanguageRegistryError("registry_version_mismatch")
        object.__setattr__(self, "source_bytes", raw)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "sha256", expected_sha256)
        object.__setattr__(self, "_records", records)

    @property
    def records(self):
        return tuple(self._records.values())

    def lookup(self, kind, value):
        """Exact or reserved-range lookup. No aliases are followed."""
        record = self._records.get((kind, value.lower()))
        if record is not None: return record
        for (record_kind, token), record in self._records.items():
            if record_kind == kind and ".." in token:
                start, end = token.split("..")
                if len(value) == len(start) and start <= value.lower() <= end: return record
        return None

    def inspect(self, value):
        """Classify one declaration without accepting it as permitted content."""
        try:
            tag = parse_language_tag(value)
        except LanguageTagError as error:
            return LanguageAssessment(value if type(value) is str else "", None, "invalid_syntax", False,
                                      (error.reason,), (), (), (), False, self.version, self.sha256)
        unknown = []; reasons = []; found = []; private = bool(tag.private_subtags)
        if tag.grandfathered:
            record = self.lookup("grandfathered", tag.canonical)
            if record is None: unknown.append(tag.canonical)
            else: found.append(record)
        elif tag.language:
            subtags = [("language", tag.language)]
            subtags += [("extlang", part) for part in tag.extlangs]
            if tag.script: subtags.append(("script", tag.script))
            if tag.region: subtags.append(("region", tag.region))
            subtags += [("variant", part) for part in tag.variants]
            for kind, part in subtags:
                record = self.lookup(kind, part)
                if record is None:
                    unknown.append(kind + ":" + part)
                else:
                    found.append(record)
                    private |= (".." in record.value or "private-use" in record.values("Scope")
                                or (kind == "script" and "qaaa" <= part.lower() <= "qabx")
                                or (kind == "region" and (part.upper() in {"AA", "ZZ"}
                                    or "QM" <= part.upper() <= "QZ" or "XA" <= part.upper() <= "XZ")))
                    if kind == "extlang" and tag.language not in tuple(p.lower() for p in record.values("Prefix")):
                        reasons.append("extlang_prefix_mismatch")
            if len(tag.extlangs) > 1: reasons.append("multiple_extlangs_unverified")
        # Extensions are preserved, not misrepresented as checked against this
        # subtag-only registry. Their separate registry/content rules are unbound.
        if tag.extensions: reasons.append("extension_registration_unverified")
        if unknown: reasons.insert(0, "unregistered_subtag")
        state = "unverified_registry" if unknown or reasons else "private_use" if private else "registered"
        deprecated = tuple(record.value for record in found if record.values("Deprecated"))
        preferred = tuple((record.value, val) for record in found for val in record.values("Preferred-Value"))
        return LanguageAssessment(tag.original, tag.canonical, state, True, tuple(reasons), tuple(unknown),
                                  deprecated, preferred, tag.unspecified, self.version, self.sha256)
