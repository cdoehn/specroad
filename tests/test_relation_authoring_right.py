"""Owned identity exclusions, exact refusals and interrupted real relation writes."""
import json
import os
from unittest.mock import patch
import pytest

from specroad.authoring import relations
from specroad.authoring.relations import add_relation, remove_relation
from specroad.changes import (AuthoringError, ChangePlanError, CommitPublicationError,
    ProjectLockError, PublicationCheckError, RequestIdConflict, project_lock)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.model.relation_identity import RelationInventory
from support.project_locks import options as lock_options
from support.read_only import inventory as file_inventory, no_write_attempts
from support.relations import aid, rid
from test_relation_authoring import (ACTOR, TIME, ENTROPY, stored_project, inventory,
    arguments, call, receipt)


@pytest.mark.parametrize('field', ['archived_ids', 'reserved_ids'])
@pytest.mark.parametrize('during', ['source_read', 'entropy'])
def test_initial_identity_exclusions_survive_caller_mutation(tmp_path, field, during):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    values = {'current_ids': (), 'archived_ids': (), 'reserved_ids': ()}
    values[field] = (rid(90),)
    supplied = RelationInventory(**values); draws = []; native_source = relations.ProjectSource
    def mutate(): object.__setattr__(supplied, field, frozenset())
    def read(*args, **kwargs):
        if during == 'source_read': mutate()
        return native_source(*args, **kwargs)
    def entropy(size):
        assert size == 16
        if during == 'entropy': mutate()
        value = 90 if not draws else 91
        draws.append(value)
        return value.to_bytes(16, 'big')
    with patch.object(relations, 'ProjectSource', side_effect=read), \
            patch('secrets.token_bytes', side_effect=entropy):
        result = add_relation(model, source['id'], 'addresses', goals[0]['id'],
                              inventory=supplied, **arguments(root, 'add'))
    assert getattr(supplied, field) == frozenset()
    assert draws == [90, 91] and result['relation_id'] == rid(91)
    actual = json.loads((root / artifact_path('requirement', source['id'], 'SR')).read_bytes())
    assert [e['relation_id'] for e in actual['relations']] == [rid(91)]
    assert actual['revision'] == 8 and receipt(root, result)['created_ids'] == [rid(91)]


@pytest.mark.parametrize('field,value', [('archived_ids', None), ('reserved_ids', ['bad']),
    ('current_ids', [rid(1), rid(1)]), ('archived_ids', 'not-an-inventory')])
def test_forged_inventory_fields_are_revalidated_before_external_io(tmp_path, field, value):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    supplied = inventory(model); object.__setattr__(supplied, field, value)
    before = file_inventory(root)
    with no_write_attempts(), patch.object(relations, 'ProjectSource', side_effect=AssertionError), \
            pytest.raises(AuthoringError) as error:
        add_relation(model, source['id'], 'addresses', goals[0]['id'],
                     inventory=supplied, **arguments(root, 'add'))
    assert error.value.exit_code == 3 and file_inventory(root) == before


@pytest.mark.parametrize('defect,reason', [('wrong_type', 'relation_type_pair_forbidden'),
    ('missing_target', 'missing_relation_target'), ('missing_source', 'missing_operation_source'),
    ('self', 'self_relation_forbidden'), ('symmetric_direction', 'noncanonical_symmetric_relation')])
def test_invalid_relation_endpoints_never_publish_partial_source(tmp_path, defect, reason):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    source_id, target_id, kind = source['id'], goals[0]['id'], 'addresses'
    if defect == 'wrong_type': kind = 'verified_by'
    if defect == 'missing_target': target_id = aid('goal', 99)
    if defect == 'missing_source': source_id = aid('requirement', 99)
    if defect == 'self': target_id, kind = source_id, 'depends_on'
    if defect == 'symmetric_direction': kind = 'conflicts_with'
    before = file_inventory(root)
    with pytest.raises(ChangePlanError) as error:
        add_relation(model, source_id, kind, target_id, inventory=inventory(model), **arguments(root, 'add'))
    assert error.value.reason == reason and error.value.exit_code == 3
    assert file_inventory(root) == before


@pytest.mark.parametrize('values,reason', [({'rationale': []}, 'rationale_string_required'),
                                         ({'position': 0}, 'position_only_for_contains')])
def test_invalid_optional_relation_fields_leave_original_tree(tmp_path, values, reason):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    before = file_inventory(root)
    with pytest.raises(ChangePlanError) as error:
        add_relation(model, source['id'], 'addresses', goals[0]['id'],
                     inventory=inventory(model), **values, **arguments(root, 'add'))
    assert error.value.reason == reason and error.value.exit_code == 3
    assert file_inventory(root) == before


@pytest.mark.parametrize('defect,reason', [('missing_source', 'missing_operation_source'),
    ('other_source', 'missing_operation_relation'), ('wrong_relation', 'missing_operation_relation'),
    ('stale_hash', 'expected_relation_hash_mismatch'), ('source_hash', 'expected_relation_hash_mismatch'),
    ('empty_reason', None)])
def test_remove_needs_exact_source_relation_hash_and_reason(tmp_path, defect, reason):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=True)
    source_id, identity = source['id'], rid(10)
    digest, why = canonical_json_sha256(source['relations'][0]), 'Remove obsolete link.'
    if defect == 'missing_source': source_id = aid('requirement', 99)
    if defect == 'other_source': source_id = goals[0]['id']
    if defect == 'wrong_relation': identity = rid(99)
    if defect == 'stale_hash': digest = 'a' * 64
    if defect == 'source_hash': digest = canonical_json_sha256(source)
    if defect == 'empty_reason': why = ''
    before = file_inventory(root)
    with patch('secrets.token_bytes', side_effect=AssertionError), pytest.raises(ChangePlanError) as error:
        remove_relation(model, source_id, identity, expected_sha256=digest,
                        reason=why, **arguments(root, 'remove'))
    if reason is not None: assert error.value.reason == reason
    assert error.value.exit_code == 3 and file_inventory(root) == before


def test_missing_model_reservation_is_rejected_before_lock(tmp_path):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, reserved=[rid(90)])
    before = file_inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError), \
            pytest.raises(AuthoringError) as error:
        add_relation(model, source['id'], 'addresses', goals[0]['id'],
                     inventory=inventory(model), **arguments(root, 'add'))
    assert error.value.reason == 'relation_identity_inventory_mismatch' and error.value.exit_code == 6
    assert file_inventory(root) == before


@pytest.mark.parametrize('excluded', ['current', 'archived', 'reserved'])
def test_allocator_preserves_all_declared_identity_exclusions(tmp_path, excluded):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=True)
    blocked = 10 if excluded == 'current' else 90
    supplied = inventory(model, archived=[rid(blocked)] if excluded == 'archived' else (),
        reserved=[rid(blocked)] if excluded == 'reserved' else ())
    with patch('secrets.token_bytes', side_effect=[blocked.to_bytes(16, 'big'), (91).to_bytes(16, 'big')]) as draws:
        result = add_relation(model, source['id'], 'addresses', goals[0]['id'],
                             inventory=supplied, **arguments(root, 'add'))
    assert result['relation_id'] == rid(91) and draws.call_count == 2
    actual = json.loads((root / artifact_path('requirement', source['id'], 'SR')).read_bytes())
    assert actual['relations'][:2] == source['relations'] and len(actual['relations']) == 3
    assert actual['revision'] == 8 and actual['updated_by'] == ACTOR


@pytest.mark.parametrize('changed', ['source', 'type', 'target', 'rationale'])
def test_confirmed_add_request_cannot_be_retargeted(tmp_path, changed):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    options = arguments(root, 'add'); call(model, source, goals, 'add', options)
    source_id, kind, target = source['id'], 'addresses', goals[0]['id']
    why = 'Supports this goal.'
    if changed == 'source': source_id = goals[1]['id']
    if changed == 'type': kind = 'conflicts_with'
    if changed == 'target': target = goals[1]['id']
    if changed == 'rationale': why = 'Another intent.'
    before = file_inventory(root)
    with no_write_attempts(), patch.object(relations, 'project_lock', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError), \
            pytest.raises((AuthoringError, RequestIdConflict)) as error:
        add_relation(model, source_id, kind, target, inventory=inventory(model), rationale=why, **options)
    assert error.value.exit_code == 6 and file_inventory(root) == before


@pytest.mark.parametrize('action', ['add', 'remove'])
def test_same_operation_retry_with_another_actor_retains_historical_actor(tmp_path, action):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=action == 'remove')
    options = arguments(root, action); original = call(model, source, goals, action, options)
    before = file_inventory(root)
    options['actor'] = {**ACTOR, 'actor_id': 'later-caller'}
    with no_write_attempts(), patch.object(relations, 'prepare_change_target', side_effect=AssertionError), \
            patch.object(relations, 'project_lock', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError):
        result = call(model, source, goals, action, options)
    assert result['replayed'] and result['relation_id'] == original['relation_id']
    assert result['completion']['receipts'] == original['completion']['receipts']
    assert not result['completion']['current_target_verified']
    assert receipt(root, result)['journal']['actor'] == ACTOR
    actual = json.loads((root / artifact_path('requirement', source['id'], 'SR')).read_bytes())
    assert actual['updated_by'] == ACTOR and actual['revision'] == 8
    if action == 'add': assert actual['relations'][0]['created_by'] == ACTOR
    assert file_inventory(root) == before


@pytest.mark.parametrize('changed', ['relation_id', 'hash', 'reason'])
def test_confirmed_remove_request_cannot_describe_another_removal(tmp_path, changed):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=True)
    options = arguments(root, 'remove'); call(model, source, goals, 'remove', options)
    identity, digest, why = rid(10), canonical_json_sha256(source['relations'][0]), 'Replaced by another link.'
    if changed == 'relation_id': identity = rid(11)
    if changed == 'hash': digest = 'a' * 64
    if changed == 'reason': why = 'Another reason.'
    before = file_inventory(root)
    with no_write_attempts(), patch.object(relations, 'project_lock', side_effect=AssertionError), \
            pytest.raises((AuthoringError, RequestIdConflict)) as error:
        remove_relation(model, source['id'], identity, expected_sha256=digest, reason=why, **options)
    assert error.value.exit_code == 6 and file_inventory(root) == before


@pytest.mark.parametrize('first', ['add', 'remove'])
def test_request_id_cannot_change_between_add_and_remove(tmp_path, first):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=True)
    call(model, source, goals, first, arguments(root, first)); before = file_inventory(root)
    other = 'remove' if first == 'add' else 'add'
    with no_write_attempts(), patch.object(relations, 'project_lock', side_effect=AssertionError), \
            pytest.raises(AuthoringError) as error:
        call(model, source, goals, other, arguments(root, other))
    assert error.value.reason == 'request_operations_conflict' and error.value.exit_code == 6
    assert file_inventory(root) == before


@pytest.mark.parametrize('action', ['add', 'remove'])
def test_changed_physical_source_is_preserved(tmp_path, action):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=action == 'remove')
    path = root / artifact_path('requirement', source['id'], 'SR')
    foreign = canonical_json_bytes({**source, 'statement': 'Foreign change.'}); path.write_bytes(foreign)
    before = file_inventory(root)
    with pytest.raises(PublicationCheckError) as error:
        call(model, source, goals, action, arguments(root, action))
    assert error.value.reason == 'publication_base_changed' and error.value.exit_code == 6
    assert path.read_bytes() == foreign and file_inventory(root) == before


@pytest.mark.parametrize('action', ['add', 'remove'])
def test_existing_writer_remains_untouched(tmp_path, action):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=action == 'remove')
    with project_lock(root, **lock_options()) as held:
        before = file_inventory(root)
        with patch('secrets.token_bytes', side_effect=AssertionError), pytest.raises(ProjectLockError) as error:
            call(model, source, goals, action, arguments(root, action))
        assert error.value.reason == 'project_lock_busy' and error.value.exit_code == 5
        assert held.check() and file_inventory(root) == before


@pytest.mark.parametrize('action', ['add', 'remove'])
@pytest.mark.parametrize('moved', [False, True])
def test_failed_real_replace_retains_actual_relation_bytes_and_recovery_evidence(tmp_path, action, moved):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=action == 'remove')
    path = artifact_path('requirement', source['id'], 'SR'); raw = (root / path).read_bytes()
    before = file_inventory(root); native_replace = os.replace; attempts = []
    def replace(src, dst, **kwargs):
        if str(dst) == source['id'] + '.json':
            attempts.append(str(dst))
            if moved: native_replace(src, dst, **kwargs)
            raise OSError('injected relation replace failure')
        return native_replace(src, dst, **kwargs)
    with patch.object(os, 'replace', side_effect=replace), \
            patch('secrets.token_bytes', return_value=ENTROPY), pytest.raises(CommitPublicationError) as error:
        call(model, source, goals, action, arguments(root, action))
    assert attempts == [source['id'] + '.json']
    assert error.value.reason == 'publication_io_failure' and error.value.exit_code == 5
    assert error.value.write_state == 'unknown' and error.value.mutation_possible and error.value.publication_possible
    assert error.value.published_count == 0
    if moved:
        value = json.loads((root / path).read_bytes())
        assert value['revision'] == 8 and value['updated_by'] == ACTOR and value['updated_at'] == TIME
        if action == 'remove': assert value['relations'] == source['relations'][1:]
        else:
            assert len(value['relations']) == 1
            assert value['relations'][0]['type'] == 'addresses' and value['relations'][0]['target'] == goals[0]['id']
    else: assert (root / path).read_bytes() == raw
    journal = json.loads((root / '.specroad/transactions/txn-relation/journal.json').read_bytes())
    assert journal['state'] == 'committing' and journal['published_count'] == 0
    after = {p: rest for p, *rest in file_inventory(root)}
    for p, *rest in before:
        if p != path: assert after[p] == rest
    retained = file_inventory(root)
    with pytest.raises(ProjectLockError) as retry:
        call(model, source, goals, action, arguments(root, action))
    assert retry.value.reason == 'transaction_journal_blocks_lock' and retry.value.exit_code == 5
    assert file_inventory(root) == retained


@pytest.mark.parametrize('action', ['add', 'remove'])
def test_ci_with_explicit_request_keeps_actor_in_source_and_audit(tmp_path, action):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=action == 'remove')
    actor = {'actor_type': 'ci', 'actor_id': 'owned-ci'}
    result = call(model, source, goals, action, arguments(root, action, actor=actor, request_id='ci-rel-1'))
    actual = json.loads((root / artifact_path('requirement', source['id'], 'SR')).read_bytes())
    assert actual['revision'] == 8 and actual['updated_by'] == actor
    assert receipt(root, result)['journal']['actor'] == actor
    assert result['completion']['request_id'] == 'ci-rel-1'
