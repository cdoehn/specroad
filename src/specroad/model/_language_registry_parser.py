"""Strict parsing of the frozen RFC 5646 registry resource, without I/O."""

from datetime import date
from types import MappingProxyType
import re

from .language_tags import LanguageTagError, parse_language_tag
from .language_values import LanguageRegistryError, RegistryRecord


def parse_registry_records(raw):
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


