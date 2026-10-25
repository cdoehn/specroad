"""Live read-only project description with separate semantic/runtime contracts.

No repair, writer lock, entropy, stdin or publication. Repeated observations
detect changes but do not promise atomicity against noncooperating writers.
Missing specialist validation services remain incomplete, never green stubs.
"""
from ..changes.locking import inspect_project_lock
from ..changes._target_materialization import validation_resources
from ..cli.result_schemas import validate_result_document
from ..cli.results import CommandResult, FailureKind, OperationFailure
from ..bundles.errors import BundleError
from ..srx.errors import SrxError
from ..diagnostics import Diagnostic, from_model_error
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from ..storage.operational_preflight import observe_operational_preflight
from ..validation import ModelGate, validate_model
from ..validation.diagnostics import assess_validation
from ._inspection_snapshot import InspectionChanged, InspectionSnapshot
from ._inspection_projection import semantic_description

SEMANTIC_FIELDS = ('project_id', 'model_root_sha256', 'schema_version', 'active_profiles',
                   'artifact_counts', 'migration_needed', 'diagnostic_summary', 'primary_documents')


def _unknown():
    return {'observation_status': 'unknown'}


def _runtime(boundary, project_id=None):
    operational = observe_operational_preflight(boundary, complete_inventory=True)
    lock = inspect_project_lock(boundary.root, expected_project_id=project_id).data
    again = observe_operational_preflight(boundary, complete_inventory=True)
    repeated_lock = inspect_project_lock(boundary.root, expected_project_id=project_id).data
    if operational != again or lock != repeated_lock:
        raise InspectionChanged('inspection_runtime_observation_changed')
    record = lock['record']
    state = operational['consistency_state']
    if record is not None:
        if record['kind'] == 'writer' and lock['owner_state'] == 'alive':
            state = 'writer_active'
        elif lock['owner_state'] in ('dead', 'pid_reused') or record['kind'] == 'recovery':
            state = 'recovery_required'
        else:
            state = 'unknown'
    unknown_locks = [p for p in operational['unknown_paths'] if p.startswith('.specroad/locks/')]
    transaction = (operational if operational['unresolved_paths'] else
                   _unknown() if lock['journal_paths'] else None)
    writer = lock if record is not None else _unknown() if unknown_locks else None
    return {'project_root': str(boundary.root), 'open_transaction': transaction,
            'writer_lock': writer, 'consistency_state': state}


def _result(payload, *, code=0, diagnostics=(), **details):
    validate_result_document('project-inspect-v1', payload)
    details.update(atomic_snapshot=False, approval_granted=False, write_authorized=False,
                   recovery_performed=False)
    project = None
    if payload['runtime']['project_root'] is not None:
        project = {'project_root': payload['runtime']['project_root'],
                   **{k: payload['semantic'][k] for k in ('project_id', 'model_root_sha256')}}
    if code:
        return CommandResult.failed('project.inspect', FailureKind(code), result=payload,
                                    project=project, diagnostics=diagnostics, details=details)
    return CommandResult('project.inspect', result=payload, project=project, diagnostics=diagnostics, details=details)


def _blocked_result(payload):
    state = payload['runtime']['consistency_state']
    code = 6 if state == 'writer_active' else 5
    return _result(payload, code=code, diagnostics=(Diagnostic(
        'CORE_CONFLICT' if code == 6 else 'CORE_ENVIRONMENT', 'error', 'runtime',
        'Project inspection is blocked by operational state.', rationale=state),))


def inspect_project(root, *, profiles=None, gates=()):
    """Describe actual files. Trusted host gates are explicit, never project code.

    A completed description may contain semantic findings; it is not approval.
    If required checks cannot finish, known model facts remain observable but
    diagnostic_summary is null and the outcome fails with the actual class.
    """
    payload = {'format_version': '1.0.0', 'semantic': dict.fromkeys(SEMANTIC_FIELDS),
        'runtime': {'project_root': None, 'open_transaction': _unknown(),
                    'writer_lock': _unknown(), 'consistency_state': 'unknown'}}
    try:
        if profiles is not None and (type(profiles) not in (tuple, list) or
                any(type(key) is not str for key in profiles)):
            raise ModelError('inspection_profile_sequence_required')
        profiles = None if profiles is None else tuple(profiles)
        if type(gates) not in (tuple, list) or any(type(g) is not ModelGate for g in gates):
            raise ModelError('inspection_gate_sequence_required')
        gates = tuple(gates)
        boundary = ProjectBoundary(root)
        from ..bundles._partial_read import _marker
        _marker(boundary)
        payload['runtime']['project_root'] = str(boundary.root)
        payload['runtime'] = initial = _runtime(boundary)
        state = initial['consistency_state']
        if state != 'consistent':
            return _blocked_result(payload)
        from ..bundles._partial_read import partial_read_snapshot
        from ..bundles._read_context import PartialReadContext
        from ..documents._read_model import PartialDocumentModel
        partial = partial_read_snapshot(boundary.root)
        if partial is not None:
            if profiles is not None and tuple(profiles) != tuple(partial.payload_model.profile.profile_chain):
                raise ModelError('inspection_partial_profile_selection_mismatch')
            snapshot = partial
            model = PartialDocumentModel(partial)
        else:
            snapshot = InspectionSnapshot(boundary.root, profiles)
            if snapshot.source.boundary._root_identity != boundary._root_identity:
                raise InspectionChanged('inspection_root_changed')
            model = snapshot.model
        report = validate_model(model.documents, profile=model.profile,
            resources=validation_resources(model) if partial is None else None,
            gates=gates, partial=partial)
        assessment = assess_validation(report, documents=model.documents)
        semantic = semantic_description(model, report, assessment)
        snapshot.verify_current()
        payload['runtime'] = final = _runtime(boundary, model.configuration.project_id)
        if final['consistency_state'] != 'consistent':
            return _blocked_result(payload)
        if final != initial:
            raise InspectionChanged('inspection_runtime_changed')
        # Runtime observation itself can interleave with a normative write.
        # Recheck the inputs once more without claiming a writer-lock snapshot.
        snapshot.verify_current()
        payload['semantic'] = semantic
        code = assessment.exit_code if assessment.exit_code >= 2 else 0
        return _result(payload, code=code, diagnostics=assessment.diagnostics,
                       diagnostic_checks_complete=report.data['checks_complete'],
                       **({} if partial is None else PartialReadContext(partial).details))
    except (BundleError, OperationFailure, SrxError) as error:
        from ..query._read_errors import read_failure
        failed = read_failure('project.inspect', error, None, {})
        payload['semantic'] = dict.fromkeys(SEMANTIC_FIELDS)
        payload['runtime'].update(open_transaction=_unknown(), writer_lock=_unknown(),
                                  consistency_state='unknown')
        return _result(payload, code=failed.exit_code, diagnostics=failed.diagnostics)
    except (ModelError, SafetyViolation, OSError) as error:
        # No stale model facts or unverified negative lock/transaction claims.
        payload['semantic'] = dict.fromkeys(SEMANTIC_FIELDS)
        payload['runtime'].update(open_transaction=_unknown(), writer_lock=_unknown(),
                                  consistency_state='unknown')
        if isinstance(error, ModelError):
            code = 6 if error.reason == 'configuration_changed' else getattr(error, 'exit_code', 3)
            diagnostic = from_model_error(error)
        else:
            code = 7 if isinstance(error, SafetyViolation) else 5
            diagnostic = Diagnostic('CORE_SECURITY' if code == 7 else 'CORE_ENVIRONMENT',
                'error', 'runtime', 'Project inspection could not safely read its inputs.')
        return _result(payload, code=code, diagnostics=(diagnostic,))


def inspect_command(invocation):
    return inspect_project(invocation.resolved.project_root,
                           profiles=invocation.resolved.values['profiles'])
