"""Compatibility facade for the public SRX foundation API.

Literal, fields, Boolean logic, comparisons sequence operations and nested lexical quantifiers are enabled. Parsing, validation, immutable values and
execution have separate responsibilities and retain their W/R contracts.
"""

from .validation import LANGUAGE, VERSION, SUPPORTED_OPERATORS, CONTEXT_NAMES
from .program import SrxProgram
from .context import EvaluationContext
from .evaluation import evaluate
from .parsing import parse_program, parse_context

__all__ = ("LANGUAGE", "VERSION", "SUPPORTED_OPERATORS", "CONTEXT_NAMES",
           "SrxProgram", "EvaluationContext", "evaluate", "parse_program", "parse_context")

from .types import MISSING, value_type

__all__ += ("MISSING", "value_type")

from .fields import read_field
from .types import require_type
__all__ += ("read_field", "require_type")

from .comparisons import compare
__all__ += ("compare",)
