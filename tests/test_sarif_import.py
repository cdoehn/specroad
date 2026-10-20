"""SARIF observations require exact mappings and never imply an executed check."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.model.canonical import canonical_json_sha256
from specroad.verification import (SarifDocument, SarifMapping, SarifCandidates,
    EvidenceImportError, map_sarif_candidates)
from support.artifacts import artifact_bytes
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from test_evidence_exchange import exchange_case


def sarif_case(kind='fail', *, level='warning'):
    exchange, targets = exchange_case()
    exchange['results'][0]['result'] = {'pass': 'passed', 'fail': 'failed',
                                       'notApplicable': 'skipped'}[kind]
    report = {'version': '2.1.0', '$schema': 'https://example.invalid/never-fetched',
        'runs': [{'tool': {'driver': {'name': 'analyzer', 'version': '1',
                                     'rules': [{'id': 'RULE1', 'name': 'Explicitly selected'},
                                               {'id': 'UNMAPPED', 'properties': {'passed': True}}]}},
                  'invocations': [{'executionSuccessful': True}],
                  'artifacts': [{'location': {'uri': 'https://example.invalid/report'},
                                 'contents': {'text': 'passive $(no command)'}}],
                  'results': [{'ruleIndex': 0, 'ruleId': 'RULE1', 'kind': kind,
                               'level': level, 'message': {'text': 'Measured finding'}},
                              {'message': {'text': 'Unmapped; not a pass'}, 'level': 'note'}]}]}
    row = {'exchange_result_index': 0, 'run_index': 0, 'result_index': 0,
           'rule_index': 0, 'invocation_index': 0, 'artifact_indices': [0]}
    mapping = {'format_version': 'sarif-mapping-v1', 'source_sha256': sha256(artifact_bytes(report)).hexdigest(),
               'exchange': exchange, 'bindings': [row]}
    return report, mapping, targets


def resolved(report, mapping, targets):
    raw = artifact_bytes(report)
    mapping = {**mapping, 'source_sha256': sha256(raw).hexdigest()}
    return map_sarif_candidates(SarifDocument(raw), SarifMapping(artifact_bytes(mapping)), targets=targets)


@pytest.mark.parametrize('kind,level,outcome', [
    ('fail', 'warning', 'failed'), ('fail', 'note', 'failed'), ('fail', 'none', 'failed'),
    ('fail', 'error', 'failed'), ('pass', 'none', 'passed'), ('notApplicable', 'none', 'skipped')])
def test_explicit_inline_mapping_retains_bound_data_and_selected_sarif_objects(kind, level, outcome):
    report, mapping, targets = sarif_case(kind, level=level)
    with no_write_attempts():
        output = resolved(report, mapping, targets).data
    candidate, = output['candidates']
    assert candidate['result'] == outcome and candidate['origin'] == 'imported_sarif'
    assert candidate['producer'] == mapping['exchange']['producer']
    assert candidate['run_context'] == {**mapping['exchange']['run'], 'check_id': 'measurement',
                                       'test_id': targets[2].data['id']}
    assert candidate['subjects'] == mapping['exchange']['subjects']
    source = candidate['sarif']
    assert source['driver'] == {'name': 'analyzer', 'version': '1'}  # No unmapped rules.
    assert source['result']['value'] == report['runs'][0]['results'][0]
    assert source['result']['pointer'] == '/runs/0/results/0'
    assert source['result']['sha256'] == canonical_json_sha256(report['runs'][0]['results'][0])
    assert source['rule']['value'] == report['runs'][0]['tool']['driver']['rules'][0]
    assert source['rule']['pointer'] == '/runs/0/tool/driver/rules/0'
    assert source['invocation']['pointer'] == '/runs/0/invocations/0'
    assert source['artifacts'][0]['value'] == report['runs'][0]['artifacts'][0]
    assert output['unmapped_results'] == ['/runs/0/results/1']
    assert output['source']['sha256'] == mapping['source_sha256']
    assert output['mapping_sha256'] == canonical_json_sha256(mapping)
    assert output['mapping_source_sha256'] == sha256(artifact_bytes(mapping)).hexdigest()
    for flag in ('external_run_verified', 'project_targets_verified', 'evidence_created',
                 'full_verification_evaluated', 'test_code_executed', 'import_policy_applied'):
        assert output[flag] is False


def test_no_mapping_means_no_candidates_even_for_a_successful_tool_run():
    report, mapping, targets = sarif_case()
    mapping['bindings'] = []
    mapping['exchange']['results'] = []
    data = resolved(report, mapping, targets).data
    assert data['candidate_count'] == 0 and data['candidates'] == []
    assert data['unmapped_results'] == ['/runs/0/results/0', '/runs/0/results/1']


def test_explicit_null_selectors_never_implicitly_import_related_objects():
    report, mapping, targets = sarif_case()
    mapping['bindings'][0].update(rule_index=None, invocation_index=None, artifact_indices=[])
    data = resolved(report, mapping, targets).data['candidates'][0]['sarif']
    assert data['rule'] is None and data['invocation'] is None and data['artifacts'] == []
    assert 'rules' not in data['driver']


def test_multiple_runs_and_occurrences_follow_mapping_order_without_aggregation():
    report, mapping, targets = sarif_case()
    report['runs'].append(json.loads(json.dumps(report['runs'][0])))
    other = {**mapping['exchange']['results'][0], 'result': 'passed'}
    mapping['exchange']['results'].append(other)
    report['runs'][1]['results'][0].update(kind='pass', level='none')
    mapping['bindings'].insert(0, {**mapping['bindings'][0], 'run_index': 1, 'exchange_result_index': 1})
    data = resolved(report, mapping, targets).data
    assert [c['result'] for c in data['candidates']] == ['passed', 'failed']
    assert [c['result_index'] for c in data['candidates']] == [1, 0]
    assert data['unmapped_results'] == ['/runs/0/results/1', '/runs/1/results/1']


@pytest.mark.parametrize('level', ['none', 'note', 'warning', 'error'])
def test_level_and_successful_invocation_alone_cannot_be_mapped_to_passed(level):
    report, mapping, targets = sarif_case()
    del report['runs'][0]['results'][0]['kind']
    report['runs'][0]['results'][0]['level'] = level
    mapping['exchange']['results'][0]['result'] = 'passed'
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'unsupported_sarif_outcome_mapping'
    mapping['exchange']['results'][0]['result'] = 'failed'
    assert resolved(report, mapping, targets).data['candidates'][0]['result'] == 'failed'


@pytest.mark.parametrize('kind', ['open', 'review', 'informational', 'not-a-kind', None, {}, []])
def test_unsupported_kinds_do_not_gain_an_implicit_interpretation(kind):
    report, mapping, targets = sarif_case()
    report['runs'][0]['results'][0]['kind'] = kind
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'unsupported_sarif_outcome_mapping'


@pytest.mark.parametrize('level', ['error', None, {}, 'success'])
def test_explicit_pass_rejects_inconsistent_or_malformed_level(level):
    report, mapping, targets = sarif_case('pass', level=level)
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'invalid_sarif_result_level'


def test_report_bytes_are_exactly_bound_and_cached_data_cannot_replace_them():
    report, mapping, targets = sarif_case()
    doc = SarifDocument(artifact_bytes(report))
    rules = SarifMapping(artifact_bytes(mapping))
    before = map_sarif_candidates(doc, rules, targets=targets).data
    object.__setattr__(doc, '_encoded', b'{}')
    object.__setattr__(rules, '_encoded', b'{}')
    assert map_sarif_candidates(doc, rules, targets=targets).data == before
    with pytest.raises(EvidenceImportError) as caught:
        map_sarif_candidates(SarifDocument(doc.source_bytes + b' '), rules, targets=targets)
    assert caught.value.reason == 'sarif_source_binding_mismatch'


@pytest.mark.parametrize('field,value', [('ruleIndex', 1), ('ruleIndex', True),
                                       ('ruleId', 'unrelated')])
def test_selected_driver_rule_must_agree_with_the_result_reference(field, value):
    report, mapping, targets = sarif_case()
    report['runs'][0]['results'][0][field] = value
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'sarif_rule_binding_mismatch'


@pytest.mark.parametrize('success,reason', [
    (False, 'sarif_failed_invocation_cannot_pass'), (None, 'invalid_sarif_invocation'),
    (1, 'invalid_sarif_invocation'), ('true', 'invalid_sarif_invocation')])
def test_invocation_failure_or_invalid_success_cannot_support_a_pass(success, reason):
    report, mapping, targets = sarif_case('pass', level='none')
    report['runs'][0]['invocations'][0]['executionSuccessful'] = success
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == reason


@pytest.mark.parametrize('field', ['run_index', 'result_index', 'rule_index', 'invocation_index',
                                  'artifact_indices'])
def test_selectors_require_in_range_exact_indices(field):
    report, mapping, targets = sarif_case()
    mapping['bindings'][0][field] = [100] if field == 'artifact_indices' else 100
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'sarif_index_out_of_range'


@pytest.mark.parametrize('index', [True, -1, 0.0, '0', None])
def test_selector_types_are_never_coerced(index):
    report, mapping, _ = sarif_case()
    mapping['bindings'][0]['run_index'] = index
    with pytest.raises(EvidenceImportError):
        SarifMapping(artifact_bytes(mapping))


@pytest.mark.parametrize('duplicate', ['result', 'exchange', 'artifact'])
def test_duplicate_mapping_bindings_are_rejected(duplicate):
    report, mapping, _ = sarif_case()
    if duplicate == 'artifact':
        mapping['bindings'][0]['artifact_indices'] = [0, 0]
    else:
        row = dict(mapping['bindings'][0])
        row['exchange_result_index' if duplicate == 'result' else 'result_index'] = 1
        mapping['bindings'].append(row)
    with pytest.raises(EvidenceImportError) as caught:
        SarifMapping(artifact_bytes(mapping))
    assert caught.value.reason == 'duplicate_evidence_import_binding'


def test_unbound_exchange_results_and_unknown_mapping_keys_are_rejected():
    _, mapping, _ = sarif_case()
    mapping['bindings'] = []
    with pytest.raises(EvidenceImportError) as caught:
        SarifMapping(artifact_bytes(mapping))
    assert caught.value.reason == 'sarif_exchange_mapping_incomplete'
    _, mapping, _ = sarif_case()
    mapping['bindings'][0]['script'] = 'never execute'
    with pytest.raises(EvidenceImportError):
        SarifMapping(artifact_bytes(mapping))


@pytest.mark.parametrize('change', [
    {'version': '2.2.0'}, {'runs': None}, {'runs': [None]}, {'runs': [{}]},
    {'runs': [{'tool': {'driver': {'name': 'x'}}, 'results': [None]}]}])
def test_invalid_document_profile_is_refused_before_mapping(change):
    report, _, _ = sarif_case()
    with pytest.raises(EvidenceImportError):
        SarifDocument(artifact_bytes({**report, **change}))


@pytest.mark.parametrize('field', ['externalPropertyFileReferences', 'rule'])
def test_external_properties_and_component_rules_require_a_future_explicit_profile(field):
    report, mapping, targets = sarif_case()
    if field == 'rule':
        report['runs'][0]['results'][0]['rule'] = {'id': 'RULE1'}
    else:
        report['runs'][0][field] = {'results': [{'location': {'uri': 'file:///secret'}}]}
    with no_write_attempts(), pytest.raises(EvidenceImportError):
        resolved(report, mapping, targets)


def test_opaque_metadata_and_uris_are_never_host_access_or_implicit_result_data(monkeypatch):
    report, mapping, targets = sarif_case()
    report['runs'][0]['properties'] = {'results': [{'kind': 'pass'}], 'command': 'sh -c false'}
    report['runs'][0]['invocations'][0]['commandLine'] = 'never-executed'
    report['runs'][0]['artifacts'][0]['location']['uri'] = 'file:///secret'
    def forbidden(*args, **kwargs): raise AssertionError('External access')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('builtins.open', 'io.open', 'time.time', 'os.urandom'):
            patch.setattr(name, forbidden)
        data = resolved(report, mapping, targets).data
    assert data['candidate_count'] == 1 and data['candidates'][0]['result'] == 'failed'
    assert data['candidates'][0]['sarif']['artifacts'][0]['value']['location']['uri'] == 'file:///secret'


def test_owned_values_and_outputs_have_no_boolean_or_mutation_authority():
    report, mapping, targets = sarif_case()
    doc, rules = SarifDocument(artifact_bytes(report)), SarifMapping(artifact_bytes(mapping))
    result = map_sarif_candidates(doc, rules, targets=targets)
    original = result.data
    report.clear(); mapping.clear(); doc.data.clear(); rules.data.clear(); result.data.clear()
    assert result.data == original and result.sha256 == canonical_json_sha256(original)
    for item in (doc, rules, result):
        with pytest.raises(FrozenInstanceError): item._encoded = b'{}'
        with pytest.raises(TypeError): bool(item)
    with pytest.raises(TypeError): SarifCandidates(original)
    for raw in ('{}', b'{"x":1,"x":2}', b'{"x":NaN}'):
        for cls in (SarifDocument, SarifMapping):
            with pytest.raises(EvidenceImportError): cls(raw)


def test_reusing_a_large_artifact_cannot_amplify_small_input_into_unbounded_output():
    report, mapping, targets = sarif_case()
    report['runs'][0]['artifacts'][0]['contents']['text'] = 'x' * 40000
    report['runs'][0]['results'] = [report['runs'][0]['results'][0]] * 500
    mapping['exchange']['results'] *= 500
    first = mapping['bindings'][0]
    mapping['bindings'] = [{**first, 'result_index': i, 'exchange_result_index': i}
                           for i in range(500)]
    assert len(artifact_bytes(report)) + len(artifact_bytes(mapping)) < 1024 * 1024
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'evidence_import_candidate_limit'


@pytest.mark.parametrize('portable', [False, True])
def test_source_and_pyz_support_the_same_passive_sarif_binding(tmp_path, portable):
    report, mapping, targets = sarif_case()
    body = f"""
import json
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import VerificationContract, VerificationTest, SarifDocument, SarifMapping, map_sarif_candidates
targets=[DomainArtifact({targets[0].source_bytes!r}), VerificationContract({targets[1].source_bytes!r}),
         VerificationTest({targets[2].source_bytes!r})]
print(json.dumps(map_sarif_candidates(SarifDocument({artifact_bytes(report)!r}),
    SarifMapping({artifact_bytes(mapping)!r}), targets=targets).data, sort_keys=True))
"""
    if portable:
        _, archive = build_distribution(tmp_path / 'dist')
        process = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(archive)) + ');\n' + body], tmp_path, capture=True)
    else:
        process = run_core(body, tmp_path, capture=True)
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == resolved(report, mapping, targets).data
