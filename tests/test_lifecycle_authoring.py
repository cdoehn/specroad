"""Real lifecycle publication, unchanged content, native audit and safe retry."""
import json
from unittest.mock import patch

import pytest

from specroad.authoring import lifecycle
from specroad.authoring.lifecycle import (normalize_transition_input, normalize_retire_input,
    transition_artifact, retire_artifact)
from specroad.changes import (AuthoringError, ChangePlanError, LifecycleError,
    PublicationAuthority, PublicationCheckError, TargetError, TargetModel,
    inspect_project_lock, lifecycle_content_sha256)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.validation import ModelDocument, ModelGate
from support.domain import domain_value
from support.model import put
from support.read_only import inventory as file_inventory, no_write_attempts
from support.records import record_value
from test_relation_authoring import stored_project, receipt, assert_preserved

ACTOR = {'actor_type': 'human', 'actor_id': 'lifecycle-editor'}
TIME = '2026-10-10T18:30:00Z'
REASON = 'Explicit lifecycle decision.'


def arguments(root, kind, *, actor=ACTOR, request_id='lifecycle-1', transaction_id='txn-lifecycle'):
    def authorize(request):
        state = inspect_project_lock(root).data
        assert state['record']['kind'] == 'writer'
        assert state['record']['transaction_id'] == transaction_id
        assert [op.op for op in request.plan.operations] == [kind]
        return True
    return dict(actor=actor, request_id=request_id, transaction_id=transaction_id,
        planned_at=TIME, change_plan_id='CP-lifecycle',
        authority=PublicationAuthority('owned-lifecycle-host', '1', authorize))


def operation(source, kind):
    if kind == 'transition':
        return normalize_transition_input(source, to='retired', reason=REASON)
    return normalize_retire_input(source, reason=REASON, expected_revision=source['revision'])


def call(model, prepared, options):
    writer = transition_artifact if prepared.op == 'transition' else retire_artifact
    return writer(model, prepared, **options)


def replace_values(root, model, values):
    documents = [ModelDocument(artifact_path(a['artifact_type'], a['id'], 'SR'),
                              canonical_json_bytes(a)) for a in values]
    rebuilt = TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files, **model.reservations)
    for document in documents: put(root, document.path, document.content)
    return rebuilt


def assert_publication(root, model, old, prepared, actor, result, before, maturity):
    path = artifact_path(old['artifact_type'], old['id'], 'SR')
    expected = {**old, 'maturity': maturity, 'revision': old['revision'] + 1,
                'updated_by': actor, 'updated_at': TIME}
    actual = json.loads((root / path).read_bytes())
    assert actual == expected and (root / path).read_bytes() == canonical_json_bytes(expected)
    assert lifecycle_content_sha256(actual) == lifecycle_content_sha256(old)
    assert result['command_id'] == 'lifecycle.transition' and result['artifact_id'] == old['id']
    assert result['operation'] == prepared.op and not result['no_change'] and not result['replayed']
    assert result['write_state'] == 'committed' and result['completion']['commit_completed']
    assert result['completion']['cleanup_completed'] and result['completion']['current_target_verified']
    proof = receipt(root, result)
    assert proof['operations'] == [prepared.data] and proof['created_ids'] == []
    assert proof['journal']['actor'] == actor and proof['journal']['planned_at'] == TIME
    assert next(a for a in model.artifacts if a['id'] == old['id']) == old
    assert_preserved(root, before, path)


@pytest.mark.parametrize('actor_type', ['human', 'tool'])
@pytest.mark.parametrize('artifact_kind,source_state,target_state', [
    ('requirement', 'draft', 'proposed'), ('requirement', 'draft', 'rejected'),
    ('requirement', 'draft', 'retired'), ('need', 'proposed', 'in_review'),
    ('requirement', 'in_review', 'proposed'), ('requirement', 'proposed', 'draft')])
def test_transition_preserves_content_and_binds_one_revision_and_original_audit(
        tmp_path, actor_type, artifact_kind, source_state, target_state):
    root = tmp_path / 'project'
    model, source, _ = stored_project(root, kind=artifact_kind, maturity=source_state)
    actor = {**ACTOR, 'actor_type': actor_type}; before = file_inventory(root)
    prepared = normalize_transition_input(source, to=target_state, reason=REASON)
    assert prepared.data == {'op': 'transition', 'target': source['id'],
        'from': source_state, 'to': target_state, 'metadata': {'reason': REASON}}
    with patch('secrets.token_bytes', side_effect=AssertionError('lifecycle allocates no identity')):
        result = transition_artifact(model, prepared, **arguments(root, 'transition', actor=actor))
    assert_publication(root, model, source, prepared, actor, result, before, target_state)


@pytest.mark.parametrize('actor_type', ['human', 'tool'])
@pytest.mark.parametrize('guard', ['revision', 'hash', 'both'])
def test_retire_uses_explicit_guards_and_preserves_content_and_reason_audit(tmp_path, actor_type, guard):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    actor = {**ACTOR, 'actor_type': actor_type}; before = file_inventory(root)
    guards = {}
    if guard in ('revision', 'both'): guards['expected_revision'] = 7
    if guard in ('hash', 'both'): guards['expected_sha256'] = canonical_json_sha256(source)
    prepared = normalize_retire_input(source, reason=REASON, **guards)
    assert prepared.data == {'op': 'retire', 'target': source['id'], 'reason': REASON, **guards}
    with patch('secrets.token_bytes', side_effect=AssertionError('retire allocates no identity')):
        result = retire_artifact(model, prepared, **arguments(root, 'retire', actor=actor))
    assert_publication(root, model, source, prepared, actor, result, before, 'retired')


@pytest.mark.parametrize('kind', ['transition', 'retire'])
def test_human_request_id_is_optional(tmp_path, kind):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    result = call(model, operation(source, kind), arguments(root, kind, request_id=None))
    assert result['completion']['receipts']['request'] is None
    assert result['completion']['commit_completed']


@pytest.mark.parametrize('kind', ['transition', 'retire'])
def test_confirmed_retry_precedes_planning_and_lock_and_preserves_original_actor(tmp_path, kind):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    prepared = operation(source, kind); first = call(model, prepared, arguments(root, kind))
    before = file_inventory(root)
    options = arguments(root, kind, actor={'actor_type': 'tool', 'actor_id': 'retry-agent'},
                        transaction_id='txn-retry')
    options.update(planned_at='2026-10-11T00:00:00Z', change_plan_id='CP-retry')
    with no_write_attempts(), patch.object(lifecycle, 'prepare_change_target',
            side_effect=AssertionError('historical retry must not replan')), \
            patch.object(lifecycle, 'project_lock', side_effect=AssertionError('no retry lock')):
        repeated = call(model, prepared, options)
    assert repeated['replayed'] and not repeated['no_change']
    assert not repeated['completion']['current_target_verified']
    for key in ('transaction_id', 'request_id', 'target_model_root_sha256', 'receipts'):
        assert repeated['completion'][key] == first['completion'][key]
    assert receipt(root, repeated)['journal']['actor'] == ACTOR
    assert file_inventory(root) == before


def test_fresh_guarded_retire_of_actual_retired_target_is_noop_without_new_receipt(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    call(model, operation(source, 'retire'), arguments(root, 'retire'))
    documents = [ModelDocument(d.path, (root / d.path).read_bytes()) for d in model.documents]
    current = TargetModel(model.configuration_bytes, model.binding, documents,
                         profile=model.profile, resource_files=model.resource_files)
    retired = next(a for a in current.artifacts if a['id'] == source['id'])
    assert retired['maturity'] == 'retired' and retired['revision'] == 8
    before = file_inventory(root)
    result = retire_artifact(current, normalize_retire_input(retired, reason=REASON,
        expected_revision=8, expected_sha256=canonical_json_sha256(retired)),
        **arguments(root, 'retire', request_id='retire-again', transaction_id='txn-noop'))
    assert result['no_change'] and result['completion'] is None and not result['replayed']
    assert result['write_state'] == 'not_committed' and file_inventory(root) == before


@pytest.mark.parametrize('kind', ['transition', 'retire'])
@pytest.mark.parametrize('actor_type,request_id,code', [('ai', 'lifecycle-1', 7), ('ci', None, 2)])
def test_actor_policy_blocks_before_writer(tmp_path, kind, actor_type, request_id, code):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    before = file_inventory(root); prepared = operation(source, kind)
    options = arguments(root, kind, actor={'actor_type': actor_type, 'actor_id': 'caller'},
                        request_id=request_id)
    with no_write_attempts(), patch.object(lifecycle, 'project_lock', side_effect=AssertionError('no lock')):
        with pytest.raises(AuthoringError) as error: call(model, prepared, options)
    assert error.value.exit_code == code and file_inventory(root) == before


@pytest.mark.parametrize('kind', ['transition', 'retire'])
def test_host_denial_leaves_original_tree(tmp_path, kind):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    before = file_inventory(root); options = arguments(root, kind)
    options['authority'] = PublicationAuthority('deny', '1', lambda request: False)
    with pytest.raises(PublicationCheckError) as error: call(model, operation(source, kind), options)
    assert error.value.reason == 'publication_authorization_denied' and error.value.exit_code == 7
    assert file_inventory(root) == before


@pytest.mark.parametrize('kind', ['transition', 'retire'])
def test_explicit_host_lifecycle_denial_is_not_replaced(tmp_path, kind):
    root = tmp_path / 'project'; model, source, _ = stored_project(root)
    before = file_inventory(root); options = arguments(root, kind)
    options['gates'] = [ModelGate('lifecycle', 'host-denial-v1',
        lambda c: c.dependency_result({key: list(c.all_ids) for key in c.subjects}),
        lambda c: c.result([{'reason': 'host_lifecycle_denied', 'severity': 'error'}]))]
    with pytest.raises(TargetError) as error: call(model, operation(source, kind), options)
    assert error.value.reason == 'complete_target_validation_required' and file_inventory(root) == before


@pytest.mark.parametrize('kind', ['transition', 'retire'])
def test_other_non_draft_subject_still_requires_actual_lifecycle_service(tmp_path, kind):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    model = replace_values(root, model, [{**goals[0], 'maturity': 'proposed'}, goals[1], source])
    before = file_inventory(root)
    with pytest.raises(TargetError) as error: call(model, operation(source, kind), arguments(root, kind))
    assert error.value.reason == 'complete_target_validation_required' and file_inventory(root) == before


@pytest.mark.parametrize('kind', ['transition', 'retire'])
def test_invalid_unrelated_artifact_blocks_full_supplied_target(tmp_path, kind):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, broken=True)
    before = file_inventory(root)
    with pytest.raises(ChangePlanError) as error: call(model, operation(source, kind), arguments(root, kind))
    assert error.value.reason == 'missing_field' and file_inventory(root) == before


@pytest.mark.parametrize('operation_kind', ['transition', 'retire'])
@pytest.mark.parametrize('artifact_kind', ['proposal', 'evidence', 'baseline', 'relation_review'])
def test_special_artifacts_cannot_use_general_lifecycle(tmp_path, operation_kind, artifact_kind):
    root = tmp_path / 'project'; model, source, goals = stored_project(root)
    special = record_value(artifact_kind)
    model = replace_values(root, model, [*goals, source, special]); before = file_inventory(root)
    with no_write_attempts(), pytest.raises(ChangePlanError) as error:
        call(model, operation(special, operation_kind), arguments(root, operation_kind))
    assert type(error.value) is ChangePlanError and error.value.exit_code == 3
    assert error.value.reason == 'specialized_operation_required' and file_inventory(root) == before


@pytest.mark.parametrize('actor_type', ['human', 'tool'])
def test_requirement_without_formal_prerequisites_cannot_enter_review(tmp_path, actor_type):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, maturity='proposed')
    before = file_inventory(root); observed = []
    native = lifecycle.prepare_change_target
    def observe(*args, **kwargs):
        checked = native(*args, **kwargs)
        observed.append(checked.data)
        return checked
    with patch.object(lifecycle, 'prepare_change_target', side_effect=observe):
        with pytest.raises(TargetError) as error:
            transition_artifact(model, normalize_transition_input(source, to='in_review', reason=REASON),
                **arguments(root, 'transition', actor={**ACTOR, 'actor_type': actor_type}))
    assert error.value.reason == 'complete_target_validation_required' and file_inventory(root) == before
    assert len(observed) == 1 and not observed[0]['target_validated']
    stage = next(s for s in observed[0]['validation']['source_report']['stages']
                 if s['stage'] == 'approval_formal')
    assert stage['status'] == 'failed' and source['id'] in stage['checked_ids']
    assert [(d['code'], d['reason'], d['location']['pointer'], d['artifact_id'])
            for d in stage['diagnostics']] == [('SRV002', 'schema_any_of', '', source['id'])]


def test_approval_requires_dedicated_gate_and_is_not_granted_by_human_label(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, maturity='in_review')
    before = file_inventory(root)
    with pytest.raises(LifecycleError) as error:
        transition_artifact(model, normalize_transition_input(source, to='approved'),
                            **arguments(root, 'transition'))
    assert error.value.reason == 'approval_gate_required' and file_inventory(root) == before


@pytest.mark.parametrize('guards', [{}, {'expected_revision': None}, {'expected_revision': True},
    {'expected_revision': 0}, {'expected_sha256': None}, {'expected_sha256': 'short'}])
def test_retire_guard_is_explicit_and_never_inferred(guards):
    with no_write_attempts(), pytest.raises(ChangePlanError) as error:
        normalize_retire_input(domain_value('requirement'), reason=REASON, **guards)
    assert error.value.exit_code == 3
