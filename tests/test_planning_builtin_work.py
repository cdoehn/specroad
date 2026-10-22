"""Saved semantic selections, genuine native gates and durable input resumption.

Human reviews and host services below are explicit synthetic test inputs.
No rendered text, Markdown, documentation or external approvals are test oracles.
"""
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from specroad.changes import TargetModel
from specroad.documents import (prepare_builtin_view_work_input,
    resume_builtin_view_work_input, resolve_builtin_view, BuiltinViewWorkInput)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.planning import assess_release_readiness, resume_release_readiness_context
from specroad.validation import ModelDocument
from specroad.verification import VerificationReadBindingConflict, assess_verification_coverage
from support.read_only import no_write_attempts, inventory
from support.targets import model
from test_release_readiness import release_case, context, services, native_bindings
from test_release_readiness_right import refresh_reviews
from test_roadmap_projection import roadmap_values
from test_verification_coverage import coverage_case, prepare, page
from test_verification_coverage_right import release_case as coverage_release_case, release_input
from test_verification_evaluation import INPUTS


def restore(supplied, value, **extra):
    options = dict(expected_sha256=value.sha256, inputs=dict(INPUTS),
                   input_roles={p: 'input' for p in INPUTS})
    options.update(extra)
    return resume_builtin_view_work_input(supplied, value.work_input, **options)


@pytest.mark.parametrize('name', ['verification', 'traceability'])
@pytest.mark.parametrize('selection', ['explicit', 'absent', 'release', 'configured'])
def test_view_resume_retains_direct_coverage_query_and_selection_values(name, selection):
    if selection in ('release', 'configured'):
        _, supplied, evaluation, cfg, scope = coverage_release_case(configured=selection == 'configured')
        verification = release_input(supplied, None, cfg, scope)
        from test_verification_required_checks_right import bindings_for
        options = {'scope_bindings': bindings_for(supplied)}
    else:
        values, evaluation = coverage_case()
        supplied, verification = prepare(values, None if selection == 'absent' else evaluation)
        options = {}
    before = supplied.source_files
    value = prepare_builtin_view_work_input(supplied, name, verification=verification)
    with no_write_attempts():
        resumed = restore(supplied, value, **options)
        result = resumed.resolve()
    direct = resolve_builtin_view(supplied, name, verification=verification)
    assert result.data == direct.data and result.sha256 == direct.sha256
    assert resumed.work_input == value.work_input and supplied.source_files == before
    coverage = assess_verification_coverage(supplied, verification).data
    assert result.data['computed_reports']['verification']['result'] == coverage
    assert result.data['summary'] == verification.summary
    if selection in ('explicit', 'absent'):
        query = page(supplied, verification, filters={'type': ['requirement']},
                     select=['/id', '/verification_result'], sort=['id:asc'])
        expected = {r['requirement_id']: r['verification_result'] for r in coverage['requirements']}
        assert {r['id']: r['values']['/verification_result'] for r in query.data['items']} == expected
    assert not result.data['approval_granted'] and not result.data['release_readiness_evaluated']


@pytest.mark.parametrize('case', ['ready', 'missing-service', 'blocked', 'provisional'])
def test_readiness_resumption_preserves_eight_native_gates_and_never_saves_a_pass(case):
    values, evaluation = release_case()
    if case == 'blocked': values[1]['implementation_status'] = 'blocked'
    if case == 'provisional':
        del values[0]['readiness_policy']['verification_evaluation']
        values = refresh_reviews(values)
    ctx = context(values, evaluation=evaluation if case == 'provisional' else None)
    supplied = ctx._model
    value = prepare_builtin_view_work_input(supplied, 'roadmap', readiness=ctx)
    raw = ctx.work_input
    assert json.loads(raw)['evaluation'] == evaluation.data
    assert set(json.loads(raw)) == {'format_version', 'release_id', 'configuration_id',
        'evaluation', 'evaluation_sha256', 'evaluated_at', 'input_sha256'}
    with no_write_attempts():
        rebound = resume_release_readiness_context(supplied, raw,
            expected_sha256=sha256(raw).hexdigest(), scope_bindings=native_bindings(supplied),
            inputs=dict(INPUTS), input_roles={p: 'input' for p in INPUTS})
        resumed = restore(supplied, value, scope_bindings=native_bindings(supplied))
    gates = services(rebound)
    if case == 'missing-service': gates = [g for g in gates if g.gate_id != 'lifecycle']
    direct = assess_release_readiness(ctx, gates=gates)
    with no_write_attempts(): report = resumed.resolve(readiness_gates=gates)
    assert rebound.data == ctx.data and rebound.input_sha256 == ctx.input_sha256
    assert resumed.work_input == value.work_input
    assert report.data == resolve_builtin_view(supplied, 'roadmap', readiness=ctx, readiness_gates=gates).data
    assert report.data['readiness'] == direct.data
    assert len(report.data['readiness']['gates']) == 8
    assert direct.data['ready'] is (case in ('ready', 'provisional'))
    assert direct.data['provisional'] is (case == 'provisional')
    assert not report.data['write_authorized'] and not report.data['approval_granted']
    assert not report.data['readiness']['release_baseline_authorized']
    with pytest.raises(TypeError): bool(resumed)
    with pytest.raises(TypeError): bool(rebound)


def test_missing_fresh_host_services_cannot_reuse_a_previously_ready_result():
    values, _ = release_case(); ctx = context(values)
    value = prepare_builtin_view_work_input(ctx._model, 'roadmap', readiness=ctx)
    assert value.resolve(readiness_gates=services(ctx)).data['readiness']['ready']
    resumed = restore(ctx._model, value, scope_bindings=native_bindings(ctx._model))
    with no_write_attempts(): data = resumed.resolve().data
    assert not data['readiness']['ready'] and len(data['readiness']['gates']) == 8
    assert any(g['status'] == 'incomplete' for g in data['readiness']['gates'])
    assert 'ready' not in value.data and 'gates' not in value.data['readiness']
    assert not data['full_validation_passed'] and not data['approval_granted']


@pytest.mark.parametrize('view', ['roadmap', 'traceability', 'specification'])
def test_plain_view_roundtrip_is_snapshot_bound_and_has_no_implicit_evaluation(view):
    if view == 'specification':
        from test_document_includes import include_project
        values = include_project()
    else: values = roadmap_values()
    supplied = model(values); value = prepare_builtin_view_work_input(supplied, view)
    with no_write_attempts(): resumed = restore(supplied, value)
    assert resumed.resolve().data == resolve_builtin_view(supplied, view).data
    assert all(value.data[k] is None for k in ('verification', 'currentness', 'readiness'))
    assert not resumed.resolve().data['release_readiness_evaluated']


@pytest.mark.parametrize('view', ['verification', 'traceability'])
@pytest.mark.parametrize('code', ['current', 'missing'])
@pytest.mark.parametrize('explicit_verification', [False, True])
def test_currentness_resumes_with_original_observations_and_selection(tmp_path, view, code, explicit_verification):
    from test_currentness_read_integration import case
    supplied, verification, currentness, state = case(tmp_path / 'project', code=code, evidence='failed')
    options = {'currentness': currentness}
    if explicit_verification: options['verification'] = verification
    value = prepare_builtin_view_work_input(supplied, view, **options)
    before = inventory(tmp_path)
    with no_write_attempts():
        resumed = restore(supplied, value, code_states=[state])
        result = resumed.resolve()
    assert result.data == resolve_builtin_view(supplied, view, **options).data
    assert result.data['currentness'] == currentness.observation
    assert inventory(tmp_path) == before
    with no_write_attempts(), pytest.raises(ModelError): restore(supplied, value)


@pytest.mark.parametrize('change', ['record', 'bytes', 'resource', 'project'])
def test_saved_view_rejects_other_model_bytes_before_recomputation(change):
    supplied = model(roadmap_values()); value = prepare_builtin_view_work_input(supplied, 'roadmap')
    documents = list(supplied.documents); resources = list(supplied.resource_files)
    binding = supplied.binding
    if change == 'record':
        data = json.loads(documents[0].content); data['title'] += ' changed'
        documents[0] = ModelDocument(documents[0].path, canonical_json_bytes(data))
    elif change == 'bytes': documents[0] = ModelDocument(documents[0].path, documents[0].content + b'\n')
    elif change == 'resource': resources[0] = ModelDocument(resources[0].path, resources[0].content + b'\n')
    else:
        data = value.data; data['project_id'] = 'other'; raw = canonical_json_bytes(data)
        with pytest.raises(VerificationReadBindingConflict):
            resume_builtin_view_work_input(supplied, raw, expected_sha256=sha256(raw).hexdigest())
        return
    other = TargetModel(supplied.configuration_bytes, binding, documents,
        profile=supplied.profile, resource_files=resources)
    with no_write_attempts(), pytest.raises(VerificationReadBindingConflict) as caught: restore(other, value)
    assert caught.value.exit_code == 6


@pytest.mark.parametrize('change', ['hash', 'unknown', 'version', 'model_hash', 'verification', 'view'])
def test_invalid_work_input_does_not_reinterpret_a_result_as_a_provider(change):
    values, evaluation = coverage_case(); supplied, verification = prepare(values, evaluation)
    value = prepare_builtin_view_work_input(supplied, 'verification', verification=verification)
    data = value.data
    if change == 'hash': raw = value.work_input + b' '; expected = value.sha256
    else:
        if change == 'unknown': data['ready'] = True
        elif change == 'version': data['format_version'] = 'builtin-view-work-input-v999'
        elif change == 'model_hash': data['model_root_sha256'] = 'f' * 64
        elif change == 'verification': data['verification'] = {'verification_result': 'passed'}
        else: data['view_name'] = 'roadmap'
        raw = canonical_json_bytes(data); expected = sha256(raw).hexdigest()
    with no_write_attempts(), pytest.raises(ModelError):
        resume_builtin_view_work_input(supplied, raw, expected_sha256=expected,
            inputs=INPUTS, input_roles={p: 'input' for p in INPUTS})


@pytest.mark.parametrize('change', ['descriptor', 'descriptor_hash', 'time', 'context_hash', 'unknown'])
def test_readiness_work_input_cannot_change_selection_time_or_bound_context(change):
    values, _ = release_case(); ctx = context(values); data = json.loads(ctx.work_input)
    if change == 'descriptor': data['evaluation']['evaluation_id'] = 'EVAL-' + '1' * 26
    elif change == 'descriptor_hash': data['evaluation_sha256'] = 'f' * 64
    elif change == 'time': data['evaluated_at'] = '2026-10-23T00:00:00Z'
    elif change == 'context_hash': data['input_sha256'] = 'f' * 64
    else: data['gates'] = []
    raw = canonical_json_bytes(data)
    with no_write_attempts(), pytest.raises(ModelError):
        resume_release_readiness_context(ctx._model, raw, expected_sha256=sha256(raw).hexdigest(),
            scope_bindings=native_bindings(ctx._model), inputs=INPUTS,
            input_roles={p: 'input' for p in INPUTS})


@pytest.mark.parametrize('change', ['missing', 'bytes', 'roles'])
def test_view_resume_requires_original_product_inputs(change):
    values, _ = release_case(); ctx = context(values)
    value = prepare_builtin_view_work_input(ctx._model, 'roadmap', readiness=ctx)
    options = {'scope_bindings': native_bindings(ctx._model)}
    if change == 'missing': options['inputs'] = None
    elif change == 'bytes': options['inputs'] = {p: b'changed' for p in INPUTS}
    else: options['input_roles'] = {p: 'output' for p in INPUTS}
    with no_write_attempts(), pytest.raises(ModelError): restore(ctx._model, value, **options)


def test_capture_does_not_run_a_projection_or_create_readiness_and_owns_its_input(monkeypatch):
    values, _ = release_case(); ctx = context(values); before = ctx._model.source_files
    def forbidden(*args, **kwargs): raise AssertionError('Input capture ran a projection')
    monkeypatch.setattr('specroad.documents.builtin_work.resolve_builtin_view', forbidden)
    with no_write_attempts(): value = prepare_builtin_view_work_input(ctx._model, 'roadmap', readiness=ctx)
    raw = value.work_input; data = value.data; data['readiness'].clear(); data['view_name'] = 'other'
    assert value.work_input == raw and ctx._model.source_files == before
    assert not any(k in value.data for k in ('ready', 'completed', 'outcome', 'approval_granted'))
    with pytest.raises(TypeError): bool(value)
    with pytest.raises(TypeError): BuiltinViewWorkInput({'ready': True})


def test_relocated_snapshot_uses_explicit_new_root_without_changing_semantic_hashes():
    values, _ = release_case(); ctx = context(values); supplied = ctx._model
    value = prepare_builtin_view_work_input(supplied, 'roadmap', readiness=ctx)
    relocated = TargetModel(supplied.configuration_bytes,
        replace(supplied.binding, source_root='/explicit/restored/snapshot', root_identity=(9, 11)),
        supplied.documents, profile=supplied.profile, resource_files=supplied.resource_files)
    resumed = restore(relocated, value, scope_bindings=native_bindings(relocated))
    assert resumed.work_input == value.work_input
    assert resumed.resolve().data == value.resolve().data
    with pytest.raises(ModelError): prepare_builtin_view_work_input(relocated, 'roadmap', readiness=ctx)


@pytest.mark.parametrize('name', ['verification', 'traceability'])
def test_resume_rechecks_required_waiver_authentication_instead_of_saving_an_exception(name):
    from test_verification_aggregation import waiver_case
    from test_verification_run_selection import observation
    records, evaluation, cfg, key, review, verifier = waiver_case()
    records.append(observation(records, evaluation, key, run='ci:expected'))
    options = dict(waiver_reviews={key['subject_artifact_id']: review}, waiver_verifier=verifier)
    supplied, verification = prepare(records, evaluation, cfg, **options)
    value = prepare_builtin_view_work_input(supplied, name, verification=verification)
    with no_write_attempts(), pytest.raises(VerificationReadBindingConflict): restore(supplied, value)
    with no_write_attempts(): resumed = restore(supplied, value, **options)
    assert resumed.resolve().data == value.resolve().data


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('view', ['roadmap', 'verification', 'traceability'])
def test_durable_work_input_and_fresh_process_keep_full_snapshot_parity(mode, view, tmp_path):
    """Native Work stores all bytes; the trusted host rebuilds native services.

    No current project is read and no saved observation becomes a provider.
    Pending global Work is not completed merely by restoring a View input.
    """
    import base64
    from specroad.cli.requests import CommandRequest
    from test_work_manifest import create
    from test_work_checkpoints import setup
    from support.portable import build_distribution
    from support.processes import run_core, run_python
    if view == 'roadmap':
        values, _ = release_case(); ctx = context(values); supplied = ctx._model
        value = prepare_builtin_view_work_input(supplied, view, readiness=ctx)
    else:
        values, evaluation = coverage_case(); supplied, verification = prepare(values, evaluation)
        value = prepare_builtin_view_work_input(supplied, view, verification=verification)
    expected = value.resolve().data
    metadata = {'documents': [d.path for d in supplied.documents],
        'resources': [d.path for d in supplied.resource_files],
        'profile_chain': list(supplied.profile.profile_chain),
        'project_id': supplied.binding.project_id}
    initial = create(request=CommandRequest('query'), data=[
        *[{'root_id': 'project', 'path': p, 'raw': b} for p, b in supplied.source_files.items()],
        *[{'root_id': 'product', 'path': p, 'raw': b} for p, b in INPUTS.items()],
        {'root_id': 'context', 'path': 'model.json', 'raw': canonical_json_bytes(metadata)},
        {'root_id': 'view', 'path': 'input.json', 'raw': value.work_input}],
        plan=[{'key': 'view', 'phase': 'projection', 'range': {'view_name': view}},
              {'key': 'delivery', 'phase': 'result_delivery', 'range': {'complete': True}}])
    initial, roots, location, store = setup(tmp_path, initial=initial); store.publish(initial)
    # Independently supplied initial binding, not a hash obtained from work.json.
    trusted = {'raw': base64.b64encode(initial.raw).decode(),
        'objects': {h: base64.b64encode(b).decode() for h, b in initial.objects.items()},
        'build': initial.as_dict()['tool_build']}
    # Keep the independently trusted snapshot out of OS command-line limits.
    trusted_path = tmp_path / 'trusted-initial.json'
    trusted_path.write_bytes(canonical_json_bytes(trusted))
    body = 'import json\nfrom pathlib import Path\n'
    body += 'trusted=json.loads(Path(' + repr(str(trusted_path)) + ').read_bytes())\n'
    body += 'work_path=' + repr(str(location.path)) + '\nprotected=' + repr(str(roots[0].root)) + '\n'
    body += '''
import base64,json
from pathlib import Path
from specroad.cli.commands import builtin_registry
from specroad.work.manifest import read_work_manifest
from specroad.work.checkpoints import CheckpointStore
from specroad.work.root import WorkDirectory
from specroad.security import ProjectBoundary
from specroad.changes import TargetModel
from specroad.documents import resume_builtin_view_work_input
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.configuration import ProjectConfiguration
from specroad.model.language_registry import LanguageRegistry
from specroad.model.paths import classify_path,PathClass
from specroad.profiles import ProfileResource,compose_profiles
from specroad.validation import ModelDocument
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_inputs import ScopeSeedInputs,ScopeResource
from specroad.graph.closure_inputs import ClosureBindings,artifact_node,resource_node
from specroad.graph.review_status import RelationReviewStatuses
initial=read_work_manifest(base64.b64decode(trusted['raw']),
 {h:base64.b64decode(b) for h,b in trusted['objects'].items()},registry=builtin_registry(),expected_tool_build=trusted['build'])
store=CheckpointStore(WorkDirectory(initial,protected_roots=(ProjectBoundary(protected),),directory=Path(work_path)),initial)
saved=store.read()
rows={(r['root_id'],r['path']):r for r in saved.entries('inputs')}
read=lambda key:saved.objects[rows[key]['sha256']]
metadata=json.loads(read(('context','model.json')))
config=ProjectConfiguration(json.loads(read(('project','specroad.json'))))
declared=config.data.get('language_registry');language=None
if declared is not None:
 language=LanguageRegistry(read(('project',declared['path'])),expected_sha256=declared['sha256'],expected_version=declared['registry_version'])
resources=[ModelDocument(p,read(('project',p))) for p in metadata['resources']]
profiles=[ProfileResource(d.content) for d in resources
 if (declared is None or d.path != declared['path']) and classify_path(d.path,config) is PathClass.PROFILE]
chain=metadata['profile_chain']
profile=compose_profiles(profiles,core_key=chain[0],cli_profiles=chain[1:],language_registry=language)
observed=Path(work_path).stat()
owned=TargetModel(read(('project','specroad.json')),ProjectReadBinding(metadata['project_id'],work_path,(observed.st_dev,observed.st_ino)),
 [ModelDocument(p,read(('project',p))) for p in metadata['documents']],profile=profile,resource_files=resources)
inputs={path:read((root,path)) for root,path in rows if root=='product'}
options={}
request=json.loads(read(('view','input.json')))
if request['readiness'] is not None:
 resources=[ScopeResource('fixture-resource:'+str(i),r.data['kind'],r.data['sha256'],
  r.data.get('version') if r.data['kind'] in ('profile','rule','mapping') else None,
  active=r.data['kind']=='profile') for i,r in enumerate(owned.resources)]
 records=[SourceRelations(d.content,path=d.path) for d in owned.documents]
 scope=ScopeSeedInputs(owned.configuration,records,resources)
 # Explicit empty resource-use observations belong only to this owned fixture.
 uses={artifact_node(r.identity.id):() for r in scope.records}
 uses.update({resource_node(r.resource_id):() for r in scope.resources})
 reviews={r['relation_id']:(() if r['selected_review_id'] is None else (r['selected_review_id'],))
  for r in RelationReviewStatuses(records).data['relations']}
 options['scope_bindings']=ClosureBindings(scope,uses=uses,current_reviews=reviews)
value=resume_builtin_view_work_input(owned,read(('view','input.json')),
 expected_sha256=rows['view','input.json']['sha256'],inputs=inputs,input_roles={p:'input' for p in inputs},**options)
print(json.dumps({'input_sha256':value.sha256,'projection':value.resolve().data,
 'work_state':store.read().as_dict()['state'],'remaining':len(store.read().entries('remaining'))}))
'''
    before = inventory(location.path); before_project = inventory(roots[0].root)
    if mode == 'core': completed = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        completed = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {'input_sha256': value.sha256, 'projection': expected,
        'work_state': 'running', 'remaining': 2}
    assert store.read().raw == initial.raw and not store.read().entries('completed')
    assert inventory(location.path) == before and inventory(roots[0].root) == before_project
    if view == 'roadmap': assert expected['readiness']['ready'] is False
