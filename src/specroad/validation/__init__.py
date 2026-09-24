"""Shared loaded-model validation. No CLI, filesystem inventory or write authority."""
from .core import (ModelDocument, ModelGate, GateContext, GateDependencies, GateResult,
                   ValidationReport, validate_model)

__all__ = ["ModelDocument", "ModelGate", "GateContext", "GateDependencies", "GateResult",
           "ValidationReport", "validate_model"]
