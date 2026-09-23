"""Strict selectors and shared errors for passive literal-check inputs."""
from ..model.domain_fields import reference_schema
from ..model._schema import validate_builtin
from ..model.errors import ModelError
from ..model.language_tags import parse_language_tag
from ..srx.errors import SrxError
from ..srx.pointers import parse_pointer


class LiteralLintError(ModelError):
    """Invalid supplied data or selection, not a passed or empty lint result."""
    exit_code = 3



def _fail(reason, pointer=""):
    raise LiteralLintError(reason, pointer=pointer)



def _text(value, pointer):
    if type(value) is not str or not value.strip():
        _fail("literal_nonempty_text_required", pointer)



def _language(value):
    return parse_language_tag(value).canonical.lower()



def _pointer(value, at):
    try:
        tokens = parse_pointer(value, rule_id="literal-policy", at=at)
    except SrxError as error:
        raise LiteralLintError("literal_invalid_pointer", pointer=at) from error
    if not tokens:
        _fail("literal_field_pointer_required", at)
    return tokens



def _term_id(value, pointer):
    try:
        validate_builtin(value, reference_schema("TERM"))
    except ModelError as error:
        raise LiteralLintError("literal_invalid_term_id", pointer=pointer) from error

