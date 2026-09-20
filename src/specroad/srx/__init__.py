"""Pure declarative SRX foundation; this development stage enables literal only."""

from .core import (LANGUAGE, VERSION, SUPPORTED_OPERATORS, CONTEXT_NAMES,
                   SrxProgram, EvaluationContext, evaluate)
from .errors import SrxError

__all__ = ("LANGUAGE", "VERSION", "SUPPORTED_OPERATORS", "CONTEXT_NAMES",
           "SrxProgram", "EvaluationContext", "evaluate", "SrxError")
