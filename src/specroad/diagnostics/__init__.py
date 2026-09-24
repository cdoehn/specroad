"""Versioned findings and explicit fail thresholds; no validation execution or I/O."""
from .core import (Diagnostic, DiagnosticAssessment, FailPolicy, assess_diagnostics,
                   diagnostic_key, diagnostic_schema, from_model_error)
from .catalog import code_metadata, known_codes
from ..result_contract import ResultContractError

__all__ = ["Diagnostic", "DiagnosticAssessment", "FailPolicy", "assess_diagnostics",
           "diagnostic_key", "diagnostic_schema", "from_model_error", "code_metadata",
           "known_codes", "ResultContractError"]
