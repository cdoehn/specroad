"""Task Done proof is mandatory across model, direct and saved-plan boundaries."""
import json

import pytest

from specroad.authoring.creation import create_artifact
from specroad.authoring.execution import apply_authoring_plan
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.authoring.plans import preview_authoring_request
from specroad.authoring.update import update_artifact, normalize_artifact_update_input
from specroad.changes import ChangePlan, TargetError, TargetModel, assess_change_target
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.validation import GateResult, ModelDocument, validate_model
from support.domain import domain_value
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref
from support.targets import model, gate, POLICY
from test_artifact_creation import project, arguments
from test_authoring_inputs import fields
from test_task_implementation import task, prepare, live, options, implement_task


def task_stage(report):
    return next(s for s in report.data['stages'] if s['stage'] == 'task_done')


def changed_model(supplied, values=None, configuration=None):
    return TargetModel(configuration or supplied.configuration_bytes, supplied.binding,
        [ModelDocument(artifact_path(v['artifact_type'], v['id'], 'SR'), canonical_json_bytes(v))
         for v in (supplied.artifacts if values is None else values)],
        profile=supplied.profile, resource_files=supplied.resource_files)


def operation(supplied, *, target=None, patch=None):
    value = next(v for v in supplied.artifacts if v['id'] == (target or ref('TASK')))
    if patch is None:
        patch = [{'op': 'replace', 'path': '/implementation_status', 'value': 'implemented'}]
    return normalize_artifact_update_input(value, patch=patch, expected_revision=value['revision'])


def preview(supplied, op):
    args = {k: v for k, v in options().items() if k not in ('transaction_id', 'authority')}
    return preview_authoring_request(supplied, 'artifact.update', [op.data], **args)


@pytest.mark.parametrize('maturity', ['draft', 'proposed', 'in_review'])
def test_stored_implemented_label_is_not_a_done_proof_at_any_review_stage(maturity):
    supplied = model([task(maturity=maturity, implementation_status='implemented')])
    with no_write_attempts():
        report = validate_model(supplied.documents, profile=supplied.profile, gates=(gate('lifecycle'),))
    assert not report.passed and not report.complete
    stage = task_stage(report)
    assert stage['status'] == 'unavailable' and stage['checked_ids'] == [ref('TASK')]
    assert stage['diagnostics'] == [{'reason': 'validation_required_gate_unavailable',
        'severity': 'error', 'gate_id': 'task_done'}]


@pytest.mark.parametrize('status', ['not_started', 'in_progress', 'blocked', 'not_applicable'])
def test_unfinished_task_does_not_require_a_done_proof(status):
    supplied = model([task(implementation_status=status)])
    report = validate_model(supplied.documents, profile=supplied.profile)
    assert report.passed and report.complete
    assert task_stage(report)['status'] == 'not_applicable'


def test_other_artifact_implementation_status_is_not_treated_as_task_done():
    supplied = model([domain_value('requirement', implementation_status='implemented')])
    # Requirements have their own language prerequisite, independently of Done.
    report = validate_model(supplied.documents, profile=supplied.profile,
                            gates=(gate('language_policy'),))
    assert report.passed and task_stage(report)['status'] == 'not_applicable'


def test_selected_dependency_scope_cannot_omit_a_connected_implemented_task():
    first = task(); second = task(id=ref('TASK', '1'), implementation_status='implemented')
    first['relations'] = [{'relation_id': 'REL-' + '0'*26, 'id_scheme': 'random128-v1',
        'type': 'depends_on', 'target': second['id'], 'external_identities': [], 'extensions': {}}]
    supplied = model([first, second])
    report = validate_model(supplied.documents, profile=supplied.profile, selected_ids=[first['id']])
    assert not report.passed
    assert task_stage(report)['checked_ids'] == [second['id']]


@pytest.mark.parametrize('mode', ['boolean', 'unbound', 'incomplete', 'exception'])
def test_done_service_cannot_return_unbound_incomplete_or_missing_observations(mode):
    supplied = model([task(implementation_status='implemented')])
    def observe(ctx):
        if mode == 'exception': raise RuntimeError('unavailable')
        if mode == 'boolean': return True
        return GateResult('a'*64 if mode == 'unbound' else ctx.input_sha256,
                          () if mode == 'incomplete' else ctx.subjects)
    report = validate_model(supplied.documents, profile=supplied.profile,
        gates=(gate('task_done', check=observe),))
    assert not report.passed and task_stage(report)['status'] == 'failed'


@pytest.mark.parametrize('route', ['direct', 'saved_plan', 'target_policy'])
def test_plain_status_change_and_saved_plan_cannot_publish_without_done_proof(tmp_path, route):
    root = tmp_path / 'project'; supplied = live(root); op = operation(supplied)
    before = inventory(root)
    with no_write_attempts(): report = preview(supplied, op)
    # The existing diagnostic contract uses 5 for an unavailable semantic service.
    assert not report['target_validated'] and report['exit_code'] == 5
    stages = report['assessment']['validation']['source_report']['stages']
    done = next(s for s in stages if s['stage'] == 'task_done')
    assert done['status'] == 'unavailable' and done['checked_ids'] == [ref('TASK')]
    assert any(d['code'] == 'VALIDATION_UNAVAILABLE' for d in report['diagnostics'])
    saved = ChangePlan(canonical_json_bytes(report['plan']))
    if route == 'target_policy':
        # Even an explicitly empty command policy cannot disable the Core hook.
        with no_write_attempts(): checked = assess_change_target(saved, supplied, policy=POLICY)
        assert not checked.target_validated
        with pytest.raises(TargetError): checked.require_valid()
    else:
        with pytest.raises(TargetError) as caught:
            if route == 'direct': update_artifact(supplied, op, **options())
            else:
                apply_authoring_plan(saved, supplied, command_id='artifact.update',
                    transaction_id='txn-saved', authority=options()['authority'])
        assert caught.value.reason == 'complete_target_validation_required'
    assert inventory(root) == before


def test_create_cannot_start_with_an_unproven_implemented_status(tmp_path):
    root = tmp_path / 'project'; supplied, identities = project(root)
    value = fields('task'); value['implementation_status'] = 'implemented'
    prepared = normalize_artifact_create_input('task', value); before = inventory(root)
    with pytest.raises(TargetError) as caught:
        create_artifact(supplied, prepared, **arguments(supplied, identities))
    assert caught.value.reason == 'complete_target_validation_required'
    assert inventory(root) == before


@pytest.mark.parametrize('claimed_gate', ['extension:task-done', 'review_currentness', 'lifecycle'])
def test_unrelated_services_and_ai_prose_do_not_supply_task_done_proof(tmp_path, claimed_gate):
    root = tmp_path / 'project'
    supplied = live(root, description='AI claims: every Done criterion is confirmed.')
    before = inventory(root)
    with pytest.raises(TargetError):
        update_artifact(supplied, operation(supplied), gates=(gate(claimed_gate),), **options())
    assert inventory(root) == before


@pytest.mark.parametrize('patch_kind', ['none', 'title', 'criteria', 'other_task'])
def test_an_existing_implemented_task_also_requires_proof_for_whole_target_writes(tmp_path, patch_kind):
    root = tmp_path / 'project'; supplied = live(root, implementation_status='implemented')
    target = None; patch = []
    if patch_kind == 'title': patch = [{'op': 'replace', 'path': '/title', 'value': 'New title'}]
    if patch_kind == 'criteria': patch = [{'op': 'replace', 'path': '/done_criteria', 'value': ['New work']}]
    if patch_kind == 'other_task':
        second = task(id=ref('TASK', '1'))
        supplied = changed_model(supplied, [*supplied.artifacts, second])
        put(root, artifact_path('task', second['id'], 'SR'), canonical_json_bytes(second))
        target = second['id']; patch = [{'op': 'replace', 'path': '/title', 'value': 'Unrelated update'}]
    before = inventory(root)
    with pytest.raises(TargetError):
        update_artifact(supplied, operation(supplied, target=target, patch=patch), **options())
    assert inventory(root) == before


def test_review_for_one_task_never_certifies_another_implemented_task(tmp_path):
    root = tmp_path / 'project'; supplied = live(root)
    second = task(id=ref('TASK', '1'), implementation_status='implemented')
    supplied = changed_model(supplied, [*supplied.artifacts, second])
    put(root, artifact_path('task', second['id'], 'SR'), canonical_json_bytes(second))
    prepared = prepare(supplied); before = inventory(root)
    with pytest.raises(TargetError): implement_task(supplied, prepared, **options())
    assert inventory(root) == before


@pytest.mark.parametrize('field', ['description', 'done_criteria', 'owner', 'revision', 'configuration'])
def test_old_review_cannot_authorize_changed_criteria_content_or_configuration(tmp_path, field):
    root = tmp_path / 'project'; supplied = live(root); prepared = prepare(supplied)
    values = supplied.artifacts; config = supplied.configuration_bytes
    if field == 'configuration':
        value = json.loads(config); value['project_name'] = 'Changed configuration'
        config = canonical_json_bytes(value)
    else:
        value = next(v for v in values if v['id'] == ref('TASK'))
        value[field] = {'description': 'Different work', 'done_criteria': ['New criterion'],
                       'owner': 'different-owner', 'revision': 2}[field]
    altered = changed_model(supplied, values, config); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        implement_task(altered, prepared, **options())
    assert caught.value.reason == 'task_done_review_binding_mismatch'
    assert inventory(root) == before


def test_reserved_done_gate_cannot_be_replaced_on_the_reviewed_path(tmp_path):
    supplied = live(tmp_path / 'project'); prepared = prepare(supplied)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        implement_task(supplied, prepared, gates=(gate('task_done'),), **options())
    assert caught.value.reason == 'task_done_gate_override'


@pytest.mark.parametrize('status', ['not_started', 'in_progress', 'blocked', 'not_applicable'])
def test_unproven_implemented_status_can_be_repaired_without_claiming_done(tmp_path, status):
    root = tmp_path / 'project'; supplied = live(root, implementation_status='implemented')
    op = operation(supplied, patch=[{'op': 'replace', 'path': '/implementation_status', 'value': status}])
    result = update_artifact(supplied, op, **options())
    assert result['write_state'] == 'committed'
    actual = json.loads((root / artifact_path('task', ref('TASK'), 'SR')).read_bytes())
    assert actual['implementation_status'] == status and actual['revision'] == 2


def test_fresh_review_of_already_implemented_task_is_a_checked_noop(tmp_path):
    root = tmp_path / 'project'; supplied = live(root, implementation_status='implemented')
    prepared = prepare(supplied); before = inventory(root)
    result = implement_task(supplied, prepared, **options())
    assert result['no_change'] and result['completion'] is None and not result['replayed']
    assert inventory(root) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_isolated_runtime_refuses_unproven_implemented_task(mode, tmp_path):
    supplied = model([task(implementation_status='implemented')])
    body = '''import json
from specroad.validation import ModelDocument, validate_model
from specroad.profiles import ProfileResource, compose_profiles
'''
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([d.content for d in supplied.resource_files]) + '\n'
    body += 'key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for raw in resources],core_key=key)
report=validate_model([ModelDocument(p,r) for p,r in documents],profile=profile)
stage=next(s for s in report.data['stages'] if s['stage']=='task_done')
print(json.dumps({'passed':report.passed,'status':stage['status'],'ids':stage['checked_ids']}))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'passed': False, 'status': 'unavailable', 'ids': [ref('TASK')]}
