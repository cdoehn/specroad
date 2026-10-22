"""The stable public report, projected from bound internal gate decisions."""
from ._readiness_decisions import GATES, GateDecision, ReadinessBinding


def readiness_report(binding: ReadinessBinding, selection, decisions: dict[str, GateDecision], *, complete):
    assert all(decisions[key].binding is binding for key in GATES)
    rows = [decisions[key].result(complete=complete) for key in GATES]
    statuses = {row['status'] for row in rows}
    status = 'blocked' if 'failed' in statuses else 'incomplete' if 'incomplete' in statuses else 'ready'
    return {'format_version': 'release-readiness-v1', 'release_id': binding.data['release_id'],
        'input_sha256': binding.sha256, 'binding': binding.data, 'status': status,
        'ready': status == 'ready', 'provisional': selection['provisional'],
        'gates': rows, 'selection': selection,
        'validation_scope': 'supplied_model_native_scope_and_explicit_trusted_services',
        'project_files_verified': False, 'release_baseline_authorized': False,
        'write_authorized': False, 'approval_granted': False}
