"""Stable pure comparison API for Change Plans, queries and future adapters.

No CLI, presentation, filesystem, network or project configuration discovery.
"""
from .comparison_values import ComparisonInputs, ComparisonResult
from .field_comparison import field_diff
from .artifact_comparison import compare_artifacts
from .direct_impact import direct_impact
from .timing_comparison import compare_duration_bounds

__all__ = ['ComparisonInputs', 'ComparisonResult', 'field_diff',
           'compare_artifacts', 'direct_impact', 'compare_duration_bounds']
