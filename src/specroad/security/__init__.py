"""Fixed Core data boundaries, not an OS sandbox for trusted Python callers.

No project-configured code, shell, network or plugin loader exists here.
Normative writers and explicit Git/worker adapters must add their own authorized
operations later; importing these helpers grants no execution permission.
"""

from .errors import SafetyViolation
from .paths import ProjectBoundary
from .policy import (check_project_declarations, isolated_process_environment,
                     require_builtin_execution)

__all__ = ["ProjectBoundary", "SafetyViolation", "check_project_declarations",
           "isolated_process_environment", "require_builtin_execution"]
