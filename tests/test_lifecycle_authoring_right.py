"""Lifecycle boundary, original gate selection and interrupted real writes."""
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring import lifecycle
from specroad.authoring.lifecycle import (normalize_transition_input, normalize_retire_input,
    transition_artifact, retire_artifact)
from specroad.changes import (AuthoringError, ChangeOperation, ChangePlanError,
    CommitPublicationError, LifecycleError, ProjectLockError, PublicationAuthority,
    PublicationCheckError, RequestIdConflict, TargetError, TargetModel, project_lock)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument, ModelGate
from support.domain import domain_value
from support.project_locks import options as lock_options
from support.read_only import inventory as file_inventory, no_write_attempts
from support.relations import aid, edge
from test_artifact_update_right import stored_project as approved_stored_project
from test_lifecycle_authoring import (ACTOR, TIME, REASON, arguments, operation, call,
    replace_values, assert_publication)
from test_relation_authoring import stored_project


def approved_project(root, successor='none'):
    # Structural approved source only; this fixture attests no approval history.
    model, source, _ = approved_stored_project(root, maturity='approved')
    if successor != 'none':
        newer = domain_value('requirement', id=aid('requirement', 99))
        if successor in ('incoming', 'cycle'):
            newer['relations'] = [edge('supersedes', source['id'], number=20)]
        if successor in ('outgoing', 'cycle'):
            source = {**source, 'relations': [edge('supersedes', newer['id'], number=21)]}
        model = replace_values(root, model,
            [source if a['id'] == source['id'] else a for a in model.artifacts] + [newer])
    return model, source


def load_current(root, model):
    return TargetModel(model.configuration_bytes, model.binding,
        [ModelDocument(d.path, (root / d.path).read_bytes()) for d in model.documents],
        profile=model.profile, resource_files=model.resource_files, **model.reservations)


@pytest.mark.parametrize('kind', ['transition', 'retire'])
def test_initial_host_gate_denial_survives_caller_list_mutation(tmp_path, kind):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    checked = []
    def deny(context):
        checked.append(context.subjects)
        return context.result([{'reason': 'host_lifecycle_denied', 'severity': 'error'}])
    supplied = [ModelGate('lifecycle', 'host-denial-v1',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}), deny)]
    options = arguments(root, kind); options['gates'] = supplied
    before = file_inventory(root); native_source = lifecycle.ProjectSource
    def read(*args, **kwargs):
        supplied.clear()
        return native_source(*args, **kwargs)
    with patch.object(lifecycle, 'ProjectSource', side_effect=read), pytest.raises(TargetError) as error:
        call(model, operation(source, kind), options)
    assert supplied == [] and checked and all(v == (source['id'],) for v in checked)
    assert error.value.reason == 'complete_target_validation_required' and file_inventory(root) == before


@pytest.mark.parametrize('to', ['rejected', 'retired'])
@pytest.mark.parametrize('metadata', [{}, {'reason': ''}, {'reason': ' '}])
def test_required_transition_reason_is_checked_before_publication(tmp_path, to, metadata):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    before = file_inventory(root)
    prepared = ChangeOperation({'op': 'transition', 'target': source['id'],
        'from': 'draft', 'to': to, 'metadata': metadata})
    with pytest.raises(LifecycleError) as error:
        transition_artifact(model, prepared, **arguments(root, 'transition'))
    assert error.value.reason == 'nonempty_text_required' and error.value.exit_code == 3
    assert file_inventory(root) == before


@pytest.mark.parametrize('to', ['draft', 'proposed', 'in_review', 'approved', 'rejected', 'superseded'])
def test_retired_source_cannot_be_resurrected(tmp_path, to):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, maturity='retired')
    before = file_inventory(root)
    with pytest.raises(LifecycleError) as error:
        transition_artifact(model, normalize_transition_input(source, to=to, reason=REASON),
                            **arguments(root, 'transition'))
    assert error.value.reason == 'invalid_lifecycle_transition' and error.value.exit_code == 3
    assert file_inventory(root) == before


def test_equal_transition_states_are_not_a_guarded_retire_noop():
    with no_write_attempts(), pytest.raises(ChangePlanError) as error:
        normalize_transition_input(domain_value('requirement', maturity='retired'),
                                   to='retired', reason=REASON)
    assert error.value.reason == 'transition_requires_distinct_states' and error.value.exit_code == 3


def test_original_transition_from_is_not_rebased_to_current_maturity(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, maturity='proposed')
    prepared = normalize_transition_input({**source, 'maturity': 'draft'}, to='retired', reason=REASON)
    before = file_inventory(root)
    with pytest.raises(LifecycleError) as error:
        transition_artifact(model, prepared, **arguments(root, 'transition'))
    assert error.value.reason == 'expected_maturity_mismatch' and error.value.exit_code == 3
    assert file_inventory(root) == before


@pytest.mark.parametrize('maturity', ['draft', 'retired'])
@pytest.mark.parametrize('bad', ['revision', 'hash', 'both'])
def test_both_retire_guards_remain_required_even_for_noop(tmp_path, maturity, bad):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, maturity=maturity)
    guards = {'expected_revision': 7, 'expected_sha256': canonical_json_sha256(source)}
    if bad in ('revision', 'both'): guards['expected_revision'] = 6
    if bad in ('hash', 'both'): guards['expected_sha256'] = 'a' * 64
    before = file_inventory(root)
    with pytest.raises(LifecycleError) as error:
        retire_artifact(model, normalize_retire_input(source, reason=REASON, **guards),
                        **arguments(root, 'retire'))
    assert error.value.reason == ('expected_hash_mismatch' if bad == 'hash' else 'expected_revision_mismatch')
    assert error.value.exit_code == 3 and file_inventory(root) == before


@pytest.mark.parametrize('to', ['retired', 'proposed', 'superseded'])
def test_pure_approved_transition_has_one_revision_and_no_hidden_reset(tmp_path, to):
    root = tmp_path / 'project'
    model, source = approved_project(root, 'incoming' if to == 'superseded' else 'none')
    before = file_inventory(root); prepared = normalize_transition_input(source, to=to, reason=REASON)
    result = transition_artifact(model, prepared, **arguments(root, 'transition'))
    assert_publication(root, model, source, prepared, ACTOR, result, before, to)


def test_guarded_retire_of_approved_content_does_not_reset_to_proposed(tmp_path):
    root = tmp_path / 'project'; model, source = approved_project(root)
    before = file_inventory(root); prepared = normalize_retire_input(source, reason=REASON,
        expected_revision=7, expected_sha256=canonical_json_sha256(source))
    result = retire_artifact(model, prepared, **arguments(root, 'retire'))
    assert_publication(root, model, source, prepared, ACTOR, result, before, 'retired')


@pytest.mark.parametrize('successor,reason', [('none', 'successor_required_in_final_model'),
    ('outgoing', 'successor_required_in_final_model'), ('cycle', 'relation_hierarchy_cycle')])
def test_superseded_needs_real_incoming_acyclic_successor(tmp_path, successor, reason):
    root = tmp_path / 'project'; model, source = approved_project(root, successor)
    before = file_inventory(root)
    with pytest.raises(LifecycleError) as error:
        transition_artifact(model, normalize_transition_input(source, to='superseded', reason=REASON),
                            **arguments(root, 'transition'))
    assert error.value.reason == reason and error.value.exit_code == 3 and file_inventory(root) == before


@pytest.mark.parametrize('changed', ['target', 'from', 'to', 'reason'])
def test_confirmed_transition_request_cannot_change_its_original_operation(tmp_path, changed):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    prepared = operation(source, 'transition'); options = arguments(root, 'transition')
    call(model, prepared, options); value = prepared.data
    if changed == 'target': value['target'] = goals[0]['id']
    if changed == 'from': value['from'] = 'proposed'
    if changed == 'to': value['to'] = 'rejected'
    if changed == 'reason': value['metadata']['reason'] = 'Changed request intent.'
    before = file_inventory(root)
    with no_write_attempts(), patch.object(lifecycle, 'prepare_change_target', side_effect=AssertionError), \
            patch.object(lifecycle, 'project_lock', side_effect=AssertionError), \
            pytest.raises((AuthoringError, RequestIdConflict)) as error:
        transition_artifact(model, ChangeOperation(value), **options)
    assert error.value.exit_code == 6 and file_inventory(root) == before


@pytest.mark.parametrize('changed', ['target', 'revision', 'hash', 'reason'])
def test_confirmed_retire_request_cannot_change_guards_or_intent(tmp_path, changed):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    prepared = normalize_retire_input(source, reason=REASON, expected_revision=7,
                                     expected_sha256=canonical_json_sha256(source))
    options = arguments(root, 'retire'); call(model, prepared, options); value = prepared.data
    if changed == 'target': value['target'] = goals[0]['id']
    if changed == 'revision': value['expected_revision'] = 8
    if changed == 'hash': value['expected_sha256'] = 'a' * 64
    if changed == 'reason': value['reason'] = 'Changed retirement intent.'
    before = file_inventory(root)
    with no_write_attempts(), patch.object(lifecycle, 'prepare_change_target', side_effect=AssertionError), \
            patch.object(lifecycle, 'project_lock', side_effect=AssertionError), \
            pytest.raises((AuthoringError, RequestIdConflict)) as error:
        retire_artifact(model, ChangeOperation(value), **options)
    assert error.value.exit_code == 6 and file_inventory(root) == before


@pytest.mark.parametrize('first', ['transition', 'retire'])
def test_request_id_cannot_change_between_transition_and_retire(tmp_path, first):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    call(model, operation(source, first), arguments(root, first)); before = file_inventory(root)
    other = 'retire' if first == 'transition' else 'transition'
    with no_write_attempts(), patch.object(lifecycle, 'project_lock', side_effect=AssertionError), \
            pytest.raises(RequestIdConflict) as error:
        call(model, operation(source, other), arguments(root, other))
    assert error.value.reason == 'request_operations_conflict' and error.value.exit_code == 6
    assert file_inventory(root) == before


@pytest.mark.parametrize('kind', ['transition', 'retire'])
def test_changed_physical_source_is_preserved(tmp_path, kind):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    path = root / artifact_path('requirement', source['id'], 'SR')
    foreign = canonical_json_bytes({**source, 'statement': 'Foreign change.'}); path.write_bytes(foreign)
    before = file_inventory(root)
    with pytest.raises(PublicationCheckError) as error:
        call(model, operation(source, kind), arguments(root, kind))
    assert error.value.reason == 'publication_base_changed' and error.value.exit_code == 6
    assert path.read_bytes() == foreign and file_inventory(root) == before


@pytest.mark.parametrize('kind', ['transition', 'retire'])
def test_existing_writer_remains_untouched(tmp_path, kind):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    with project_lock(root, **lock_options()) as held:
        before = file_inventory(root)
        with pytest.raises(ProjectLockError) as error:
            call(model, operation(source, kind), arguments(root, kind))
        assert error.value.reason == 'project_lock_busy' and error.value.exit_code == 5
        assert held.check() and file_inventory(root) == before


@pytest.mark.parametrize('kind', ['transition', 'retire'])
@pytest.mark.parametrize('moved', [False, True])
def test_failed_real_replace_keeps_actual_lifecycle_bytes_and_recovery_evidence(tmp_path, kind, moved):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    path = artifact_path('requirement', source['id'], 'SR'); raw = (root / path).read_bytes()
    before = file_inventory(root); native_replace = os.replace; attempts = []
    def replace(src, dst, **kwargs):
        if str(dst) == source['id'] + '.json':
            attempts.append(str(dst))
            if moved: native_replace(src, dst, **kwargs)
            raise OSError('injected lifecycle replace failure')
        return native_replace(src, dst, **kwargs)
    with patch.object(os, 'replace', side_effect=replace), pytest.raises(CommitPublicationError) as error:
        call(model, operation(source, kind), arguments(root, kind))
    assert attempts == [source['id'] + '.json']
    assert error.value.reason == 'publication_io_failure' and error.value.exit_code == 5
    assert error.value.write_state == 'unknown' and error.value.mutation_possible and error.value.publication_possible
    assert error.value.published_count == 0
    if moved:
        value = json.loads((root / path).read_bytes())
        assert value == {**source, 'maturity': 'retired', 'revision': 8,
                        'updated_by': ACTOR, 'updated_at': TIME}
    else: assert (root / path).read_bytes() == raw
    journal = json.loads((root / '.specroad/transactions/txn-lifecycle/journal.json').read_bytes())
    assert journal['state'] == 'committing' and journal['published_count'] == 0
    after = {p: rest for p, *rest in file_inventory(root)}
    for p, *rest in before:
        if p != path: assert after[p] == rest
    retained = file_inventory(root)
    with pytest.raises(ProjectLockError) as retry:
        call(model, operation(source, kind), arguments(root, kind))
    assert retry.value.reason == 'transaction_journal_blocks_lock' and retry.value.exit_code == 5
    assert file_inventory(root) == retained


@pytest.mark.parametrize('kind', ['transition', 'retire'])
def test_ci_with_explicit_request_keeps_original_actor_in_content_and_audit(tmp_path, kind):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    actor = {'actor_type': 'ci', 'actor_id': 'owned-ci'}; before = file_inventory(root)
    prepared = operation(source, kind)
    result = call(model, prepared, arguments(root, kind, actor=actor, request_id='ci-lifecycle-1'))
    assert_publication(root, model, source, prepared, actor, result, before, 'retired')
    assert result['completion']['request_id'] == 'ci-lifecycle-1'


def test_fresh_retire_noop_still_requires_current_host_authority(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    call(model, operation(source, 'retire'), arguments(root, 'retire'))
    current = load_current(root, model); retired = next(a for a in current.artifacts if a['id'] == source['id'])
    options = arguments(root, 'retire', request_id='new-noop', transaction_id='txn-noop')
    options['authority'] = PublicationAuthority('deny-current-noop', '1', lambda r: False)
    before = file_inventory(root)
    with pytest.raises(PublicationCheckError) as error:
        retire_artifact(current, operation(retired, 'retire'), **options)
    assert error.value.reason == 'publication_authorization_denied' and error.value.exit_code == 7
    assert file_inventory(root) == before


@pytest.mark.parametrize('changed', ['actor', 'time', 'target', 'maturity', 'unrelated_content'])
def test_bound_lifecycle_evidence_does_not_certify_a_different_target(tmp_path, changed):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    prepared = operation(source, 'transition')
    bound = lifecycle._prepare_lifecycle_gate(model, prepared, actor=ACTOR, planned_at=TIME)
    options = arguments(root, 'transition'); options['gates'] = [bound]
    if changed == 'actor': options['actor'] = {**ACTOR, 'actor_id': 'another-author'}
    if changed == 'time': options['planned_at'] = '2026-10-11T00:00:00Z'
    if changed == 'target': prepared = operation(goals[0], 'transition')
    if changed == 'maturity': prepared = normalize_transition_input(source, to='rejected', reason=REASON)
    if changed == 'unrelated_content':
        model = replace_values(root, model, [{**goals[0], 'statement': 'Changed context.'}, goals[1], source])
    before = file_inventory(root)
    with pytest.raises(TargetError) as error: transition_artifact(model, prepared, **options)
    assert error.value.reason == 'complete_target_validation_required' and file_inventory(root) == before
