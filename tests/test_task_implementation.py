"""Human Done decisions bound to an exact task and real guarded publication."""
from dataclasses import FrozenInstanceError
import json

import pytest

from specroad.changes import TargetModel, PublicationAuthority, PublicationCheckError, TargetError
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.planning import (TaskDoneContext, HumanTaskDoneReview, TaskImplementation,
    prepare_task_implementation, implement_task)
from specroad.validation import ModelDocument, ModelGate, ReviewVerifier, ReviewVerification
from support.domain import domain_value
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts, inventory
from support.records import ref
from support.targets import model, SCOPE
from test_artifact_creation import project

NOW = '2026-10-21T16:00:00Z'
ACTOR = {'actor_type': 'human', 'actor_id': 'task-editor'}


def task(**kwargs):
    return domain_value('task', done_criteria=['Reject invalid input.', 'Preserve the original file.'],
                        **kwargs)


def context(supplied=None):
    return TaskDoneContext(model([task()]) if supplied is None else supplied,
                           ref('TASK'), scope_descriptor=ScopeDescriptor(SCOPE))


def review_data(ctx):
    value = ctx.data
    return {'review_id': 'synthetic-done-review', 'input_sha256': ctx.input_sha256,
        **{key: value[key] for key in ('task_id', 'task_sha256', 'done_criteria_sha256')},
        'reviewer': {'actor_type': 'human', 'actor_id': 'synthetic-reviewer'},
        'reviewed_at': NOW, 'decision': 'confirmed', 'criteria': [True, True]}


def verifier(*, authenticated=True, current=True):
    # Explicit test double; it never authenticates a real human.
    return ReviewVerifier('synthetic-host-review-service', '1', lambda ctx, review:
        ReviewVerification(ctx.input_sha256, review.sha256, authenticated, current))


def prepare(supplied=None):
    ctx = context(supplied)
    return prepare_task_implementation(ctx, review=HumanTaskDoneReview(review_data(ctx)),
                                       verifier=verifier())


def live(root, **kwargs):
    original, _ = project(root)
    value = task(**kwargs)
    supplied = TargetModel(original.configuration_bytes, original.binding,
        (*original.documents, ModelDocument(artifact_path('task', value['id'], 'SR'),
                                           canonical_json_bytes(value))),
        profile=original.profile, resource_files=original.resource_files)
    for name, raw in supplied.source_files.items(): put(root, name, raw)
    return supplied


def options():
    return dict(actor=ACTOR, planned_at=NOW, change_plan_id='CP-task', transaction_id='txn-task',
        request_id='implement-task-1',
        authority=PublicationAuthority('explicit-test-host', '1', lambda request: True))


@pytest.mark.parametrize('status', ['not_started', 'in_progress', 'blocked', 'not_applicable'])
def test_complete_human_review_prepares_only_the_guarded_status_update(status):
    value = task(implementation_status=status); supplied = model([value]); before = supplied.source_files
    with no_write_attempts(): prepared = prepare(supplied)
    assert prepared.operation.data == {'op': 'update', 'target': value['id'],
        'expected_revision': 1, 'expected_sha256': canonical_json_sha256(value),
        'patch': [{'op': 'replace', 'path': '/implementation_status', 'value': 'implemented'}]}
    assert supplied.source_files == before and value in supplied.artifacts
    assert prepared.data['done_criteria_sha256'] == canonical_json_sha256(value['done_criteria'])
    assert prepared.data['done_criteria_satisfied'] and prepared.data['authenticated_by_supplied_verifier']
    assert not any(prepared.data[key] for key in ('write_authorized', 'approval_granted',
        'project_files_verified', 'test_code_executed', 'release_readiness_evaluated'))


def test_native_writer_publishes_reviewed_implemented_with_one_revision_and_durable_retry(tmp_path):
    root = tmp_path / 'project'; supplied = live(root, implementation_status='in_progress')
    prepared = prepare(supplied); value = next(v for v in supplied.artifacts if v['id'] == ref('TASK'))
    path = artifact_path('task', ref('TASK'), 'SR'); (root / path).chmod(0o640)
    before = inventory(root)
    result = implement_task(supplied, prepared, **options())
    actual = json.loads((root / path).read_bytes())
    assert actual == {**value, 'implementation_status': 'implemented', 'revision': 2,
                      'updated_at': NOW, 'updated_by': ACTOR}
    assert (root / path).read_bytes() == canonical_json_bytes(actual)
    assert (root / path).stat().st_mode & 0o777 == 0o640
    assert result['write_state'] == 'committed' and not result['replayed']
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    after = {entry[0]: entry[1:] for entry in inventory(root)}
    for name, *old in before:
        if name != path: assert after[name] == tuple(old)
    assert value in supplied.artifacts
    after = inventory(root)
    with no_write_attempts(): repeated = implement_task(supplied, prepared, **options())
    assert repeated['replayed'] and not repeated['completion']['current_target_verified']
    assert repeated['completion']['transaction_id'] == result['completion']['transaction_id']
    assert inventory(root) == after


@pytest.mark.parametrize('criteria', [[], [True], [True, False], [False, True], [True, True, True]])
def test_every_stored_done_criterion_needs_explicit_confirmation(criteria):
    ctx = context(); value = review_data(ctx); value['criteria'] = criteria
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        prepare_task_implementation(ctx, review=HumanTaskDoneReview(value), verifier=verifier())
    assert caught.value.reason == 'task_done_criteria_unconfirmed'


@pytest.mark.parametrize('field', ['input_sha256', 'task_sha256', 'done_criteria_sha256', 'task_id'])
def test_review_must_match_the_exact_context_task_and_criteria(field):
    ctx = context(); value = review_data(ctx)
    value[field] = ref('TASK', '1') if field == 'task_id' else 'a' * 64
    with pytest.raises(ModelError) as caught:
        prepare_task_implementation(ctx, review=HumanTaskDoneReview(value), verifier=verifier())
    assert caught.value.reason == 'task_done_review_binding_mismatch'


@pytest.mark.parametrize('kind', ['ai', 'ci', 'tool'])
def test_nonhuman_claim_cannot_replace_a_human_done_review(kind):
    ctx = context(); value = review_data(ctx); value['reviewer']['actor_type'] = kind
    with pytest.raises(ModelError) as caught:
        prepare_task_implementation(ctx, review=HumanTaskDoneReview(value), verifier=verifier())
    assert caught.value.reason == 'task_done_human_review_required'


def test_rejected_review_is_not_a_positive_decision():
    ctx = context(); value = review_data(ctx); value['decision'] = 'rejected'
    with pytest.raises(ModelError) as caught:
        prepare_task_implementation(ctx, review=HumanTaskDoneReview(value), verifier=verifier())
    assert caught.value.reason == 'task_done_criteria_unconfirmed'


@pytest.mark.parametrize('mode', ['missing', 'unauthenticated', 'revoked', 'wrong_context', 'wrong_review', 'boolean', 'exception'])
def test_passive_human_label_requires_a_current_bound_host_verification(mode):
    ctx = context(); review = HumanTaskDoneReview(review_data(ctx)); service = verifier()
    if mode == 'missing': service = None
    elif mode == 'unauthenticated': service = verifier(authenticated=False)
    elif mode == 'revoked': service = verifier(current=False)
    else:
        def observe(context, value):
            if mode == 'exception': raise RuntimeError('service unavailable')
            if mode == 'boolean': return True
            return ReviewVerification('f'*64 if mode == 'wrong_context' else context.input_sha256,
                'e'*64 if mode == 'wrong_review' else value.sha256, True, True)
        service = ReviewVerifier('adversarial-test-service', '1', observe)
    with no_write_attempts(), pytest.raises(ModelError):
        prepare_task_implementation(ctx, review=review, verifier=service)


@pytest.mark.parametrize('scope', ['configuration', 'explicit'])
def test_partial_or_configured_review_cannot_certify_global_task_status(scope):
    data = dict(SCOPE)
    if scope == 'configuration': data['configuration_id'] = ref('CFG')
    else: data.update(scope_kind='explicit', selector={'artifact_ids': [ref('TASK')], 'resource_ids': []})
    with pytest.raises(ModelError) as caught:
        TaskDoneContext(model([task()]), ref('TASK'), scope_descriptor=ScopeDescriptor(data))
    assert caught.value.reason == 'task_done_unconfigured_project_scope_required'


def test_review_context_and_preparation_are_owned_not_truthy_or_serialized_authorities():
    ctx = context(); value = review_data(ctx); review = HumanTaskDoneReview(value)
    prepared = prepare_task_implementation(ctx, review=review, verifier=verifier())
    value['criteria'][0] = False; review.data['criteria'][0] = False
    ctx.data['task']['done_criteria'].clear()
    prepared.data['operation']['patch'][0]['value'] = 'blocked'
    assert review.data['criteria'] == [True, True]
    assert len(ctx.data['task']['done_criteria']) == 2
    assert prepared.operation.data['patch'][0]['value'] == 'implemented'
    assert prepared.sha256 == canonical_json_sha256(prepared.data)
    with pytest.raises(TypeError): bool(prepared)
    with pytest.raises(TypeError): bool(ctx)
    with pytest.raises(TypeError): TaskImplementation({})
    with pytest.raises(FrozenInstanceError): prepared._encoded = b'{}'
    with pytest.raises(ModelError):
        prepare_task_implementation(ctx, review=review.data, verifier=verifier())


@pytest.mark.parametrize('changed', ['task', 'other_artifact'])
def test_review_cannot_be_rebound_to_a_changed_model(tmp_path, changed):
    supplied = live(tmp_path / 'project'); prepared = prepare(supplied)
    rows = supplied.artifacts
    next(v for v in rows if v['artifact_type'] == ('task' if changed == 'task' else 'goal'))['title'] = 'Changed'
    altered = TargetModel(supplied.configuration_bytes, supplied.binding,
        [ModelDocument(artifact_path(v['artifact_type'], v['id'], 'SR'), canonical_json_bytes(v)) for v in rows],
        profile=supplied.profile, resource_files=supplied.resource_files)
    before = inventory(tmp_path / 'project')
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        implement_task(altered, prepared, **options())
    assert caught.value.reason == 'task_done_review_binding_mismatch'
    assert inventory(tmp_path / 'project') == before


def test_native_publication_authority_is_still_required(tmp_path):
    supplied = live(tmp_path / 'project'); prepared = prepare(supplied); args = options()
    args['authority'] = PublicationAuthority('deny', '1', lambda request: False)
    before = inventory(tmp_path / 'project')
    with pytest.raises(PublicationCheckError) as caught: implement_task(supplied, prepared, **args)
    assert caught.value.reason == 'publication_authorization_denied'
    assert inventory(tmp_path / 'project') == before


def test_changed_live_task_blocks_native_publication(tmp_path):
    supplied = live(tmp_path / 'project'); prepared = prepare(supplied)
    value = next(v for v in supplied.artifacts if v['id'] == ref('TASK')); value['description'] = 'Changed'
    put(tmp_path / 'project', artifact_path('task', value['id'], 'SR'), canonical_json_bytes(value))
    before = inventory(tmp_path / 'project')
    with pytest.raises(ModelError): implement_task(supplied, prepared, **options())
    assert inventory(tmp_path / 'project') == before


def test_review_is_rechecked_at_the_target_gate_after_preparation(tmp_path):
    supplied = live(tmp_path / 'project'); ctx = context(supplied); calls = []
    def observe(context, review):
        calls.append(context.input_sha256)
        return ReviewVerification(context.input_sha256, review.sha256, True, len(calls) < 3)
    prepared = prepare_task_implementation(ctx, review=HumanTaskDoneReview(review_data(ctx)),
        verifier=ReviewVerifier('revoked-at-target', '1', observe))
    before = inventory(tmp_path / 'project')
    with pytest.raises(TargetError): implement_task(supplied, prepared, **options())
    assert len(calls) >= 3 and inventory(tmp_path / 'project') == before


def test_host_cannot_replace_the_done_gate(tmp_path):
    supplied = live(tmp_path / 'project'); prepared = prepare(supplied); args = options()
    args['gates'] = (ModelGate('extension:task-done', 'forged',
        lambda c: c.dependency_result({i: [] for i in c.subjects}), lambda c: c.result()),)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        implement_task(supplied, prepared, **args)
    assert caught.value.reason == 'task_done_gate_override'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_review_preparation_has_identical_bindings_in_isolated_core_and_pyz(mode, tmp_path):
    supplied = model([task()]); expected = prepare(supplied).data
    body = '''import json
from specroad.changes import TargetModel
from specroad.model.model_manifest import ProjectReadBinding
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument, ReviewVerifier, ReviewVerification
from specroad.planning import TaskDoneContext, HumanTaskDoneReview, prepare_task_implementation
'''
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += 'review_data=' + repr(review_data(context(supplied))) + '\nscope=' + repr(SCOPE) + '\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
context=TaskDoneContext(owned,'SR-TASK-'+'0'*26,scope_descriptor=ScopeDescriptor(scope))
review=HumanTaskDoneReview(review_data)
verifier=ReviewVerifier('synthetic-host-review-service','1',lambda c,r:
 ReviewVerification(c.input_sha256,r.sha256,True,True))
print(json.dumps(prepare_task_implementation(context,review=review,verifier=verifier).data))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
