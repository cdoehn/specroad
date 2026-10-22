"""Explicit coverage/input bindings and computed read projections; no UI or pass claims."""
from dataclasses import FrozenInstanceError
import json

import pytest

from specroad.documents.builtin_views import resolve_builtin_view, BuiltinViewProviderError
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, select_query, query_records
from specroad.verification import (VerificationReadInput, VerificationCoverage,
    prepare_verification_read_input, assess_verification_coverage,
    VerificationEvaluationError)
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import ref, record_value
from support.srx import expression_document, literal
from support.targets import model
from test_verification_aggregation import scenario, NOW, waiver_case
from test_verification_evaluation import INPUTS, descriptor
from test_verification_required_checks import edge
from test_verification_run_selection import observation

DIMENSIONS = ('positive', 'negative', 'boundary', 'exception', 'timing', 'error', 'security', 'performance')


def prepare(records, evaluation, cfg=None, **kwargs):
    options = dict(configuration_id=cfg, inputs=dict(INPUTS),
                   input_roles={p: 'input' for p in INPUTS}, evaluated_at=NOW)
    options.update(kwargs)
    supplied = model(records)
    return supplied, prepare_verification_read_input(supplied, evaluation, **options)


def records_for(supplied):
    return tuple(SourceRelations(d.content, path=d.path) for d in supplied.documents)


def coverage_case():
    first, second = ref(), ref('REQ', '1')
    records = [domain_value('requirement', id=first, verification_plan_status='planned',
        relations=[edge(ref('VER'), 1)]),
        domain_value('requirement', id=second, requirement_kind='quality',
        verification_plan_status='running', relations=[edge(ref('VER', '1'), 2)]),
        record_value('verification', dimensions=list(DIMENSIONS), subjects=[first], configuration_policy='independent',
            evidence_slots=[{'check_id': name, 'test_id': None, 'dimension': name} for name in DIMENSIONS]),
        record_value('verification', id=ref('VER', '1'), dimensions=['performance'], subjects=[second], configuration_policy='independent',
            evidence_slots=[{'check_id': 'latency', 'test_id': None, 'dimension': 'performance'}])]
    keys = [{'subject_artifact_id': first, 'contract_id': ref('VER'),
             'test_id': None, 'check_id': name} for name in DIMENSIONS]
    keys.append({'subject_artifact_id': second, 'contract_id': ref('VER', '1'),
                 'test_id': None, 'check_id': 'latency'})
    evaluation = descriptor(required_runs=[{**key, 'run_ids': ['ci:measured']} for key in keys])
    evidence = []
    for i, key in enumerate(keys):
        item = observation(records, evaluation, key, run='ci:measured',
                           result='failed' if i == 8 else 'passed')
        item['id'] = 'SR-EVD-' + '0' * 25 + str(i)
        item['configuration_policy'] = 'independent'
        evidence.append(item)
    return records + evidence, evaluation


def page(supplied, verification, **kwargs):
    query = NormalizedQuery(evaluation=verification.data['evaluation'], **kwargs)
    return query_records(records_for(supplied), query, project=supplied.configuration.data,
        configuration_id=verification.data['scope_descriptor']['configuration_id'], verification=verification)


def test_requirement_and_kind_totals_do_not_count_contracts_as_requirements():
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    before = supplied.source_files
    with no_write_attempts(): result = assess_verification_coverage(supplied, value)
    data = result.data
    assert data['totals']['requirements'] == 2
    assert data['totals']['requirement_ids'] == [ref(), ref('REQ', '1')]
    assert data['totals']['verification_results'] == {'passed': 1, 'failed': 1}
    assert data['totals']['required_checks'] == data['totals']['active_runs'] == 9
    assert data['totals']['evidence_freshness'] == {'current': 9}
    assert data['totals']['evidence_results'] == {'passed': 8, 'failed': 1}
    kinds = {row['requirement_kind']: row for row in data['by_kind']}
    assert kinds['functional']['requirement_ids'] == [ref()]
    assert kinds['functional']['required_checks'] == 8
    assert kinds['quality']['verification_results'] == {'failed': 1}
    assert kinds['quality']['required_checks'] == 1
    assert supplied.source_files == before
    assert result.sha256 == canonical_json_sha256(data)
    assert data['summary']['evaluation_sha256'] == evaluation.sha256
    assert data['summary']['verification_input_sha256'] == value.sha256
    assert not any(data[k] for k in ('project_files_verified', 'full_verification_evaluated',
        'project_required_checks_complete', 'release_readiness_evaluated', 'test_code_executed',
        'external_run_verified', 'write_authorized', 'approval_granted'))


@pytest.mark.parametrize('dimension', DIMENSIONS)
def test_declared_dimensions_keep_independent_exact_check_sets(dimension):
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    data = assess_verification_coverage(supplied, value).data
    row = next(r for r in data['by_dimension'] if r['dimension'] == dimension)
    assert {c['check_id'] for c in row['checks']} == ({dimension, 'latency'} if dimension == 'performance' else {dimension})
    assert row['totals']['required_checks'] == (2 if dimension == 'performance' else 1)
    assert row['totals']['check_results'] == ({'passed': 1, 'failed': 1} if dimension == 'performance' else {'passed': 1})
    assert row['requirement_ids'] == ([ref(), ref('REQ', '1')] if dimension == 'performance' else [ref()])


@pytest.mark.parametrize('kind,expected,freshness', [
    ('passed', 'passed', {'current': 1}), ('failed', 'failed', {'current': 1}),
    ('stale', 'stale', {'stale': 1}), ('missing', 'incomplete', {}),
    ('unknown', 'incomplete', {'current': 1})])
def test_coverage_keeps_current_result_and_evidence_freshness_separate(kind, expected, freshness):
    records, evaluation, cfg, key = scenario(configured=False, policy='independent')
    if kind != 'missing':
        ev = observation(records, evaluation, key, run='ci:expected',
                         result='not_measured' if kind == 'unknown' else 'failed' if kind == 'failed' else 'passed')
        ev['configuration_policy'] = 'independent'
        if kind == 'stale': ev['subjects'][0]['verification_context_sha256'] = 'f' * 64
        records.append(ev)
    supplied, value = prepare(records, evaluation, cfg)
    data = assess_verification_coverage(supplied, value).data
    assert data['totals']['verification_results'] == {expected: 1}
    assert data['totals']['evidence_freshness'] == freshness
    assert data['totals']['required_checks'] == 1
    assert data['totals']['active_runs'] == 1
    assert data['requirements'][0]['checks'][0]['dimension'] == 'overall'


def test_absent_evaluation_preserves_required_dimensions_without_inventing_selection():
    records, _, cfg, _ = scenario(configured=False)
    supplied, value = prepare(records, None, cfg, inputs=None, input_roles=None)
    data = assess_verification_coverage(supplied, value).data
    assert data['summary']['evaluation_sha256'] is None
    assert data['totals']['requirements'] == data['totals']['required_checks'] == 1
    assert data['totals']['active_runs'] == data['totals']['evidence_observations'] == 0
    check = data['requirements'][0]['checks'][0]
    assert not check['run_selection_evaluated'] and check['evidence_result'] == 'incomplete'
    assert 'evaluation_required' in check['reasons']
    assert data['totals']['verification_results'] == {'incomplete': 1}


def test_requirement_without_contract_remains_in_totals_and_cannot_pass():
    records = [domain_value('requirement', verification_plan_status='planned')]
    supplied, value = prepare(records, None)
    data = assess_verification_coverage(supplied, value).data
    assert data['totals']['requirements'] == 1 and data['totals']['required_checks'] == 0
    assert data['totals']['verification_results'] == {'incomplete': 1}
    assert data['by_dimension'] == []


def test_configuration_exclusion_remains_visible_and_never_becomes_covered_evidence():
    records, _, cfg, _ = scenario()
    records[0]['applicability'] = expression_document(literal(False))
    supplied, value = prepare(records, None, cfg)
    data = assess_verification_coverage(supplied, value).data
    assert data['totals']['verification_results'] == {'not_applicable': 1}
    assert data['totals']['required_checks'] == 0
    assert value.data['scope_descriptor']['configuration_id'] == cfg
    assert value.data['configuration_hash'] is not None


def test_bound_waiver_and_current_failure_remain_distinct_coverage_axes():
    records, evaluation, cfg, key, review, verifier = waiver_case()
    records.append(observation(records, evaluation, key, run='ci:expected'))
    supplied, value = prepare(records, evaluation, cfg,
        waiver_reviews={key['subject_artifact_id']: review}, waiver_verifier=verifier)
    data = assess_verification_coverage(supplied, value).data
    assert data['totals']['verification_results'] == {'waived': 1}
    assert data['totals']['check_results'] == {'failed': 1}
    assert data['requirements'][0]['checks'][0]['active_runs'][0]['evidence'][0]['result'] == 'failed'


def test_same_selection_and_reordered_sources_produce_identical_coverage_and_binding():
    records, evaluation = coverage_case()
    a, first = prepare(records, evaluation); b, second = prepare(list(reversed(records)), evaluation)
    assert first.data == second.data and first.sha256 == second.sha256
    assert assess_verification_coverage(a, first).data == assess_verification_coverage(b, second).data


def test_owned_inputs_cannot_be_changed_through_report_copies():
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    result = assess_verification_coverage(supplied, value); before = result.data
    value.data['aggregation']['subjects'].clear(); value.summary.clear(); result.data['requirements'].clear()
    records[0]['statement'] = 'Changed outside the snapshot'
    assert result.data == before and assess_verification_coverage(supplied, value).data == before
    for owned in (value, result):
        with pytest.raises(TypeError): bool(owned)
        with pytest.raises(FrozenInstanceError): owned._encoded = b'{}'
    for cls in (VerificationReadInput, VerificationCoverage):
        with pytest.raises(TypeError): cls()


@pytest.mark.parametrize('consumer', ['coverage', 'view'])
def test_changed_model_rejects_a_previously_computed_input(consumer):
    records, evaluation = coverage_case(); _, value = prepare(records, evaluation)
    records[0]['statement'] = 'A changed requirement'
    supplied = model(records)
    with pytest.raises(ModelError) as caught:
        if consumer == 'coverage': assess_verification_coverage(supplied, value)
        else: resolve_builtin_view(supplied, 'verification', verification=value)
    assert caught.value.reason == 'verification_read_input_model_mismatch'


@pytest.mark.parametrize('fake', [{}, True, 'passed'])
def test_untyped_input_cannot_create_coverage_view_or_query_success(fake):
    records, evaluation = coverage_case(); supplied = model(records)
    with pytest.raises(ModelError): assess_verification_coverage(supplied, fake)
    with pytest.raises(ModelError): resolve_builtin_view(supplied, 'verification', verification=fake)
    with pytest.raises(ModelError):
        select_query(records_for(supplied), NormalizedQuery(limit=0),
                     project=supplied.configuration.data, verification=fake)


def test_plan_status_and_computed_result_are_independent_query_filters():
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    with no_write_attempts():
        result = page(supplied, value, filters={'type': ['requirement'],
            'verification_plan_status': ['running'], 'verification_result': ['failed']},
            select=['/verification_plan_status', '/verification_result'])
    assert result.data == {'items': [{'id': ref('REQ', '1'), 'artifact_type': 'requirement',
        'values': {'/verification_plan_status': 'running', '/verification_result': 'failed'}}],
        'total': 1, 'offset': 0, 'limit': 100, 'returned': 1, 'truncated': False}
    assert result.evaluation_binding == value.summary
    assert page(supplied, value, filters={'verification_plan_status': ['running'],
        'verification_result': ['passed']}).data['total'] == 0
    assert 'verification_result' not in supplied.artifacts[0]


@pytest.mark.parametrize('direction,first', [('asc', ref('REQ', '1')), ('desc', ref())])
def test_computed_sort_precedes_paging_and_works_without_projecting_the_sort_key(direction, first):
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    result = page(supplied, value, filters={'type': ['requirement']},
                  sort=['verification_result:' + direction], select=['/id'], limit=1)
    assert result.data['items'][0]['id'] == first
    assert result.data['total'] == 2 and result.data['truncated']
    assert result.data['items'][0]['values'] == {'/id': first}


def test_query_identity_binds_evaluation_time_even_for_the_same_results():
    records, evaluation = coverage_case(); supplied, first = prepare(records, evaluation)
    _, second = prepare(records, evaluation, evaluated_at='2026-10-21T00:00:01Z')
    left, right = page(supplied, first), page(supplied, second)
    assert left.data == right.data and left.query_sha256 == right.query_sha256
    assert left.inputs_sha256 != right.inputs_sha256
    assert left.evaluation_binding != right.evaluation_binding


@pytest.mark.parametrize('change', ['evaluation', 'record', 'missing_record', 'project', 'configuration', 'raw_configuration'])
def test_query_rejects_foreign_binding_even_when_no_rows_are_requested(change):
    records, evaluation, cfg, _ = scenario()
    supplied, value = prepare(records, evaluation, cfg)
    sources = records_for(supplied); query_value = evaluation.data; project = supplied.configuration.data
    configuration = None; configuration_id = cfg
    if change == 'evaluation': query_value = None
    if change == 'record':
        records[0]['statement'] = 'Different input'; sources = records_for(model(records))
    if change == 'missing_record': sources = sources[:-1]
    if change == 'project': project = {}
    if change == 'configuration': configuration_id = None
    if change == 'raw_configuration': configuration = {}
    with pytest.raises(ModelError) as caught:
        query_records(sources, NormalizedQuery(evaluation=query_value, limit=0), project=project,
            configuration=configuration, configuration_id=configuration_id, verification=value)
    assert caught.value.reason in {'verification_query_evaluation_mismatch',
        'verification_query_sources_mismatch', 'verification_query_configuration_mismatch'}


def test_computed_input_does_not_silently_admit_unintegrated_srx_or_release_queries():
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    with pytest.raises(ModelError) as caught:
        page(supplied, value, srx_filters=[expression_document(literal(True))])
    assert caught.value.reason == 'verification_query_srx_provider_required'
    with pytest.raises(ModelError) as caught:
        page(supplied, value, filters={'release': [ref('REL')]})
    assert caught.value.reason == 'query_filter_provider_required'


def test_missing_descriptor_in_query_remains_explicit_incomplete_and_bound():
    records, _, cfg, _ = scenario(configured=False); supplied, value = prepare(records, None, cfg)
    result = page(supplied, value, filters={'verification_result': ['incomplete']}, select=['/verification_result'])
    assert result.data['total'] == 1
    assert result.data['items'][0]['values']['/verification_result'] == 'incomplete'
    assert result.evaluation_binding['evaluation_sha256'] is None


def test_non_subject_records_have_no_fabricated_verification_result():
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    result = page(supplied, value, filters={'type': ['verification']}, select=['/verification_result'])
    assert result.data['total'] == 2
    assert all(row['values']['/verification_result'] == {'state': 'missing'} for row in result.data['items'])


def test_builtin_view_uses_the_same_bound_coverage_without_rendering_or_release_approval():
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    with no_write_attempts(): result = resolve_builtin_view(supplied, 'verification', verification=value)
    data = result.data
    assert data['coverage'] == assess_verification_coverage(supplied, value).data
    assert data['rows'] == data['coverage']['requirements'] and data['row_count'] == 2
    assert data['summary'] == value.summary and data['verification_evaluated']
    assert data['computed_reports']['verification']['status'] == 'computed'
    assert not data['release_readiness_evaluated'] and not data['rendering_performed']
    assert result.source_files == supplied.source_files
    with pytest.raises(BuiltinViewProviderError): resolve_builtin_view(supplied, 'verification')
    with pytest.raises(ModelError): resolve_builtin_view(supplied, 'roadmap', verification=value)
    trace = resolve_builtin_view(supplied, 'traceability', verification=value).data
    assert trace['computed_reports']['verification']['result'] == data['coverage']


@pytest.mark.parametrize('bad', [b'{}', {}, 'evaluation.json'])
def test_passive_descriptor_values_do_not_trigger_import_or_file_access(bad):
    records, _, cfg, _ = scenario(configured=False)
    with no_write_attempts(), pytest.raises(VerificationEvaluationError): prepare(records, bad, cfg)


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_coverage_and_computed_query_agree_in_isolated_core_and_pyz(mode, tmp_path):
    records, evaluation = coverage_case(); supplied, value = prepare(records, evaluation)
    expected = {'coverage': assess_verification_coverage(supplied, value).data,
                'page': page(supplied, value, filters={'type': ['requirement']}, select=['/verification_result']).data}
    body = '''import json
from specroad.changes import TargetModel
from specroad.verification import VerificationEvaluation, prepare_verification_read_input, assess_verification_coverage
from specroad.query import NormalizedQuery, query_records
from specroad.graph.relations import SourceRelations
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'config=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'core_key=' + repr(supplied.profile.profile_chain[0]) + '\n'
    body += 'evaluation=VerificationEvaluation(' + repr(evaluation.source_bytes) + ')\n'
    body += 'inputs=' + repr(INPUTS) + '\nnow=' + repr(NOW) + '\n'
    body += '''profile=compose_profiles([ProfileResource(raw) for path,raw in resources],core_key=core_key)
owned=TargetModel(config,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
value=prepare_verification_read_input(owned,evaluation,configuration_id=None,
 inputs=inputs,input_roles={p:'input' for p in inputs},evaluated_at=now)
query=NormalizedQuery(evaluation=evaluation.data,filters={'type':['requirement']},select=['/verification_result'])
page=query_records(tuple(SourceRelations(raw,path=path) for path,raw in documents),query,
 project=owned.configuration.data,verification=value)
print(json.dumps({'coverage':assess_verification_coverage(owned,value).data,'page':page.data}))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
