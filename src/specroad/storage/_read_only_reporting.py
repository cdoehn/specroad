"""Operation status projection; does not load inputs, repair state or emit output."""
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..profiles.composition_values import ProfileCompositionError
from .read_only_values import READ_ONLY_VERSION, ReadOnlyResult

def _base(operation):
    return {"format_version": READ_ONLY_VERSION, "operation": operation,
            "passed": None, "checks_complete": False, "exit_code": 5, "status": "blocked",
            "phase": "arguments",
            "normal_operation_started": False, "model_loaded": False,
            "project_id": None, "read_only": True, "project_complete": False,
            "write_authorized": False, "approval_granted": False,
            "atomic_snapshot": False, "operational": None, "diagnostics": [],
            "source_bindings": [], "configuration_sha256": None,
            "resource_bindings": [], "resource_files_verified": False,
            "freshness_verified": False, "source_observation_sha256": None,
            "validation": None, "lint": None}


def _failure(data, error):
    if isinstance(error, ModelError):
        diagnostic = error.diagnostic()
        from ..configurations.evaluation import ConfigurationEvaluationError
        if isinstance(error, ConfigurationEvaluationError):
            diagnostic['code'] = 'SRV130'
        if error.reason == "unsafe_registry_resource":
            code = 7
        elif error.reason in ("operational_metadata_changed", "read_only_membership_changed",
                            "read_only_source_changed", "read_only_project_replaced", "configuration_changed",
                            "read_only_resource_changed", "read_only_profile_observation_changed",
                            "registry_changed", "registry_observation_changed"):
            code = 5
        elif isinstance(error, ProfileCompositionError) or data["phase"] in ("arguments", "configuration", "profiles"):
            code = 2
        else:
            code = 3
    elif isinstance(error, SafetyViolation):
        diagnostic = {"reason": "unsafe_project_read"}
        code = 7
    else:
        diagnostic = {"reason": "project_read_unavailable", "errno": error.errno}
        code = 5
    if "exit_code" in diagnostic and diagnostic["exit_code"] != code:
        diagnostic["producer_exit_code"] = diagnostic["exit_code"]
    diagnostic["exit_code"] = code
    data.update(status="failed", passed=False, exit_code=code, checks_complete=False,
                freshness_verified=False, source_observation_sha256=None,
                resource_files_verified=False,
                validation=None, lint=None, diagnostics=[diagnostic])
    return ReadOnlyResult._create(data)


def _blocked(data, observation):
    data["operational"] = observation
    data["diagnostics"] = [{"code": "SRV168" if observation["recovery_required"] else "READ_STATE_UNKNOWN",
        "reason": "recovery_required" if observation["recovery_required"] else "operational_state_unresolved",
        "severity": "error"}]
    return ReadOnlyResult._create(data)
