"""Explicit Force adapter into the existing guarded publication engine.

The adapter determines complete bytes and findings; it contains no filesystem
write primitive and does not recover, unlock or finish another transaction.
"""
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4
from .force_outcome import _outcome
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
    value.update(format_version='1.4.0' if 'native_intent' in value else '1.3.0',
        project_id=project_id, force=ForceRequest(force, reason).data)
    return prepare_change_plan(value)


def _replay(files, plan, command_id='change.apply'):
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
    require(write['plan'] == data and write['marker']['command_id'] == command_id,
        'request_force_binding_conflict', exit_code=6)
    return _outcome(plan, write['validation'], write['force'], completion=force_receipts.completion(write, current=False), replayed=True, command_id=command_id)




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
        from .force_projection import recorded_target
        from ..model.errors import ModelError
        from ..bundles.errors import BundleError
        from .force_domain_gates import record_denial
        # Continue the native examination when possible, but retain its
        # negative policy result instead of using it as a target generator.
        try:
            sources = AuthoringSources(root)
            checked = assess_change_target(plan, sources.model,
                policy=TargetPolicy('change.apply', 'force-common-target-v1', ()))
            checked.require_valid()
            sources.verify_current()
        except (ModelError, BundleError) as error:
            record_denial(decisions, error, operation='change.apply',
                subject='project', requested={'plan_sha256': plan.sha256})
        target = recorded_target(plan, before, decisions)
    return target


def apply_force_plan(root, plan, *, actor, request_id, force=False, force_reason=None,
                     dry_run=False, authority=None, services=None, _attempt=None,
                     _command_id='change.apply', _native_findings=(), _observed_source=None):
    require(type(plan) is ChangePlan and type(dry_run) is bool, 'force_change_plan_required', exit_code=2)
    request = ForceRequest(force, force_reason); data = plan.data
    command = _command_id
    if command != 'change.apply':
        require(data.get('native_intent', {}).get('command_id') == command
            or command in ('proposal.apply', 'proposal.review', 'proposal.review.start', 'merge.apply', 'migrate.apply'),
            'force_native_command_binding', exit_code=2)
    require(request.requested, 'explicit_force_required', exit_code=2)
    require(data.get('force') == request.data, 'request_force_binding_conflict', exit_code=6)
    require(data['actor'] == actor and data['request_id'] == request_id, 'saved_authoring_identity_mismatch', exit_code=6)
    if not dry_run:
        require(type(authority) is PublicationAuthority, 'authoring_host_authority_required', exit_code=7)
    from .normal_access import require_normal_access
    require_normal_access(root, expected_project_id=data['project_id'])
    with LockFiles(root) as files:
        if not dry_run:
            replay = _replay(files, plan, command)
            if replay is not None: return replay
        before, _, _ = project_files(files, exclude=('.specroad',))
        observed_all, _, _ = project_files(files)
        from ..bundles._receipts import receipt_path
        history = {p: raw for p, raw in observed_all.items() if receipt_path(p)}
    if 'specroad.json' in before:
        try:
            actual_project_id = parsed(before['specroad.json']).get('project_id')
        except ValueError:
            actual_project_id = None
        require(actual_project_id is None or actual_project_id == data['project_id'],
            'force_project_identity_conflict', exit_code=6)
    decisions = ForceDecisions(request)
    if _observed_source is not None:
        require(before == _observed_source, 'force_observed_source_changed', exit_code=6)
    from ..force import validate_override
    for value in _native_findings:
        row = validate_override(value)
        decisions.decide(False if row['original_decision'] == 'denied' else None,
            **{k: v for k, v in row.items() if k != 'original_decision'})
    if actor['actor_type'] == 'ai':
        decisions.decide(False, gate_id='actor:direct_write', diagnostic_code='CORE_SECURITY',
            subject=actor['actor_id'], operation=command, observed_binding=actor,
            requested_binding='explicit_direct_write', effect='write_without_human_approval_claim')
    if data['base']['model_root_sha256'] is not None:
        source_report = assess_files(before, services=services, history=history)
        decisions.decide(source_report['model_root_sha256'] == data['base']['model_root_sha256'],
            gate_id='hash:base_model_root', diagnostic_code='CORE_CONFLICT', subject='project', operation=command,
            observed_binding=source_report['model_root_sha256'], requested_binding=data['base']['model_root_sha256'],
            effect='execute_explicit_target_on_observed_source')
    target = _target(root, plan, before, decisions, services)
    report = assess_files(target, services=services, history=history)
    requested_binding = {'plan_sha256': plan.sha256, 'target_inventory_sha256': digest(inventory(target)),
        'expected_model_root_sha256': data['expected_result']['model_root_sha256']}
    record_findings(decisions, report, operation=command, requested_binding=requested_binding)
    if data['expected_result']['model_root_sha256'] is not None:
        decisions.decide(report['model_root_sha256'] == data['expected_result']['model_root_sha256'],
            gate_id='hash:target_model_root', diagnostic_code='CORE_CONFLICT', subject='project', operation=command,
            observed_binding=report['model_root_sha256'], requested_binding=data['expected_result']['model_root_sha256'],
            effect='publish_explicit_target_with_observed_root')
    for path in before:
        if path.startswith('archive/objects/') and before[path] != target.get(path):
            decisions.decide(False, gate_id='immutable:archive_object', diagnostic_code='CORE_SECURITY',
                subject=path, operation=command, observed_binding=sha256(before[path]).hexdigest(),
                requested_binding=None if path not in target else sha256(target[path]).hexdigest(),
                effect='change_explicit_original_invalidating_dependent_evidence')
    summary = decisions.summary
    if _attempt is not None:
        _attempt['force'] = summary
        _attempt['validation_status'] = report['validation_status']
        _attempt['force_report'] = report
    if dry_run:
        return _outcome(plan, report, summary, dry_run=True, command_id=command)
    execution = data.get('native_intent', {}).get('execution_binding')
    txid = execution['transaction_id'] if execution is not None else 'force-' + str(uuid4())
    with project_lock(root, kind='writer', command='change apply', project_id=data['project_id'],
            transaction_id=txid, request_id=request_id, force_plan=plan) as held:
        replay = _replay(held._files, plan, command)
        if replay is not None: return replay
        def inventory_check(expected):
            actual, _, _ = project_files(held._files, exclude=('.specroad',))
            if actual != expected:
                decisions.decide(False, gate_id='hash:live_source', diagnostic_code='CORE_CONFLICT',
                    subject='project', operation=command, observed_binding=inventory(actual),
                    requested_binding=inventory(expected), effect='publication_not_confirmed_source_changed')
                if _attempt is not None: _attempt['force'] = decisions.summary
                require(False, 'force_observed_source_changed', exit_code=6)
            for path, original in history.items():
                require(_read_path(held._files, path) == original, 'force_history_changed', exit_code=6)
        inventory_check(before)
        current_all, _, _ = project_files(held._files)
        require({p: raw for p, raw in current_all.items() if receipt_path(p)} == history,
            'force_history_changed', exit_code=6)
        host_request = ForcePublicationRequest(jcs({'format_version': 'force-publication-request-v1',
            'plan': data, 'force': summary, 'operations_sha256': operations_hash(data),
            'before_inventory': inventory(before), 'target_inventory': inventory(target), 'validation': report}))
        publication_started = False
        def qualify(actual):
            current = assess_files(actual, services=services, history=history)
            require(current == report, 'force_target_observation_changed', exit_code=6)
            detached = ForcePublicationRequest(host_request.source_bytes)
            allowed = authority.check(detached)
            if not (type(allowed) is bool and allowed and detached.source_bytes == host_request.source_bytes):
                from .execution_values import ChangeExecutionError
                raise ChangeExecutionError('write_authority_denied', exit_code=7,
                    write_state='unknown' if publication_started else 'not_committed')
            return current
        qualify(target)
        if target == before and data['format_version'] != '1.4.0':
            return _outcome(plan, report, summary, command_id=command)
        from .guarded_write import _Inputs, _run
        publication_started = True
        if _attempt is not None: _attempt['publication_started'] = True
        try:
            done = _run(_Inputs(plan, data['project_id'], command, before, target,
                inventory_check, qualify, effect_path=effect_path, force_record=summary), held)
        except OSError as error:
            from .write_guard_values import WriteGuardError
            raise WriteGuardError('publication_io_failure', exit_code=5) from error
        return _outcome(plan, report, summary, completion=done, command_id=command)
