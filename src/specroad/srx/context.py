"""Immutable explicitly supplied evaluation context; no loaders or defaults."""

from dataclasses import dataclass
from ._json_values import JsonSnapshot
from .validation import _rule_id, _validate_context

@dataclass(frozen=True, init=False)
class EvaluationContext:
    """Only four explicit roots; profiles/statistics are passive project data.

    configuration=None explicitly means no selected configuration. No defaults
    or host environment are consulted. item is lexically bound only in quantifier predicates
    and is never accepted as an external root. Relations are precomputed data,
    never a callable resolver. Field lookup reads only these supplied immutable roots.
    """
    _snapshot: JsonSnapshot

    def __init__(self, document, *, rule_id):
        rule_id = _rule_id(rule_id)
        snapshot = JsonSnapshot(document, rule_id=rule_id, subject="context")
        _validate_context(snapshot.data, rule_id)
        object.__setattr__(self, "_snapshot", snapshot)

    @property
    def data(self):
        return self._snapshot.data


