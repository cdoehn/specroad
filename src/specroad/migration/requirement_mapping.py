"""Authored requirement decisions, separate from structural schema additions.

These helpers neither infer a decision nor establish review/write authority.
The closed normalized input schema and real source hashes remain mandatory.
"""
from ..model.language_tags import parse_language_tag

AUTHORED_FIELDS = ('language', 'normative_force', 'statement')


def materialize_language_default(rows, default):
    """Fill only absent languages in already owned rows with an explicit value."""
    if default is not None:
        parse_language_tag(default)
        for row in rows:
            if 'language' not in row:
                row['language'] = default


def validate_mapping_languages(rows):
    """Syntax checking also applies when unrelated planning inputs are missing."""
    for row in rows:
        parse_language_tag(row['language'])


def authored_fields(mapping):
    """Project only the decisions bound by the requirement's checked mapping."""
    return {key: mapping[key] for key in AUTHORED_FIELDS}
