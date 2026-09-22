"""Pure raw-byte parsing via the existing strict JSON reader."""

from .program import SrxProgram
from .context import EvaluationContext
from .errors import SrxError
from ._json_values import json_type
from .validation import _rule_id

def _decode(raw, rule_id, subject):
    """Use the existing strict reader; never interpret a string as a filename."""
    from ..model.errors import ModelError
    from ..storage.json_syntax import parse_json_object
    rule_id = _rule_id(rule_id)
    if type(raw) is not bytes:
        raise SrxError("bytes_required", rule_id=rule_id, pointer="",
                       expected="UTF-8 bytes", actual=json_type(raw), subject=subject)
    try:
        return parse_json_object(raw)
    except ModelError as error:
        raise SrxError(error.reason, rule_id=rule_id, pointer=error.pointer,
                       expected="strict JSON object", actual="invalid_json", subject=subject,
                       position=error.position, line=error.line, column=error.column) from None


def parse_program(raw, *, rule_id):
    """Parse original UTF-8 object bytes; keep them separate from JSON values."""
    program = SrxProgram(_decode(raw, rule_id, "expression"), rule_id=rule_id)
    object.__setattr__(program, "source_bytes", raw)
    return program


def parse_context(raw, *, rule_id, graph=None):
    """Explicit passive context bytes, never a path, environment or live loader."""
    return EvaluationContext(_decode(raw, rule_id, "context"), rule_id=rule_id, graph=graph)
