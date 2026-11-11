"""Human quorum, current provenance and recovery boundaries under adversarial inputs."""
from dataclasses import replace
from base64 import b64decode, b64encode
from hashlib import sha256
import json

import pytest

from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.proposals import ProposalOriginal, ProposalContext
from specroad.proposals.review_decision import review_project
from specroad.proposals._decision_control import read_review_observations
from specroad.changes import PublicationAuthority
from specroad.cli.application import dispatch_result
from specroad.cli.invocation_context import InvocationContextBuilder
from support.proposal_decisions import ReviewCase
from support.read_only import inventory


def test_same_human_is_counted_once_and_different_human_completes_quorum(tmp_path):
    case = ReviewCase(tmp_path / 'project')
    case.decide()
    second = case.decide()
    assert second['proposal_status'] == 'in_review'
    assert second['review_validity']['effective_human_approvals'] == 1
    assert len(case.original.data['reviews']) == 2
    assert len(case.original.data['control_history']) == 3
    final = case.decide('other-human')
    assert final['proposal_status'] == 'approved'
    assert final['review_validity']['effective_human_approvals'] == 2


@pytest.mark.parametrize('actor_type', ['ai', 'ci'])
@pytest.mark.parametrize('dry_run', [False, True])
def test_nonhuman_review_is_security_failure_before_any_write(tmp_path, actor_type, dry_run):
    case = ReviewCase(tmp_path / 'project')
    before = inventory(case.root)
    result = dispatch_result(['proposal', 'review', case.original.data['id'], '--expected-revision', '2',
        '--decision', 'approved', '--actor-type', actor_type, '--actor-id', 'machine', '--request-id', 'nonhuman',
        *(['--dry-run'] if dry_run else [])], cwd=case.root,
        context_builder=InvocationContextBuilder(restore_services=case.services, publication_authority=case.authority))
    assert result.exit_code == 7, result.as_dict()
    assert inventory(case.root) == before


def test_withdrawn_host_decision_does_not_count_toward_current_quorum(tmp_path):
    case = ReviewCase(tmp_path / 'project')
    case.decide()
    case.current_decisions = False
    result = case.decide('second-human')
    assert result['proposal_status'] == 'in_review'
    assert result['review_validity']['effective_human_approvals'] == 1


def test_native_request_replay_is_exact_and_changed_decision_or_comment_conflicts(tmp_path):
    case = ReviewCase(tmp_path / 'project', minimum=1)
    options = case.options(request_id='stable-review')
    result = review_project(case.root, case.original.data['id'], **options)
    case.capture(); before = inventory(case.root)
    replayed = review_project(case.root, case.original.data['id'], **options)
    assert replayed['replayed'] and not replayed['project_writes_performed']
    assert replayed['revision'] == result['revision'] == 3
    assert replayed['review_validity'] == result['review_validity']
    assert inventory(case.root) == before
    for change in ({'decision': 'rejected'}, {'comment': 'changed'}, {'expected_revision': 3},
                   {'actor': {'actor_type': 'human', 'actor_id': 'another'}}):
        with pytest.raises(Exception) as error:
            review_project(case.root, case.original.data['id'], **dict(options, **change))
        assert error.value.exit_code == 6
        assert inventory(case.root) == before


@pytest.mark.parametrize('fault', ['missing-originals', 'denied', 'revision', 'stale-basis', 'external'])
def test_invalid_inputs_or_authority_never_publish_decision(tmp_path, fault):
    case = ReviewCase(tmp_path / 'project')
    operand = case.original.data['id']; options = case.options()
    if fault == 'missing-originals':
        options['services'] = None
    elif fault == 'denied':
        options['authority'] = PublicationAuthority('synthetic-denied-host', '1', lambda request: False)
    elif fault == 'revision':
        options['expected_revision'] = 1
    elif fault == 'external':
        outside = tmp_path / 'outside.json'; outside.write_bytes(case.original.source_bytes)
        operand = str(outside)
    else:
        from specroad.authoring._inspection_snapshot import InspectionSnapshot
        model = InspectionSnapshot(case.root, None).model
        goal = next(d for d in model.documents if json.loads(d.content)['artifact_type'] == 'goal')
        value = json.loads(goal.content); value['statement'] = 'Different specification basis'
        (case.root / goal.path).write_bytes(canonical_json_bytes(value))
    before = inventory(case.root)
    with pytest.raises(Exception):
        review_project(case.root, operand, **options)
    assert inventory(case.root) == before


def test_real_staging_failure_preserves_original_and_recovery_journal(tmp_path, monkeypatch):
    from specroad import changes
    case = ReviewCase(tmp_path / 'project')
    before = case.original.source_bytes
    stage = changes.stage_building_journal
    def interrupt(*args, **kwargs):
        stage(*args, **kwargs)
        raise OSError('synthetic-interrupted-review-staging')
    monkeypatch.setattr(changes, 'stage_building_journal', interrupt)
    options = case.options(request_id='interrupted-review')
    with pytest.raises(OSError, match='synthetic-interrupted-review-staging'):
        review_project(case.root, case.original.data['id'], **options)
    assert (case.root / case.original.path).read_bytes() == before
    journal = case.root / '.specroad/transactions' / options['transaction_id'] / 'journal.json'
    assert json.loads(journal.read_bytes())['state'] == 'prepared'
    observed = inventory(case.root)
    with pytest.raises(Exception):
        review_project(case.root, case.original.data['id'], **options)
    assert inventory(case.root) == observed


@pytest.fixture(scope='module')
def immutable_review_originals(tmp_path_factory):
    # Only immutable completed originals for decoder cases; never reused live gates.
    case = ReviewCase(tmp_path_factory.mktemp('review-originals') / 'project')
    context = case.contexts[-1]
    case.decide()
    return case.original, context


@pytest.mark.parametrize('fault', ['hash', 'bytes', 'binding', 'context', 'actor', 'metadata', 'revision', 'extra'])
def test_stored_decision_rejects_tampering_without_treating_hash_as_authority(immutable_review_originals, fault):
    original, context = immutable_review_originals
    value = original.data; row = value['reviews'][-1]
    if fault == 'hash': row['result_sha256'] = '0' * 64
    elif fault == 'bytes':
        raw = b64decode(row['result_bytes_base64']) + b' '
        row['result_bytes_base64'] = b64encode(raw).decode(); row['result_sha256'] = sha256(raw).hexdigest()
    elif fault == 'binding': row['binding']['content_revision'] += 1
    elif fault == 'context':
        proof = json.loads(b64decode(row['result_bytes_base64']))
        proof['context_sha256'] = '0' * 64
        proof['result_sha256'] = canonical_json_sha256({k: v for k, v in proof.items() if k != 'result_sha256'})
        raw = canonical_json_bytes(proof); row['result_bytes_base64'] = b64encode(raw).decode()
        row['result_sha256'] = sha256(raw).hexdigest()
    elif fault == 'actor': row['reviewer']['actor_type'] = 'ai'
    elif fault == 'metadata': value['updated_by']['actor_id'] = 'different'
    elif fault == 'revision': row['observed_revision'] = True
    else: row['authority'] = True
    tampered = ProposalOriginal(canonical_json_bytes(value), path=original.path)
    with pytest.raises(Exception):
        read_review_observations(tampered, context)


def test_late_loss_of_effective_human_decision_blocks_before_publication(tmp_path, monkeypatch):
    from specroad.proposals import _decision_checks
    case = ReviewCase(tmp_path / 'project')
    case.decide()
    before = inventory(case.root)
    native = _decision_checks.assessment
    def withdrawn(*args, **kwargs):
        case.current_decisions = False
        return native(*args, **kwargs)
    monkeypatch.setattr(_decision_checks, 'assessment', withdrawn)
    with pytest.raises(Exception):
        case.decide('second-human')
    assert inventory(case.root) == before


def test_generic_change_route_cannot_authorize_a_human_decision(tmp_path):
    from specroad.changes import prepare_authoring_request
    from specroad.proposals._decision_evidence import assessment, operation
    from specroad.authoring._inspection_snapshot import InspectionSnapshot
    case = ReviewCase(tmp_path / 'project')
    actor = case.options()['actor']
    raw = assessment(InspectionSnapshot(case.root, None), case.original, case.services)
    op = operation(case.original, raw, 'approved', None, actor)
    before = inventory(case.root)
    with pytest.raises(Exception) as error:
        prepare_authoring_request(command_id='change apply', actor=actor, operations=[op])
    assert error.value.reason == 'proposal_control_specialist_required'
    assert inventory(case.root) == before
