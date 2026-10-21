"""Complete bound Work inputs and recomputed read parity, never saved approval."""
from hashlib import sha256
import json

import pytest

from specroad.cli.requests import CommandRequest
from specroad.documents.builtin_views import resolve_builtin_view
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, QueryWork, query_records
from specroad.security import ProjectBoundary
from specroad.storage.record_artifact import RecordArtifact
from specroad.validation import validate_model, ValidationResources
from specroad.verification import (prepare_currentness_read_input, resume_currentness_read_input,
    assess_code_reference, assess_verification_coverage, VerificationReadBindingConflict)
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref, record_value
from support.targets import model
from test_currentness_read_integration import case, consumed, verification_for
from test_query_paging_right import protected
from test_verification_aggregation import waiver_case
from test_verification_coverage import prepare, records_for
from test_verification_coverage_right import release_case, release_input
from test_verification_evaluation import INPUTS
from test_verification_required_checks_right import bindings_for
from test_verification_run_replacements import retest, selection
from test_verification_run_selection import observation


def resumed(supplied, value, states=(), **kwargs):
    options = dict(expected_sha256=sha256(value.work_input).hexdigest(),
        inputs=INPUTS, input_roles={p: 'input' for p in INPUTS}, code_states=states)
    options.update(kwargs)
    return resume_currentness_read_input(supplied, value.work_input, **options)


@pytest.mark.parametrize('code', ['current', 'stale', 'missing', 'relocated'])
@pytest.mark.parametrize('evidence', ['passed', 'failed', 'stale', 'missing', 'no_evaluation'])
def test_resumed_native_inputs_preserve_all_consumers_and_never_write_subjects(code, evidence, tmp_path):
    root = tmp_path / 'project'
    supplied, verification, value, state = case(root, code=code, evidence=evidence)
    before = inventory(root)
    with no_write_attempts():
        native = RecordArtifact(canonical_json_bytes(state.data['reference']))
        fresh = assess_code_reference(ProjectBoundary(root), native)
        restored = resumed(supplied, value, [fresh])
        assert consumed(supplied, restored, root) == consumed(supplied, value, root)
    assert inventory(root) == before
    assert restored.data == value.data and restored.sha256 == value.sha256
    assert restored.verification.data == verification.data
    assert restored.work_input == value.work_input
    saved = json.loads(value.work_input)
    assert saved['verification_input']['evaluation'] == verification.data['evaluation']
    assert saved['record_bindings'] == [
        {'id': r.identity.id, 'sha256': sha256(r.source_bytes).hexdigest()}
        for r in sorted(records_for(supplied), key=lambda r: r.identity.id)]
    assert saved['code_bindings'] == [{'artifact_id': ref('CODE'),
        'reference_sha256': state.data['reference_sha256'], 'assessment_sha256': fresh.sha256}]
    assert not any(restored.data[k] for k in ('write_authorized', 'approval_granted',
        'release_readiness_evaluated', 'source_code_executed', 'external_run_verified'))


@pytest.mark.parametrize('replaced', [False, True])
def test_resume_retains_superseded_and_concurrent_evidence_not_only_success(replaced):
    records, evaluation, cfg, key, old, new, decision = retest()
    records[0]['verification_plan_status'] = 'planned'
    concurrent = observation(records, evaluation, key, token='3', run='ci:concurrent')
    if replaced: evaluation = selection(evaluation, [decision])
    supplied, verification = prepare(records + [old, new, concurrent], evaluation, cfg)
    value = prepare_currentness_read_input(supplied, verification)
    with no_write_attempts(): restored = resumed(supplied, value)
    data = restored.data['coverage']
    assert data == value.data['coverage']
    assert data['totals']['verification_results'] == {'failed': 1}
    assert {v['evidence_id'] for v in data['evidence_dispositions']} == {old['id'], new['id'], concurrent['id']}
    assert data['requirements'][0]['checks'][0]['superseded_run_ids'] == (['ci:old'] if replaced else [])
    assert len(json.loads(restored.work_input)['record_bindings']) == len(records) + 3
    # Even discarded/superseded history remains bound to its original raw bytes.
    old['title'] = 'Changed historical record'
    with no_write_attempts(), pytest.raises(ModelError):
        resumed(model(records + [old, new, concurrent]), value)


@pytest.mark.parametrize('change', ['raw', 'version', 'unknown', 'noncanonical', 'evaluation',
    'evaluation_hash', 'evaluated_at', 'scope', 'model_hash', 'records', 'codes',
    'code_reference', 'code_assessment', 'currentness_hash', 'verification_hash', 'untyped_verification'])
def test_changed_work_bytes_and_rebound_semantics_cannot_become_saved_success(change, tmp_path):
    supplied, _, value, state = case(tmp_path / 'project')
    data = json.loads(value.work_input)
    if change == 'version': data['format_version'] = 'currentness-read-work-input-v2'
    elif change == 'unknown': data['approval_granted'] = True
    elif change == 'evaluation': data['verification_input']['evaluation']['evaluation_id'] = 'EVAL-' + '1' * 26
    elif change == 'evaluation_hash': data['verification_input']['evaluation_sha256'] = 'f' * 64
    elif change == 'evaluated_at': data['verification_input']['evaluated_at'] = '2026-10-22T00:00:00Z'
    elif change == 'scope': data['verification_input']['configuration_id'] = ref('CFG')
    elif change == 'model_hash': data['input_sha256'] = 'f' * 64
    elif change == 'records': data['record_bindings'].pop()
    elif change == 'codes': data['code_bindings'].clear()
    elif change == 'code_reference': data['code_bindings'][0]['reference_sha256'] = 'f' * 64
    elif change == 'code_assessment': data['code_bindings'][0]['assessment_sha256'] = 'f' * 64
    elif change == 'currentness_hash': data['currentness_input_sha256'] = 'f' * 64
    elif change == 'verification_hash': data['verification_work_input_sha256'] = 'f' * 64
    elif change == 'untyped_verification': data['verification_input'] = []
    if change in ('evaluation', 'evaluation_hash', 'evaluated_at', 'scope'):
        data['verification_work_input_sha256'] = canonical_json_sha256(data['verification_input'])
    raw = canonical_json_bytes(data)
    expected = sha256(raw).hexdigest()
    if change in ('raw', 'noncanonical'):
        raw += b' '
        if change == 'noncanonical': expected = sha256(raw).hexdigest()
    with no_write_attempts(), pytest.raises(ModelError):
        resume_currentness_read_input(supplied, raw, expected_sha256=expected,
            inputs=INPUTS, input_roles={p: 'input' for p in INPUTS}, code_states=[state])


@pytest.mark.parametrize('bad', [None, '', 'F' * 64, 'g' * 64, '0' * 63, 0, True])
def test_work_hash_must_be_an_explicit_native_binding(bad, tmp_path):
    supplied, _, value, state = case(tmp_path / 'project')
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resumed(supplied, value, [state], expected_sha256=bad)
    assert caught.value.reason == 'currentness_work_input_binding_required'


@pytest.mark.parametrize('change', ['code', 'missing_code', 'code_dict', 'product', 'missing_product',
    'roles', 'model', 'configuration'])
def test_resume_rechecks_original_model_product_and_complete_native_code_inputs(change, tmp_path):
    root = tmp_path / 'project'
    supplied, _, value, state = case(root)
    options = {}; states = [state]
    if change == 'code':
        put(root, state.data['path'], b'CHANGED\n')
        states = [assess_code_reference(ProjectBoundary(root),
            RecordArtifact(canonical_json_bytes(state.data['reference'])))]
    elif change == 'missing_code': states = []
    elif change == 'code_dict': states = [state.data]
    elif change == 'product': options['inputs'] = {p: b'CHANGED' for p in INPUTS}
    elif change == 'missing_product': options['inputs'] = None
    elif change == 'roles': options['input_roles'] = {p: 'output' for p in INPUTS}
    else:
        records = [r.data for r in records_for(supplied)]
        config = supplied.configuration.data
        if change == 'model': records[0]['title'] = 'Changed source bytes'
        else: config['extensions'] = {'org.example': {'changed': True}}
        supplied = model(records, config=config)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resumed(supplied, value, states, **options)
    if change == 'code':
        assert caught.value.exit_code == 6
        assert caught.value.reason == 'currentness_work_observation_changed'


def test_resume_rechecks_native_waiver_trust_instead_of_saving_authority():
    records, evaluation, cfg, key, review, verifier = waiver_case()
    records.append(observation(records, evaluation, key, run='ci:expected'))
    options = dict(waiver_reviews={key['subject_artifact_id']: review}, waiver_verifier=verifier)
    supplied, verification = prepare(records, evaluation, cfg, **options)
    value = prepare_currentness_read_input(supplied, verification)
    with no_write_attempts(), pytest.raises(VerificationReadBindingConflict): resumed(supplied, value)
    with no_write_attempts(): restored = resumed(supplied, value, **options)
    assert restored.data == value.data
    assert restored.data['coverage']['totals']['verification_results'] == {'waived': 1}
    assert not restored.data['approval_granted']


@pytest.mark.parametrize('configured', [False, True])
def test_scoped_model_views_keep_complete_inventory_but_no_whole_project_or_release_claim(configured, tmp_path):
    records, _, evaluation, cfg, selected_scope = release_case(configured=configured)
    coderef = record_value('code_ref', path='absent.data')
    records.append(coderef)
    supplied = model(records)
    root = tmp_path / 'source'; root.mkdir()
    state = assess_code_reference(ProjectBoundary(root), RecordArtifact(canonical_json_bytes(coderef)))
    verification = release_input(supplied, evaluation, cfg, selected_scope)
    value = prepare_currentness_read_input(supplied, verification, code_states=[state])
    with no_write_attempts():
        restored = resumed(supplied, value, [state], scope_bindings=bindings_for(supplied))
        assert restored.data == value.data
        for view in ('traceability', 'verification'):
            data = resolve_builtin_view(supplied, view, currentness=restored).data
            assert data['currentness'] == value.observation
        coverage = assess_verification_coverage(supplied, currentness=restored).data
        assert coverage['totals']['requirement_ids'] == [ref()]
        assert not coverage['release_readiness_evaluated']
        assert len(restored.data['record_bindings']) == len(records)
        assert restored.data['code_states'][0]['state'] == 'missing'
        with pytest.raises(ModelError):
            validate_model(supplied.documents, resources=ValidationResources(supplied.configuration_bytes),
                           currentness=restored)
        with pytest.raises(ModelError):
            QueryWork(tmp_path / 'spool', records_for(supplied), NormalizedQuery(evaluation=evaluation.data),
                project=supplied.configuration.data, configuration_id=cfg,
                protected_roots=(ProjectBoundary(root),), currentness=restored)
    assert not (tmp_path / 'spool').exists()
    with no_write_attempts(), pytest.raises(ModelError): resumed(supplied, value, [state])


@pytest.mark.parametrize('units', [1, 10000])
@pytest.mark.parametrize('offset,limit', [(0, 1), (0, 0), (3, 5)])
def test_incremental_query_keeps_unselected_evidence_and_code_beyond_page(units, offset, limit, tmp_path):
    supplied, _, value, state = case(tmp_path / 'source', code='stale', evidence='failed')
    restored = resumed(supplied, value, [state])
    roots = protected(tmp_path); before = inventory(roots[0].root)
    query = NormalizedQuery(evaluation=restored.verification.data['evaluation'],
        filters={'type': ['requirement']}, select=['/verification_result'],
        sort=['verification_result:asc'], offset=offset, limit=limit)
    expected = query_records(records_for(supplied), query,
        project=supplied.configuration.data, verification=value.verification)
    with QueryWork(tmp_path / 'spool', records_for(supplied), query,
            project=supplied.configuration.data, protected_roots=roots,
            currentness=restored, batch_bytes=1) as work:
        while not work.state['complete']:
            previous = work.state['units_completed']
            work.advance(units)
            assert work.state['units_completed'] > previous
            assert work.currentness_input == value.work_input
            assert work.currentness_observation == value.observation
            assert work.evaluation_input == value.verification.work_input
            work.currentness_observation['observation']['code_states'].clear()
            assert work.state['currentness_sha256'] == value.sha256
        assert work.result.data == expected.data
        assert work.result.evaluation_binding == expected.evaluation_binding
        assert work.currentness_observation['observation']['code_states'][0]['state'] == 'stale'
        assert work.currentness_observation['observation']['coverage']['totals']['verification_results'] == {'failed': 1}
        assert not work.state['durable_checkpoint']
    assert inventory(roots[0].root) == before


@pytest.mark.parametrize('bad', ['foreign_records', 'foreign_configuration', 'different_verification', 'dict'])
def test_invalid_query_currentness_is_rejected_before_spool_creation(bad, tmp_path):
    supplied, _, value, _ = case(tmp_path / 'source')
    roots = protected(tmp_path); before = inventory(tmp_path)
    records = records_for(supplied); project = supplied.configuration.data; options = {}
    if bad == 'foreign_records': records = records[:-1]
    elif bad == 'foreign_configuration': project['extensions'] = {'org.example': {'changed': True}}
    elif bad == 'different_verification': options['verification'] = verification_for(supplied, None)
    query = NormalizedQuery(evaluation=value.verification.data['evaluation'])
    with no_write_attempts(), pytest.raises(ModelError):
        QueryWork(tmp_path / 'spool', records, query, project=project, protected_roots=roots,
                  currentness=value.data if bad == 'dict' else value, **options)
    assert inventory(tmp_path) == before


def test_empty_model_roundtrip_does_not_invent_evidence_or_readiness():
    supplied = model([])
    value = prepare_currentness_read_input(supplied, verification_for(supplied, None))
    with no_write_attempts(): restored = resumed(supplied, value)
    assert restored.data == value.data
    assert restored.data['coverage']['totals']['requirements'] == 0
    assert restored.data['code_states'] == restored.data['record_bindings'] == []
    assert not restored.data['release_readiness_evaluated']


@pytest.mark.parametrize('mode', ['core', 'pyz'])
@pytest.mark.parametrize('code', ['current', 'stale', 'missing', 'relocated'])
def test_real_checkpoint_supplies_all_bytes_after_original_source_is_unavailable(mode, code, tmp_path):
    from test_work_manifest import create
    from test_work_checkpoints import setup
    from specroad.work.checkpoints import CheckpointStore
    from specroad.work.root import WorkDirectory
    import base64
    root = tmp_path / 'original'
    supplied, _, value, state = case(root, code=code, evidence='failed')
    # All model/config/profile, Evaluation, product and code bytes enter Work.
    # The separate metadata only names members of this content-addressed store.
    metadata = {'documents': [d.path for d in supplied.documents],
        'resources': [d.path for d in supplied.resource_files],
        'core_key': supplied.profile.profile_chain[0]}
    initial = create(request=CommandRequest('query'), data=[
        {'root_id': 'currentness', 'path': 'input.json', 'raw': value.work_input},
        {'root_id': 'context', 'path': 'model.json', 'raw': canonical_json_bytes(metadata)},
        *[{'root_id': 'model', 'path': p, 'raw': b} for p, b in supplied.source_files.items()],
        *[{'root_id': 'product', 'path': p, 'raw': b} for p, b in INPUTS.items()],
        *([] if code == 'missing' else [{'root_id': 'code', 'path': state.data['path'],
                                        'raw': (root / state.data['path']).read_bytes()}])])
    initial, roots, location, store = setup(tmp_path, initial=initial)
    store.publish(initial)
    trusted = {'raw': base64.b64encode(initial.raw).decode(),
        'objects': {h: base64.b64encode(b).decode() for h, b in initial.objects.items()},
        'build': initial.as_dict()['tool_build']}
    # Rehydrate the trusted snapshot at a new native location. Copying a live
    # Work root/lock binding to another inode would correctly be rejected.
    root.rename(tmp_path / 'old-source')
    moved = tmp_path / 'relocated-work'
    relocated = CheckpointStore(WorkDirectory(initial, protected_roots=roots,
        directory=moved), initial)
    relocated.publish(store.read())
    body = '''import base64,json
from pathlib import Path
from specroad.cli.commands import builtin_registry
from specroad.work.manifest import read_work_manifest
from specroad.work.checkpoints import CheckpointStore
from specroad.work.root import WorkDirectory
from specroad.security import ProjectBoundary
from specroad.changes import TargetModel
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource,compose_profiles
from specroad.storage.record_artifact import RecordArtifact
from specroad.validation import ModelDocument
from specroad.verification import resume_currentness_read_input,assess_code_reference,assess_verification_coverage
'''
    body += 'trusted=' + repr(trusted) + '\n'
    body += 'work_path=' + repr(str(moved)) + '\nprotected=' + repr(str(roots[0].root)) + '\n'
    body += 'code_root=' + repr(str(tmp_path / 'restored-code')) + '\n'
    body += '''initial=read_work_manifest(base64.b64decode(trusted['raw']),
 {h:base64.b64decode(b) for h,b in trusted['objects'].items()},registry=builtin_registry(),expected_tool_build=trusted['build'])
store=CheckpointStore(WorkDirectory(initial,protected_roots=(ProjectBoundary(protected),),directory=Path(work_path)),initial)
saved=store.read()
rows={(r['root_id'],r['path']):r for r in saved.entries('inputs')}
read=lambda key:saved.objects[rows[key]['sha256']]
meta=json.loads(read(('context','model.json')))
resources=[ModelDocument(path,read(('model',path))) for path in meta['resources']]
profile=compose_profiles([ProfileResource(d.content) for d in resources],core_key=meta['core_key'])
owned=TargetModel(read(('model','specroad.json')),ProjectReadBinding('sample','/relocated/provider',(3,4)),
 [ModelDocument(path,read(('model',path))) for path in meta['documents']],profile=profile,resource_files=resources)
Path(code_root).mkdir()
for root,path in rows:
 if root=='code':
  target=Path(code_root)/path
  target.parent.mkdir(parents=True,exist_ok=True)
  target.write_bytes(read((root,path)))
states=[]
for d in owned.documents:
 if json.loads(d.content)['artifact_type']=='code_ref':
  states.append(assess_code_reference(ProjectBoundary(code_root),RecordArtifact(d.content,path=d.path)))
inputs={path:read((root,path)) for root,path in rows if root=='product'}
value=resume_currentness_read_input(owned,read(('currentness','input.json')),
 expected_sha256=rows[('currentness','input.json')]['sha256'],inputs=inputs,input_roles={p:'input' for p in inputs},code_states=states)
print(json.dumps({'input':value.data,'coverage':assess_verification_coverage(owned,currentness=value).data}))
'''
    before_work = inventory(moved)
    before_source = inventory(tmp_path / 'old-source')
    before_project = inventory(roots[0].root)
    if mode == 'core': completed = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        completed = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {'input': value.data,
        'coverage': assess_verification_coverage(supplied, currentness=value).data}
    assert inventory(moved) == before_work and not root.exists()
    assert inventory(tmp_path / 'old-source') == before_source
    assert inventory(roots[0].root) == before_project
