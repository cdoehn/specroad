"""Shared loaded-model validation. No CLI, filesystem inventory or write authority."""
from .core import (ModelDocument, ModelGate, GateContext, GateDependencies, GateResult,
                   ValidationReport, validate_model)

__all__ = ["ModelDocument", "ModelGate", "GateContext", "GateDependencies", "GateResult",
           "ValidationReport", "validate_model"]

from .diagnostics import ValidationAssessment, assess_validation, validation_command_result
__all__ += ["ValidationAssessment", "assess_validation", "validation_command_result"]
