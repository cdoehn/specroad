"""Explicit native Force authoring into complete, immutable byte intentions.

Only the common publication engine writes. Historical results are verified
before allocating IDs/time; an input document can never supply host authority.
"""
from base64 import b64encode
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4
from ..force import ForceRequest, ForceDecisions
from ..model.audit import actor as read_actor
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..changes.request_ids import normalize_request_id
from ..changes.write_guard_values import require
from ..changes._lock_files import LockFiles
from ..changes._guarded_io import _read_path
from ..changes._schema_transition_io import project_files
from ..changes.receipt_values import request_receipt_path
from ..changes.force_domain_gates import record_denial
from ..changes.force_write import apply_force_plan
from ..changes.force_target import assess_files
from ..changes.publication_values import PublicationAuthority
from ..changes import force_receipts
from ..storage.json_syntax import parse_json_object as parsed


def native_binding(intent, expected_model_root, as_proposal, proposal_fields, execution_binding=None):
    require(type(intent) is dict and type(intent.get('command_id')) is str and type(as_proposal) is bool,
        'force_native_intent_required', exit_code=2)
    return dict(command_id=intent['command_id'], intent=deepcopy(intent),
        expected_model_root_sha256=expected_model_root, as_proposal=as_proposal,
        proposal_fields=deepcopy(proposal_fields), execution_binding=deepcopy(execution_binding))


def _previous(files, original, actor, request_id, force, project_id):
    if request_id is None:
        return None
    raw = _read_path(files, request_receipt_path(request_id), optional=True)
    if raw is None:
        return None
    hint = parsed(raw)
    require(hint.get('format_version') == 'force-request-receipt-v1',
        'request_force_binding_conflict', exit_code=6)
    write = force_receipts.read_group(files, hint['transaction_id'], project_id=project_id)
    value = write['plan']
    require(value.get('native_intent') == original and value['actor'] == actor
        and value['force'] == force.data and value['request_id'] == request_id
        and write['marker']['command_id'] == original['command_id'],
        'request_force_binding_conflict', exit_code=6)
    from ..changes.values import ChangePlan
    return ChangePlan(jcs(value))


from ..changes.force_attempt import audited


@audited
def author_force(root, intent, *, actor, request_id=None, dry_run=False,
                 expected_model_root=None, authority=None, services=None,
                 as_proposal=False, proposal_fields=None, force=False,
                 force_reason=None, _attempt=None, execution_binding=None):
    request = ForceRequest(force, force_reason)
    _attempt['force'] = ForceDecisions(request).summary
    require(request.requested and type(dry_run) is bool, 'explicit_force_required', exit_code=2)
    actor = read_actor(actor).as_fields()
    normalized_request_id = normalize_request_id(request_id)
    request_id = None if normalized_request_id is None else normalized_request_id.value
    require(dry_run or type(authority) is PublicationAuthority,
        'authoring_host_authority_required', exit_code=7)
    original = native_binding(intent, expected_model_root, as_proposal, proposal_fields, execution_binding)
    if execution_binding is not None:
        require(type(execution_binding) is dict and set(execution_binding) == {
            "planned_at", "change_plan_id", "transaction_id"}, "force_execution_binding_required", exit_code=2)
        from ..model.audit_values import UtcTimestamp
        from ..changes._journal_codec import _transaction
        UtcTimestamp(execution_binding["planned_at"])
        _transaction(execution_binding["transaction_id"])
        require(type(execution_binding["change_plan_id"]) is str and bool(execution_binding["change_plan_id"].strip()),
            "force_change_plan_identity_required", exit_code=2)
    from ..changes.normal_access import require_normal_access
    require_normal_access(root)
    with LockFiles(root) as files:
        observed, _, _ = project_files(files)
        from ..model.configuration import ProjectConfiguration
        configuration = ProjectConfiguration(parsed(observed['specroad.json']))
        previous = _previous(files, original, actor, request_id, request, configuration.project_id)
    if previous is not None:
        return apply_force_plan(root, previous, actor=actor, request_id=request_id,
            force=True, force_reason=force_reason, dry_run=dry_run,
            authority=authority, services=services, _attempt=_attempt,
            _command_id=original['command_id'])
    from ..bundles._receipts import receipt_path
    before = {p: b for p, b in observed.items() if not p.startswith('.specroad/')}
    history = {p: b for p, b in observed.items() if receipt_path(p)}
    decisions = ForceDecisions(request)
    _attempt['decisions'] = decisions
    # Observe actor policy independently from target validation.
    from ..changes import prepare_authoring_request
    try:
        prepare_authoring_request(command_id=original['command_id'].replace('.', ' '),
            actor=actor, request_id=request_id, operations=[], dry_run=dry_run, as_proposal=as_proposal)
    except ModelError as error:
        record_denial(decisions, error, operation=original['command_id'], subject=actor['actor_id'], requested=original)
    time = (execution_binding['planned_at'] if execution_binding is not None else
        datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'))
    if intent['command_id'] == 'evidence.record':
        require(type(intent.get('record')) is dict and type(intent['record'].get('created_at')) is str,
            'explicit_recorded_evidence_required', exit_code=2)
        time = intent['record']['created_at']
    from .force_sources import ForceSources
    sources = ForceSources(root, before, history, configuration, decisions, original)
    from .force_compile import compile_target
    target = compile_target(sources, intent, actor, time, decisions, services=services)
    source_report = assess_files(before, history=history, services=services)
    report = assess_files(target, history=history, services=services)
    plan = byte_plan(before, target, original, actor, request_id, time, configuration.project_id,
        request, source_report['model_root_sha256'], report['model_root_sha256'])
    if as_proposal:
        from .force_proposal import redirect
        target = redirect(sources, plan, proposal_fields, actor, time)
        report = assess_files(target, history=history, services=services)
        plan = byte_plan(before, target, original, actor, request_id, time,
            configuration.project_id, request, source_report['model_root_sha256'], report['model_root_sha256'])
    else:
        require(proposal_fields is None, 'proposal_option_requires_redirect', exit_code=2)
    sources.verify_current()
    if _attempt is not None:
        _attempt['plan'] = plan
    return apply_force_plan(root, plan, actor=actor, request_id=request_id, dry_run=dry_run,
        force=True, force_reason=force_reason, authority=authority, services=services,
        _attempt=_attempt, _command_id=original['command_id'],
        _native_findings=decisions.summary['overrides'], _observed_source=before)


def byte_plan(before, target, original, actor, request_id, time, project_id, request, base_root, target_root):
    from ..changes.core import prepare_change_plan
    from ..changes.target_model import _default_scope
    rows = []
    for path in sorted(before.keys() | target.keys()):
        if before.get(path) == target.get(path):
            continue
        rows.append(dict(op='resource_replace', path=path,
            observed_byte_sha256='absent' if path not in before else sha256(before[path]).hexdigest(),
            target={'delete': True} if path not in target else {'bytes_base64': b64encode(target[path]).decode('ascii')},
            reason='Native explicit ' + original['command_id'], force=request.data))
    return prepare_change_plan(dict(format_version='1.4.0', metadata_policy_version='change-metadata-v1',
        change_plan_id=(original['execution_binding']['change_plan_id'] if original['execution_binding'] is not None
            else 'force-native-' + str(uuid4())), request_id=request_id, actor=actor,
        planned_at=time, project_id=project_id, force=request.data, native_intent=original,
        base={'scope_descriptor': _default_scope(), 'model_root_sha256':
            original['expected_model_root_sha256'] if original['expected_model_root_sha256'] is not None else base_root},
        expected_result={'model_root_sha256': target_root}, operations=rows,
        preconditions=[], result_artifacts=[]))
