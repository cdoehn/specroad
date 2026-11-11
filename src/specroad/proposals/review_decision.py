"""Explicit human review decisions through the native transaction writer.

The report/observation service, deterministic control reducer and native writer
adapter have separate responsibilities. No technical check supplies the explicit human decision.
"""
from ..authoring._inspection_snapshot import InspectionSnapshot
from ..changes import (PublicationAuthority, TargetPolicy, prepare_change_target,
                       project_lock, prepare_authoring_request)
from ..changes._journal_codec import _transaction
from ..changes.target_model import _default_scope
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes
from ..recovery.services import native_services
from ..storage.project import ProjectSource
from ._check_report import _now
from ._decision_checks import gates as _gates
from ._decision_evidence import assessment, operation as _operation
from ._decision_control import COMMAND, GATE, prepare_review_candidates as prepare_control_candidates
from ._decision_result import result as _result
from ._review_transaction import _publish
from ._decision_transaction import replay as _replay
from ._validation_input import ProposalInput
from .project_validation import _preflight
from .values import ProposalOriginal, require


POLICY = TargetPolicy(COMMAND, '1', (GATE,))


def review_project(root, operand, *, expected_revision, decision, actor, planned_at,
                         change_plan_id, transaction_id, authority=None, request_id=None,
                         dry_run=False, comment=None, cwd=None, services=None):
    """Fresh full checks and exactly one physical revision, or no publication.

    A host supplies authority and historical contexts when needed. Actor names,
    report hashes and request IDs do not grant human approval or write rights.
    """
    require(type(expected_revision) is int and expected_revision > 0,
            'proposal_expected_revision_required', exit_code=2)
    require(type(dry_run) is bool, 'proposal_dry_run_boolean_required', exit_code=2)
    require(dry_run or type(authority) is PublicationAuthority,
            'proposal_host_publication_authority_required', exit_code=2)
    require(decision in ('approved', 'rejected'), 'proposal_review_decision_invalid', exit_code=2)
    require(comment is None or type(comment) is str, 'proposal_review_comment_invalid', exit_code=2)
    UtcTimestamp(planned_at)
    _transaction(transaction_id)
    require(type(change_plan_id) is str and bool(change_plan_id.strip()),
            'proposal_change_plan_identity_required', exit_code=2)
    services = native_services(services)
    from ..changes.authoring import normalize_authoring_actor
    normalized_actor = normalize_authoring_actor(actor)
    require(normalized_actor.actor_type == 'human',
            'human_review_required', exit_code=7)
    request = prepare_authoring_request(command_id='proposal review', actor=actor,
        operations=[], request_id=request_id, dry_run=dry_run)
    actor, request_id = request.data['actor'], request.data['request_id']
    source = ProjectSource(root)
    _preflight(source)
    supplied = ProposalInput(source, operand, cwd)
    initial = supplied.original()
    require(supplied.path == source.boundary.root / initial.path,
            'proposal_review_requires_managed_original', exit_code=7)
    if not dry_run:
        result = _replay(source, initial.data['id'], expected_revision, actor, request_id, decision, comment)
        if result is not None:
            return result
    require(initial.data['revision'] == expected_revision, 'proposal_revision_conflict', exit_code=6)
    require(initial.data['proposal_status'] == 'in_review', 'proposal_review_requires_in_review')

    def prepare():
        original = supplied.original()
        require(original.data['revision'] == expected_revision, 'proposal_revision_conflict', exit_code=6)
        require(original.data['proposal_status'] == 'in_review', 'proposal_review_requires_in_review')
        snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
        require(snapshot.raw.get(original.path) == original.source_bytes,
                'proposal_input_changed', exit_code=6)
        proof = assessment(snapshot, original, services)
        operation = _operation(original, proof, decision, comment, actor)
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
        return _result(operation, actor, None, dry_run=True)
    with project_lock(source.boundary.root, kind='writer', command='change apply',
            project_id=source.configuration.project_id, request_id=request_id,
            transaction_id=transaction_id) as held:
        result = _replay(source, initial.data['id'], expected_revision, actor, request_id, decision, comment)
        if result is not None:
            return result
        snapshot, original, operation, checked, gates = prepare()
        completion = _publish(snapshot, checked, gates, policy=POLICY, held=held,
                              transaction_id=transaction_id, authority=authority)
        return _result(operation, actor, completion)


def _command(invocation):
    from uuid import uuid4
    from ..cli.results import CommandResult, FailureKind, OperationFailure
    options = invocation.options
    revision = options['--expected-revision']
    if not revision.isascii() or not revision.isdecimal() or int(revision) < 1:
        raise OperationFailure(FailureKind.USAGE, 'proposal_expected_revision_required')
    result = review_project(invocation.resolved.project_root, invocation.arguments['proposal'],
        expected_revision=int(revision), decision=options['--decision'], comment=options.get('--comment'), actor={
            'actor_type': options['--actor-type'], 'actor_id': options['--actor-id']},
        planned_at=_now(), change_plan_id='review-' + uuid4().hex,
        transaction_id='review-' + uuid4().hex, authority=invocation.publication_authority,
        request_id=options.get('--request-id'), dry_run=options.get('--dry-run', False),
        cwd=invocation.resolved.working_directory, services=invocation.restore_services)
    return CommandResult(COMMAND, result=result)


def review_command(invocation):
    from ..bundles.errors import BundleError
    from ..model.errors import ModelError
    from ..security import SafetyViolation
    from ..srx.errors import SrxError
    from ..cli.results import FailureKind, OperationFailure
    try:
        return _command(invocation)
    except (ModelError, BundleError, SrxError, SafetyViolation, OSError) as error:
        code = 7 if isinstance(error, SafetyViolation) else 5 if isinstance(error, OSError) else getattr(error, 'exit_code', 3)
        reason = getattr(error, 'reason', 'proposal_review_failed')
        facts = {'reason': reason}
        if hasattr(error, 'write_state'):
            facts['write_state'] = error.write_state
        raise OperationFailure(FailureKind(code), reason, details=facts) from error
