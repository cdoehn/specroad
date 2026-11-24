"""Explicit Force adapter into the existing guarded publication engine.

The adapter determines complete bytes and findings; it contains no filesystem
write primitive and does not recover, unlock or finish another transaction.
"""
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4
from ..force import ForceRequest, ForceDecisions, operations_hash
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from .values import ChangePlan
from .core import prepare_change_plan
from .resource_replace import check_plan, target_bytes
from .force_target import assess_files, record_findings, effect_path
from .write_guard_values import require, inventory
from ._schema_transition_io import project_files
from ._lock_files import LockFiles
from ._guarded_io import _read_path
from .receipt_values import request_receipt_path
from .publication_values import PublicationAuthority
from .locking import project_lock
from . import force_receipts


@dataclass(frozen=True)
class ForcePublicationRequest:
    """Detached host input, not host authorization or positive validation."""
    source_bytes: bytes

    @property
    def data(self):
        return parsed(self.source_bytes)

    @property
    def sha256(self):
        return sha256(self.source_bytes).hexdigest()


def bind_force_plan(plan, *, project_id, force=False, reason=None):
    require(type(plan) is ChangePlan, 'force_change_plan_required', exit_code=2)
    value = plan.data
    value.pop('change_plan_sha256')
    value.update(format_version='1.3.0', project_id=project_id, force=ForceRequest(force, reason).data)
    return prepare_change_plan(value)


def _replay(files, plan):
    data = plan.data
    if data['request_id'] is None:
        return None
    raw = _read_path(files, request_receipt_path(data['request_id']), optional=True)
    if raw is None:
        return None
    hint = parsed(raw)
    require(hint.get('format_version') == 'force-request-receipt-v1'
        and hint.get('plan_sha256') == plan.sha256 and hint.get('operations_sha256') == operations_hash(data),
        'request_force_binding_conflict', exit_code=6)
    write = force_receipts.read_group(files, hint['transaction_id'], project_id=data['project_id'])
    require(write['plan'] == data, 'request_force_binding_conflict', exit_code=6)
    return _outcome(plan, write['validation'], write['force'], completion=force_receipts.completion(write, current=False), replayed=True)


def _outcome(plan, report, force, *, dry_run=False, completion=None, replayed=False):
    data = plan.data
    state = 'not_committed' if completion is None else 'committed'
    return {'format_version': 'force-authoring-execution-v1', 'command_id': 'change.apply',
        'status': 'forced' if force['used'] else 'success', 'exit_code': 0,
        'dry_run': dry_run, 'write_state': state, 'replayed': replayed, 'complete': True,
        'plan_sha256': plan.sha256, 'operations_sha256': operations_hash(data),
        'target_model_root_sha256': report['model_root_sha256'], 'validation_status': report['validation_status'],
        'force': force, 'report': report, 'diagnostics': report['diagnostics'],
        'completion': None if completion is None else completion.data, 'approval_granted': False,
        'audit': {'format_version': 'force-authoring-audit-v1', 'plan': data,
            'force': force, 'operations_sha256': operations_hash(data), 'write_state': state,
            'dry_run': dry_run, 'replayed': replayed, 'validation_status': report['validation_status'],
            'target_inventory': report['inventory'], 'approval_granted': False}}


def _target(root, plan, before, decisions, services):
    value = plan.data
    target = dict(before)
    if check_plan(value):
        for operation in value['operations']:
            path = operation['path']; effect_path(path)
            old = before.get(path)
            observed = 'absent' if old is None else sha256(old).hexdigest()
            requested = operation['observed_byte_sha256']
            require(decisions.decide(observed == requested, gate_id='hash:resource_precondition',
                diagnostic_code='CORE_CONFLICT', subject=path, operation='resource_replace',
                observed_binding=observed, requested_binding=requested, effect='replace_explicit_bytes_on_observed_source'),
                'resource_replace_source_changed', exit_code=6)
            raw = target_bytes(operation)
            if raw is None:
                target.pop(path, None)
            else:
                target[path] = raw
    else:
        from ..authoring.project_sources import AuthoringSources
        from .target import assess_change_target
        from .target_values import TargetPolicy
        from .plan_source_operation import deleted_paths
        sources = AuthoringSources(root)
        checked = assess_change_target(plan, sources.model,
            policy=TargetPolicy('change.apply', 'force-common-target-v1', ()))
        for document in checked.publication_documents:
            target[document.path] = document.content
        for path in deleted_paths(value['operations']):
            target.pop(path)
        sources.verify_current()
    return target


def apply_force_plan(root, plan, *, actor, request_id, force=False, force_reason=None,
                     dry_run=False, authority=None, services=None, _attempt=None):
    require(type(plan) is ChangePlan and type(dry_run) is bool, 'force_change_plan_required', exit_code=2)
    request = ForceRequest(force, force_reason); data = plan.data
    require(request.requested, 'explicit_force_required', exit_code=2)
    require(data.get('force') == request.data, 'request_force_binding_conflict', exit_code=6)
    require(data['actor'] == actor and data['request_id'] == request_id, 'saved_authoring_identity_mismatch', exit_code=6)
    if not dry_run:
        require(type(authority) is PublicationAuthority, 'authoring_host_authority_required', exit_code=7)
    from .normal_access import require_normal_access
    require_normal_access(root, expected_project_id=data['project_id'])
    with LockFiles(root) as files:
        if not dry_run:
            replay = _replay(files, plan)
            if replay is not None: return replay
        before, _, _ = project_files(files, exclude=('.specroad',))
    decisions = ForceDecisions(request)
    if actor['actor_type'] == 'ai':
        decisions.decide(False, gate_id='actor:direct_write', diagnostic_code='CORE_SECURITY',
            subject=actor['actor_id'], operation='change.apply', observed_binding=actor,
            requested_binding='explicit_direct_write', effect='write_without_human_approval_claim')
    target = _target(root, plan, before, decisions, services)
    report = assess_files(target, services=services)
    requested_binding = {'plan_sha256': plan.sha256, 'target_inventory_sha256': digest(inventory(target)),
        'expected_model_root_sha256': data['expected_result']['model_root_sha256']}
    record_findings(decisions, report, operation='change.apply', requested_binding=requested_binding)
    if data['expected_result']['model_root_sha256'] is not None:
        decisions.decide(report['model_root_sha256'] == data['expected_result']['model_root_sha256'],
            gate_id='hash:target_model_root', diagnostic_code='CORE_CONFLICT', subject='project', operation='change.apply',
            observed_binding=report['model_root_sha256'], requested_binding=data['expected_result']['model_root_sha256'],
            effect='publish_explicit_target_with_observed_root')
    summary = decisions.summary
    if _attempt is not None:
        _attempt['force'] = summary
        _attempt['validation_status'] = report['validation_status']
        _attempt['force_report'] = report
    if dry_run:
        return _outcome(plan, report, summary, dry_run=True)
    txid = 'force-' + str(uuid4())
    with project_lock(root, kind='writer', command='change apply', project_id=data['project_id'],
            transaction_id=txid, request_id=request_id, force_plan=plan) as held:
        replay = _replay(held._files, plan)
        if replay is not None: return replay
        def inventory_check(expected):
            actual, _, _ = project_files(held._files, exclude=('.specroad',))
            require(actual == expected, 'force_observed_source_changed', exit_code=6)
        inventory_check(before)
        host_request = ForcePublicationRequest(jcs({'format_version': 'force-publication-request-v1',
            'plan': data, 'force': summary, 'operations_sha256': operations_hash(data),
            'before_inventory': inventory(before), 'target_inventory': inventory(target), 'validation': report}))
        def qualify(actual):
            current = assess_files(actual, services=services)
            require(current == report, 'force_target_observation_changed', exit_code=6)
            detached = ForcePublicationRequest(host_request.source_bytes)
            allowed = authority.check(detached)
            require(type(allowed) is bool and allowed and detached.source_bytes == host_request.source_bytes,
                'write_authority_denied', exit_code=7)
            return current
        qualify(target)
        if target == before:
            return _outcome(plan, report, summary)
        from .guarded_write import _Inputs, _run
        if _attempt is not None: _attempt['publication_started'] = True
        try:
            done = _run(_Inputs(plan, data['project_id'], 'change.apply', before, target,
                inventory_check, qualify, effect_path=effect_path, force_record=summary), held)
        except OSError as error:
            from .write_guard_values import WriteGuardError
            raise WriteGuardError('publication_io_failure', exit_code=5) from error
        return _outcome(plan, report, summary, completion=done)
