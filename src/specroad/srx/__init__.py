"""Pure declarative SRX foundation; fields, logic, comparison and sequence operations."""

from .core import (LANGUAGE, VERSION, SUPPORTED_OPERATORS, CONTEXT_NAMES,
                   SrxProgram, EvaluationContext, evaluate, parse_program, parse_context)
from .errors import SrxError

__all__ = ("LANGUAGE", "VERSION", "SUPPORTED_OPERATORS", "CONTEXT_NAMES",
           "SrxProgram", "EvaluationContext", "evaluate", "parse_program", "parse_context", "SrxError")

from .types import MISSING, value_type

__all__ += ("MISSING", "value_type")

from .fields import read_field
from .types import require_type
__all__ += ("read_field", "require_type")

from .comparisons import compare
__all__ += ("compare",)
