"""Selected SARIF fields are checked; foreign data never becomes a passing test."""
import json

import pytest

from specroad.verification import EvidenceImportError
from support.artifacts import artifact_bytes
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, make_project, no_write_attempts
from test_sarif_import import sarif_case, resolved


@pytest.mark.parametrize('kind,level', [('pass', 'none'), ('fail', 'warning'), ('notApplicable', 'none')])
def test_baseline_only_findings_are_not_current_measurements(kind, level):
    report, mapping, targets = sarif_case(kind, level=level)
    report['runs'][0]['results'][0]['baselineState'] = 'absent'
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'sarif_baseline_only_result'
    assert caught.value.pointer == '/runs/0/results/0/baselineState'


@pytest.mark.parametrize('baseline', ['new', 'unchanged', 'updated'])
def test_current_baseline_states_do_not_change_an_explicit_result(baseline):
    report, mapping, targets = sarif_case()
    report['runs'][0]['results'][0]['baselineState'] = baseline
    candidate, = resolved(report, mapping, targets).data['candidates']
    assert candidate['result'] == 'failed'
    assert candidate['sarif']['result']['value']['baselineState'] == baseline


@pytest.mark.parametrize('status', [None, 'accepted', 'underReview', 'rejected'])
def test_suppression_is_not_a_pass_or_waiver_even_when_an_explicit_pass_is_claimed(status):
    report, mapping, targets = sarif_case('pass', level='none')
    suppression = {'kind': 'external'}
    if status is not None: suppression['status'] = status
    report['runs'][0]['results'][0]['suppressions'] = [suppression]
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'sarif_suppressed_pass_unsupported'
    # Suppressed failures remain failures, never an inferred success/approval.
    report['runs'][0]['results'][0].update(kind='fail', level='warning')
    mapping['exchange']['results'][0]['result'] = 'failed'
    candidate, = resolved(report, mapping, targets).data['candidates']
    assert candidate['result'] == 'failed'
    assert candidate['sarif']['result']['value']['suppressions'] == [suppression]


@pytest.mark.parametrize('suppression', [None, []])
def test_no_suppression_is_compatible_with_explicit_pass(suppression):
    report, mapping, targets = sarif_case('pass', level='none')
    report['runs'][0]['results'][0]['suppressions'] = suppression
    result = resolved(report, mapping, targets).data
    assert result['candidates'][0]['result'] == 'passed'
    assert result['approval_granted'] is False and result['external_run_verified'] is False


@pytest.mark.parametrize('field,bad,pointer', [
    ('message', {'text': 'valid', 'markdown': 7}, '/message/markdown'),
    ('message', {'text': 'valid', 'id': None}, '/message/id'),
    ('message', {'text': 'valid', 'arguments': [False]}, '/message/arguments/0'),
    ('provenance', None, '/provenance'), ('provenance', [], '/provenance'),
    ('baselineState', 'fixed', '/baselineState'), ('properties', [], '/properties'),
    ('suppressions', {}, '/suppressions'),
    ('suppressions', [{}], '/suppressions'),
    ('suppressions', [{'kind': 'waived'}], '/suppressions'),
    ('suppressions', [{'kind': 'inSource', 'status': 'approved'}], '/suppressions')])
def test_selected_known_metadata_rejects_wrong_types_and_unknown_semantics(field, bad, pointer):
    report, mapping, targets = sarif_case()
    report['runs'][0]['results'][0][field] = bad
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'invalid_sarif_result_metadata'
    assert caught.value.pointer.startswith('/runs/0/results/0' + pointer)


@pytest.mark.parametrize('field,bad', [('ruleIndex', 99), ('ruleIndex', 0.0),
                                     ('ruleIndex', True), ('ruleId', 'OTHER')])
def test_result_rule_references_remain_checked_when_the_rule_is_not_imported(field, bad):
    report, mapping, targets = sarif_case()
    mapping['bindings'][0]['rule_index'] = None
    report['runs'][0]['results'][0][field] = bad
    with pytest.raises(EvidenceImportError):
        resolved(report, mapping, targets)


def test_rule_id_without_an_index_must_not_choose_between_duplicate_descriptors():
    report, mapping, targets = sarif_case()
    run = report['runs'][0]
    del run['results'][0]['ruleIndex']
    run['tool']['driver']['rules'][1]['id'] = 'RULE1'
    mapping['bindings'][0]['rule_index'] = None
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'ambiguous_sarif_rule_reference'
    # A precise source index identifies the descriptor without guessing.
    run['results'][0]['ruleIndex'] = 0
    candidate, = resolved(report, mapping, targets).data['candidates']
    assert candidate['sarif']['rule'] is None


@pytest.mark.parametrize('explicit', [True, False])
def test_linked_failed_invocation_is_not_hidden_by_omitting_its_import(explicit):
    report, mapping, targets = sarif_case('pass', level='none')
    report['runs'][0]['invocations'][0]['executionSuccessful'] = False
    mapping['bindings'][0]['invocation_index'] = None
    if explicit:
        report['runs'][0]['results'][0]['provenance'] = {'invocationIndex': 0}
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'sarif_failed_invocation_cannot_pass'


def test_mapping_cannot_substitute_another_successful_invocation():
    report, mapping, targets = sarif_case('pass', level='none')
    run = report['runs'][0]
    run['invocations'] = [{'executionSuccessful': False}, {'executionSuccessful': True}]
    run['results'][0]['provenance'] = {'invocationIndex': 0}
    mapping['bindings'][0]['invocation_index'] = 1
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'sarif_invocation_binding_mismatch'


def test_explicit_unknown_invocation_keeps_unknown_status_without_inferred_attachment():
    report, mapping, targets = sarif_case()
    run = report['runs'][0]
    run['results'][0]['provenance'] = {'invocationIndex': -1}
    mapping['bindings'][0]['invocation_index'] = None
    candidate, = resolved(report, mapping, targets).data['candidates']
    assert candidate['sarif']['invocation'] is None
    assert candidate['result'] == 'failed'


@pytest.mark.parametrize('index', [False, -2, 0.0, 1, '0'])
def test_invalid_original_invocation_references_are_not_coerced(index):
    report, mapping, targets = sarif_case()
    report['runs'][0]['results'][0]['provenance'] = {'invocationIndex': index}
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.pointer.startswith('/runs/0/results/0/provenance')


def test_invocation_reference_requires_an_invocations_array():
    report, mapping, targets = sarif_case()
    del report['runs'][0]['invocations']
    report['runs'][0]['results'][0]['provenance'] = {'invocationIndex': -1}
    mapping['bindings'][0]['invocation_index'] = None
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'invalid_sarif_reference'


@pytest.mark.parametrize('bad', [[], '', None, False])
def test_falsy_external_reference_values_are_not_treated_as_absent(bad):
    report, mapping, targets = sarif_case()
    report['runs'][0]['externalPropertyFileReferences'] = bad
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'invalid_sarif_external_properties'


@pytest.mark.parametrize('field,bad', [
    ('location', {'uri': False}), ('location', {'index': 1}),
    ('location', {'index': 0.0}), ('location', {'uriBaseId': None}),
    ('contents', {'text': []}), ('contents', {'binary': None}),
    ('hashes', {'sha-256': 10}), ('length', -2), ('length', 0.0)])
def test_selected_artifact_metadata_and_references_have_exact_types(field, bad):
    report, mapping, targets = sarif_case()
    report['runs'][0]['artifacts'][0][field] = bad
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.pointer.startswith('/runs/0/artifacts/0')


@pytest.mark.parametrize('base', [False, True])
def test_selected_artifact_location_cannot_disagree_with_its_indexed_target(base):
    report, mapping, targets = sarif_case()
    report['runs'][0]['artifacts'].append({'location': {'uri': 'different-file'}})
    location = {'uri': 'different-file', 'index': 1}
    if base: location['uriBaseId'] = 'source'
    else: location['uri'] = 'other-file'
    report['runs'][0]['artifacts'][0]['location'] = location
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'sarif_artifact_binding_mismatch'


def test_matching_artifact_location_and_index_are_retained_as_data_without_uri_access():
    report, mapping, targets = sarif_case()
    report['runs'][0]['artifacts'][0]['location'].update(index=0, uriBaseId='SRCROOT')
    with no_write_attempts():
        candidate, = resolved(report, mapping, targets).data['candidates']
    assert candidate['sarif']['artifacts'][0]['value'] == report['runs'][0]['artifacts'][0]


@pytest.mark.parametrize('field', ['version', 'semanticVersion'])
def test_selected_driver_metadata_cannot_embed_other_structures_as_version(field):
    report, mapping, targets = sarif_case()
    report['runs'][0]['tool']['driver'][field] = {'result': 'passed'}
    with pytest.raises(EvidenceImportError) as caught:
        resolved(report, mapping, targets)
    assert caught.value.reason == 'invalid_sarif_driver_metadata'


def test_unselected_foreign_data_remains_unmapped_and_never_changes_a_valid_candidate():
    report, mapping, targets = sarif_case()
    report['runs'][0]['results'][1] = {'message': {}, 'kind': 'pass',
        'baselineState': 'not-a-state', 'properties': {'specroad': {'result': 'passed'}}}
    report['runs'][0]['tool']['driver']['rules'][1] = {'id': 5, 'result': 'passed'}
    report['runs'][0]['artifacts'].append({'location': {'uri': 'file:///secret'}, 'result': 'passed'})
    report['runs'][0]['properties'] = {'producer': 'forged', 'results': [{'kind': 'pass'}]}
    with no_write_attempts():
        data = resolved(report, mapping, targets).data
    assert data['unmapped_results'] == ['/runs/0/results/1']
    assert data['candidate_count'] == 1 and data['candidates'][0]['result'] == 'failed'
    assert len(data['candidates'][0]['sarif']['artifacts']) == 1
    assert data['import_policy_applied'] is False


@pytest.mark.parametrize('failure', ['rule', 'invocation', 'artifact', 'baseline', 'suppression'])
def test_late_mapping_error_never_publishes_earlier_valid_measurements(tmp_path, failure):
    report, mapping, targets = sarif_case('pass', level='none')
    root = make_project(tmp_path, targets[0].data)
    before = inventory(root)
    run = report['runs'][0]
    run['results'][1] = json.loads(json.dumps(run['results'][0]))
    mapping['exchange']['results'].append(dict(mapping['exchange']['results'][0]))
    mapping['bindings'].append({**mapping['bindings'][0], 'result_index': 1, 'exchange_result_index': 1})
    row = mapping['bindings'][1]
    if failure == 'rule': run['results'][1]['ruleId'] = 'OTHER'
    elif failure == 'invocation': run['results'][1]['provenance'] = {'invocationIndex': 3}
    elif failure == 'artifact':
        run['artifacts'].append({'location': {'uri': False}})
        row['artifact_indices'] = [1]
    elif failure == 'baseline': run['results'][1]['baselineState'] = 'absent'
    else: run['results'][1]['suppressions'] = [{'kind': 'external'}]
    with no_write_attempts(), pytest.raises(EvidenceImportError):
        resolved(report, mapping, targets)
    assert inventory(root) == before


@pytest.mark.parametrize('portable', [False, True])
def test_new_rejection_contract_is_identical_in_core_and_pyz(tmp_path, portable):
    report, mapping, targets = sarif_case('pass', level='none')
    report['runs'][0]['results'][0]['baselineState'] = 'absent'
    from hashlib import sha256
    mapping['source_sha256'] = sha256(artifact_bytes(report)).hexdigest()
    body = f"""
import json
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import VerificationContract, VerificationTest, SarifDocument, SarifMapping, map_sarif_candidates, EvidenceImportError
targets=[DomainArtifact({targets[0].source_bytes!r}), VerificationContract({targets[1].source_bytes!r}),
         VerificationTest({targets[2].source_bytes!r})]
try:
    map_sarif_candidates(SarifDocument({artifact_bytes(report)!r}), SarifMapping({artifact_bytes(mapping)!r}), targets=targets)
except EvidenceImportError as error:
    print(json.dumps(error.diagnostic(), sort_keys=True))
else:
    raise AssertionError('Baseline-only result accepted')
"""
    if portable:
        _, archive = build_distribution(tmp_path / 'dist')
        process = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(archive)) + ');\n' + body], tmp_path, capture=True)
    else:
        process = run_core(body, tmp_path, capture=True)
    assert process.returncode == 0, process.stderr
    diagnostic = json.loads(process.stdout)
    assert diagnostic['reason'] == 'sarif_baseline_only_result'
    assert diagnostic['code'] == 'SRV091' and diagnostic['exit_code'] == 3
