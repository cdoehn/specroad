"""Compatibility exports for the separated diagnostic boundary.

Creating or presenting findings never runs a rule or grants project approval.
"""
from ..result_contract import ResultContractError
from .values import Diagnostic, FIELDS, LOCATION_KEYS, ORIGINS, SEVERITIES
from .ordering import diagnostic_key
from .projection import from_model_error
from .policy import DiagnosticAssessment, FailPolicy, assess_diagnostics
from .schema import diagnostic_schema
