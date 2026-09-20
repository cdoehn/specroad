"""Pure declarative SRX foundation; this development stage enables literal only."""

from .core import (LANGUAGE, VERSION, SUPPORTED_OPERATORS, CONTEXT_NAMES,
                   SrxProgram, EvaluationContext, evaluate, parse_program, parse_context)
from .errors import SrxError

__all__ = ("LANGUAGE", "VERSION", "SUPPORTED_OPERATORS", "CONTEXT_NAMES",
           "SrxProgram", "EvaluationContext", "evaluate", "parse_program", "parse_context", "SrxError")
