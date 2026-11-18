"""Strict parsing of the frozen RFC 5646 registry resource, without I/O."""

from collections.abc import Mapping
from copy import deepcopy
from datetime import date
from functools import lru_cache
from types import MappingProxyType
import re

from .language_tags import LanguageTagError, parse_language_tag
from .language_values import LanguageRegistryError, RegistryRecord


_HEADER = re.compile(r"File-Date: [0-9]{4}-[0-9]{2}-[0-9]{2}")
_FIELD = re.compile(r"([A-Za-z][A-Za-z0-9-]*): (.+)")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_SUBTAG = re.compile(r"[A-Za-z0-9-]+(?:\.\.[A-Za-z0-9]+)?")
_PREFIX = re.compile(r"[A-Za-z]{2,3}")
_GRAMMAR = MappingProxyType({
    kind: re.compile(pattern) for kind, pattern in {
        "language": r"[A-Za-z]{2,8}", "extlang": r"[A-Za-z]{3}",
        "script": r"[A-Za-z]{4}", "region": r"[A-Za-z]{2}|[0-9]{3}",
        "variant": r"[A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}",
    }.items()
})
_MAX_CACHED_BYTES = 1024 * 1024


def parse_registry_records(raw):
    """Reuse pure byte parsing, but never share public record instances.

    Keys are complete bytes, not paths or claimed hashes. Only successful
    parses of at most one MiB enter the four-entry cache. Binding checks
    remain in LanguageRegistry and run for every construction.
    """
    if type(raw) is not bytes or len(raw) > _MAX_CACHED_BYTES:
        version, records = _parse_registry_records(raw)
        return version, _fresh_records(_record_values(records))
    version, values = _cached_registry_values(raw)
    return version, _fresh_records(values)


class _RegistryRecords(Mapping):
    """Instance-owned public records over private immutable parser values."""
    def __init__(self, values):
        self._values = values
        self._materialized = {}

    def __getitem__(self, identity):
        if identity not in self._materialized:
            record = RegistryRecord(*self._values[0][identity])
            self._materialized.setdefault(identity, record)
        return self._materialized[identity]

    def __iter__(self):
        return iter(self._values[0])

    def __len__(self):
        return len(self._values[0])

    def range_keys(self):
        return self._values[1]

    def __deepcopy__(self, memo):
        # Only immutable private strings/tuples are shared. Even records that
        # a caller mutated with object.__setattr__ stay local to their copy.
        result = type(self)(self._values)
        memo[id(self)] = result
        result._materialized = deepcopy(self._materialized, memo)
        return result


def _record_values(records):
    return (MappingProxyType({identity: (record.kind, record.value, record.fields)
                              for identity, record in records.items()}),
            tuple(identity for identity in records if '..' in identity[1]))


def _fresh_records(values):
    return _RegistryRecords(values)


@lru_cache(maxsize=4)
def _cached_registry_values(raw):
    version, records = _parse_registry_records(raw)
    # Frozen dataclasses can still be modified with object.__setattr__.
    # Retain only private strings/tuples, never any exported Record object.
    return version, _record_values(records)


def _parse_registry_records(raw):
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
    if not lines or not _HEADER.fullmatch(lines[0]):
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
            match = _FIELD.fullmatch(line)
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
                if not _DATE.fullmatch(value):
                    raise LanguageRegistryError("invalid_registry_date")
                try: date.fromisoformat(value)
                except ValueError as error: raise LanguageRegistryError("invalid_registry_date") from error
        for key in ("Preferred-Value", "Suppress-Script", "Scope", "Macrolanguage"):
            if len(fields.get(key, ())) > 1: raise LanguageRegistryError("invalid_registry_record")
        value = fields[field][0]
        if not value.isascii() or not _SUBTAG.fullmatch(value):
            raise LanguageRegistryError("invalid_registry_subtag")
        if ".." not in value:
            if kind in _GRAMMAR and not _GRAMMAR[kind].fullmatch(value):
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
                                  or not _PREFIX.fullmatch(record.values("Prefix")[0])):
            raise LanguageRegistryError("invalid_registry_prefix")
    return version, MappingProxyType(records)


