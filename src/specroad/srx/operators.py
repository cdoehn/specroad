"""Closed operator fields used by AST validation; no dynamic registration."""

from types import MappingProxyType

OPERATOR_FIELDS = MappingProxyType({
    "literal": ("op", "value"),
    "field": ("op", "context", "pointer"),
    "exists": ("op", "arg"),
    "not": ("op", "arg"),
    "and": ("op", "args"),
    "or": ("op", "args"),
    "eq": ("op", "args"),
    "ne": ("op", "args"),
    "lt": ("op", "args"),
    "lte": ("op", "args"),
    "gt": ("op", "args"),
    "gte": ("op", "args"),
    "in": ("op", "args"),
    "contains": ("op", "args"),
    "starts_with": ("op", "args"),
    "ends_with": ("op", "args"),
    "length": ("op", "arg"),
    "count": ("op", "arg"),
})
SUPPORTED_OPERATORS = tuple(OPERATOR_FIELDS)

# Static arities shared by validation and the evaluator. No dynamic registration.
UNARY_OPERATORS = tuple(op for op, names in OPERATOR_FIELDS.items() if names == ("op", "arg"))
BINARY_OPERATORS = tuple(op for op, names in OPERATOR_FIELDS.items()
                         if names == ("op", "args") and op not in ("and", "or"))
