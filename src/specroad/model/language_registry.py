"""Immutable bound offline registry; storage, syntax, and policy stay separate."""

from dataclasses import dataclass
from hashlib import sha256
import re

from ._language_registry_parser import parse_registry_records
from .language_lookup import assess_language_tag
# Re-export public values for callers of the original registry API.
from .language_values import LanguageAssessment, LanguageRegistryError, RegistryRecord


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
        version, records = parse_registry_records(raw)
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
        return assess_language_tag(self, value)
