"""Closed operator fields used by AST validation; no dynamic registration."""

from types import MappingProxyType

OPERATOR_FIELDS = MappingProxyType({
    "literal": ("op", "value"),
    "field": ("op", "context", "pointer"),
    "exists": ("op", "arg"),
})
SUPPORTED_OPERATORS = tuple(OPERATOR_FIELDS)
