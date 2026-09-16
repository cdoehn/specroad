"""Registry assessments; no linguistic, profile, or write-policy decisions."""

from .language_tags import LanguageTagError, parse_language_tag
from .language_values import LanguageAssessment


def assess_language_tag(registry, value):
    """Classify one declaration without accepting it as permitted content."""
    try:
        tag = parse_language_tag(value)
    except LanguageTagError as error:
        return LanguageAssessment(value if type(value) is str else "", None, "invalid_syntax", False,
                                  (error.reason,), (), (), (), False, registry.version, registry.sha256)
    unknown = []; reasons = []; found = []; private = bool(tag.private_subtags)
    if tag.grandfathered:
        record = registry.lookup("grandfathered", tag.canonical)
        if record is None: unknown.append(tag.canonical)
        else: found.append(record)
    elif tag.language:
        subtags = [("language", tag.language)]
        subtags += [("extlang", part) for part in tag.extlangs]
        if tag.script: subtags.append(("script", tag.script))
        if tag.region: subtags.append(("region", tag.region))
        subtags += [("variant", part) for part in tag.variants]
        for kind, part in subtags:
            record = registry.lookup(kind, part)
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
                              deprecated, preferred, tag.unspecified, registry.version, registry.sha256)
