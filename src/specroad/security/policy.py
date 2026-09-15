"""Fixed authority declarations; only future explicitly built-in adapters may run."""

import os
from types import MappingProxyType

from .errors import SafetyViolation
from .paths import _parts


def require_builtin_execution(executor_id):
    """No execution adapters are enabled in the current Core stage.

This is an authorization rejection, not an analyzer implementation or a success
placeholder. Future built-in Git/worker adapters require explicit integration.
"""
    raise SafetyViolation("No matching trusted execution adapter is enabled")


def check_project_declarations(data):
    """Reject attempted authority extensions before handlers see configuration.

This bounded bootstrap check does not replace the future project schema. Plain
prose and unknown non-executable metadata remain inert, never evaluated.
"""
    if "project_id" in data and (not isinstance(data["project_id"], str)
                                 or not data["project_id"] or "\0" in data["project_id"]):
        raise SafetyViolation("One scalar project identity is required")
    for key in ("project_roots", "project_ids", "repositories", "projects"):
        if key in data:
            raise SafetyViolation("Multiple project authorities are not supported")
    if "managed_paths" in data:
        if not isinstance(data["managed_paths"], list):
            raise SafetyViolation("Managed paths must be declared explicitly")
        for logical_path in data["managed_paths"]:
            _parts(logical_path)
    if "generated_path" in data:
        _parts(data["generated_path"])
    for key in ("plugins", "plugin", "execution", "executor", "entrypoint", "hooks"):
        if key in data:
            require_builtin_execution(data[key])


def isolated_process_environment():
    """Minimal process data for future explicit adapters, not a spawn permission.

Never inherit credentials, proxies, Git overrides, Python search paths or user
startup hooks. The current Core authorizes no external adapter at all.
"""
    return MappingProxyType({"PATH": os.defpath, "LC_ALL": "C", "PYTHONNOUSERSITE": "1"})
