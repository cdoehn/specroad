"""Bound historical bytes, retry identity and real interrupted writer state."""
from base64 import b64decode, b64encode
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.changes import PublicationAuthority, prepare_authoring_request
from specroad.model.audit_values import Actor, Revision, UtcTimestamp
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.proposals import ProposalOriginal, ProposalContext, ProposalRevision
from specroad.proposals.history import ProposalInputs
from specroad.proposals.observations import ProposalVerifier
from specroad.proposals._review_control import prepare_control_candidates, read_review_start_observations
from specroad.proposals.review_start import review_start_project, _fresh_reports, _operation
from specroad.recovery.services import RestoreServices
from support.proposal_validation import validation_project
from support.read_only import inventory
from test_proposal_review_start import options


def test_registered_cli_writes_with_explicit_host_authority_and_ci_request(tmp_path):
    from specroad.cli.application import dispatch_result
    from specroad.cli.invocation_context import InvocationContextBuilder
    root = tmp_path / 'project'
    _, original = validation_project(root)
    outcome = dispatch_result(['proposal', 'review', 'start', original.data['id'],
        '--expected-revision', '1', '--actor-type', 'ci', '--actor-id', 'synthetic-ci',
        '--request-id', 'ci-review'], cwd=root, context_builder=InvocationContextBuilder(
            publication_authority=options()['authority']))
    assert outcome.exit_code == 0, outcome.as_dict()
    assert outcome.result['revision'] == 2 and outcome.result['proposal_status'] == 'in_review'
    assert outcome.result['review_validity']['current_approval'] is False
    assert len(json.loads((root / original.path).read_bytes())['control_history']) == 3


def test_same_request_replays_confirmed_completion_and_actor_or_revision_conflicts(tmp_path):
    root = tmp_path / 'project'
    _, original = validation_project(root, changed=True)
    supplied = options(request_id='stable-request')
    supplied['actor'] = {'actor_type': 'ai', 'actor_id': 'synthetic-agent'}
    first = review_start_project(root, original.data['id'], **supplied)
    before = inventory(root)
    retry = dict(supplied, planned_at='2026-11-11T00:00:00Z', transaction_id='another-transaction')
    second = review_start_project(root, original.data['id'], **retry)
    assert second['replayed'] and not second['project_writes_performed']
    assert first['completion']['current_target_verified'] is True
    assert second['completion'] == {**first['completion'], 'current_target_verified': False}
    assert second['revision'] == first['revision'] == 2
    assert inventory(root) == before
    for conflict in ({'expected_revision': 2}, {'actor': {'actor_type': 'human', 'actor_id': 'other'}}):
        with pytest.raises(ModelError) as error:
            review_start_project(root, original.data['id'], **dict(retry, **conflict))
        assert error.value.exit_code == 6 and error.value.reason == 'proposal_request_conflict'
        assert inventory(root) == before


def test_denied_host_authority_and_stale_basis_leave_proposal_bytes_unchanged(tmp_path):
    root = tmp_path / 'project'
    basis, original = validation_project(root)
    supplied = options()
    supplied['authority'] = PublicationAuthority('synthetic-denied-host', '1', lambda request: False)
    with pytest.raises(ModelError) as denied:
        review_start_project(root, original.data['id'], **supplied)
    assert denied.value.exit_code == 7
    assert (root / original.path).read_bytes() == original.source_bytes
    assert not list((root / '.specroad').glob('transactions/*/journal.json'))
    goal = next(d for d in basis.documents if json.loads(d.content)['artifact_type'] == 'goal')
    value = json.loads(goal.content); value['title'] = 'A different current basis'
    (root / goal.path).write_bytes(jcs(value))
    with pytest.raises(ModelError) as stale:
        review_start_project(root, original.data['id'], **options())
    assert stale.value.exit_code == 6
    assert (root / original.path).read_bytes() == original.source_bytes


def test_prepared_journal_failure_preserves_draft_and_native_recovery_evidence(tmp_path, monkeypatch):
    from specroad import changes
    root = tmp_path / 'project'
    _, original = validation_project(root)
    stage = changes.stage_building_journal
    def interrupt(*args, **kwargs):
        stage(*args, **kwargs)
        raise OSError('synthetic-interruption-after-durable-staging')
    monkeypatch.setattr(changes, 'stage_building_journal', interrupt)
    with pytest.raises(OSError, match='synthetic-interruption-after-durable-staging'):
        review_start_project(root, original.data['id'], **options(request_id='interrupted'))
    assert (root / original.path).read_bytes() == original.source_bytes
    journals = list((root / '.specroad').glob('transactions/*/journal.json'))
    assert len(journals) == 1 and json.loads(journals[0].read_bytes())['state'] == 'prepared'
    assert not list((root / '.specroad').glob('requests/*.json'))
    before = inventory(root)
    with pytest.raises(Exception):
        review_start_project(root, original.data['id'], **options(request_id='interrupted'))
    assert inventory(root) == before


def test_content_revision_two_needs_complete_explicit_original_contexts(tmp_path):
    root = tmp_path / 'project'
    _, first = validation_project(root, changed=True)
    first_model = InspectionSnapshot(root, None).model
    value = first.data; value['title'] = 'A genuine authored revision'
    second = ProposalRevision(first, value, expected_revision=Revision(1),
        actor=Actor('human', 'synthetic-author'), planned_at=UtcTimestamp('2026-11-09T00:00:00Z')).after
    (root / first.path).write_bytes(second.source_bytes)
    second_model = InspectionSnapshot(root, None).model
    def no_history(observation):
        raise AssertionError('This draft has no review or control observations')
    inputs = ProposalInputs((first, second), (ProposalContext(first, first_model),
        ProposalContext(second, second_model)), (), (), ProposalVerifier('synthetic-originals', '1', no_history))
    supplied = options(); supplied['expected_revision'] = 2
    with pytest.raises(ModelError):
        review_start_project(root, first.data['id'], **supplied)
    assert (root / first.path).read_bytes() == second.source_bytes
    services = RestoreServices(proposal_inputs=lambda model, original: inputs)
    result = review_start_project(root, first.data['id'], **dict(supplied, services=services))
    after = json.loads((root / first.path).read_bytes())
    assert (result['revision'], result['content_revision'], after['proposal_status']) == (3, 2, 'in_review')
    assert after['content_sha256'] == second.binding.content_sha256


@pytest.fixture(scope='module')
def control_originals(tmp_path_factory):
    # Immutable decoder inputs only. No cached write, authority, live gate or
    # reusable passing result; every writer test above obtains fresh observations.
    root = tmp_path_factory.mktemp('review-control-originals') / 'project'
    _, original = validation_project(root)
    snapshot = InspectionSnapshot(root, None)
    validation, check = _fresh_reports(snapshot, original, RestoreServices())
    operation = _operation(original, validation, check)
    supplied = options()
    folded = prepare_control_candidates(snapshot.model, [operation], metadata_policy_version='change-metadata-v1',
        actor=supplied['actor'], planned_at=supplied['planned_at'])
    after = ProposalOriginal(jcs(folded.candidates[0].data), path=original.path)
    return original, after, ProposalContext(original, snapshot.model), jcs(operation)


def test_stored_control_reader_binds_complete_bytes_but_never_grants_authority(control_originals):
    original, after, context, encoded = control_originals
    rows = read_review_start_observations(after, 0, context)
    assert len(rows) == 3 and all(row.context == context for row in rows)
    assert rows[1].result_bytes == rows[2].result_bytes
    for row in rows:
        assert row.data['result_sha256'] == sha256(row.result_bytes).hexdigest()
    with pytest.raises(ModelError) as error:
        prepare_authoring_request(command_id='change apply', actor=options()['actor'],
            operations=[json.loads(encoded)])
    assert error.value.reason == 'proposal_control_specialist_required'


@pytest.mark.parametrize('mutation', ['bytes', 'hash', 'context', 'actor', 'revision', 'extra', 'order'])
def test_stored_control_rejects_tampering_even_after_outer_content_rehash(control_originals, mutation):
    original, after, context, _ = control_originals
    value = after.data
    row = value['control_history'][1]
    if mutation == 'bytes':
        raw = b64decode(row['result_bytes_base64']) + b' '
        row['result_bytes_base64'] = b64encode(raw).decode('ascii')
        row['result_sha256'] = sha256(raw).hexdigest()
    elif mutation == 'hash': row['result_sha256'] = '0' * 64
    elif mutation == 'context':
        report = json.loads(b64decode(row['result_bytes_base64']))
        report['context_sha256'] = '0' * 64
        report['result_sha256'] = canonical_json_sha256({k: v for k, v in report.items() if k != 'result_sha256'})
        raw = jcs(report); row['result_bytes_base64'] = b64encode(raw).decode('ascii')
        row['result_sha256'] = sha256(raw).hexdigest()
    elif mutation == 'actor': row['actor']['actor_id'] = 'other-actor'
    elif mutation == 'revision': row['observed_revision'] = True
    elif mutation == 'extra': row['origin_verified'] = True
    else: value['control_history'].reverse()
    tampered = ProposalOriginal(jcs(value), path=after.path)
    with pytest.raises(ModelError):
        read_review_start_observations(tampered, 0, context)
