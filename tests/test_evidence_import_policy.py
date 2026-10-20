"""Original-bound JUnit preparation and explicit all-or-diagnosed-subset policy."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad import __version__
from specroad.model.canonical import canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.verification import (EvidenceImportError, EvidenceImportPreparation,
    JUnitDocument, JUnitMapping, JUnitMappingRules, JUnitMappingError,
    JUnitExternalIdentifiers, prepare_junit_import, analyze_junit_candidates)
from support.artifacts import artifact_bytes
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, make_project, no_write_attempts
from support.records import ref
from test_junit_mapping import document, mapping, target
from test_junit_mapping_right import report, rules, row, external


POLICIES = ('abort_import', 'skip_invalid_with_diagnostic')


def import_case():
    return document(), mapping(), {
        'targets': [target()], 'policy': 'abort_import',
        'tool': {'name': 'explicit-reporter', 'version': '9.0'}}


def bound_hash(raw):
    return {'sha256': sha256(raw).hexdigest(), 'size': len(raw)}


def assert_passive(value):
    assert value['import_policy_applied'] is True
    for name in ('test_code_executed', 'evidence_created', 'project_targets_verified',
                 'full_verification_evaluated', 'write_authorized', 'approval_granted',
                 'run_context_bound', 'producer_tool_verified'):
        assert value[name] is False


def assert_accounted(value):
    accepted = {c['testcase_index'] for c in value['candidates']}
    invalid = set(value['rejected_testcase_indexes'])
    withheld = set(value['withheld_testcase_indexes'])
    assert not (accepted & invalid or accepted & withheld or invalid & withheld)
    assert accepted | invalid | withheld == set(range(value['testcase_count']))
    assert invalid == {n for d in value['diagnostics'] for n in d['testcase_indexes']}
    assert value['candidate_count'] == len(value['candidates'])
    assert_passive(value)


@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('mapping_kind', [JUnitMapping, JUnitMappingRules])
@pytest.mark.parametrize('body,outcome', [
    ('', 'passed'), ('<failure/>', 'failed'), ('<error/>', 'failed'), ('<skipped/>', 'skipped')])
def test_originals_and_declared_tool_bind_every_valid_measurement(policy, mapping_kind, body, outcome):
    doc, chosen, args = import_case()
    doc = document(body=body)
    chosen = chosen if mapping_kind is JUnitMapping else rules()
    args['policy'] = policy
    analysis = analyze_junit_candidates(doc, chosen, targets=args['targets'])
    with no_write_attempts():
        prepared = prepare_junit_import(doc, chosen, **args)
    value = prepared.data
    assert value['format_version'] == 'evidence-import-preparation-v1'
    assert value['import_format'] == 'junit' and value['policy'] == policy
    assert value['decision'] == 'prepared'
    assert value['analysis_sha256'] == analysis.sha256
    provenance = value['provenance']
    assert provenance == {
        'format_version': 'evidence-import-provenance-v1', 'import_format': 'junit',
        'source': bound_hash(doc.source_bytes),
        'mapping': {**bound_hash(chosen.source_bytes), 'canonical_sha256': chosen.sha256,
                    'format_version': chosen.data['format_version']},
        'external_identifiers': None, 'parser_profile': 'junit-core-v1',
        'tool': args['tool'], 'importer': {'name': 'specroad', 'version': __version__}}
    assert value['provenance_sha256'] == canonical_json_sha256(provenance)
    assert value['candidates'] == [
        {**c, 'provenance_sha256': value['provenance_sha256']} for c in analysis.data['candidates']]
    assert value['candidates'][0]['result'] == outcome
    assert prepared.original_files == {'source': doc.source_bytes, 'mapping': chosen.source_bytes}
    assert prepared.sha256 == canonical_json_sha256(value)
    assert_accounted(value)


@pytest.mark.parametrize('policy', POLICIES)
def test_policy_retains_every_diagnostic_and_never_selects_a_favorable_conflicting_result(policy):
    doc = report(({'name': 'valid'}, '<failure/>'), ({'name': 'unknown'}, ''),
                 ({'name': 'ambiguous'}, ''), ({'name': 'mixed'}, '<failure/><skipped/>'),
                 ({'name': 'repeated'}, ''), ({'name': 'repeated'}, '<error/>'))
    chosen = rules(rows=[row({'name': name}) for name in ('valid', 'ambiguous', 'mixed', 'repeated')]
                   + [row({'name': 'ambiguous'}, ref('VER'))])
    args = {'targets': [target(), target('verification')], 'policy': policy,
            'tool': {'name': 'reporter', 'version': '1'}}
    analysis = analyze_junit_candidates(doc, chosen, targets=args['targets']).data
    value = prepare_junit_import(doc, chosen, **args).data
    assert value['diagnostics'] == analysis['diagnostics']
    assert value['rejected_testcase_indexes'] == [1, 2, 3, 4, 5]
    if policy == 'abort_import':
        assert value['decision'] == 'aborted' and value['candidates'] == []
        assert value['withheld_testcase_indexes'] == [0]
    else:
        assert value['decision'] == 'prepared' and value['withheld_testcase_indexes'] == []
        assert [(c['testcase_index'], c['result']) for c in value['candidates']] == [(0, 'failed')]
    assert_accounted(value)


@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('bad_unused_mapping', [False, True])
def test_empty_reports_and_diagnostics_without_occurrences_do_not_invent_evidence(policy, bad_unused_mapping):
    doc, _, args = import_case()
    doc = JUnitDocument(b'<testsuite/>')
    chosen = rules(rows=[row({'name': 'unused'}, ref('TEST', '1'))] if bad_unused_mapping else [])
    value = prepare_junit_import(doc, chosen, **{**args, 'policy': policy}).data
    assert value['decision'] == ('aborted' if bad_unused_mapping and policy == 'abort_import' else 'prepared')
    assert value['candidate_count'] == value['testcase_count'] == 0
    assert bool(value['diagnostics']) == bad_unused_mapping
    assert_accounted(value)


@pytest.mark.parametrize('change', ['xml-space', 'xml-encoding', 'mapping-space'])
def test_semantically_equal_files_retain_distinct_original_byte_bindings(change):
    doc, chosen, args = import_case()
    original = prepare_junit_import(doc, chosen, **args)
    if change == 'xml-space':
        doc = JUnitDocument(doc.source_bytes + b'\r\n')
    elif change == 'xml-encoding':
        doc = JUnitDocument(doc.source_bytes.decode().encode('utf-16'))
    else:
        chosen = JUnitMapping(json.dumps(chosen.data, indent=3).encode())
    changed = prepare_junit_import(doc, chosen, **args)
    first, second = original.data['provenance'], changed.data['provenance']
    assert original.data['provenance_sha256'] != changed.data['provenance_sha256']
    assert changed.original_files == {'source': doc.source_bytes, 'mapping': chosen.source_bytes}
    assert first['mapping']['canonical_sha256'] == second['mapping']['canonical_sha256']
    key = 'mapping' if change == 'mapping-space' else 'source'
    assert first[key]['sha256'] != second[key]['sha256']
    assert changed.data['candidates'][0]['result'] == original.data['candidates'][0]['result']


@pytest.mark.parametrize('policy', POLICIES)
def test_selected_external_identifiers_have_their_own_raw_and_canonical_provenance(policy):
    doc, _, args = import_case()
    chosen = rules(['external_id'], [row({'external_id': '../literal external ID'})])
    sidecar = external(doc, [(0, '../literal external ID')])
    sidecar = JUnitExternalIdentifiers(json.dumps(sidecar.data, indent=2).encode())
    prepared = prepare_junit_import(doc, chosen, **{**args, 'policy': policy}, external_identifiers=sidecar)
    assert prepared.original_files['external_identifiers'] == sidecar.source_bytes
    assert prepared.data['provenance']['external_identifiers'] == {
        **bound_hash(sidecar.source_bytes), 'canonical_sha256': sidecar.sha256,
        'format_version': 'junit-external-identifiers-v1'}
    assert prepared.data['candidates'][0]['identity'] == {'external_id': '../literal external ID'}
    assert_accounted(prepared.data)


@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('kind', ['unused', 'foreign', 'missing'])
def test_a_sidecar_binding_failure_cannot_be_silently_skipped(policy, kind):
    doc, chosen, args = import_case()
    sidecar = external(doc, [(0, 'id')])
    if kind != 'unused':
        chosen = rules(['external_id'], [row({'external_id': 'id'})])
        sidecar = None if kind == 'missing' else external(document(body='<failure/>'), [(0, 'id')])
    with pytest.raises(JUnitMappingError):
        prepare_junit_import(doc, chosen, **{**args, 'policy': policy}, external_identifiers=sidecar)


@pytest.mark.parametrize('policy', [None, True, '', 'abort', 'skip', ['abort_import'], {}, 0])
def test_exactly_one_explicit_supported_policy_is_required(policy):
    doc, chosen, args = import_case()
    with pytest.raises(EvidenceImportError) as caught, no_write_attempts():
        prepare_junit_import(doc, chosen, **{**args, 'policy': policy})
    assert caught.value.reason == 'explicit_import_policy_required'
    assert caught.value.pointer == '/policy' and caught.value.diagnostic()['code'] == 'SRV091'


@pytest.mark.parametrize('tool', [
    None, [], {}, {'name': 'reporter'}, {'name': '', 'version': '1'},
    {'name': 'reporter', 'version': ' \t'}, {'name': 'reporter', 'version': 1},
    {'name': 'reporter', 'version': '1', 'write_authorized': True}])
def test_tool_name_and_version_must_be_explicit_native_metadata(tool):
    doc, chosen, args = import_case()
    with pytest.raises(EvidenceImportError) as caught:
        prepare_junit_import(doc, chosen, **{**args, 'tool': tool})
    assert caught.value.pointer.startswith('/tool')
    assert caught.value.diagnostic()['code'] == 'SRV091'


def test_policy_and_tool_changes_are_distinguishable_without_rewriting_the_sources():
    doc, chosen, args = import_case()
    first = prepare_junit_import(doc, chosen, **args)
    policy = prepare_junit_import(doc, chosen, **{**args, 'policy': POLICIES[1]})
    tool = prepare_junit_import(doc, chosen, **{**args, 'tool': {**args['tool'], 'version': '10'}})
    assert first.original_files == policy.original_files == tool.original_files
    assert first.data['provenance_sha256'] == policy.data['provenance_sha256']
    assert first.data['provenance_sha256'] != tool.data['provenance_sha256']
    assert len({value.sha256 for value in (first, policy, tool)}) == 3


def test_preparation_owns_detached_metadata_and_original_files_without_boolean_authority():
    doc, chosen, args = import_case()
    prepared = prepare_junit_import(doc, chosen, **args)
    data, files = prepared.data, prepared.original_files
    prepared.data['candidates'].clear()
    prepared.original_files['source'] = b'replaced'
    args['tool']['version'] = 'changed later'
    assert prepared.data == data and prepared.original_files == files
    with pytest.raises(TypeError):
        bool(prepared)
    with pytest.raises(TypeError):
        EvidenceImportPreparation()
    for name in ('_encoded', '_originals'):
        with pytest.raises(FrozenInstanceError):
            setattr(prepared, name, None)


def test_input_caches_cannot_replace_the_bound_originals_or_analysis():
    doc, _, args = import_case()
    chosen = rules(['external_id'], [row({'external_id': 'explicit'})])
    sidecar = external(doc, [(0, 'explicit')])
    before = prepare_junit_import(doc, chosen, **args, external_identifiers=sidecar)
    for value in (doc, chosen, sidecar, args['targets'][0]):
        object.__setattr__(value, '_encoded', b'{}')
    after = prepare_junit_import(doc, chosen, **args, external_identifiers=sidecar)
    assert after.data == before.data and after.original_files == before.original_files


@pytest.mark.parametrize('policy', POLICIES)
@pytest.mark.parametrize('which', ['document', 'mapping'])
def test_invalid_original_bytes_are_fatal_under_both_policies(policy, which):
    doc, chosen, args = import_case()
    object.__setattr__(doc if which == 'document' else chosen, 'source_bytes', b'not a document')
    with pytest.raises(ModelError), no_write_attempts():
        prepare_junit_import(doc, chosen, **{**args, 'policy': policy})


@pytest.mark.parametrize('which,bad', [
    ('document', {}), ('mapping', {}), ('targets', None), ('targets', [{}]),
    ('external_identifiers', {})])
def test_untyped_values_are_rejected_before_they_supply_provenance(which, bad):
    doc, chosen, args = import_case()
    if which == 'document':
        doc = bad
    elif which == 'mapping':
        chosen = bad
    else:
        args[which] = bad
    with pytest.raises(ModelError):
        prepare_junit_import(doc, chosen, **args)


@pytest.mark.parametrize('policy', POLICIES)
def test_import_decision_cannot_read_host_state_or_modify_a_real_project(tmp_path, monkeypatch, policy):
    make_project(tmp_path)
    before = inventory(tmp_path)
    doc, chosen, args = import_case()
    doc = report(({'name': 'accepts'}, ''), ({'name': 'foreign'}, '<failure/>'))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('SPECROAD_IMPORT_POLICY', 'implicit and untrusted')
    def forbid(*args, **kwargs):
        raise AssertionError('Host access is not an import input')
    monkeypatch.setattr('pathlib.Path.open', forbid)
    with no_write_attempts():
        prepared = prepare_junit_import(doc, chosen, **{**args, 'policy': policy})
    monkeypatch.undo()
    assert inventory(tmp_path) == before
    assert_accounted(prepared.data)


def test_expanded_preparation_is_bounded_even_when_each_source_is_small():
    count = 4000
    doc = report(*[({'name': str(n)}, '') for n in range(count)])
    chosen = rules(rows=[row({'name': str(n)}) for n in range(count)])
    _, _, args = import_case()
    with pytest.raises(EvidenceImportError) as caught:
        prepare_junit_import(doc, chosen, **args)
    assert caught.value.reason == 'evidence_import_candidate_limit'


@pytest.mark.parametrize('portable', [False, True])
@pytest.mark.parametrize('policy', POLICIES)
def test_exact_preparation_and_original_bytes_work_in_isolated_core_and_pyz(tmp_path, portable, policy):
    doc, chosen, args = import_case()
    doc = report(({'name': 'accepts'}, '<error/>'), ({'name': 'foreign'}, ''))
    args['policy'] = policy
    expected = prepare_junit_import(doc, chosen, **args)
    body = f"""
import json
from specroad.verification import JUnitDocument, JUnitMapping, VerificationTest, prepare_junit_import
v = prepare_junit_import(JUnitDocument({doc.source_bytes!r}), JUnitMapping({chosen.source_bytes!r}),
    targets=[VerificationTest({args['targets'][0].source_bytes!r})],
    policy={policy!r}, tool={args['tool']!r})
print(json.dumps({{'data': v.data, 'originals': {{k: b.hex() for k, b in v.original_files.items()}}}}))
"""
    if portable:
        _, artifact = build_distribution(tmp_path / 'dist')
        result = run_python(['-I', '-S', '-B', '-c',
            f'import sys;sys.path.insert(0,{str(artifact)!r});\n' + body], tmp_path, capture=True)
    else:
        result = run_core(body, tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        'data': expected.data, 'originals': {k: raw.hex() for k, raw in expected.original_files.items()}}
