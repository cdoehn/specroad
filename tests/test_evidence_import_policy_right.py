"""Complete original binding and explicit policy without publishing Evidence."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.model.canonical import canonical_json_sha256
from specroad.verification import (EvidenceExchange, EvidenceImportError, SarifDocument,
    SarifMapping, prepare_generic_import, prepare_sarif_import, map_generic_candidates,
    map_sarif_candidates)
from support.artifacts import artifact_bytes
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, make_project, no_write_attempts
from support.records import ref
from test_evidence_exchange import exchange_case
from test_evidence_import_policy import POLICIES, assert_passive
from test_sarif_import import sarif_case


def import_right_case():
    value, targets = exchange_case()
    value['results'].append({**value['results'][0], 'check_id': 'second'})
    report, mapping, _ = sarif_case()
    report['runs'][0]['results'] = [deepcopy(report['runs'][0]['results'][0]) for _ in range(2)]
    mapping['exchange'] = value
    mapping['bindings'].append({**mapping['bindings'][0], 'exchange_result_index': 1, 'result_index': 1})
    return value, report, mapping, targets


def prepare(format_name, value, report, mapping, targets, policy):
    if format_name == 'generic':
        return prepare_generic_import(artifact_bytes(value), targets=targets, policy=policy)
    mapping = {**mapping, 'exchange': value, 'source_sha256': sha256(artifact_bytes(report)).hexdigest()}
    return prepare_sarif_import(artifact_bytes(report), artifact_bytes(mapping),
                                targets=targets, policy=policy)


def accounted(value):
    accepted = [c['source_pointer'] for c in value['candidates']]
    rejected, withheld = value['rejected_occurrences'], value['withheld_occurrences']
    assert len(accepted) == len(set(accepted))
    assert not (set(accepted) & set(rejected) or set(accepted) & set(withheld)
                or set(rejected) & set(withheld))
    assert set(accepted + rejected + withheld) == set(value['occurrences'])
    assert set(rejected) == {p for d in value['diagnostics'] for p in d['occurrences']}
    assert value['candidate_count'] == len(accepted)
    assert_passive(value)
    for flag in ('external_run_verified', 'configuration_verified', 'attachments_verified',
                 'contract_slots_verified'):
        assert value[flag] is False


@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('typed', [False, True])
@pytest.mark.parametrize('outcome', ['passed', 'failed', 'skipped', 'incomplete', 'custom-outcome'])
def test_generic_original_and_inline_mapping_bind_every_explicit_observation(policy, typed, outcome):
    value, targets = exchange_case()
    value['results'][0]['result'] = outcome
    raw = json.dumps(value, indent=3).encode() + b'\r\n'
    doc = EvidenceExchange(raw)
    expected = map_generic_candidates(doc, targets=targets).data['candidates'][0]
    prepared = prepare_generic_import(doc if typed else raw, targets=targets, policy=policy)
    data = prepared.data
    candidate, = data['candidates']
    assert {k: v for k, v in candidate.items() if k not in ('source_pointer', 'provenance_sha256')} == expected
    assert candidate['source_pointer'] == '/results/0' and candidate['result'] == outcome
    assert prepared.original_files == {'source': raw}
    provenance = data['provenance']
    assert provenance['source'] == {'sha256': sha256(raw).hexdigest(), 'size': len(raw)}
    assert provenance['mapping'] == {
        **provenance['source'], 'canonical_sha256': canonical_json_sha256(value),
        'format_version': 'specroad-evidence-exchange-v1', 'source_role': 'source'}
    assert provenance['tool'] == value['tool']
    assert provenance['parser_profile'] == 'specroad-evidence-exchange-v1'
    assert candidate['provenance_sha256'] == data['provenance_sha256'] == canonical_json_sha256(provenance)
    assert prepared.sha256 == canonical_json_sha256(data)
    assert data['decision'] == 'prepared' and data['diagnostics'] == []
    accounted(data)


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('failure', [
    'missing-time', 'bad-time', 'missing-result', 'unknown-subject', 'duplicate-subject',
    'unknown-attachment', 'duplicate-attachment', 'unknown-target', 'unknown-test',
    'blank-result', 'extra-field', 'not-object'])
def test_invalid_required_records_are_explained_after_valid_records(format_name, policy, failure):
    value, report, mapping, targets = import_right_case()
    broken = value['results'][1]
    if failure == 'missing-time': del broken['produced_at']
    elif failure == 'bad-time': broken['produced_at'] = 'not UTC'
    elif failure == 'missing-result': del broken['result']
    elif failure == 'unknown-subject': broken['subject_ids'] = [ref('REQ', '2')]
    elif failure == 'duplicate-subject': broken['subject_ids'] = [broken['subject_ids'][0]] * 2
    elif failure == 'unknown-attachment': broken['attachment_paths'] = ['attachments/missing']
    elif failure == 'duplicate-attachment': broken['attachment_paths'] = broken['attachment_paths'] * 2
    elif failure == 'unknown-target': broken['target_id'] = ref('VER', '2')
    elif failure == 'unknown-test': broken['test_id'] = ref('TEST', '2')
    elif failure == 'blank-result': broken['result'] = ' \t'
    elif failure == 'extra-field': broken['write_authorized'] = True
    else: value['results'][1] = None
    data = prepare(format_name, value, report, mapping, targets, policy).data
    assert data['candidate_count'] == (0 if policy == 'abort_import' else 1)
    assert data['decision'] == ('aborted' if policy == 'abort_import' else 'prepared')
    diagnostic, = data['diagnostics']
    assert diagnostic['result_indexes'] == [1] and diagnostic['code'] == 'SRV091'
    assert diagnostic['pointer'].startswith(('/results/1', '/exchange/results/1'))
    assert diagnostic['input_role'] == ('source' if format_name == 'generic' else 'mapping')
    assert len(data['rejected_occurrences']) == 1
    if data['candidates']: assert data['candidates'][0]['result_index'] == 0
    accounted(data)


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('unused', [False, True])
def test_subject_binding_failure_affects_only_dependents_but_never_disappears(format_name, policy, unused):
    value, report, mapping, targets = import_right_case()
    value['results'][0]['subject_ids'] = [targets[1].data['id']]
    if unused: value['results'][1]['subject_ids'] = [targets[1].data['id']]
    value['subjects'][0]['artifact_sha256'] = 'a' * 64
    data = prepare(format_name, value, report, mapping, targets, policy).data
    diagnostic, = data['diagnostics']
    assert diagnostic['reason'] == 'import_subject_binding_mismatch'
    assert diagnostic['result_indexes'] == ([] if unused else [1])
    assert data['candidate_count'] == (0 if policy == 'abort_import' else (2 if unused else 1))
    accounted(data)


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('invalid_time', [False, True])
def test_conflicting_slot_results_cannot_keep_only_the_favorable_one(format_name, policy, invalid_time):
    value, report, mapping, targets = import_right_case()
    value['results'][1].update(check_id=value['results'][0]['check_id'], result='passed',
                               subject_ids=list(reversed(value['results'][0]['subject_ids'])))
    report['runs'][0]['results'][1].update(kind='pass', level='none')
    if invalid_time: del value['results'][1]['produced_at']
    data = prepare(format_name, value, report, mapping, targets, policy).data
    assert data['candidates'] == [] and len(data['rejected_occurrences']) == 2
    conflicts = [d for d in data['diagnostics'] if d['reason'] == 'conflicting_import_results']
    assert len(conflicts) == 1 and conflicts[0]['result_indexes'] == [0, 1]
    accounted(data)
    value['results'][1]['subject_ids'].append(value['results'][1]['subject_ids'][0])
    duplicate = prepare(format_name, value, report, mapping, targets, policy).data
    assert duplicate['candidates'] == [] and len(duplicate['rejected_occurrences']) == 2
    assert any(d['reason'] == 'conflicting_import_results' for d in duplicate['diagnostics'])
    accounted(duplicate)


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('policy', POLICIES)
def test_repeated_equal_observations_are_retained_for_later_idempotency_not_merged(format_name, policy):
    value, report, mapping, targets = import_right_case()
    value['results'][1] = deepcopy(value['results'][0])
    data = prepare(format_name, value, report, mapping, targets, policy).data
    assert data['candidate_count'] == 2 and data['diagnostics'] == []
    accounted(data)


@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('typed', [False, True])
def test_sarif_retains_exact_originals_and_selected_objects_at_original_positions(policy, typed):
    value, report, mapping, targets = import_right_case()
    mapping['source_sha256'] = sha256(artifact_bytes(report)).hexdigest()
    mapping['bindings'].reverse()
    raw, rules = artifact_bytes(report), json.dumps(mapping, indent=3).encode()
    doc, chosen = SarifDocument(raw), SarifMapping(rules)
    expected = map_sarif_candidates(doc, chosen, targets=targets).data['candidates']
    prepared = prepare_sarif_import(doc if typed else raw, chosen if typed else rules,
                                    targets=targets, policy=policy)
    data = prepared.data
    assert [{k: v for k, v in c.items() if k not in ('source_pointer', 'provenance_sha256')}
            for c in data['candidates']] == expected
    assert [c['result_index'] for c in data['candidates']] == [1, 0]
    assert prepared.original_files == {'source': raw, 'mapping': rules}
    assert data['provenance']['mapping'] == {
        'sha256': sha256(rules).hexdigest(), 'size': len(rules),
        'canonical_sha256': canonical_json_sha256(mapping), 'format_version': 'sarif-mapping-v1'}
    assert data['provenance']['source']['sha256'] == mapping['source_sha256']
    assert data['provenance']['parser_profile'] == 'sarif-inline-2.1.0-v1'
    assert data['provenance']['tool'] == value['tool']
    accounted(data)


@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('failure,reason', [
    ('message', 'invalid_sarif_message'), ('kind', 'unsupported_sarif_outcome_mapping'),
    ('level', 'invalid_sarif_result_level'), ('baseline', 'sarif_baseline_only_result'),
    ('rule', 'sarif_rule_binding_mismatch'), ('rule-float', 'sarif_rule_binding_mismatch'),
    ('selector', 'sarif_index_out_of_range'),
    ('artifact-duplicate', 'duplicate_evidence_import_binding'),
    ('suppression', 'sarif_suppressed_pass_unsupported'),
    ('invocation', 'sarif_failed_invocation_cannot_pass')])
def test_selected_sarif_errors_and_unmapped_results_have_separate_diagnostics(policy, failure, reason):
    value, report, mapping, targets = import_right_case()
    bad = report['runs'][0]['results'][1]
    if failure == 'message': bad['message'] = {}
    elif failure == 'kind': bad['kind'] = 'review'
    elif failure == 'level': bad['level'] = []
    elif failure == 'baseline': bad['baselineState'] = 'absent'
    elif failure == 'rule': bad['ruleId'] = 'OTHER'
    elif failure == 'rule-float': bad['ruleIndex'] = 0.0
    elif failure == 'selector': mapping['bindings'][1]['artifact_indices'] = [500]
    elif failure == 'artifact-duplicate': mapping['bindings'][1]['artifact_indices'] = [0, 0]
    else:
        value['results'][1]['result'] = 'passed'
        bad.update(kind='pass', level='none')
        if failure == 'suppression': bad['suppressions'] = [{'kind': 'external'}]
        else: report['runs'][0]['invocations'][0]['executionSuccessful'] = False
    report['runs'][0]['results'].append({'message': {'text': 'unselected'}})
    data = prepare('sarif', value, report, mapping, targets, policy).data
    assert {d['reason'] for d in data['diagnostics']} == {reason, 'unmapped_sarif_result'}
    assert data['rejected_occurrences'] == ['/runs/0/results/1', '/runs/0/results/2']
    assert data['candidate_count'] == (0 if policy == 'abort_import' else 1)
    accounted(data)


@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('kind', ['source', 'exchange', 'malformed-duplicate'])
def test_ambiguous_sarif_mapping_never_selects_a_first_or_last_row(policy, kind):
    value, report, mapping, targets = import_right_case()
    if kind == 'exchange': mapping['bindings'][1]['exchange_result_index'] = 0
    else:
        row = {**mapping['bindings'][0], 'exchange_result_index': 1}
        if kind == 'malformed-duplicate': del row['rule_index']
        mapping['bindings'][1] = row
    data = prepare('sarif', value, report, mapping, targets, policy).data
    assert data['candidates'] == []
    assert any(d['reason'].startswith('ambiguous_sarif_') for d in data['diagnostics'])
    assert len(data['rejected_occurrences']) == 2
    accounted(data)


@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('bad', [None, {}, '0', True, 0.0, -1, 99])
def test_malformed_sarif_selectors_are_diagnosed_without_renumbering_valid_neighbors(policy, bad):
    value, report, mapping, targets = import_right_case()
    mapping['bindings'][1]['result_index'] = bad
    data = prepare('sarif', value, report, mapping, targets, policy).data
    assert data['candidate_count'] == (0 if policy == 'abort_import' else 1)
    assert any(d.get('binding_indexes') == [1] for d in data['diagnostics'])
    assert any(d['reason'] == 'unmapped_sarif_result' for d in data['diagnostics'])
    accounted(data)


@pytest.mark.parametrize('policy', POLICIES)
def test_unbound_exchange_records_are_explicit_even_when_no_source_occurrence_is_assigned(policy):
    value, report, mapping, targets = import_right_case()
    mapping['bindings'] = mapping['bindings'][:1]
    data = prepare('sarif', value, report, mapping, targets, policy).data
    missing = [d for d in data['diagnostics'] if d['reason'] == 'sarif_exchange_mapping_incomplete']
    assert len(missing) == 1 and missing[0]['result_indexes'] == [1]
    assert missing[0]['occurrences'] == [] and missing[0]['pointer'] == '/exchange/results/1'
    assert data['candidate_count'] == (0 if policy == 'abort_import' else 1)
    accounted(data)


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('failure', ['tool', 'run', 'subjects', 'attachments', 'results', 'targets'])
def test_unsafe_global_inputs_remain_fatal_under_both_policies(format_name, policy, failure):
    value, report, mapping, targets = import_right_case()
    if failure == 'tool': del value['tool']['version']
    elif failure == 'run': value['run']['run_id'] = 'not-namespaced'
    elif failure == 'subjects': value['subjects'].append(value['subjects'][0])
    elif failure == 'attachments': value['attachments'][0]['path'] = '../secret'
    elif failure == 'results': value['results'] = {}
    else: targets = [{}]
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        prepare(format_name, value, report, mapping, targets, policy)
    assert caught.value.diagnostic()['code'] == 'SRV091'
    if failure == 'targets': assert caught.value.pointer.startswith('/targets')
    elif format_name == 'sarif': assert caught.value.pointer.startswith('/exchange')


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('raw', [None, bytearray(b'{}'), {}, b'[]', b'{"x":1,"x":2}',
                                b'{"x":NaN}', b'{} trailing'])
def test_inputs_are_exact_owned_bytes_not_decoded_or_repaired_documents(format_name, raw):
    value, report, mapping, targets = import_right_case()
    with pytest.raises(EvidenceImportError):
        if format_name == 'generic':
            prepare_generic_import(raw, targets=targets, policy=POLICIES[1])
        else:
            prepare_sarif_import(raw, artifact_bytes(mapping), targets=targets, policy=POLICIES[1])


@pytest.mark.parametrize('policy', POLICIES)
def test_sarif_hash_mismatch_is_global_even_with_no_selected_results(policy):
    _, report, mapping, targets = import_right_case()
    mapping['bindings'] = []
    mapping['exchange']['results'] = []
    mapping['source_sha256'] = 'f' * 64
    with pytest.raises(EvidenceImportError) as caught:
        prepare_sarif_import(artifact_bytes(report), artifact_bytes(mapping), targets=targets, policy=policy)
    assert caught.value.reason == 'sarif_source_binding_mismatch'


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('bad', [None, True, '', 'skip', ['abort_import'], {}])
def test_each_format_requires_exactly_one_explicit_policy(format_name, bad):
    with pytest.raises(EvidenceImportError) as caught:
        prepare(format_name, *import_right_case(), bad)
    assert caught.value.reason == 'explicit_import_policy_required'


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
def test_whitespace_keeps_mapping_semantics_but_changes_raw_provenance(format_name):
    value, report, mapping, targets = import_right_case()
    first = prepare(format_name, value, report, mapping, targets, POLICIES[1])
    if format_name == 'generic':
        second = prepare_generic_import(first.original_files['source'] + b' ', targets=targets, policy=POLICIES[1])
    else:
        second = prepare_sarif_import(first.original_files['source'], first.original_files['mapping'] + b' ',
                                      targets=targets, policy=POLICIES[1])
    assert first.data['provenance']['mapping']['canonical_sha256'] == second.data['provenance']['mapping']['canonical_sha256']
    assert first.data['provenance_sha256'] != second.data['provenance_sha256']
    assert first.data['analysis_sha256'] == second.data['analysis_sha256']


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
def test_caches_and_returned_views_cannot_rewrite_preparation_inputs(format_name):
    value, report, mapping, targets = import_right_case()
    expected = prepare(format_name, value, report, mapping, targets, POLICIES[1])
    if format_name == 'generic':
        doc = EvidenceExchange(expected.original_files['source'])
        object.__setattr__(doc, '_encoded', b'{}')
        actual = prepare_generic_import(doc, targets=targets, policy=POLICIES[1])
    else:
        doc, chosen = SarifDocument(expected.original_files['source']), SarifMapping(expected.original_files['mapping'])
        for item in (doc, chosen, *targets): object.__setattr__(item, '_encoded', b'{}')
        actual = prepare_sarif_import(doc, chosen, targets=targets, policy=POLICIES[1])
    before = actual.data
    actual.data['candidates'].clear()
    actual.original_files.clear()
    assert actual.data == before == expected.data and actual.original_files == expected.original_files
    with pytest.raises(TypeError): bool(actual)
    with pytest.raises(FrozenInstanceError): actual._originals = ()


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('policy', POLICIES)
def test_both_policies_preserve_project_bytes_modes_and_do_not_read_the_host(tmp_path, monkeypatch, format_name, policy):
    value, report, mapping, targets = import_right_case()
    del value['results'][1]['produced_at']
    make_project(tmp_path, targets[0].data)
    before = inventory(tmp_path)
    monkeypatch.chdir(tmp_path)
    def forbid(*args, **kwargs): raise AssertionError('Host state is not an import input')
    with no_write_attempts(), monkeypatch.context() as patch:
        for name in ('builtins.open', 'io.open', 'time.time', 'os.urandom', 'os.getenv'):
            patch.setattr(name, forbid)
        prepared = prepare(format_name, value, report, mapping, targets, policy)
    assert inventory(tmp_path) == before
    accounted(prepared.data)


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('policy', POLICIES)
def test_repeated_metadata_is_bounded_before_accumulating_a_large_output(format_name, policy):
    value, report, mapping, targets = import_right_case()
    value['environment'] = {'text': 'x' * 40000}
    value['results'] = [value['results'][0]] * 500
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        prepare(format_name, value, report, mapping, targets, policy)
    assert caught.value.reason == 'evidence_import_candidate_limit'


@pytest.mark.parametrize('policy', POLICIES)
def test_sarif_expanded_selected_artifacts_have_their_own_aggregate_budget(policy):
    value, report, mapping, targets = import_right_case()
    value['results'] = [value['results'][0]] * 300
    report['runs'][0]['results'] = [report['runs'][0]['results'][0]] * 300
    report['runs'][0]['artifacts'][0]['contents']['text'] = 'x' * 60000
    mapping['bindings'] = [{**mapping['bindings'][0], 'exchange_result_index': n, 'result_index': n}
                           for n in range(300)]
    with pytest.raises(EvidenceImportError) as caught:
        prepare('sarif', value, report, mapping, targets, policy)
    assert caught.value.reason == 'evidence_import_candidate_limit'


def test_many_unmapped_sarif_occurrences_are_reported_in_source_order():
    value, report, mapping, targets = import_right_case()
    value['results'] = []
    mapping['bindings'] = []
    report['runs'][0]['results'] = [{'message': {'text': 'unselected'}}] * 1000
    data = prepare('sarif', value, report, mapping, targets, POLICIES[1]).data
    assert data['candidate_count'] == 0 and len(data['diagnostics']) == 1000
    assert [d['pointer'] for d in data['diagnostics']] == [f'/runs/0/results/{n}' for n in range(1000)]
    accounted(data)


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('policy', POLICIES)
def test_empty_reports_never_invent_a_passing_measurement(format_name, policy):
    value, report, mapping, targets = import_right_case()
    value['results'], report['runs'][0]['results'], mapping['bindings'] = [], [], []
    data = prepare(format_name, value, report, mapping, targets, policy).data
    assert data['decision'] == 'prepared' and data['candidate_count'] == 0
    assert data['diagnostics'] == [] and data['occurrences'] == []
    accounted(data)


@pytest.mark.parametrize('format_name', ['generic', 'sarif'])
@pytest.mark.parametrize('policy', POLICIES)
def test_preparation_and_originals_agree_in_isolated_core_and_pyz(tmp_path, format_name, policy):
    value, report, mapping, targets = import_right_case()
    del value['results'][1]['produced_at']
    expected = prepare(format_name, value, report, mapping, targets, policy)
    body = f"""
import json
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import VerificationContract, VerificationTest, prepare_generic_import, prepare_sarif_import
targets=[DomainArtifact({targets[0].source_bytes!r}),
         VerificationContract({targets[1].source_bytes!r}), VerificationTest({targets[2].source_bytes!r})]
raw={expected.original_files['source']!r}
"""
    body += (f"v=prepare_generic_import(raw,targets=targets,policy={policy!r})\n" if format_name == 'generic'
             else f"v=prepare_sarif_import(raw,{expected.original_files['mapping']!r},targets=targets,policy={policy!r})\n")
    body += "print(json.dumps({'data':v.data,'originals':{k:b.hex() for k,b in v.original_files.items()}}))"
    _, archive = build_distribution(tmp_path / 'dist')
    outputs = [run_core(body, tmp_path, capture=True),
               run_python(['-I', '-S', '-B', '-c', f'import sys;sys.path.insert(0,{str(archive)!r});\n'+body],
                          tmp_path, capture=True)]
    for output in outputs:
        assert output.returncode == 0, output.stderr
        assert json.loads(output.stdout) == {'data': expected.data,
            'originals': {k: raw.hex() for k, raw in expected.original_files.items()}}
