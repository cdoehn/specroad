"""Controlled, non-sensitive failure for forbidden Core data operations."""


class SafetyViolation(ValueError):
    """Messages never interpolate project data or secrets."""
