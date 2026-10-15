"""Read-only product configuration services over explicitly supplied records."""

from .values import EffectiveConfiguration, resolve_configuration
from .applicability import ApplicabilityResult, evaluate_applicability

__all__ = ['EffectiveConfiguration', 'resolve_configuration', 'ApplicabilityResult', 'evaluate_applicability']
