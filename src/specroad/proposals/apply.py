"""Public Proposal Apply: exact inner plan through the shared native writer."""
from ..authoring._inspection_snapshot import InspectionSnapshot
from ..changes import (PublicationAuthority, TargetPolicy, prepare_change_target,
    prepare_authoring_request, project_lock, read_transaction_completion, resolve_normative_request)
from ..changes._journal_codec import _transaction
from ..changes._lock_files import LockFiles
from ..changes.receipt_read import _CompletionProof, _read_confirmed_request
from ..changes.target_model import _default_scope
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..recovery.services import native_services
from ..storage.project import ProjectSource
from ..validation import ModelDocument
from ._apply_control import (COMMAND, GATE, assessment, operation, operation_proof,
                            prepare_apply_candidates)
from ._apply_checks import gates as apply_gates
from ._check_report import _initial, _now
from ._review_transaction import _publish
from ._validation_input import ProposalInput
from .context import ProposalContext
from .project_validation import _preflight
from .publication import ProposalPublication, verify_proposal_publication
from .values import ProposalOriginal, SPECIFICATION_SCOPE, require

POLICY = TargetPolicy(COMMAND, '1', (GATE,))


def _result(operations, completion, audit, *, dry_run=False, replayed=False):
    from ..changes.values import ChangeOperation
    from ..cli.result_schemas import validate_result_document
    control = operations[-1]
    _, proof = operation_proof(control)
    created = set()
    affected = set()
    for op in operations:
        ids = ChangeOperation(op).result_ids
        affected.update(ids)
        if op['op'] in ('create', 'evidence_record', 'relation_review_record'):
            field = {'create': 'artifact', 'evidence_record': 'evidence', 'relation_review_record': 'record'}[op['op']]
            created.add(op[field]['id'])
    audit.update(proposal_id=control['target'], base={'scope_descriptor': SPECIFICATION_SCOPE, 'model_root_sha256': control['base_model_root_sha256']},
        ended_at=_now(), outcome='dry_run' if dry_run else 'replayed' if replayed else 'committed',
        created_ids=sorted(created), changed_ids=sorted(affected - created), removed_ids=[])
    value = dict(format_version='proposal-apply-v1', proposal_id=control['target'],
        revision=control['expected_revision'] + 1, content_revision=control['content_revision'],
        content_sha256=control['content_sha256'], base_model_root_sha256=control['base_model_root_sha256'],
        change_plan_sha256=control['change_plan_sha256'], proposal_status='applied', maturity='applied',
        dry_run=dry_run, replayed=replayed, project_writes_performed=not dry_run and not replayed,
        approval_granted=False, write_authorized=False,
        completion=None if completion is None else completion.data, audit=audit)
    validate_result_document('proposal-apply-v1', value)
    return value


def _replay(source, proposal_id, expected_revision, actor, request_id, audit):
    if request_id is None:
        return None
    receipt = _read_confirmed_request(source, request_id)
    if receipt is None:
        return None
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, receipt.data['transaction_id'])
        value = proof.journal.data
        require(value['receipts']['request'] == {'path': receipt.path, 'sha256': receipt.sha256},
                'proposal_request_receipt_changed', exit_code=6)
        binding = value['authoring_binding']; operations = binding['operations']
        require(binding['command_id'] == 'proposal apply' and bool(operations)
            and operations[-1]['op'] == 'proposal_control'
            and operations[-1]['target'] == proposal_id
            and operations[-1]['expected_revision'] == expected_revision and binding['actor'] == actor,
            'proposal_request_conflict', exit_code=6)
        operation_proof(operations[-1])
        request = prepare_authoring_request(command_id='proposal apply', actor=actor,
            operations=operations, request_id=request_id)
        resolution = resolve_normative_request(source, request).data
        require(resolution['action'] == 'replay' and resolution['receipt'] == {
            'path': receipt.path, 'sha256': receipt.sha256}, 'proposal_request_conflict', exit_code=6)
        proof.check()
        completion = read_transaction_completion(source, value['transaction_id'])
        proof.check()
        return _result(operations, completion, audit, replayed=True)


def _verify_completion(source, transaction, plan, before, target, original, after):
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, transaction)
        paths = [*proof.receipt_paths, proof.archive_path]
        receipts = tuple(ModelDocument(path, proof.read(path)) for path in paths)
        publication = ProposalPublication(plan, before, target, receipts)
        verify_proposal_publication(publication, original, after, ProposalContext(after, before))
        proof.check()


def apply_project(root, operand, *, expected_revision, actor, planned_at, change_plan_id,
                  transaction_id, authority=None, request_id=None, dry_run=False, cwd=None, services=None):
    audit = _initial()['audit']
    try:
        return _apply(root, operand, expected_revision=expected_revision, actor=actor,
            planned_at=planned_at, change_plan_id=change_plan_id, transaction_id=transaction_id,
            authority=authority, request_id=request_id, dry_run=dry_run, cwd=cwd, services=services, audit=audit)
    except Exception as error:
        audit.update(ended_at=_now(), outcome='failed',
            diagnostics=[{'reason': getattr(error, 'reason', 'proposal_apply_failed')}])
        error.proposal_audit = audit
        raise


def _apply(root, operand, *, expected_revision, actor, planned_at, change_plan_id,
           transaction_id, authority, request_id, dry_run, cwd, services, audit):
    require(type(expected_revision) is int and expected_revision > 0,
            'proposal_expected_revision_required', exit_code=2)
    require(type(dry_run) is bool, 'proposal_dry_run_boolean_required', exit_code=2)
    require(dry_run or type(authority) is PublicationAuthority,
            'proposal_host_publication_authority_required', exit_code=7)
    UtcTimestamp(planned_at); _transaction(transaction_id)
    require(type(change_plan_id) is str and bool(change_plan_id.strip()),
            'proposal_change_plan_identity_required', exit_code=2)
    services = native_services(services)
    request = prepare_authoring_request(command_id='proposal apply', actor=actor,
        operations=[], request_id=request_id, dry_run=dry_run)
    actor, request_id = request.data['actor'], request.data['request_id']
    source = ProjectSource(root); _preflight(source)
    supplied = ProposalInput(source, operand, cwd)
    initial = supplied.original()
    audit.update(proposal_id=initial.data['id'], base=initial.data['base'])
    require(supplied.path == source.boundary.root / initial.path,
            'proposal_apply_requires_managed_original', exit_code=7)
    if not dry_run:
        replay = _replay(source, initial.data['id'], expected_revision, actor, request_id, audit)
        if replay is not None:
            return replay
    require(initial.data['revision'] == expected_revision, 'proposal_revision_conflict', exit_code=6)

    def prepare():
        original = supplied.original()
        require(original.data['revision'] == expected_revision, 'proposal_revision_conflict', exit_code=6)
        snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
        require(snapshot.raw.get(original.path) == original.source_bytes, 'proposal_input_changed', exit_code=6)
        evidence = assessment(snapshot, original, services)
        operations = [*original.data['change_plan']['operations'], operation(original, evidence)]
        preconditions = original.data['change_plan']['preconditions']
        folded = prepare_apply_candidates(snapshot.model, operations, metadata_policy_version='change-metadata-v1',
            actor=actor, planned_at=planned_at, preconditions=preconditions)
        target = folded.target_model
        after = ProposalOriginal(target.source_files[original.path], path=original.path)
        gates = apply_gates(snapshot, original, target, after, operations[-1], services)
        checked = prepare_change_target(snapshot.model, operations, change_plan_id=change_plan_id,
            request_id=request_id, actor=actor, planned_at=planned_at, scope_descriptor=_default_scope(),
            metadata_policy_version='change-metadata-v1', policy=POLICY, gates=gates, preconditions=preconditions)
        checked.require_valid()
        supplied.verify_current(); snapshot.verify_current()
        return snapshot, original, operations, checked, gates, target, after

    if dry_run:
        snapshot, original, operations, checked, gates, target, after = prepare()
        _preflight(source); snapshot.verify_current()
        return _result(operations, None, audit, dry_run=True)
    with project_lock(source.boundary.root, kind='writer', command='change apply',
            project_id=source.configuration.project_id, request_id=request_id,
            transaction_id=transaction_id) as held:
        replay = _replay(source, initial.data['id'], expected_revision, actor, request_id, audit)
        if replay is not None:
            return replay
        snapshot, original, operations, checked, gates, target, after = prepare()
        completion = _publish(snapshot, checked, gates, policy=POLICY, held=held,
                              transaction_id=transaction_id, authority=authority)
        _verify_completion(source, transaction_id, checked.plan, snapshot.model, target, original, after)
        return _result(operations, completion, audit)


def apply_command(invocation):
    from uuid import uuid4
    from ..bundles.errors import BundleError
    from ..model.errors import ModelError
    from ..security import SafetyViolation
    from ..srx.errors import SrxError
    from ..cli.results import CommandResult, FailureKind, OperationFailure
    audit = _initial()['audit']
    try:
        options = invocation.options
        revision = options['--expected-revision']
        require(revision.isascii() and revision.isdecimal() and int(revision) > 0,
                'proposal_expected_revision_required', exit_code=2)
        result = apply_project(invocation.resolved.project_root, invocation.arguments['proposal'],
            expected_revision=int(revision), actor={'actor_type': options['--actor-type'],
                'actor_id': options['--actor-id']}, planned_at=_now(), change_plan_id='apply-' + uuid4().hex,
            transaction_id='apply-' + uuid4().hex, authority=invocation.publication_authority,
            request_id=options.get('--request-id'), dry_run=options.get('--dry-run', False),
            cwd=invocation.resolved.working_directory, services=invocation.restore_services)
        return CommandResult(COMMAND, result=result)
    except (ModelError, BundleError, SrxError, SafetyViolation, OSError) as error:
        code = 7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError) else getattr(error, 'exit_code', 3)
        reason = getattr(error, 'reason', 'proposal_apply_failed')
        audit.update(ended_at=_now(), outcome='failed', diagnostics=[{'reason': reason}])
        facts = {'reason': reason, 'audit': getattr(error, 'proposal_audit', audit)}
        if hasattr(error, 'write_state'):
            facts['write_state'] = error.write_state
        raise OperationFailure(FailureKind(code), reason, details=facts) from error
