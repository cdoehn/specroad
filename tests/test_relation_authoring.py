"""Real relation writes, source revisions, native audit and historical retry."""
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.authoring import relations
from specroad.authoring.relations import add_relation, remove_relation
from specroad.changes import (AuthoringError, ChangePlanError, TargetError, TargetModel,
    PublicationAuthority, PublicationCheckError, inspect_project_lock,
    read_transaction_completion)
from specroad.changes.receipt_values import TransactionReceipt
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.identity_tokens import encode128
from specroad.model.paths import artifact_path
from specroad.model.relation_identity import RelationInventory
from specroad.storage.project import ProjectSource
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.model import put
from support.read_only import inventory as file_inventory, no_write_attempts
from support.relations import aid, edge, rid
from test_artifact_creation import project

ACTOR = {'actor_type': 'human', 'actor_id': 'relation-editor'}
TIME = '2026-10-10T16:00:00Z'
ENTROPY = b'\x51' * 16


def stored_project(root, *, kind='requirement', with_edges=False, maturity='draft',
                   reserved=(), broken=False):
    base, _ = project(root)
    goals = [base.artifacts[0], domain_value('goal', id=aid('goal', 2))]
    values = [edge('addresses', goals[0]['id'], number=10),
              edge('addresses', goals[1]['id'], number=11)] if with_edges else []
    source = domain_value(kind, revision=7, relations=values, maturity=maturity)
    if broken: goals[0].pop('statement')
    artifacts = [*goals, source]
    documents = [ModelDocument(artifact_path(a['artifact_type'], a['id'], 'SR'),
        json.dumps(a, indent=3).encode() + b'\n') for a in artifacts]
    model = TargetModel(base.configuration_bytes, base.binding, documents,
        profile=base.profile, resource_files=base.resource_files, reserved_relation_ids=reserved)
    for path, raw in model.source_files.items(): put(root, path, raw)
    (root / artifact_path(kind, source['id'], 'SR')).chmod(0o640)
    return model, source, goals


def inventory(model, *, archived=(), reserved=()):
    return RelationInventory([e['relation_id'] for a in model.artifacts for e in a['relations']],
                             archived, reserved)


def arguments(root, action, *, actor=ACTOR, request_id='relation-1'):
    def authorize(request):
        status = inspect_project_lock(root).data
        assert status['record']['kind'] == 'writer'
        assert status['record']['transaction_id'] == 'txn-relation'
        assert [op.op for op in request.plan.operations] == ['relation_' + action]
        return True
    return dict(actor=actor, planned_at=TIME, change_plan_id='CP-relation',
        transaction_id='txn-relation', request_id=request_id,
        authority=PublicationAuthority('owned-relation-host', '1', authorize))


def call(model, source, goals, action, options, *, index=0):
    if action == 'add':
        return add_relation(model, source['id'], 'addresses', goals[0]['id'],
                            inventory=inventory(model), rationale='Supports this goal.', **options)
    relation = source['relations'][index]
    return remove_relation(model, source['id'], relation['relation_id'],
        expected_sha256=canonical_json_sha256(relation), reason='Replaced by another link.', **options)


def receipt(root, result):
    ref = result['completion']['receipts']['transaction']
    raw = (root / ref['path']).read_bytes()
    assert sha256(raw).hexdigest() == ref['sha256']
    return TransactionReceipt(raw).data


def assert_preserved(root, original, changed):
    actual = {row[0]: row[1:] for row in file_inventory(root)}
    for name, *before in original:
        if name != changed: assert actual[name] == tuple(before)
    assert (root / changed).stat().st_mode & 0o777 == 0o640
    assert not (root / '.specroad/locks/project.json').exists()


@pytest.mark.parametrize('kind', ['need', 'capability', 'requirement'])
@pytest.mark.parametrize('actor_type', ['human', 'tool'])
def test_add_allocates_under_real_lock_and_publishes_one_source_revision(tmp_path, kind, actor_type):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, kind=kind)
    actor = {**ACTOR, 'actor_type': actor_type}; options = arguments(root, 'add', actor=actor)
    before = file_inventory(root); draws = []
    def entropy(size):
        assert size == 16
        state = inspect_project_lock(root).data
        assert state['record']['kind'] == 'writer'
        assert state['record']['transaction_id'] == options['transaction_id']
        draws.append(size)
        return ENTROPY
    with patch('secrets.token_bytes', side_effect=entropy):
        result = call(model, source, goals, 'add', options)
    relation = {'relation_id': 'REL-' + encode128(ENTROPY), 'id_scheme': 'random128-v1',
        'type': 'addresses', 'target': goals[0]['id'], 'external_identities': [], 'extensions': {},
        'rationale': 'Supports this goal.', 'created_at': TIME, 'created_by': actor}
    expected = {**source, 'relations': [relation], 'revision': 8,
                'updated_at': TIME, 'updated_by': actor}
    path = artifact_path(kind, source['id'], 'SR')
    assert (root / path).read_bytes() == canonical_json_bytes(expected)
    assert result['command_id'] == 'relation.add' and result['source_id'] == source['id']
    assert result['relation_id'] == relation['relation_id'] and draws == [16]
    assert result['write_state'] == 'committed' and not result['replayed']
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    assert result['completion']['current_target_verified']
    proof = receipt(root, result)
    assert proof['operations'] == [{'op': 'relation_add', 'source': source['id'], 'relation': relation}]
    assert proof['created_ids'] == [relation['relation_id']]
    assert proof['journal']['actor'] == actor and proof['journal']['planned_at'] == TIME
    assert next(a for a in model.artifacts if a['id'] == source['id']) == source
    assert_preserved(root, before, path)


@pytest.mark.parametrize('index', [0, 1])
@pytest.mark.parametrize('actor_type', ['human', 'tool'])
def test_remove_targets_exact_relation_and_retains_reason_actor_and_other_edge(tmp_path, index, actor_type):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=True)
    actor = {**ACTOR, 'actor_type': actor_type}; before = file_inventory(root)
    selected = source['relations'][index]; remaining = source['relations'][1 - index]
    with patch('secrets.token_bytes', side_effect=AssertionError('remove allocates no identity')):
        result = call(model, source, goals, 'remove', arguments(root, 'remove', actor=actor), index=index)
    expected = {**source, 'relations': [remaining], 'revision': 8,
                'updated_at': TIME, 'updated_by': actor}
    path = artifact_path('requirement', source['id'], 'SR')
    assert (root / path).read_bytes() == canonical_json_bytes(expected)
    assert result['command_id'] == 'relation.remove' and result['source_id'] == source['id']
    assert result['relation_id'] == selected['relation_id']
    proof = receipt(root, result)
    assert proof['operations'] == [{'op': 'relation_remove', 'source': source['id'],
        'relation_id': selected['relation_id'], 'expected_sha256': canonical_json_sha256(selected),
        'reason': 'Replaced by another link.'}]
    assert proof['created_ids'] == [] and proof['journal']['actor'] == actor
    assert proof['journal']['planned_at'] == TIME
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    assert next(a for a in model.artifacts if a['id'] == source['id']) == source
    assert_preserved(root, before, path)


@pytest.mark.parametrize('action', ['add', 'remove'])
def test_confirmed_retry_uses_original_operation_without_planning_lock_or_allocation(tmp_path, action):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=action == 'remove')
    options = arguments(root, action)
    result = call(model, source, goals, action, options)
    before = file_inventory(root)
    retry = {**options, 'planned_at': '2027-01-01T00:00:00Z', 'transaction_id': 'unused-retry',
             'change_plan_id': 'CP-unused-retry'}
    with no_write_attempts(), patch.object(relations, 'prepare_change_target', side_effect=AssertionError), \
            patch.object(relations, 'project_lock', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError):
        replayed = call(model, source, goals, action, retry)
    assert replayed['replayed'] and replayed['relation_id'] == result['relation_id']
    assert replayed['completion']['transaction_id'] == 'txn-relation'
    assert replayed['completion']['receipt_verified'] and not replayed['completion']['current_target_verified']
    assert file_inventory(root) == before
    proof = read_transaction_completion(ProjectSource(root), 'txn-relation').data
    assert proof['commit_completed'] and proof['cleanup_completed']


@pytest.mark.parametrize('action', ['add', 'remove'])
def test_human_request_id_is_optional_and_creates_no_request_receipt(tmp_path, action):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=action == 'remove')
    result = call(model, source, goals, action, arguments(root, action, request_id=None))
    assert result['completion']['commit_completed']
    assert result['completion']['receipts']['request'] is None


@pytest.mark.parametrize('action', ['add', 'remove'])
@pytest.mark.parametrize('actor_type,request_id,exit_code', [('ai', 'r-1', 7), ('ci', None, 2)])
def test_actor_policy_blocks_before_lock_or_allocation(tmp_path, action, actor_type, request_id, exit_code):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=action == 'remove')
    before = file_inventory(root)
    options = arguments(root, action, actor={**ACTOR, 'actor_type': actor_type}, request_id=request_id)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError), \
            pytest.raises(AuthoringError) as error:
        call(model, source, goals, action, options)
    assert error.value.exit_code == exit_code and file_inventory(root) == before


@pytest.mark.parametrize('action', ['add', 'remove'])
def test_host_refusal_retains_all_original_files(tmp_path, action):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=action == 'remove')
    before = file_inventory(root); options = arguments(root, action)
    options['authority'] = PublicationAuthority('denied-relation-host', '1', lambda request: False)
    with pytest.raises(PublicationCheckError) as error:
        call(model, source, goals, action, options)
    assert error.value.exit_code == 7 and file_inventory(root) == before


@pytest.mark.parametrize('action', ['add', 'remove'])
def test_missing_real_lifecycle_service_remains_closed(tmp_path, action):
    root = tmp_path / 'project'
    model, source, goals = stored_project(root, with_edges=action == 'remove', maturity='proposed')
    before = file_inventory(root)
    with pytest.raises(TargetError) as error:
        call(model, source, goals, action, arguments(root, action))
    assert error.value.reason == 'complete_target_validation_required'
    assert file_inventory(root) == before


@pytest.mark.parametrize('action', ['add', 'remove'])
def test_invalid_unrelated_artifact_blocks_complete_target(tmp_path, action):
    root = tmp_path / 'project'
    model, source, goals = stored_project(root, with_edges=action == 'remove', broken=True)
    before = file_inventory(root)
    with pytest.raises(ChangePlanError) as error:
        call(model, source, goals, action, arguments(root, action))
    assert error.value.reason == 'missing_field' and error.value.exit_code == 3
    assert file_inventory(root) == before


def test_add_inventory_must_include_live_relations_before_allocation(tmp_path):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=True)
    before = file_inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError), \
            pytest.raises(AuthoringError) as error:
        add_relation(model, source['id'], 'addresses', goals[0]['id'],
                     inventory=RelationInventory((), (), ()), **arguments(root, 'add'))
    assert error.value.reason == 'relation_identity_inventory_mismatch' and error.value.exit_code == 6
    assert file_inventory(root) == before


@pytest.mark.parametrize('bad_hash', [None, '', 'short', 'A' * 64])
def test_remove_requires_explicit_relation_hash_before_io(tmp_path, bad_hash):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True)
    before = file_inventory(root)
    with no_write_attempts(), pytest.raises(ChangePlanError) as error:
        remove_relation(model, source['id'], rid(10), expected_sha256=bad_hash,
                        reason='Remove obsolete link.', **arguments(root, 'remove'))
    assert error.value.exit_code == 3 and file_inventory(root) == before


def test_unknown_relation_type_is_not_inferred(tmp_path):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    before = file_inventory(root)
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        add_relation(model, source['id'], 'unknown', goals[0]['id'],
                     inventory=inventory(model), **arguments(root, 'add'))
    assert error.value.reason == 'unknown_stored_relation_type' and error.value.exit_code == 3
    assert file_inventory(root) == before
