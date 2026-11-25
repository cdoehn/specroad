"""Exact saved Merge/Migration inputs through the common Force writer.

The complete original plan and caller bindings are retained in native_intent.
A retry verifies the historical receipt before revisiting external originals.
"""
from ..force import ForceRequest, ForceDecisions
from ..model.errors import ModelError
from ..bundles.errors import BundleError
from ..storage.json_syntax import parse_json_object
from .values import ChangePlan
from .write_guard_values import require
from .force_domain_gates import record_denial
from .force_write import apply_force_plan
from ._lock_files import LockFiles


from .force_attempt import audited


@audited
def apply_saved(root, plan, *, command, expected_plan_sha256, authority=None,
                dry_run=False, force=False, force_reason=None, observe=None, services=None,
                execution_binding=None, _attempt=None):
    require(type(plan) is ChangePlan, 'force_saved_plan_required', exit_code=2)
    from ..model.native_force_command_ids import SAVED_COMMANDS
    require(command in SAVED_COMMANDS, 'force_saved_command_required', exit_code=2)
    request = ForceRequest(force, force_reason)
    _attempt['force'] = ForceDecisions(request).summary
    require(request.requested and type(dry_run) is bool, 'explicit_force_required', exit_code=2)
    from .publication_values import PublicationAuthority
    require(dry_run or type(authority) is PublicationAuthority, 'authoring_host_authority_required', exit_code=7)
    data = plan.data
    expected_policy = 'merge-metadata-v1' if command == 'merge.apply' else 'migration-metadata-v1'
    require(data['metadata_policy_version'] == expected_policy, 'force_saved_domain_mismatch', exit_code=2)
    from .native_force_binding import native_binding, _previous
    from ..authoring.force_native import byte_plan
    original = native_binding(dict(command_id=command, plan=data,
        expected_plan_sha256=expected_plan_sha256, execution_binding=execution_binding), None, False, None,
        None if not execution_binding or execution_binding.get('transaction_id', execution_binding.get('--transaction-id')) is None else dict(
            planned_at=data['planned_at'], change_plan_id=data['change_plan_id'],
            transaction_id=execution_binding.get('transaction_id', execution_binding.get('--transaction-id'))))
    from .normal_access import require_normal_access
    from ._schema_transition_io import project_files
    from ..bundles._receipts import receipt_path
    require_normal_access(root)
    with LockFiles(root) as files:
        observed, _, _ = project_files(files)
        configuration = parse_json_object(observed['specroad.json'])
        project_id = configuration['project_id']
        prior = _previous(files, original, data['actor'], data['request_id'], request, project_id)
    if prior is not None:
        return apply_force_plan(root, prior, actor=data['actor'], request_id=data['request_id'],
            dry_run=dry_run, force=True, force_reason=force_reason, authority=authority,
            services=services, _command_id=command, _attempt=_attempt)
    decisions = ForceDecisions(request)
    _attempt['decisions'] = decisions
    decisions.decide(plan.sha256 == expected_plan_sha256, gate_id='hash:saved_plan',
        diagnostic_code='CORE_CONFLICT', subject='plan', operation=command,
        observed_binding=plan.sha256, requested_binding=expected_plan_sha256,
        effect='execute_explicit_supplied_plan')
    for check in (() if observe is None else observe if type(observe) is tuple else (observe,)):
        try:
            check()
        except (ModelError, BundleError) as error:
            record_denial(decisions, error, operation=command, subject='saved-plan', requested=original)
    before = {p: b for p, b in observed.items() if not p.startswith('.specroad/')}
    history = {p: b for p, b in observed.items() if receipt_path(p)}
    from .force_projection import recorded_target
    from .force_target import assess_files
    target = recorded_target(plan, before, decisions)
    source_report = assess_files(before, history=history, services=services)
    report = assess_files(target, history=history, services=services)
    for side, actual in (('base', source_report['model_root_sha256']), ('expected_result', report['model_root_sha256'])):
        expected = data[side]['model_root_sha256']
        decisions.decide(actual == expected, gate_id='hash:saved_' + side, diagnostic_code='CORE_CONFLICT',
            subject='project', operation=command, observed_binding=actual, requested_binding=expected,
            effect='publish_complete_recorded_target_without_rebase')
    bound = byte_plan(before, target, original, data['actor'], data['request_id'], data['planned_at'],
        project_id, request, source_report['model_root_sha256'], report['model_root_sha256'])
    return apply_force_plan(root, bound, actor=data['actor'], request_id=data['request_id'],
        force=True, force_reason=force_reason, dry_run=dry_run, authority=authority, services=services,
        _attempt=_attempt, _command_id=command, _native_findings=decisions.summary['overrides'], _observed_source=before)
