"""RFC 5646 structural parsing, without registry access or rewriting inputs.

Case normalization is a proposed spelling for a future planned write. It is not
Preferred-Value replacement, extension sorting, or Unicode normalization.
"""

from dataclasses import dataclass
import re

from .errors import ModelError

VALIDATOR_VERSION = "specroad-bcp47-v1"
# The RFC 5646 grammar defines this immutable set, independently of a snapshot.
_GRANDFATHERED = {tag.lower(): tag for tag in (
    "en-GB-oed", "i-ami", "i-bnn", "i-default", "i-enochian", "i-hak",
    "i-klingon", "i-lux", "i-mingo", "i-navajo", "i-pwn", "i-tao", "i-tay",
    "i-tsu", "sgn-BE-FR", "sgn-BE-NL", "sgn-CH-DE", "art-lojban", "cel-gaulish",
    "no-bok", "no-nyn", "zh-guoyu", "zh-hakka", "zh-min", "zh-min-nan", "zh-xiang",
)}


class LanguageTagError(ModelError):
    """A structural language-tag error; never downgraded by registry policy."""
    code = "SRV177"
    exit_code = 3


@dataclass(frozen=True)
class LanguageTag:
    original: str
    canonical: str
    language: str | None
    extlangs: tuple = ()
    script: str | None = None
    region: str | None = None
    variants: tuple = ()
    extensions: tuple = ()
    private_subtags: tuple = ()
    grandfathered: bool = False

    @property
    def unspecified(self):
        return self.language in {"und", "mul", "zxx"}


def parse_language_tag(value):
    """Parse a tag and reject malformed/duplicated structural components.

    No lookup occurs. Unknown 2..8-letter languages are valid syntactic input.
    Private-use subtags are deliberately opaque, including one-letter values.
    """
    if type(value) is not str or not value or not value.isascii():
        raise LanguageTagError("invalid_language_tag")
    lower = value.lower()
    if lower in _GRANDFATHERED:
        return LanguageTag(value, _GRANDFATHERED[lower], None, grandfathered=True)
    parts = lower.split("-")
    if any(not re.fullmatch(r"[a-z0-9]{1,8}", part) for part in parts):
        raise LanguageTagError("invalid_language_tag")
    if parts[0] == "x":
        if len(parts) == 1:
            raise LanguageTagError("private_subtag_required")
        return LanguageTag(value, lower, None, private_subtags=tuple(parts[1:]))
    primary = parts[0]
    if not re.fullmatch(r"[a-z]{2,8}", primary):
        raise LanguageTagError("primary_language_required")
    index = 1
    extlangs = []
    if len(primary) <= 3:
        while index < len(parts) and len(extlangs) < 3 and re.fullmatch(r"[a-z]{3}", parts[index]):
            extlangs.append(parts[index]); index += 1
    script = region = None
    if index < len(parts) and re.fullmatch(r"[a-z]{4}", parts[index]):
        script = parts[index].title(); index += 1
    if index < len(parts) and re.fullmatch(r"[a-z]{2}|[0-9]{3}", parts[index]):
        region = parts[index].upper(); index += 1
    variants = []
    while index < len(parts) and re.fullmatch(r"[a-z0-9]{5,8}|[0-9][a-z0-9]{3}", parts[index]):
        if parts[index] in variants:
            raise LanguageTagError("duplicate_variant")
        variants.append(parts[index]); index += 1
    extensions = []
    seen = set()
    while index < len(parts) and len(parts[index]) == 1 and parts[index] != "x":
        singleton = parts[index]; index += 1
        if singleton in seen:
            raise LanguageTagError("duplicate_extension")
        seen.add(singleton)
        values = []
        while index < len(parts) and len(parts[index]) >= 2:
            values.append(parts[index]); index += 1
        if not values:
            raise LanguageTagError("extension_subtag_required")
        extensions.append((singleton, tuple(values)))
    private = ()
    if index < len(parts) and parts[index] == "x":
        private = tuple(parts[index + 1:]); index = len(parts)
        if not private:
            raise LanguageTagError("private_subtag_required")
    if index != len(parts):
        raise LanguageTagError("invalid_subtag_order")
    normalized = [primary, *extlangs]
    if script: normalized.append(script)
    if region: normalized.append(region)
    normalized.extend(variants)
    for singleton, values in extensions: normalized.extend((singleton, *values))
    if private: normalized.extend(("x", *private))
    return LanguageTag(value, "-".join(normalized), primary, tuple(extlangs), script,
                       region, tuple(variants), tuple(extensions), private)
