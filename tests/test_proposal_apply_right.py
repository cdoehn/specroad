"""Retry identity, host provenance, byte races and native crash recovery."""
from base64 import b64decode, b64encode
from dataclasses import replace
import json
import multiprocessing
import os
from unittest.mock import patch

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.changes import PublicationAuthority
from specroad.cli.results import OperationFailure
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.proposals._apply_control import operation_proof
from specroad.proposals.apply import apply_project
from specroad.proposals.observations import ProposalVerifier
from support.proposal_apply import ApplyCase
from support.read_only import inventory, no_write_attempts


def test_confirmed_request_replays_after_basis_moves_without_a_second_write(tmp_path):
    case = ApplyCase(tmp_path / 'project')
    first = case.apply()
    path = next(d.path for d in case.before.documents if json.loads(d.content)['artifact_type'] == 'goal')
    changed = json.loads((case.root / path).read_bytes()); changed['statement'] = 'Later independent edit'
    (case.root / path).write_bytes(jcs(changed))
    before = inventory(case.root)
    with no_write_attempts():
        retry = case.apply(planned_at='2026-11-13T01:00:00Z', change_plan_id='retry-plan', transaction_id='retry')
    assert retry['replayed'] and not retry['project_writes_performed']
    assert retry['revision'] == first['revision']
    assert retry['completion'] == {**first['completion'], 'current_target_verified': False}
    assert retry['audit']['outcome'] == 'replayed'
    assert inventory(case.root) == before
    for differences in ({'expected_revision': first['revision']},
                        {'actor': {'actor_type': 'human', 'actor_id': 'another-applier'}}):
        with no_write_attempts(), pytest.raises(ModelError) as error:
            case.apply(**differences)
        assert error.value.reason == 'proposal_request_conflict'
        assert error.value.exit_code == 6 and inventory(case.root) == before


def test_applied_without_matching_request_is_not_implicitly_replayed(tmp_path):
    case = ApplyCase(tmp_path / 'project')
    first = case.apply(); before = inventory(case.root)
    with pytest.raises(ModelError) as error:
        case.apply(expected_revision=first['revision'], request_id='different-request')
    assert error.value.reason == 'proposal_apply_requires_approved'
    assert (case.root / case.original.path).read_bytes() == dict((p, b) for p, _, b, _ in before)[case.original.path]
    assert not list((case.root / '.specroad/transactions').glob('*/journal.json'))


@pytest.mark.parametrize('fault', ['missing', 'origin', 'actor', 'binding'])
def test_missing_or_forged_host_original_provenance_never_authorizes_apply(tmp_path, fault):
    from specroad.recovery.services import RestoreServices
    case = ApplyCase(tmp_path / 'project')
    def inputs(model, original):
        old = case.inputs(model, original)
        def verify(observation):
            proof = old.verifier.check(observation)
            changes = {'origin': {'origin_verified': False}, 'actor': {'actor_verified': False},
                       'binding': {'input_sha256': '0' * 64}}[fault]
            return replace(proof, **changes)
        return replace(old, verifier=ProposalVerifier('synthetic-rejected-origin', '1', verify))
    services = RestoreServices() if fault == 'missing' else RestoreServices(proposal_inputs=inputs)
    before = inventory(case.root)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        case.apply(dry_run=True, services=services)
    assert error.value.exit_code == (6 if fault == 'binding' else 7)
    assert inventory(case.root) == before


def test_authority_revocation_between_preparation_and_journal_is_rechecked(tmp_path):
    case = ApplyCase(tmp_path / 'project')
    def revoke(request):
        case.current_decisions = False
        return True
    authority = PublicationAuthority('synthetic-revoking-host', '1', revoke)
    with pytest.raises(ModelError):
        case.apply(authority=authority)
    assert (case.root / case.original.path).read_bytes() == case.original.source_bytes
    for path, raw in case.before.source_files.items():
        assert (case.root / path).read_bytes() == raw
    assert not list((case.root / '.specroad/requests').glob('*synthetic-apply*'))


@pytest.mark.parametrize('kind', ['proposal', 'target'])
def test_publication_race_is_detected_without_overwriting_foreign_bytes(tmp_path, kind):
    case = ApplyCase(tmp_path / 'project')
    path = case.original.path if kind == 'proposal' else next(
        d.path for d in case.before.documents if json.loads(d.content)['artifact_type'] == 'goal')
    foreign = json.loads((case.root / path).read_bytes()); foreign['title'] = 'Concurrent foreign input'
    raw = jcs(foreign)
    def change(request):
        (case.root / path).write_bytes(raw)
        return True
    authority = PublicationAuthority('synthetic-racing-host', '1', change)
    with pytest.raises(ModelError):
        case.apply(authority=authority)
    assert (case.root / path).read_bytes() == raw
    assert not list((case.root / '.specroad/transactions').glob('*/committed.json'))


@pytest.mark.parametrize('fault', ['version', 'quorum', 'status', 'extra', 'hash'])
def test_apply_evidence_cannot_be_a_review_or_self_declared_approval(tmp_path, fault):
    case = ApplyCase(tmp_path / 'project')
    # Only the native dry-run reducer supplies this valid starting operation.
    from specroad.proposals._apply_control import assessment, operation
    snapshot = InspectionSnapshot(case.root, None)
    value = operation(case.original, assessment(snapshot, case.original, case.services))
    report = json.loads(b64decode(value['apply_check']['assessment_bytes_base64']))
    if fault == 'version': report['format_version'] = 'proposal-review-assessment-v2'
    if fault == 'quorum': report['history']['effective_human_approvals'] = 0
    if fault == 'status': report['history']['observed_status'] = 'in_review'
    if fault == 'extra': report['write_authorized'] = True
    report['result_sha256'] = canonical_json_sha256({k: v for k, v in report.items() if k != 'result_sha256'})
    if fault == 'hash': report['result_sha256'] = '0' * 64
    value['apply_check']['assessment_bytes_base64'] = b64encode(jcs(report)).decode('ascii')
    with no_write_attempts(), pytest.raises(ModelError):
        operation_proof(value)


def test_live_gate_rejects_fully_rehashed_foreign_assessment(tmp_path):
    from specroad.proposals._apply_control import assessment, operation, prepare_apply_candidates
    from specroad.proposals._apply_checks import gates
    from specroad.proposals.apply import POLICY
    from specroad.proposals import ProposalOriginal
    from specroad.changes import prepare_change_target
    from specroad.changes.target_model import _default_scope
    case = ApplyCase(tmp_path / 'project')
    snapshot = InspectionSnapshot(case.root, None)
    report = json.loads(assessment(snapshot, case.original, case.services))
    report['native_check']['target_sources_sha256'] = '0' * 64
    report['result_sha256'] = canonical_json_sha256({k: v for k, v in report.items() if k != 'result_sha256'})
    control = operation(case.original, jcs(report))
    operations = [*case.original.data['change_plan']['operations'], control]
    options = case.apply_options()
    folded = prepare_apply_candidates(snapshot.model, operations, metadata_policy_version='change-metadata-v1',
        actor=options['actor'], planned_at=options['planned_at'])
    target = folded.target_model
    after = ProposalOriginal(target.source_files[case.original.path], path=case.original.path)
    registered = gates(snapshot, case.original, target, after, control, case.services)
    before = inventory(case.root)
    with no_write_attempts():
        result = prepare_change_target(snapshot.model, operations, metadata_policy_version='change-metadata-v1',
            actor=options['actor'], planned_at=options['planned_at'], change_plan_id='tampered', request_id='tampered',
            scope_descriptor=_default_scope(), policy=POLICY, gates=registered)
    assert not result.target_validated
    with pytest.raises(ModelError): result.require_valid()
    assert inventory(case.root) == before


def _crash(root, phase, retained):
    from support.proposal_apply import restore_apply_host
    case = restore_apply_host(root, retained)
    from specroad.proposals import _review_transaction as writer
    real = writer.changes.stage_building_journal if phase == 'prepared' else writer.publish_prepared_journal
    def stop(*args, **kwargs):
        real(*args, **kwargs)
        os._exit(91)  # Real process loss: no context-manager cleanup or finalizers.
    owner, name = (writer.changes, 'stage_building_journal') if phase == 'prepared' else (writer, 'publish_prepared_journal')
    with patch.object(owner, name, stop):
        case.apply()
    os._exit(92)


def _recover(case, phase):
    from specroad.changes import (PreparedJournal, CommittingJournal, LockRecord, transaction_recovery_lock,
        prepare_discard_recovery, discard_unpublished_transaction, complete_published_transaction,
        cleanup_recovered_transaction)
    from specroad.changes._recovery_terminal import read_terminal_journal
    from support.recovery import RECOVER
    transaction = 'synthetic-apply'
    raw = (case.root / '.specroad/transactions' / transaction / 'journal.json').read_bytes()
    journal = (PreparedJournal if phase == 'prepared' else CommittingJournal)(raw)
    project_id = case.before.configuration.project_id
    proof = prepare_discard_recovery(case.root, transaction, expected_project_id=project_id,
        expected_journal_sha256=journal.sha256) if phase == 'prepared' else None
    lock = LockRecord((case.root / '.specroad/locks/project.json').read_bytes())
    with transaction_recovery_lock(case.root, transaction, project_id=project_id,
        request_id=journal.data['request_id'], command='recover discard' if phase == 'prepared' else 'recover run',
        expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256, authority=RECOVER,
        actor=case.apply_options()['actor'], reason='Explicit synthetic Proposal recovery', force=True) as held:
        if phase == 'prepared':
            done = discard_unpublished_transaction(proof, transaction, held_lock=held, authority=RECOVER,
                actor=case.apply_options()['actor'], reason='Explicit synthetic discard',
                expected_journal_sha256=journal.sha256)
            assert done.data['discard_completed']
        else:
            done = complete_published_transaction(transaction, held_lock=held, authority=RECOVER,
                expected_journal_sha256=journal.sha256)
            assert done.data['commit_completed']
            terminal = read_terminal_journal(held._files, transaction)
            done = cleanup_recovered_transaction(transaction, held_lock=held, authority=RECOVER,
                expected_journal_sha256=terminal.sha256)
            assert done.data['cleanup_completed']


@pytest.mark.parametrize('phase', ['prepared', 'published'])
def test_real_process_loss_requires_native_recovery_then_exactly_one_apply(tmp_path, phase):
    case = ApplyCase(tmp_path / 'project')
    # Transfer actual retained originals, never worker threads or closures.
    retained = [(o.path, o.source_bytes, dict(c.basis.source_files), c.sha256)
                for o, c in zip(case.originals, case.contexts)]
    child = multiprocessing.get_context('spawn').Process(
        target=_crash, args=(case.root, phase, retained))
    child.start()
    try:
        # Native preparation/publication has no fixed per-test time contract.
        # Wait for the real crash boundary; the outer runner owns cancellation.
        child.join()
        assert child.exitcode == 91
    finally:
        if child.is_alive():
            child.kill(); child.join()
        child.close()
    before = inventory(case.root)
    with pytest.raises(OperationFailure) as blocked:
        case.apply()
    assert int(blocked.value.kind) == 5
    assert inventory(case.root) == before
    _recover(case, phase)
    if phase == 'prepared':
        assert all((case.root / path).read_bytes() == raw for path, raw in case.before.source_files.items())
        # Discard receipts retain the old transaction ID; a fresh explicit retry
        # uses a new transaction/request and never overwrites that evidence.
        result = case.apply(transaction_id='after-recovery', request_id='after-recovery')
        assert not result['replayed'] and result['project_writes_performed']
    else:
        before = inventory(case.root)
        with no_write_attempts():
            result = case.apply(transaction_id='after-recovery')
        assert result['replayed'] and not result['project_writes_performed']
        assert inventory(case.root) == before
    saved = json.loads((case.root / case.original.path).read_bytes())
    assert saved['revision'] == case.original.data['revision'] + 1
    assert len(saved['control_history']) == len(case.original.data['control_history']) + 1
    for row in saved['change_plan']['result_artifacts']:
        goal = row['artifact']
        path = next(d.path for d in case.before.documents if json.loads(d.content)['id'] == goal['id'])
        assert json.loads((case.root / path).read_bytes()) == goal


def test_normalization_keeps_inner_byte_targets_and_semantic_metadata(tmp_path):
    from support.proposal_apply import normalization_change
    case = ApplyCase(tmp_path / 'project', plan_factory=normalization_change)
    original = case.original
    source = case.before.source_files
    result = case.apply()
    inputs, model = case.completion_inputs()
    for op in original.data['change_plan']['operations']:
        path = op['path']
        from hashlib import sha256
        assert sha256(model.source_files[path]).hexdigest() == op['target_byte_sha256']
        assert model.source_files[path] != source[path]
        assert json.loads(model.source_files[path]) == json.loads(source[path])
    assert result['audit']['changed_ids'] == [original.data['id']]
    assert case.requests[-1].plan.data['result_artifacts'] == [
        {'artifact': inputs.originals[-1].data, 'sha256': canonical_json_sha256(inputs.originals[-1].data)}]
    before = inventory(case.root)
    with no_write_attempts():
        replay = case.apply(transaction_id='normalization-retry')
    assert replay['replayed'] and not replay['project_writes_performed']
    assert inventory(case.root) == before


@pytest.mark.parametrize('boundary', ['journal', 'completion'])
def test_normalization_rejects_foreign_configuration_after_publication(tmp_path, monkeypatch, boundary):
    from specroad.proposals import _review_transaction as writer
    from support.proposal_apply import normalization_change
    case = ApplyCase(tmp_path / 'project', plan_factory=normalization_change)
    name = 'publish_prepared_journal' if boundary == 'journal' else 'cleanup_completed_transaction'
    real = getattr(writer, name)
    foreign = []
    def change(*args, **kwargs):
        result = real(*args, **kwargs)
        path = case.root / 'specroad.json'
        raw = path.read_bytes() + b'\n'
        path.write_bytes(raw); foreign.append(raw)
        return result
    monkeypatch.setattr(writer, name, change)
    with pytest.raises(ModelError) as rejected:
        case.apply()
    assert rejected.value.reason == 'publication_configuration_changed'
    assert foreign and (case.root / 'specroad.json').read_bytes() == foreign[0]


def test_native_pending_preflight_keeps_failure_kind_and_audit_at_public_boundary(tmp_path, monkeypatch):
    from specroad import changes
    from specroad.cli.application import dispatch_result
    from specroad.cli.invocation_context import InvocationContextBuilder
    case = ApplyCase(tmp_path / 'project')
    real = changes.stage_building_journal
    def interrupted(*args, **kwargs):
        real(*args, **kwargs)
        raise OSError('synthetic durable staging failure')
    monkeypatch.setattr(changes, 'stage_building_journal', interrupted)
    with pytest.raises(OSError): case.apply()
    before = inventory(case.root)
    result = dispatch_result(['proposal', 'apply', case.original.data['id'], '--expected-revision',
        str(case.original.data['revision']), '--actor-type', 'human', '--actor-id', 'synthetic-applier'],
        cwd=case.root, context_builder=InvocationContextBuilder(restore_services=case.services,
                                                               publication_authority=case.authority))
    assert result.exit_code == 5, result.as_dict()
    assert inventory(case.root) == before
    facts = result.as_dict()['summary']
    assert facts['reason'] == 'recovery_required'
    assert facts['preflight']['reason'] == 'recovery_required'
    assert facts['preflight']['normal_operation_started'] is False
    assert facts['audit']['outcome'] == 'failed'
    assert facts['audit']['diagnostics'] == [{'reason': 'recovery_required'}]
    assert (case.root / case.original.path).read_bytes() == case.original.source_bytes


@pytest.mark.parametrize('invalid', ['stale-basis', 'lost-quorum'])
def test_known_stale_approval_is_rejected_before_even_opening_the_writer(tmp_path, invalid):
    case = ApplyCase(tmp_path / 'project')
    if invalid == 'lost-quorum':
        case.current_decisions = False
    else:
        path = next(d.path for d in case.before.documents if json.loads(d.content)['artifact_type'] == 'goal')
        value = json.loads((case.root / path).read_bytes()); value['statement'] = 'New independent basis'
        (case.root / path).write_bytes(jcs(value))
    before = inventory(case.root)
    with no_write_attempts(), pytest.raises(ModelError) as rejected:
        case.apply()
    assert rejected.value.exit_code == (6 if invalid == 'stale-basis' else 3)
    assert inventory(case.root) == before and not case.requests


@pytest.mark.parametrize('boundary', ['external-file', 'symlink'])
def test_apply_cannot_publish_from_a_foreign_or_redirected_original(tmp_path, boundary):
    case = ApplyCase(tmp_path / 'project')
    external = tmp_path / 'external.json'; external.write_bytes(case.original.source_bytes)
    operand = str(external)
    if boundary == 'symlink':
        stored = case.root / case.original.path
        stored.unlink(); stored.symlink_to(external)
        operand = case.original.data['id']
    before = inventory(tmp_path)
    from specroad.security import SafetyViolation
    with no_write_attempts(), pytest.raises((ModelError, SafetyViolation, OperationFailure)):
        apply_project(case.root, operand, **case.apply_options(dry_run=True))
    assert inventory(tmp_path) == before
