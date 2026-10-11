"""Saved preview plans, real native publication, original audit and replay."""
import json
from unittest.mock import patch

import pytest

from specroad.authoring.plans import preview_authoring_request
from specroad.authoring.execution import apply_authoring_plan
from specroad.authoring import execution
from specroad.authoring.creation import create_artifact, _draft
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.authoring.update import update_artifact, normalize_artifact_update_input
from specroad.authoring.lifecycle import (transition_artifact, retire_artifact,
    normalize_transition_input, normalize_retire_input)
from specroad.authoring.relations import add_relation, remove_relation
from specroad.authoring.reviews import record_relation_review
from specroad.authoring.negative_reviews import record_coupled_relation_review
from specroad.changes import (AuthoringError, ChangePlan, ChangePlanError, ChangeOperation,
    PublicationAuthority, PublicationCheckError, inspect_project_lock)
from specroad.changes.relation_inputs import normalize_relation_add_input, _addition
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.identities import IdentityInventory
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.identity_tokens import encode128
from specroad.model.relation_values import RelationIdentity
from specroad.model.paths import artifact_path
from specroad.changes.receipt_values import TransactionReceipt
from support.read_only import inventory as file_inventory, no_write_attempts
from test_artifact_creation import project
from test_authoring_inputs import fields
from test_relation_authoring import stored_project, inventory as relation_inventory
from test_relation_review_authoring import planned as confirmed_plan
from test_relation_review_authoring import ACTOR as REVIEW_ACTOR, TIME as REVIEW_TIME, ENTROPY as REVIEW_ENTROPY, REASON as REVIEW_REASON
from test_negative_relation_review import negative_project, operation as negative_operation
from test_negative_relation_review import ACTOR as NEGATIVE_ACTOR, TIME as NEGATIVE_TIME, ENTROPY as NEGATIVE_ENTROPY, REASON as NEGATIVE_REASON

ACTOR = {'actor_type': 'human', 'actor_id': 'plan-editor'}
TIME = '2026-10-11T09:00:00Z'
ENTROPY = b'\x31' * 16
KINDS = ('create', 'update', 'transition', 'retire', 'add', 'remove', 'confirmed', 'rejected')


def scenario(root, kind):
    actor, time, entropy, gates = ACTOR, TIME, ENTROPY, ()
    if kind == 'create':
        model, ids = project(root)
        prepared = normalize_artifact_create_input('need', fields('need'))
        identity = ArtifactIdentity('SR-NEED-' + encode128(entropy), 'random128-v1', 'need', 'SR')
        artifact = _draft(prepared, identity, actor, time, model.configuration)
        op = ChangeOperation({'op': 'create', 'artifact': artifact, 'result_id': identity.id})
        command = 'artifact.create'
        def direct(options): return create_artifact(model, prepared, inventory=ids, **options)
    elif kind == 'rejected':
        model, source, _, gates = negative_project(root)
        actor, time, entropy = NEGATIVE_ACTOR, NEGATIVE_TIME, NEGATIVE_ENTROPY
        op = negative_operation(model, source); command = 'relation.review'
        ids = IdentityInventory('SR', [a['id'] for a in model.artifacts], (), ())
        def direct(options):
            return record_coupled_relation_review(model, source['id'], source['relations'][0]['relation_id'],
                decision='rejected', reason=NEGATIVE_REASON, expected_revision=4, inventory=ids, **options)
    else:
        model, source, goals = stored_project(root, with_edges=kind in ('remove', 'confirmed'))
        if kind == 'update':
            op = normalize_artifact_update_input(source, expected_revision=7,
                options=[('--set', '/statement="The saved plan supplies this exact statement."')])
            command = 'artifact.update'
            def direct(options): return update_artifact(model, op, **options)
        elif kind in ('transition', 'retire'):
            op = (normalize_transition_input(source, to='retired', reason='Planned closure.')
                if kind == 'transition' else normalize_retire_input(source,
                    reason='Planned closure.', expected_revision=7))
            command = 'lifecycle.transition'
            def direct(options):
                return (transition_artifact if kind == 'transition' else retire_artifact)(model, op, **options)
        elif kind == 'add':
            intent = normalize_relation_add_input(source['id'], 'addresses', goals[0]['id'], rationale='Planned link.')
            identity = RelationIdentity('REL-' + encode128(entropy), 'random128-v1')
            op = _addition(intent, identity, actor, time); command = 'relation.add'
            def direct(options):
                return add_relation(model, source['id'], 'addresses', goals[0]['id'],
                    inventory=relation_inventory(model), rationale='Planned link.', **options)
        elif kind == 'remove':
            relation = source['relations'][0]
            op = ChangeOperation({'op': 'relation_remove', 'source': source['id'],
                'relation_id': relation['relation_id'], 'expected_sha256': canonical_json_sha256(relation),
                'reason': 'Planned removal.'})
            command = 'relation.remove'
            def direct(options):
                return remove_relation(model, source['id'], relation['relation_id'],
                    expected_sha256=canonical_json_sha256(relation), reason='Planned removal.', **options)
        else:
            actor, time, entropy = REVIEW_ACTOR, REVIEW_TIME, REVIEW_ENTROPY
            checked, _ = confirmed_plan(model, source)
            op = checked.plan.operations[0]; command = 'relation.review'
            ids = IdentityInventory('SR', [a['id'] for a in model.artifacts], (), ())
            def direct(options):
                return record_relation_review(model, source['id'], source['relations'][0]['relation_id'],
                    decision='confirmed', reason=REVIEW_REASON, expected_revision=7, inventory=ids, **options)
    options = dict(actor=actor, planned_at=time, change_plan_id='CP-preview', request_id='preview-request', gates=gates)
    return model, command, op, options, direct, entropy


def preview(model, command, op, options, **extra):
    return preview_authoring_request(model, command, [op.data], **options, **extra)


def saved(result):
    return ChangePlan(canonical_json_bytes(result['plan']))


def assert_effects(root, before, result, kind):
    planned = result['plan']['result_artifacts']
    changed = set()
    for item in planned:
        artifact = item['artifact']; path = artifact_path(artifact['artifact_type'], artifact['id'], 'SR')
        actual = json.loads((root / path).read_bytes())
        assert actual == artifact and canonical_json_sha256(actual) == item['sha256']
        changed.add(path)
    after = {row[0]: row[1:] for row in file_inventory(root)}
    for path, *value in before:
        if path not in changed: assert after[path] == tuple(value)
    artifacts = [entry['artifact'] for entry in planned]
    if kind == 'create':
        assert [(a['artifact_type'], a['revision'], a['maturity']) for a in artifacts] == [('need', 1, 'draft')]
    elif kind == 'update':
        assert artifacts[0]['statement'] == 'The saved plan supplies this exact statement.'
        assert artifacts[0]['revision'] == 8 and artifacts[0]['maturity'] == 'draft'
    elif kind in ('transition', 'retire'):
        assert artifacts[0]['revision'] == 8 and artifacts[0]['maturity'] == 'retired'
    elif kind in ('add', 'remove'):
        assert artifacts[0]['revision'] == 8 and len(artifacts[0]['relations']) == 1
    else:
        review = next(a for a in artifacts if a['artifact_type'] == 'relation_review')
        assert (review['decision'], review['review_state'], review['maturity'], review['revision']) == (kind, 'recorded', 'approved', 1)
        if kind == 'rejected':
            requirement = next(a for a in artifacts if a['artifact_type'] == 'requirement')
            assert requirement['maturity'] == 'proposed' and requirement['revision'] == 5


@pytest.mark.parametrize('kind', KINDS)
def test_saved_preview_matches_native_files_receipt_and_replay(tmp_path, kind):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, kind)
    before = file_inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
        report = preview(model, command, op, options, fail_on_change=True)
    assert file_inventory(root) == before
    assert report['dry_run'] and report['would_change'] and report['exit_code'] == 1
    assert report['write_state'] == 'not_committed' and report['backend_receipt'] is None
    assert report['audit']['operations'] == [op.data] and not report['audit']['approval_granted']
    plan = saved(report); seen = []
    def authorize(request):
        assert inspect_project_lock(root).data['record']['kind'] == 'writer'
        assert request.plan.source_bytes == plan.source_bytes
        seen.append(request.plan.sha256)
        return True
    authority = PublicationAuthority('owned-plan-host', '1', authorize)
    with patch('secrets.token_bytes', side_effect=AssertionError('saved IDs only')):
        result = apply_authoring_plan(plan, model, command_id=command, transaction_id='txn-preview',
            authority=authority, gates=options['gates'])
    assert seen and set(seen) == {report['plan_sha256']}
    assert result['write_state'] == 'committed' and result['exit_code'] == 0 and not result['replayed']
    assert result['target_model_root_sha256'] == report['expected_model_root']
    assert result['audit'] == {**report['audit'], 'dry_run': False, 'write_state': 'committed'}
    assert result['completion']['current_target_verified'] and result['completion']['cleanup_completed']
    ref = result['completion']['receipts']['transaction']
    receipt = TransactionReceipt((root / ref['path']).read_bytes()).data
    assert receipt['journal']['plan_sha256'] == plan.sha256 and receipt['operations'] == [op.data]
    assert_effects(root, before, report, kind)
    before_retry = file_inventory(root)
    with no_write_attempts(), patch.object(execution, 'assess_change_target', side_effect=AssertionError('no replan')), \
            patch.object(execution, 'project_lock', side_effect=AssertionError('no lock')):
        repeated = apply_authoring_plan(plan, model, command_id=command, transaction_id='txn-retry',
            authority=authority, gates=options['gates'])
    assert repeated['replayed'] and repeated['audit'] == {**result['audit'], 'replayed': True}
    assert repeated['completion']['receipts'] == result['completion']['receipts']
    assert not repeated['completion']['current_target_verified'] and file_inventory(root) == before_retry


@pytest.mark.parametrize('kind', KINDS)
def test_existing_direct_adapter_builds_the_identical_saveable_plan(tmp_path, kind):
    root = tmp_path / 'project'; model, command, op, options, direct, entropy = scenario(root, kind)
    before = file_inventory(root)
    with no_write_attempts(): report = preview(model, command, op, options)
    plan = saved(report); seen = []
    def authorize(request):
        assert request.plan.source_bytes == plan.source_bytes
        seen.append(request.plan.sha256); return True
    with patch('secrets.token_bytes', return_value=entropy):
        result = direct({**options, 'transaction_id': 'txn-direct',
            'authority': PublicationAuthority('owned-direct-host', '1', authorize)})
    assert seen and set(seen) == {report['plan_sha256']}
    assert result['completion']['target_model_root_sha256'] == report['expected_model_root']
    assert_effects(root, before, report, kind)


@pytest.mark.parametrize('fail_on_change', [False, True])
def test_noop_preview_and_fresh_native_authorization_create_no_receipt(tmp_path, fail_on_change):
    root = tmp_path / 'project'; model, _, _, options, _, _ = scenario(root, 'update')
    source = next(a for a in model.artifacts if a['artifact_type'] == 'requirement')
    op = normalize_artifact_update_input(source, patch=[], expected_revision=7)
    before = file_inventory(root); report = preview(model, 'artifact.update', op, options, fail_on_change=fail_on_change)
    assert report['exit_code'] == 0 and not report['would_change']
    calls = []
    result = apply_authoring_plan(saved(report), model, command_id='artifact.update', transaction_id='txn-noop',
        authority=PublicationAuthority('owned-noop-host', '1', lambda request: calls.append(request.plan.sha256) or True))
    assert calls and result['no_change'] and result['completion'] is None
    assert result['write_state'] == 'not_committed' and file_inventory(root) == before


@pytest.mark.parametrize('actor_type,request_id,exit_code', [('ai', None, 2), ('ai', 'ai-request', 7), ('ci', None, 2)])
def test_preview_does_not_grant_actor_write_authority(tmp_path, actor_type, request_id, exit_code):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    options.update(actor={'actor_type': actor_type, 'actor_id': 'external'}, request_id=request_id)
    before = file_inventory(root)
    with no_write_attempts(): report = preview(model, command, op, options)
    assert report['target_validated'] and report['write_state'] == 'not_committed'
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        apply_authoring_plan(saved(report), model, command_id=command, transaction_id='txn-denied',
            authority=PublicationAuthority('unused', '1', lambda request: pytest.fail('no authorization callback')))
    assert error.value.exit_code == exit_code and file_inventory(root) == before


@pytest.mark.parametrize('command', ['artifact.create', 'relation.review', 'init', 'relation.status'])
def test_wrong_or_unsupported_command_cannot_relabel_an_operation(tmp_path, command):
    root = tmp_path / 'project'; model, _, op, options, _, _ = scenario(root, 'update')
    before = file_inventory(root)
    with no_write_attempts(), pytest.raises(AuthoringError): preview(model, command, op, options)
    assert file_inventory(root) == before


def test_real_authority_denial_preserves_files_and_receipts(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    report = preview(model, command, op, options); before = file_inventory(root)
    with pytest.raises(PublicationCheckError) as error:
        apply_authoring_plan(saved(report), model, command_id=command, transaction_id='txn-denied',
            authority=PublicationAuthority('deny', '1', lambda request: False))
    assert error.value.exit_code == 7 and file_inventory(root) == before


def test_changed_live_input_after_preview_cannot_be_published(tmp_path):
    root = tmp_path / 'project'; model, command, op, options, _, _ = scenario(root, 'update')
    report = preview(model, command, op, options)
    path = root / artifact_path('requirement', op.data['target'], 'SR')
    path.write_bytes(path.read_bytes() + b'\n'); before = file_inventory(root)
    with pytest.raises(ChangePlanError):
        apply_authoring_plan(saved(report), model, command_id=command, transaction_id='txn-stale',
            authority=PublicationAuthority('unused', '1', lambda request: pytest.fail('stale input')))
    assert file_inventory(root) == before
