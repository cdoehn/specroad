"""One native review-start transaction. No intermediate status is published.

Original report bytes are evidence, never a substitute for current checks or
host authority. The ordinary writer owns locking, staging, receipts and recovery.
"""
from base64 import b64encode
from dataclasses import replace
from hashlib import sha256

from ..authoring._inspection_snapshot import InspectionSnapshot
from ..changes import (PublicationAuthority, TargetPolicy, prepare_change_target,
    prepare_publication_check, project_lock, begin_building_journal,
    stage_building_journal, publish_prepared_journal, read_committing_journal,
    finalize_committing_journal, cleanup_completed_transaction,
    prepare_authoring_request, resolve_normative_request, read_transaction_completion)
from ..changes._journal_codec import _transaction
from ..changes._lock_files import LockFiles
from ..changes.receipt_read import _read_confirmed_request, _CompletionProof
from ..changes.target_model import _default_scope
from ..cli.result_schemas import validate_result_document
from ..model.audit_values import Actor, UtcTimestamp
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..recovery.services import native_services
from ..storage.project import ProjectSource
from ..validation import ModelDocument, ModelGate
from ..validation.values import HOOK_NAMES
from ._check_report import _initial, _now
from ._check_workspace import CheckWorkspace
from ._review_control import (COMMAND, GATE, TRANSITIONS, EVIDENCE_VERSION,
    prepare_control_candidates, reports)
from ._validation_input import ProposalInput
from .check import _isolated
from .context import ProposalContext
from .history import ProposalInputs
from .observations import (ProposalControlObservation, ProposalVerifier,
    ProposalVerification)
from .project_validation import _preflight
from .validation import validate_proposal
from .values import ProposalOriginal, require


POLICY = TargetPolicy(COMMAND, '1', (GATE,))


def _fresh_reports(snapshot, original, services):
    context = ProposalContext(original, snapshot.model)
    validation = validate_proposal(context).canonical_bytes
    report = _initial()
    report.update(observed_status=original.data['proposal_status'],
        binding=original.binding.data, proposal_sha256=original.sha256, context_sha256=context.sha256)
    report['audit'].update(proposal_id=original.data['id'], base=original.data['base'])
    workspace = CheckWorkspace(snapshot.source.boundary.root, False)
    try:
        workspace.create()
        _isolated(snapshot, original, workspace, report, services)
    finally:
        try:
            workspace.close()
        finally:
            report['workspace'] = dict(workspace.state)
    snapshot.verify_current()
    report.update(passed=True, full_semantic_validation=True, eligible_transition=None)
    report['audit']['diagnostics'] += [d for value in report['checks'].get('validation', {}).values()
        for stage in value['stages'] for d in stage['diagnostics']]
    report['audit']['diagnostics'] += report['checks'].get('lint', {}).get('diagnostics', [])
    report['audit'].update(ended_at=_now(), outcome='passed')
    report['result_sha256'] = canonical_json_sha256(report)
    validate_result_document('proposal-check-v1', report)
    return validation, canonical_json_bytes(report)


def _operation(original, validation, check):
    return dict(op='proposal_control', target=original.data['id'],
        expected_revision=original.data['revision'], expected_sha256=canonical_json_sha256(original.data),
        **{k: v for k, v in original.binding.data.items() if k != 'proposal_id'},
        events=[{'from': before, 'to': after, 'reason': reason,
                 'result_sha256': sha256(validation if index == 0 else check).hexdigest()}
                for index, (before, after, reason) in enumerate(TRANSITIONS)],
        review_start=dict(format_version=EVIDENCE_VERSION,
            validation_bytes_base64=b64encode(validation).decode('ascii'),
            check_bytes_base64=b64encode(check).decode('ascii')))


def _initial_inputs(model, original, services):
    if services.proposal_inputs is not None:
        return services.proposal_inputs(model.snapshot(), original)
    require(original.data['revision'] == 1 and original.data['proposal_status'] == 'draft'
        and not original.data.get('reviews', []) and not original.data['control_history'],
        'proposal_original_contexts_required')

    def no_observations(inputs):
        require(False, 'proposal_unexpected_historical_observation')

    return ProposalInputs((original,), (ProposalContext(original, model),), (), (),
        ProposalVerifier('native-initial-draft', '1', no_observations))


def _extended_services(snapshot, original, after, operation, actor, planned_at, services):
    old = _initial_inputs(snapshot.model, original, services)
    require(type(old) is ProposalInputs, 'proposal_native_inputs_required')
    context = ProposalContext(original, snapshot.model)
    result_bytes = [pair[0] for pair in reports(operation)]
    offset = len(original.data['control_history'])
    added = tuple(ProposalControlObservation(after, offset + index, context,
        Actor(**actor), UtcTimestamp(planned_at), before, final, reason,
        result_bytes[0 if index == 0 else 1])
        for index, (before, final, reason) in enumerate(TRANSITIONS))

    def verify(inputs):
        item = inputs.observation
        if item in added:
            # These exact rows were just produced from actual native checks in
            # this call. This never authenticates existing/foreign observations.
            require(item.original.source_bytes == after.source_bytes
                and item.context == context and item.actor.as_fields() == actor,
                'proposal_live_control_binding_changed', exit_code=6)
            return ProposalVerification(inputs.sha256, sha256(item.row_bytes).hexdigest(),
                True, True, False)
        return old.verifier.check(inputs)

    extended = ProposalInputs((*old.originals, after),
        (*old.contexts, ProposalContext(after, snapshot.model)), old.reviews,
        (*old.controls, *added), ProposalVerifier('native-live-review-start', '1', verify), old.publications)

    def provider(model, value):
        if value.binding.proposal_id == after.binding.proposal_id:
            require(value.source_bytes == after.source_bytes, 'proposal_target_changed', exit_code=6)
            return extended
        return _initial_inputs(model, value, services)

    return replace(services, proposal_inputs=provider)


def _gates(snapshot, original, after, operation, actor, planned_at, services):
    from ..recovery._validation import validate_project
    qualified_services = _extended_services(snapshot, original, after, operation,
                                            actor, planned_at, services)
    files = {**snapshot.raw, after.path: after.source_bytes}
    expected_documents = {d.path: (after.source_bytes if d.path == after.path else d.content)
                          for d in snapshot.model.documents}

    def dependencies(context):
        return context.dependency_result({identity: list(context.all_ids) for identity in context.subjects})

    def check(context):
        require({d.path: d.content for d in context.documents} == expected_documents,
                'proposal_review_target_changed', exit_code=6)
        # No positive-result cache: source/review providers can change between
        # native writer gates, including the post-publication target check.
        validate_project(files, services=qualified_services)
        return context.result()

    return tuple(ModelGate(name, 'proposal-review-start-native-v1', dependencies, check,
        snapshot.model._sources_sha256) for name in (
            *(name for name in HOOK_NAMES if name not in ('profile_lint', 'language_policy')),
            GATE, 'extension:target-resources'))


def _result(original, operation, completion, *, dry_run=False, replayed=False):
    result = dict(format_version='proposal-review-start-v1', proposal_id=operation['target'],
        revision=operation['expected_revision'] + 1, content_revision=operation['content_revision'],
        content_sha256=operation['content_sha256'], proposal_status='in_review', maturity='in_review',
        base_model_root_sha256=operation['base_model_root_sha256'],
        change_plan_sha256=operation['change_plan_sha256'], changed_change_ids=[],
        review_validity=dict(current_approval=False, human_decision_required=True),
        dry_run=dry_run, replayed=replayed, project_writes_performed=not dry_run and not replayed,
        approval_granted=False, write_authorized=False,
        completion=None if completion is None else completion.data)
    validate_result_document('proposal-review-start-v1', result)
    return result


def _replay(source, proposal_id, expected_revision, actor, request_id):
    if request_id is None:
        return None
    receipt = _read_confirmed_request(source, request_id)
    if receipt is None:
        return None
    transaction = receipt.data['transaction_id']
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, transaction)
        value = proof.journal.data
        require(value['receipts']['request'] == {'path': receipt.path, 'sha256': receipt.sha256},
                'proposal_request_receipt_changed', exit_code=6)
        binding = value['authoring_binding']
        operations = binding['operations']
        require(binding['command_id'] == 'proposal review start' and len(operations) == 1
            and operations[0]['op'] == 'proposal_control'
            and operations[0]['target'] == proposal_id
            and operations[0]['expected_revision'] == expected_revision
            and binding['actor'] == actor,
            'proposal_request_conflict', exit_code=6)
        request = prepare_authoring_request(command_id='proposal review start', actor=actor,
            operations=operations, request_id=request_id)
        resolution = resolve_normative_request(source, request).data
        require(resolution['action'] == 'replay' and resolution['receipt'] == {
            'path': receipt.path, 'sha256': receipt.sha256}, 'proposal_request_conflict', exit_code=6)
        proof.check()
        completion = read_transaction_completion(source, transaction)
        proof.check()
        return _result(None, operations[0], completion, replayed=True)


def review_start_project(root, operand, *, expected_revision, actor, planned_at,
                         change_plan_id, transaction_id, authority=None, request_id=None,
                         dry_run=False, cwd=None, services=None):
    """Fresh full checks and exactly one physical revision, or no publication.

    A host supplies authority and historical contexts when needed. Actor names,
    report hashes and request IDs do not grant human approval or write rights.
    """
    require(type(expected_revision) is int and expected_revision > 0,
            'proposal_expected_revision_required', exit_code=2)
    require(type(dry_run) is bool, 'proposal_dry_run_boolean_required', exit_code=2)
    require(dry_run or type(authority) is PublicationAuthority,
            'proposal_host_publication_authority_required', exit_code=2)
    UtcTimestamp(planned_at)
    _transaction(transaction_id)
    require(type(change_plan_id) is str and bool(change_plan_id.strip()),
            'proposal_change_plan_identity_required', exit_code=2)
    services = native_services(services)
    from ..changes.authoring import normalize_authoring_actor
    normalized_actor = normalize_authoring_actor(actor)
    require(normalized_actor.actor_type in ('human', 'ai', 'ci'),
            'proposal_actor_not_allowed', exit_code=7)
    request = prepare_authoring_request(command_id='proposal review start', actor=actor,
        operations=[], request_id=request_id, dry_run=dry_run)
    actor, request_id = request.data['actor'], request.data['request_id']
    source = ProjectSource(root)
    _preflight(source)
    supplied = ProposalInput(source, operand, cwd)
    initial = supplied.original()
    require(supplied.path == source.boundary.root / initial.path,
            'proposal_review_start_requires_managed_original', exit_code=7)
    if not dry_run:
        result = _replay(source, initial.data['id'], expected_revision, actor, request_id)
        if result is not None:
            return result
    require(initial.data['revision'] == expected_revision, 'proposal_revision_conflict', exit_code=6)
    require(initial.data['proposal_status'] == 'draft', 'proposal_review_start_requires_draft')

    def prepare():
        original = supplied.original()
        require(original.data['revision'] == expected_revision, 'proposal_revision_conflict', exit_code=6)
        require(original.data['proposal_status'] == 'draft', 'proposal_review_start_requires_draft')
        snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
        require(snapshot.raw.get(original.path) == original.source_bytes,
                'proposal_input_changed', exit_code=6)
        validation, check = _fresh_reports(snapshot, original, services)
        operation = _operation(original, validation, check)
        folded = prepare_control_candidates(snapshot.model, [operation],
            metadata_policy_version='change-metadata-v1', actor=actor, planned_at=planned_at)
        after = ProposalOriginal(canonical_json_bytes(folded.candidates[0].data), path=original.path)
        gates = _gates(snapshot, original, after, operation, actor, planned_at, services)
        checked = prepare_change_target(snapshot.model, [operation], change_plan_id=change_plan_id,
            request_id=request_id, actor=actor, planned_at=planned_at, scope_descriptor=_default_scope(),
            metadata_policy_version='change-metadata-v1', policy=POLICY, gates=gates)
        checked.require_valid()
        supplied.verify_current()
        snapshot.verify_current()
        return snapshot, original, operation, checked, gates

    if dry_run:
        snapshot, original, operation, checked, gates = prepare()
        _preflight(source)
        snapshot.verify_current()
        return _result(original, operation, None, dry_run=True)
    with project_lock(source.boundary.root, kind='writer', command='change apply',
            project_id=source.configuration.project_id, request_id=request_id,
            transaction_id=transaction_id) as held:
        result = _replay(source, initial.data['id'], expected_revision, actor, request_id)
        if result is not None:
            return result
        snapshot, original, operation, checked, gates = prepare()
        package_files = tuple(ModelDocument(p, raw)
            for p, raw in snapshot.raw.items() if p not in snapshot.model.source_files)
        preflight = prepare_publication_check(checked.plan, snapshot.model, policy=POLICY,
            gates=gates, package_files=package_files)
        journal = begin_building_journal(preflight, held_lock=held,
            transaction_id=transaction_id, authority=authority, gates=gates)
        from .. import changes
        journal = changes.stage_building_journal(preflight, journal, held_lock=held, authority=authority, gates=gates)
        publication = publish_prepared_journal(preflight, journal, held_lock=held, authority=authority, gates=gates)
        committing = read_committing_journal(source, transaction_id,
            expected_sha256=publication.data['journal_sha256'], preflight=preflight)
        finalize_committing_journal(preflight, committing, held_lock=held, authority=authority, gates=gates)
        completion = cleanup_completed_transaction(preflight, transaction_id, held_lock=held, authority=authority)
        return _result(original, operation, completion)


def _command(invocation):
    from uuid import uuid4
    from ..cli.results import CommandResult, FailureKind, OperationFailure
    options = invocation.options
    revision = options['--expected-revision']
    if not revision.isascii() or not revision.isdecimal() or int(revision) < 1:
        raise OperationFailure(FailureKind.USAGE, 'proposal_expected_revision_required')
    result = review_start_project(invocation.resolved.project_root, invocation.arguments['proposal'],
        expected_revision=int(revision), actor={
            'actor_type': options['--actor-type'], 'actor_id': options['--actor-id']},
        planned_at=_now(), change_plan_id='review-start-' + uuid4().hex,
        transaction_id='review-start-' + uuid4().hex, authority=invocation.publication_authority,
        request_id=options.get('--request-id'), dry_run=options.get('--dry-run', False),
        cwd=invocation.resolved.working_directory, services=invocation.restore_services)
    return CommandResult(COMMAND, result=result)


def review_start_command(invocation):
    from ..bundles.errors import BundleError
    from ..model.errors import ModelError
    from ..security import SafetyViolation
    from ..srx.errors import SrxError
    from ..cli.results import FailureKind, OperationFailure
    try:
        return _command(invocation)
    except (ModelError, BundleError, SrxError, SafetyViolation, OSError) as error:
        code = 7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError) else getattr(error, 'exit_code', 3)
        reason = getattr(error, 'reason', 'proposal_review_start_failed')
        facts = {'reason': reason}
        if hasattr(error, 'write_state'):
            facts['write_state'] = error.write_state
        raise OperationFailure(FailureKind(code), reason, details=facts) from error
