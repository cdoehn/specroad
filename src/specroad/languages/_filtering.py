"""Declared-tag filter and comparison rules; no severity, files, or detection."""
from ..model.language_packages import range_matches


def matching_ranges(ranges, language):
    return [item for item in ranges if range_matches(item, language)]


def comparison_key(assessment, comparison):
    if assessment.unspecified:
        return None
    canonical = assessment.canonical.lower()
    if comparison == "exact_tag" or assessment.registry_state in ("private_use", "unverified_registry"):
        return canonical
    return canonical.split("-", 1)[0]
