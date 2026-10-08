"""Read-profile prerequisites over the configuration already selected this call.

This gate neither loads a model nor authorizes writes. The normal handler must
still validate its own inputs and recheck every actual read/publication. Other
profile families and persistent work checkpoints have separate contracts.
"""
from ..cli.results import FailureKind, OperationFailure
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from ..storage.json_reader import JsonResource, configuration_schema
from ..storage.operational_preflight import observe_operational_preflight


def require_project_read_preflight(boundary, configuration_bytes, metadata):
    """Check current schema and shallow transaction state before a read handler.

    The same captured bytes supply option resolution after this check. A changed
    configuration/root or operational observation cannot reuse the earlier input.
    No journal body, receipt history, model, index or cache contents are read.
    """
    if not isinstance(boundary, ProjectBoundary) or type(configuration_bytes) is not bytes:
        raise TypeError('A current project boundary and captured configuration are required')
    data = {'profile': 'project_read', 'project_root': str(boundary.root),
            'normal_operation_started': False, 'model_loaded': False,
            'write_authorized': False, 'recovery_performed': False}

    def fail(kind, reason):
        raise OperationFailure(kind, 'The current project preflight did not pass.',
                               details={'preflight': {**data, **metadata.summary(), 'reason': reason}})

    try:
        JsonResource(configuration_bytes, configuration_schema(), path='specroad.json')
        first = observe_operational_preflight(boundary, metadata=metadata)
        data['operational'] = first
        if observe_operational_preflight(boundary, metadata=metadata) != first:
            fail(FailureKind.CONFLICT, 'preflight_operational_metadata_changed')
        if metadata.read_bytes(boundary, 'specroad.json') != configuration_bytes:
            fail(FailureKind.CONFLICT, 'preflight_configuration_changed')
        boundary._check_root()
        if first['consistency_state'] != 'consistent':
            fail(FailureKind.ENVIRONMENT, 'recovery_required')
    except ModelError as error:
        data['model_error'] = error.diagnostic()
        fail(FailureKind.MODEL, error.reason)
    except SafetyViolation:
        fail(FailureKind.SECURITY, 'unsafe_preflight_resource')
    except OSError:
        fail(FailureKind.ENVIRONMENT, 'preflight_resource_unavailable')
    return {**data, **metadata.summary(), 'reason': 'preflight_clear', 'preflight_passed': True}
