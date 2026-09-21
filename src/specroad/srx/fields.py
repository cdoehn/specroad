"""Named SRX field access; pointer parsing/traversal lives in one pure module."""

from .errors import SrxError
from ._json_values import json_type
from .pointers import parse_pointer, resolve_tokens


def checked_selector(name, pointer, *, rule_id, at="/expression"):
    """Both parts are static program data, never computed field expressions."""
    from .validation import CONTEXT_NAMES
    if type(name) is not str or name not in CONTEXT_NAMES:
        raise SrxError("unknown_context", rule_id=rule_id, pointer=at+"/context",
                       expected="explicit named context root", actual=json_type(name))
    return name, parse_pointer(pointer, rule_id=rule_id, at=at+"/pointer")


def read_field(context, name, pointer, *, rule_id):
    """Read an independent value from an exact immutable context instance."""
    from .context import EvaluationContext
    from .validation import _rule_id
    rule_id = _rule_id(rule_id)
    if type(context) is not EvaluationContext:
        raise SrxError("context_required", rule_id=rule_id, expected="EvaluationContext",
                       actual="non_context", subject="context")
    name, tokens = checked_selector(name, pointer, rule_id=rule_id)
    return resolve_tokens(context.data[name], tokens, rule_id=rule_id)
