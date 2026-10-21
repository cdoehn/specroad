"""Independent coverage gaps, Release precedence and preserved Work inputs."""
from hashlib import sha256
import json

import pytest

from specroad.cli.requests import CommandRequest
from specroad.documents.builtin_views import resolve_builtin_view
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, QueryWork, query_records
from specroad.verification import (VerificationEvaluation, VerificationEvaluationError,
    VerificationReadBindingConflict, prepare_verification_read_input,
    resume_verification_read_input, assess_verification_coverage)
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref
from support.srx import expression_document, literal
from support.targets import model
from test_query_paging_right import protected
from test_verification_aggregation import scenario, NOW, waiver_case
from test_verification_coverage import coverage_case, prepare, records_for
from test_verification_evaluation import INPUTS
from test_verification_required_checks import edge
from test_verification_required_checks_right import bindings_for, scope
from test_verification_run_replacements import retest, decision, selection
from test_verification_run_selection import observation


def coverage(records, evaluation, cfg=None, **kwargs):
    supplied, value = prepare(records, evaluation, cfg, **kwargs)
    return assess_verification_coverage(supplied, value).data


@pytest.mark.parametrize('with_test', [False, True])
@pytest.mark.parametrize('observed', ['missing', 'passed', 'failed', 'stale', 'not_measured'])
def test_contract_test_evidence_and_freshness_gaps_are_independent(with_test, observed):
    records, evaluation, cfg, key = scenario(with_test=with_test)
    if observed != 'missing':
        item = observation(records, evaluation, key, run='ci:expected',
                           result='passed' if observed == 'stale' else observed)
        if observed == 'stale': item['subjects'][0]['verification_context_sha256'] = 'f' * 64
        records.append(item)
    data = coverage(records, evaluation, cfg); gaps = data['gaps']
    assert data['selection_status'] == 'selected' and data['input_binding_status'] == 'ready'
    assert gaps['requirements_without_contract'] == []
    assert gaps['requirements_without_test_reference'] == ([] if with_test else [ref()])
    assert gaps['requirements_without_evidence'] == ([ref()] if observed == 'missing' else [])
    assert gaps['requirements_with_missing_runs'] == ([ref()] if observed == 'missing' else [])
    assert gaps['requirements_with_stale_evidence'] == ([ref()] if observed == 'stale' else [])
    assert gaps['missing_runs'] == ([{**key, 'run_id': 'ci:expected'}] if observed == 'missing' else [])
    assert gaps['counts']['stale_evidence'] == (1 if observed == 'stale' else 0)
    assert gaps['counts']['incomplete_evidence'] == (1 if observed == 'not_measured' else 0)
    assert gaps['unselected_checks'] == []
    assert gaps['counts'] == {k: len(v) for k, v in gaps.items() if k != 'counts'}


@pytest.mark.parametrize('absent', [True, False])
def test_absent_or_partial_selection_never_fabricates_missing_runs(absent):
    records, evaluation = coverage_case()
    if absent: evaluation = None
    else:
        data = evaluation.data; data['required_runs'].pop()
        evaluation = VerificationEvaluation(artifact_bytes(data))
    data = coverage(records, evaluation); gaps = data['gaps']
    assert data['selection_status'] == ('missing' if absent else 'incomplete')
    assert gaps['requirements_with_unselected_checks'] == [ref(), ref('REQ', '1')]
    assert gaps['counts']['unselected_checks'] == 9
    assert gaps['missing_runs'] == gaps['stale_evidence'] == gaps['requirements_without_evidence'] == []
    assert data['totals']['active_runs'] == 0
    assert data['totals']['required_checks'] == 9
    assert len(data['evidence_dispositions']) == 9
    assert {v['disposition'] for v in data['evidence_dispositions']} == {'not_evaluated'}


def test_requirement_without_contract_has_two_distinct_structural_gaps_and_no_fake_run():
    data = coverage([domain_value('requirement', verification_plan_status='planned')], None)
    assert data['gaps']['requirements_without_contract'] == [ref()]
    assert data['gaps']['requirements_without_test_reference'] == [ref()]
    assert data['gaps']['requirements_without_evidence'] == []
    assert data['gaps']['missing_runs'] == data['gaps']['unselected_checks'] == []
    assert data['totals']['verification_results'] == {'incomplete': 1}


def test_partially_present_evidence_keeps_missing_and_stale_sets_beside_success():
    records, evaluation, cfg, key = scenario(with_test=True, expected=('ci:missing', 'ci:stale', 'ci:good'))
    stale = observation(records, evaluation, key, run='ci:stale', result='passed')
    stale['subjects'][0]['verification_context_sha256'] = 'f' * 64
    good = observation(records, evaluation, key, token='2', run='ci:good', result='passed')
    data = coverage(records + [good, stale], evaluation, cfg); gaps = data['gaps']
    assert gaps['requirements_without_evidence'] == []
    assert gaps['requirements_with_missing_runs'] == gaps['requirements_with_stale_evidence'] == [ref()]
    assert gaps['missing_runs'] == [{**key, 'run_id': 'ci:missing'}]
    assert gaps['stale_evidence'] == [{**key, 'run_id': 'ci:stale', 'evidence_id': stale['id']}]
    assert data['totals']['active_runs'] == 3
    assert data['totals']['evidence_freshness'] == {'current': 1, 'stale': 1}
    assert data['totals']['verification_results'] == {'incomplete': 1}


def test_superseded_stale_observation_remains_in_history_but_not_active_gap_counts():
    records, evaluation, cfg, key, old, new, _ = retest()
    records[0]['verification_plan_status'] = 'planned'
    old['subjects'][0]['verification_context_sha256'] = 'f' * 64
    evaluation = selection(evaluation, [decision(key, 'ci:old', [old])])
    data = coverage(records + [old, new], evaluation, cfg)
    assert data['gaps']['missing_runs'] == data['gaps']['stale_evidence'] == []
    assert data['totals']['active_runs'] == data['totals']['evidence_observations'] == 1
    assert data['totals']['verification_results'] == {'passed': 1}
    assert data['requirements'][0]['checks'][0]['superseded_run_ids'] == ['ci:old']
    assert {v['evidence_id'] for v in data['evidence_dispositions']} == {old['id'], new['id']}


@pytest.mark.parametrize('kind', ['unbound', 'historical'])
def test_unbound_or_other_product_evidence_does_not_count_as_stale_or_present(kind):
    records, evaluation, cfg, key = scenario()
    item = observation(records, evaluation, key, run='ci:old')
    if kind == 'unbound': item.update(run_context=None, unbound_reason='Declared unknown origin')
    else: item['run_context']['subject_state_sha256'] = 'f' * 64
    data = coverage(records + [item], evaluation, cfg)
    assert data['gaps']['requirements_without_evidence'] == [ref()]
    assert data['gaps']['requirements_with_stale_evidence'] == []
    assert data['evidence_dispositions'][0]['disposition'] == ('unbound' if kind == 'unbound' else 'historical_other_state')


def test_excluded_requirements_stay_in_totals_without_false_structural_gaps():
    records, _, cfg, _ = scenario()
    records[0]['applicability'] = expression_document(literal(False))
    data = coverage(records, None, cfg)
    assert data['totals']['requirements'] == 1
    assert data['totals']['verification_results'] == {'not_applicable': 1}
    assert all(count == 0 for count in data['gaps']['counts'].values())


def test_invalid_dangling_test_reference_keeps_native_rejection_instead_of_partial_success():
    records, evaluation, cfg, _ = scenario(with_test=True)
    records = [r for r in records if r['artifact_type'] != 'test']
    with no_write_attempts(), pytest.raises(ModelError): coverage(records, evaluation, cfg)


def test_failed_input_binding_cannot_be_hidden_by_complete_evidence_axes():
    records, evaluation, cfg, key = scenario(with_test=True)
    records.append(observation(records, evaluation, key, run='ci:expected', result='passed'))
    data = coverage(records, evaluation, cfg, inputs=None, input_roles=None)
    assert data['input_binding_status'] == 'incomplete'
    assert data['totals']['verification_results'] == {'incomplete': 1}
    assert data['totals']['check_results'] == {'passed': 1}
    assert all(count == 0 for count in data['gaps']['counts'].values())


def release_case(*, stored=True, configured=False):
    records, evaluation, cfg, key = scenario(with_test=True, configured=configured)
    if not configured: records[1]['configuration_policy'] = 'independent'
    records[0]['relations'].append(dict(edge(ref('REL'), 4), type='scheduled_for'))
    records.append(domain_value('release', readiness_policy={
        'verification_evaluation': evaluation.data} if stored else {}))
    records.append(domain_value('requirement', id=ref('REQ', '2'), verification_plan_status='planned'))
    supplied = model(records)
    selected_scope = scope(kind='release', selector={'release_id': ref('REL')}, configuration_id=cfg)
    return records, supplied, evaluation, cfg, selected_scope


def release_input(supplied, evaluation, cfg, selected_scope, **kwargs):
    return prepare_verification_read_input(supplied, evaluation, configuration_id=cfg,
        inputs=INPUTS, input_roles={p: 'input' for p in INPUTS}, evaluated_at=NOW,
        scope_descriptor=selected_scope, scope_bindings=bindings_for(supplied), **kwargs)


@pytest.mark.parametrize('configured', [False, True])
@pytest.mark.parametrize('explicit', [False, True])
def test_release_coverage_uses_native_scope_and_stored_selection(configured, explicit):
    records, supplied, evaluation, cfg, selected_scope = release_case(configured=configured)
    before = supplied.source_files
    with no_write_attempts():
        value = release_input(supplied, evaluation if explicit else None, cfg, selected_scope)
        data = assess_verification_coverage(supplied, value).data
    assert data['totals']['requirement_ids'] == [ref()]
    assert ref('REQ', '2') not in data['gaps']['requirements_without_contract']
    release = data['by_release'][0]
    assert release['release_id'] == ref('REL') and release['selection_origin'] == 'stored'
    assert not release['provisional'] and not release['release_authorized']
    assert release['totals'] == data['totals'] and release['gaps'] == data['gaps']
    assert value.data['evaluation'] == evaluation.data
    assert value.data['scope_descriptor'] == selected_scope.data
    assert supplied.source_files == before
    view = resolve_builtin_view(supplied, 'verification', verification=value).data
    assert view['coverage'] == data and view['validation_scope'] == 'supplied_scope_requirement_coverage'
    assert not view['release_readiness_evaluated']


@pytest.mark.parametrize('explicit', [False, True])
def test_unstored_release_selection_is_explicitly_provisional_or_missing(explicit):
    _, supplied, evaluation, cfg, selected_scope = release_case(stored=False)
    value = release_input(supplied, evaluation if explicit else None, cfg, selected_scope)
    data = assess_verification_coverage(supplied, value).data
    assert data['by_release'][0]['selection_origin'] == ('explicit_provisional' if explicit else 'missing')
    assert data['by_release'][0]['provisional'] and not data['by_release'][0]['release_authorized']
    assert data['selection_status'] == ('selected' if explicit else 'missing')
    assert data['totals']['verification_results'] == {'incomplete': 1}


@pytest.mark.parametrize('change', ['evaluation_id', 'created_at', 'runs'])
def test_stored_release_selection_cannot_be_overridden(change):
    _, supplied, evaluation, cfg, selected_scope = release_case()
    data = evaluation.data
    if change == 'evaluation_id': data['evaluation_id'] = 'EVAL-' + '1' * 26
    elif change == 'created_at': data['created_at'] = '2026-10-22T00:00:00Z'
    else: data['required_runs'][0]['run_ids'] = ['ci:other']
    with no_write_attempts(), pytest.raises(VerificationReadBindingConflict) as caught:
        release_input(supplied, VerificationEvaluation(artifact_bytes(data)), cfg, selected_scope)
    assert caught.value.exit_code == 6 and caught.value.reason == 'verification_release_evaluation_conflict'


def test_invalid_stored_release_descriptor_does_not_fall_back_to_explicit_selection():
    records, _, evaluation, cfg, selected_scope = release_case()
    next(r for r in records if r['artifact_type'] == 'release')['readiness_policy']['verification_evaluation'] = {}
    with pytest.raises(VerificationEvaluationError): release_input(model(records), evaluation, cfg, selected_scope)


def test_scope_cannot_be_silently_used_for_whole_inventory_query():
    _, supplied, evaluation, cfg, selected_scope = release_case()
    value = release_input(supplied, evaluation, cfg, selected_scope)
    with pytest.raises(ModelError) as caught:
        query_records(records_for(supplied), NormalizedQuery(evaluation=evaluation.data),
            project=supplied.configuration.data, configuration_id=cfg, verification=value)
    assert caught.value.reason == 'verification_query_scoped_input_unsupported'


def resumed(supplied, value, **kwargs):
    options = dict(expected_sha256=sha256(value.work_input).hexdigest(),
                   inputs=INPUTS, input_roles={p: 'input' for p in INPUTS})
    options.update(kwargs)
    return resume_verification_read_input(supplied, value.work_input, **options)


@pytest.mark.parametrize('release', [False, True])
def test_work_roundtrip_preserves_full_descriptor_scope_time_and_all_observations(release):
    if release:
        _, supplied, evaluation, cfg, selected_scope = release_case()
        value = release_input(supplied, evaluation, cfg, selected_scope)
        options = {'scope_bindings': bindings_for(supplied)}
    else:
        records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation); options = {}
    with no_write_attempts(): restored = resumed(supplied, value, **options)
    assert restored.data == value.data and restored.sha256 == value.sha256
    assert json.loads(value.work_input)['evaluation'] == evaluation.data
    assert json.loads(value.work_input)['evaluation_sha256'] == evaluation.sha256
    assert assess_verification_coverage(supplied, restored).data == assess_verification_coverage(supplied, value).data


def test_work_null_selection_is_preserved_without_defaulting_to_a_current_evaluation():
    records, _, cfg, _ = scenario(); supplied, value = prepare(records, None, cfg)
    restored = resumed(supplied, value)
    assert restored.data['evaluation'] is None and restored.summary['evaluation_sha256'] is None
    assert assess_verification_coverage(supplied, restored).data['selection_status'] == 'missing'


@pytest.mark.parametrize('change', ['bytes', 'evaluation_hash', 'evaluation_id', 'time', 'configuration', 'input_binding', 'unknown'])
def test_work_rejects_tampered_or_rebound_semantic_inputs(change):
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    data = json.loads(value.work_input); expected = sha256(value.work_input).hexdigest()
    if change == 'bytes': raw = value.work_input + b' '
    else:
        if change == 'evaluation_hash': data['evaluation_sha256'] = 'f' * 64
        elif change == 'evaluation_id':
            data['evaluation']['evaluation_id'] = 'EVAL-' + '1' * 26
            data['evaluation_sha256'] = canonical_json_sha256(data['evaluation'])
        elif change == 'time': data['evaluated_at'] = '2026-10-21T00:00:01Z'
        elif change == 'configuration': data['configuration_id'] = ref('CFG')
        elif change == 'input_binding': data['verification_input_sha256'] = 'f' * 64
        else: data['result'] = 'passed'
        raw = canonical_json_bytes(data); expected = sha256(raw).hexdigest()
    with no_write_attempts(), pytest.raises(ModelError):
        resume_verification_read_input(supplied, raw, expected_sha256=expected,
            inputs=INPUTS, input_roles={p: 'input' for p in INPUTS})


@pytest.mark.parametrize('change', ['model', 'product', 'roles', 'missing_product'])
def test_resume_recomputes_and_requires_original_source_and_product_bindings(change):
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    options = {}
    if change == 'model': records[0]['statement'] = 'Changed'; supplied = model(records)
    elif change == 'product': options['inputs'] = {p: b'changed' for p in INPUTS}
    elif change == 'roles': options['input_roles'] = {p: 'output' for p in INPUTS}
    else: options['inputs'] = None
    with no_write_attempts(), pytest.raises(ModelError): resumed(supplied, value, **options)


def test_waiver_trust_is_rechecked_and_never_serialized_as_a_saved_approval():
    records, evaluation, cfg, key, review, verifier = waiver_case()
    records.append(observation(records, evaluation, key, run='ci:expected'))
    supplied, value = prepare(records, evaluation, cfg,
        waiver_reviews={key['subject_artifact_id']: review}, waiver_verifier=verifier)
    assert 'waiver' not in json.loads(value.work_input)
    with pytest.raises(VerificationReadBindingConflict): resumed(supplied, value)
    restored = resumed(supplied, value, waiver_reviews={key['subject_artifact_id']: review}, waiver_verifier=verifier)
    assert restored.sha256 == value.sha256


@pytest.mark.parametrize('units', [1, 10000])
@pytest.mark.parametrize('offset,limit', [(0, 1), (0, 0), (3, 7)])
def test_incremental_query_keeps_full_evaluation_input_and_exact_computed_page(units, offset, limit, tmp_path):
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    query = NormalizedQuery(evaluation=evaluation.data, filters={'type': ['requirement']},
        select=['/id', '/verification_result'], sort=['verification_result:asc'], offset=offset, limit=limit)
    expected = query_records(records_for(supplied), query, project=supplied.configuration.data, verification=value)
    roots = protected(tmp_path); before = inventory(roots[0].root)
    with QueryWork(tmp_path / 'spool', records_for(supplied), query,
            project=supplied.configuration.data, protected_roots=roots, verification=value, batch_bytes=1) as work:
        original = work.evaluation_input
        assert json.loads(original)['evaluation'] == evaluation.data
        while not work.state['complete']:
            assert work.state['evaluation_binding'] == value.summary
            work.state['evaluation_binding'].clear()
            work.advance(units)
            assert work.evaluation_input == original
        result = work.result
        assert result.data == expected.data and result.evaluation_binding == expected.evaluation_binding
        assert result.inputs_sha256 == expected.inputs_sha256
        assert not work.state['durable_checkpoint']
    assert inventory(roots[0].root) == before


def test_invalid_computed_query_input_cannot_create_spool_files(tmp_path):
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    roots = protected(tmp_path); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError):
        QueryWork(tmp_path / 'spool', records_for(supplied), NormalizedQuery(evaluation=None),
            project=supplied.configuration.data, protected_roots=roots, verification=value)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_native_work_store_and_fresh_process_preserve_saved_selection_and_coverage(mode, tmp_path):
    from test_work_manifest import create
    from test_work_checkpoints import setup
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    raw = value.work_input
    initial = create(request=CommandRequest('query'), data=[
        {'root_id': 'verification', 'path': 'read-input.json', 'raw': raw},
        {'root_id': 'model', 'path': 'records.json', 'raw': canonical_json_bytes({'records': records})},
        *[{'root_id': 'product', 'path': p, 'raw': b} for p, b in INPUTS.items()]])
    initial, roots, location, store = setup(tmp_path, initial=initial)
    store.publish(initial)
    # Trust is supplied independently by the host, never reconstructed from work.json.
    import base64
    trusted = {'raw': base64.b64encode(initial.raw).decode(),
        'objects': {h: base64.b64encode(b).decode() for h, b in initial.objects.items()},
        'build': initial.as_dict()['tool_build']}
    body = '''import base64,json
from pathlib import Path
from specroad.cli.commands import builtin_registry
from specroad.work.manifest import read_work_manifest
from specroad.work.checkpoints import CheckpointStore
from specroad.work.root import WorkDirectory
from specroad.security import ProjectBoundary
from specroad.changes import TargetModel
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource,compose_profiles
from specroad.validation import ModelDocument
from specroad.verification import resume_verification_read_input,assess_verification_coverage
'''
    body += 'trusted=' + repr(trusted) + '\n'
    body += 'work_path=' + repr(str(location.path)) + '\nprotected=' + repr(str(roots[0].root)) + '\n'
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'resources=' + repr([(d.path,d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += '''initial=read_work_manifest(base64.b64decode(trusted['raw']),
 {h:base64.b64decode(b) for h,b in trusted['objects'].items()},registry=builtin_registry(),expected_tool_build=trusted['build'])
store=CheckpointStore(WorkDirectory(initial,protected_roots=(ProjectBoundary(protected),),directory=Path(work_path)),initial)
saved=store.read()
rows={(r['root_id'],r['path']):r for r in saved.entries('inputs')}
read=lambda key:saved.objects[rows[key]['sha256']]
records=json.loads(read(('model','records.json')))['records']
profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(artifact_path(r['artifact_type'],r['id'],'SR'),canonical_json_bytes(r)) for r in records],
 profile=profile,resource_files=[ModelDocument(path,raw) for path,raw in resources])
inputs={path:read((root,path)) for root,path in rows if root=='product'}
value=resume_verification_read_input(owned,read(('verification','read-input.json')),
 expected_sha256=rows[('verification','read-input.json')]['sha256'],inputs=inputs,input_roles={p:'input' for p in inputs})
print(json.dumps({'input':value.data,'coverage':assess_verification_coverage(owned,value).data}))
'''
    before = inventory(location.path)
    if mode == 'core': completed = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        completed = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {'input': value.data, 'coverage': assess_verification_coverage(supplied, value).data}
    assert inventory(location.path) == before
