"""Untrusted import declarations cannot change native resources or gain authority."""
from hashlib import sha256
import json

import pytest

from specroad.model.canonical import canonical_json_sha256
from specroad.storage.domain_artifact import DomainArtifact
from specroad.verification import (EvidenceExchange, EvidenceImportError, SarifDocument,
    SarifMapping, map_generic_candidates, map_sarif_candidates)
from support.artifacts import artifact_bytes
from support.read_only import inventory, make_project, no_write_attempts
from support.records import ref
from test_evidence_exchange import exchange_case
from test_sarif_import import sarif_case


@pytest.mark.parametrize('path', [
    ('producer', 'producer_id'), ('tool', 'name'), ('tool', 'version'),
    ('run', 'subject_id'), ('results', 0, 'result')])
@pytest.mark.parametrize('blank', [' ', '\t\n', '\u2003'])
def test_whitespace_alone_does_not_supply_required_measurement_declarations(path, blank):
    value, _ = exchange_case()
    parent = value
    for key in path[:-1]: parent = parent[key]
    parent[path[-1]] = blank
    with pytest.raises(EvidenceImportError) as caught:
        EvidenceExchange(artifact_bytes(value))
    assert caught.value.reason == 'schema_pattern'
    assert caught.value.pointer == '/' + '/'.join(map(str, path))


def test_nonblank_opaque_identifiers_and_unknown_results_are_retained_without_normalization():
    value, targets = exchange_case()
    value['producer']['producer_id'] = ' ci Café '
    value['run']['subject_id'] = ' product \u00e9 '
    value['run']['run_id'] = 'namespace: opaque/identifier'
    value['results'][0]['result'] = ' custom-result '
    result = map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=targets).data
    candidate = result['candidates'][0]
    assert candidate['producer'] == value['producer']
    assert candidate['run_context']['run_id'] == value['run']['run_id']
    assert candidate['run_context']['subject_id'] == value['run']['subject_id']
    assert candidate['result'] == ' custom-result '
    assert result['full_verification_evaluated'] is False


def test_untrusted_environment_keys_cannot_override_measurement_or_native_bindings():
    value, targets = exchange_case()
    value['environment'] = {'result': 'passed', 'subjects': [], 'write_authorized': True,
                            'configuration_verified': True, 'run_id': 'forged:run'}
    result = map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=targets).data
    candidate = result['candidates'][0]
    assert candidate['environment'] == value['environment']
    assert candidate['result'] == 'failed' and candidate['subjects'] == value['subjects']
    assert candidate['run_context']['run_id'] == value['run']['run_id']
    assert result['write_authorized'] is False and result['configuration_verified'] is False


@pytest.mark.parametrize('failure', ['schema', 'unknown_subject', 'stale_subject', 'unknown_target'])
def test_generic_failure_after_valid_measurements_keeps_real_project_bytes_and_modes(tmp_path, failure):
    value, targets = exchange_case()
    root = make_project(tmp_path, targets[0].data)
    before = inventory(root)
    value['results'].append({**value['results'][0]})
    if failure == 'schema': value['results'][1]['produced_at'] = None
    elif failure == 'unknown_subject': value['results'][1]['subject_ids'] = [ref('REQ', '2')]
    elif failure == 'stale_subject': value['subjects'][0]['artifact_sha256'] = 'e' * 64
    else: value['results'][1]['target_id'] = ref('VER', '2')
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=targets)
    assert caught.value.diagnostic()['code'] == 'SRV091'
    assert inventory(root) == before
    assert [t.source_bytes for t in targets] == [t.source_bytes for t in exchange_case()[1]]


@pytest.mark.parametrize('kind', ['count', 'bytes'])
def test_target_budgets_are_enforced_before_expanding_or_reparsing_unbounded_inputs(kind):
    value, targets = exchange_case()
    if kind == 'count':
        targets = [targets[0]] * 10001
    else:
        object.__setattr__(targets[0], 'source_bytes', b' ' * (16 * 1024 * 1024 + 1))
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=targets)
    assert caught.value.reason == 'evidence_import_target_limit'
    assert caught.value.pointer.startswith('/targets')


def test_aggregate_target_byte_budget_counts_all_distinct_native_snapshots():
    value, targets = exchange_case()
    # Native snapshots may be larger than the small Exchange referencing them.
    # Whitespace is valid JSON and does not change the subject content/hash.
    for target in targets:
        raw = target.source_bytes
        object.__setattr__(target, 'source_bytes', raw + b' ' * (6 * 1024 * 1024 - len(raw)))
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=targets)
    assert caught.value.reason == 'evidence_import_target_limit'
    assert caught.value.pointer == '/targets/2'


@pytest.mark.parametrize('change,expected', [
    ('blank_run', '/exchange/run/subject_id'), ('bad_attachment', '/exchange/attachments/0/path'),
    ('missing_subject', '/exchange/results/0/subject_ids'),
    ('stale_subject', '/exchange/subjects/0'),
    ('untyped_target', '/targets/0')])
def test_embedded_exchange_diagnostics_point_to_the_actual_mapping_or_target_input(change, expected):
    report, mapping, targets = sarif_case()
    value = mapping['exchange']
    if change == 'blank_run': value['run']['subject_id'] = ' '
    elif change == 'bad_attachment': value['attachments'][0]['path'] = '../secret'
    elif change == 'missing_subject': value['results'][0]['subject_ids'] = [ref('REQ', '2')]
    elif change == 'stale_subject': value['subjects'][0]['artifact_sha256'] = 'a' * 64
    else: targets = [{}]
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        map_sarif_candidates(SarifDocument(artifact_bytes(report)),
                             SarifMapping(artifact_bytes(mapping)), targets=targets)
    assert caught.value.pointer == expected


def test_schema_error_diagnostic_does_not_disclose_producer_or_environment_contents():
    value, _ = exchange_case()
    value['producer']['producer_id'] = {'secret': 'synthetic-token'}
    value['environment']['secret'] = 'synthetic-token'
    with pytest.raises(EvidenceImportError) as caught:
        EvidenceExchange(artifact_bytes(value))
    encoded = json.dumps(caught.value.diagnostic())
    assert 'synthetic-token' not in encoded
    assert caught.value.pointer == '/producer/producer_id'


def test_raw_and_canonical_bindings_remain_distinct_for_whitespace_only_input_changes():
    value, targets = exchange_case()
    a = EvidenceExchange(artifact_bytes(value))
    b = EvidenceExchange(json.dumps(value, ensure_ascii=True, indent=3).encode())
    first = map_generic_candidates(a, targets=targets).data
    second = map_generic_candidates(b, targets=targets).data
    assert first['source']['sha256'] == sha256(a.source_bytes).hexdigest()
    assert second['source']['sha256'] != first['source']['sha256']
    assert first['exchange_sha256'] == second['exchange_sha256'] == canonical_json_sha256(value)
    assert first['candidates'] == second['candidates']


def test_untyped_target_attribute_hooks_are_never_invoked():
    value, _ = exchange_case()
    class ForeignTarget:
        def __getattr__(self, name):
            raise AssertionError('Unexpected foreign object protocol')
    with no_write_attempts(), pytest.raises(EvidenceImportError) as caught:
        map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=[ForeignTarget()])
    assert caught.value.reason == 'typed_verification_subject_required'


def test_forged_native_subject_source_is_revalidated_instead_of_trusting_cached_fields():
    value, targets = exchange_case()
    original = targets[0]
    changed = {**original.data, 'statement': 'Semantically changed'}
    actual = DomainArtifact(artifact_bytes(changed))
    assert actual.id == original.id
    object.__setattr__(original, 'source_bytes', actual.source_bytes)
    with pytest.raises(EvidenceImportError) as caught:
        map_generic_candidates(EvidenceExchange(artifact_bytes(value)), targets=targets)
    assert caught.value.reason == 'import_subject_binding_mismatch'
