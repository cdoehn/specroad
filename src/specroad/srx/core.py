"""Compatibility facade for the public SRX foundation API.

Only literal is currently enabled. Parsing, validation, immutable values and
execution have separate responsibilities and retain their W/R contracts.
"""

from .validation import LANGUAGE, VERSION, SUPPORTED_OPERATORS, CONTEXT_NAMES
from .program import SrxProgram
from .context import EvaluationContext
from .evaluation import evaluate
from .parsing import parse_program, parse_context

__all__ = ("LANGUAGE", "VERSION", "SUPPORTED_OPERATORS", "CONTEXT_NAMES",
           "SrxProgram", "EvaluationContext", "evaluate", "parse_program", "parse_context")
