"""Explicit Core and literal checks, never a claim of human language quality."""
from .core import Glossary, LiteralPolicy, LiteralLintError, lint_literals
from .nonliteral import lint_core

__all__ = ["Glossary", "LiteralPolicy", "LiteralLintError", "lint_literals", "lint_core"]
