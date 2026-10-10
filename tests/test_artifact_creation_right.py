"""Collision, refusal and interrupted native creation preserve actual state."""
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring.creation import create_artifact
from specroad.authoring.inputs import ArtifactCreateInput, normalize_artifact_create_input
from specroad.changes import (AuthoringError, CommitPublicationError, ProjectLockError,
    PublicationCheckError, TargetModel, project_lock)
from specroad.model.identities import IdentityInventory
from support.project_locks import attempt, options as lock_options
from support.read_only import inventory as file_inventory, no_write_attempts
from test_artifact_creation import project, arguments
from test_authoring_inputs import fields
from test_authoring_inputs_right import REQUIRED


def goal(number):
    return 'SR-GOAL-' + '0' * 25 + str(number)


def unchanged(before, root):
    after = {entry[0]: entry[1:] for entry in file_inventory(root)}
    for name, *old in before:
        assert after[name] == tuple(old)


def test_current_archived_reserved_collisions_retry_under_real_process_exclusion(tmp_path):
    root = tmp_path / 'project'; model, original = project(root)
    ids = IdentityInventory('SR', original.current_ids, [goal(1)], [goal(2)])
    before = file_inventory(root); draws = []
    def entropy(size):
        assert size == 16
        # A separate process must fail at the real kernel mutex, not just see
        # ownership metadata. All collision retries retain the same exclusion.
        assert attempt(root) == {'acquired': False, 'reason': 'project_lock_busy'}
        value = len(draws); draws.append(value)
        assert value <= 3
        return value.to_bytes(16, 'big')
    with patch('secrets.token_bytes', side_effect=entropy):
        result = create_artifact(model, normalize_artifact_create_input('goal', fields('goal')),
                                 **arguments(model, ids))
    assert draws == [0, 1, 2, 3]
    assert result['artifact_id'] == goal(3) and result['revision'] == 1
    assert result['path'] == 'spec/goals/' + goal(3) + '.json'
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    assert {p.stem for p in (root / 'spec/goals').iterdir()} == {goal(0), goal(3)}
    assert ids.current_ids == original.current_ids
    assert ids.archived_ids == {goal(1)} and ids.reserved_ids == {goal(2)}
    assert not ids.contains(goal(3))
    unchanged(before, root)
    assert attempt(root)['acquired']


@pytest.mark.parametrize('after_collision', [False, True])
def test_entropy_io_failure_is_operational_without_retry_or_journal(tmp_path, after_collision):
    root = tmp_path / 'project'; model, ids = project(root); before = file_inventory(root)
    failures = ([bytes(16)] if after_collision else []) + [OSError('private RNG detail')]
    with patch('secrets.token_bytes', side_effect=failures) as entropy:
        with pytest.raises(AuthoringError) as error:
            create_artifact(model, normalize_artifact_create_input('goal', fields('goal')),
                            **arguments(model, ids))
    assert error.value.reason == 'entropy_unavailable' and error.value.exit_code == 5
    assert error.value.diagnostic()['write_state'] == 'not_committed'
    assert error.value.diagnostic()['authorization_granted'] is False
    assert entropy.call_count == 1 + after_collision
    assert file_inventory(root) == before
    assert not (root / '.specroad/transactions').exists()
    assert attempt(root)['acquired']


@pytest.mark.parametrize('raw', [b'', bytes(15), bytes(17), None, 'not bytes'])
def test_broken_entropy_provider_never_creates_an_identity(tmp_path, raw):
    root = tmp_path / 'project'; model, ids = project(root); before = file_inventory(root)
    with patch('secrets.token_bytes', return_value=raw) as entropy:
        with pytest.raises(AuthoringError) as error:
            create_artifact(model, normalize_artifact_create_input('goal', fields('goal')),
                            **arguments(model, ids))
    assert error.value.reason == 'entropy_bytes_required' and error.value.exit_code == 5
    assert error.value.diagnostic()['write_state'] == 'not_committed'
    assert entropy.call_count == 1 and file_inventory(root) == before
    assert ids.reserved_ids == frozenset()


@pytest.mark.parametrize('kind,field', list(REQUIRED.items()))
@pytest.mark.parametrize('defect', ['missing', 'null'])
def test_writer_revalidates_required_draft_fields_before_lock_or_entropy(tmp_path, kind, field, defect):
    root = tmp_path / 'project'; model, ids = project(root); before = file_inventory(root)
    value = fields(kind)
    if defect == 'missing': value.pop(field)
    else: value[field] = None
    # A typed container is not evidence that the current content is valid.
    prepared = ArtifactCreateInput._create(kind, value)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
        with pytest.raises(AuthoringError) as error:
            create_artifact(model, prepared, **arguments(model, ids))
    # A null content-block discriminator fails its object-level variant union;
    # the native schema reports that union, rather than one variant field.
    variant_failure = kind == 'content_block' and defect == 'null'
    assert error.value.exit_code == 3
    assert error.value.pointer == ('' if variant_failure else '/' + field)
    if variant_failure: assert error.value.reason == 'schema_any_of'
    assert error.value.diagnostic()['write_state'] == 'not_committed'
    assert file_inventory(root) == before


@pytest.mark.parametrize('kind', ['evidence', 'baseline', 'proposal', 'relation_review'])
def test_specialized_records_cannot_bypass_the_generic_writer_boundary(tmp_path, kind):
    root = tmp_path / 'project'; model, ids = project(root); before = file_inventory(root)
    prepared = ArtifactCreateInput._create(kind, fields('goal'))
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
        with pytest.raises(AuthoringError) as error:
            create_artifact(model, prepared, **arguments(model, ids))
    assert error.value.reason == 'specialized_operation_required' and error.value.exit_code == 3
    assert file_inventory(root) == before


@pytest.mark.parametrize('defect', ['prefix', 'missing', 'extra', 'reservation'])
def test_incomplete_or_foreign_identity_inventory_cannot_start_a_writer(tmp_path, defect):
    root = tmp_path / 'project'; model, ids = project(root); before = file_inventory(root)
    if defect == 'prefix': ids = IdentityInventory('XY', ['XY-GOAL-' + '0' * 26], (), ())
    elif defect == 'missing': ids = IdentityInventory('SR', (), (), ())
    elif defect == 'extra': ids = IdentityInventory('SR', [goal(0), goal(1)], (), ())
    else:
        model = TargetModel(model.configuration_bytes, model.binding, model.documents,
            profile=model.profile, resource_files=model.resource_files, reserved_artifact_ids=[goal(1)])
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
        with pytest.raises(AuthoringError) as error:
            create_artifact(model, normalize_artifact_create_input('goal', fields('goal')),
                            **arguments(model, ids))
    assert error.value.reason == 'creation_identity_inventory_mismatch' and error.value.exit_code == 6
    assert file_inventory(root) == before


def test_another_held_writer_blocks_creation_without_consuming_entropy(tmp_path):
    root = tmp_path / 'project'; model, ids = project(root)
    with project_lock(root, **lock_options()) as held:
        before = file_inventory(root)
        with patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
            with pytest.raises(ProjectLockError) as error:
                create_artifact(model, normalize_artifact_create_input('goal', fields('goal')),
                                **arguments(model, ids))
        assert error.value.reason == 'project_lock_busy' and error.value.exit_code == 5
        assert held.check() and file_inventory(root) == before


def test_changed_physical_base_is_not_overwritten_or_accepted_from_cached_model(tmp_path):
    root = tmp_path / 'project'; model, ids = project(root)
    existing = root / ('spec/goals/' + goal(0) + '.json')
    raw = existing.read_bytes().replace(b'Reduce setup effort.', b'Alter setup effort.')
    assert raw != existing.read_bytes(); existing.write_bytes(raw)
    before = file_inventory(root)
    with pytest.raises(PublicationCheckError) as error:
        create_artifact(model, normalize_artifact_create_input('goal', fields('goal')),
                        **arguments(model, ids))
    assert error.value.reason == 'publication_base_changed' and error.value.exit_code == 6
    assert file_inventory(root) == before and existing.read_bytes() == raw


@pytest.mark.parametrize('moved', [False, True])
def test_failed_target_move_preserves_recovery_evidence_and_blocks_blind_retry(tmp_path, moved):
    root = tmp_path / 'project'; model, ids = project(root); before = file_inventory(root)
    native_replace = os.replace; attempts = []
    def replace(src, dst, **kwargs):
        if str(dst).startswith('SR-GOAL-'):
            attempts.append(str(dst))
            if moved: native_replace(src, dst, **kwargs)
            raise OSError('injected target move failure')
        return native_replace(src, dst, **kwargs)
    prepared = normalize_artifact_create_input('goal', fields('goal'))
    with patch('secrets.token_bytes', return_value=(7).to_bytes(16, 'big')) as entropy, \
            patch.object(os, 'replace', side_effect=replace):
        with pytest.raises(CommitPublicationError) as error:
            create_artifact(model, prepared, **arguments(model, ids))
    assert error.value.exit_code == 5 and error.value.reason == 'publication_io_failure'
    assert error.value.write_state == 'unknown' and error.value.publication_possible
    assert error.value.mutation_possible and error.value.published_count == 0
    assert entropy.call_count == 1 and attempts == [goal(7) + '.json']
    target = root / ('spec/goals/' + goal(7) + '.json')
    assert target.exists() is moved
    if moved:
        value = json.loads(target.read_bytes())
        assert value['id'] == goal(7) and value['revision'] == 1
    journal = root / '.specroad/transactions/txn-create/journal.json'
    record = json.loads(journal.read_bytes())
    assert record['state'] == 'committing' and record['published_count'] == 0
    unchanged(before, root)
    retained = file_inventory(root)
    with patch('secrets.token_bytes', side_effect=AssertionError('no retry allocation')):
        with pytest.raises(ProjectLockError) as retry:
            create_artifact(model, prepared, **arguments(model, ids))
    assert retry.value.reason == 'transaction_journal_blocks_lock' and retry.value.exit_code == 5
    assert file_inventory(root) == retained
