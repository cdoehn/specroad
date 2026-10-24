"""Shared input construction for explicit requirement content.

Callers own the JSON values before entering here. This layer resolves supplied
language/force fields, not native validation, text interpretation or a write.
New-draft authoring supplies its project default explicitly; exchange mapping
supplies complete mapped content and never supplies that default.
"""
from .errors import ModelError


REQUIREMENT_CONTENT_FIELDS = ("language", "normative_force", "statement")
_MISSING = object()


def _resolve(data, field, argument, default=_MISSING):
    """Reject conflicting supplied values; absence, null and empty are distinct."""
    if argument is not _MISSING:
        if field in data and (type(data[field]) is not type(argument) or data[field] != argument):
            raise ModelError("requirement_input_conflict", pointer="/" + field)
        data[field] = argument
        return "argument"
    if field in data:
        return "input"
    if default is not _MISSING:
        data[field] = default
        return "project_default"
    raise ModelError("missing_field", pointer="/" + field)


def _prepare_requirement_inputs(fields, *, language=_MISSING,
                                normative_force=_MISSING, default_language=_MISSING):
    """Construct fields and provenance without changing any supplied value.

    Canonicalizing a new draft's language and validating a complete native
    target remain the callers' existing, separate steps. Partial exchange
    projections must pass their missing-content loss gate before construction.
    """
    data = dict(fields)
    language_source = _resolve(data, "language", language, default_language)
    force_source = _resolve(data, "normative_force", normative_force)
    return data, language_source, force_source
