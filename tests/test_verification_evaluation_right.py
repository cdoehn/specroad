"""Explicit role boundaries and unavailable evaluation inputs never imply pass."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from unittest.mock import patch

import pytest

from specroad.verification import (EvaluationBindingAssessment, VerificationEvaluation,
    VerificationEvaluationError, assess_evaluation_binding)
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from test_verification_evaluation import descriptor, encode, INPUTS


def roles():
    return {**dict.fromkeys(INPUTS, 'input'), 'observations/evidence.json': 'evidence',
        'reports/result.bin': 'result', 'selected-evaluation.json': 'evaluation',
        'selection.json': 'selection_metadata'}


def assess(value=None, **changes):
    options = {'inputs': dict(INPUTS), 'input_roles': roles()}
    options.update(changes)
    return assess_evaluation_binding(value, **options)


def test_exact_input_and_role_binding_is_ready_but_never_verification_success():
    value = descriptor()
    with no_write_attempts():
        report = assess(value).data
    assert report['binding_status'] == 'ready'
    assert report['verification_result'] is None
    assert report['reasons'] == report['diagnostics'] == []
    assert report['evaluation_id'] == value.data['evaluation_id']
    assert report['evaluation_sha256'] == value.sha256
    assert report['state_sha256'] == value.state_sha256
    assert report['subject_id'] == 'measured-product' and report['configuration_hash'] is None
    assert report['input_bytes_verified'] and report['input_roles_checked']
    assert not report['input_roles_authenticated']
    expected = [{'logical_path': p, 'role': role} for p, role in sorted(roles().items())]
    assert report['input_roles'] == expected
    assert report['input_roles_sha256'] == sha256(encode(expected)).hexdigest()
    assert report['missing_input_roles'] == report['unlisted_inputs'] == []
    for field in ('project_required_checks_complete', 'configuration_applicability_evaluated',
            'run_selection_evaluated', 'full_verification_evaluated', 'external_run_verified',
            'release_readiness_evaluated', 'test_code_executed', 'write_authorized', 'approval_granted'):
        assert report[field] is False


@pytest.mark.parametrize('role', ['evidence', 'result', 'evaluation', 'selection_metadata'])
@pytest.mark.parametrize('available', [True, False])
def test_excluded_role_in_manifest_is_invalid_even_without_available_bytes(role, available):
    mapping = roles(); mapping['src/program.py'] = role
    with no_write_attempts(), pytest.raises(VerificationEvaluationError) as caught:
        assess(descriptor(), inputs=INPUTS if available else None, input_roles=mapping)
    error = caught.value.diagnostic()
    assert error['code'] == 'SRV175' and error['exit_code'] == 3
    assert error['reason'] == 'forbidden_evaluation_input_role'
    assert error['path'] == 'src/program.py' and error['pointer'] == '/evaluated_subject/manifest'


@pytest.mark.parametrize('path,role', [
    ('observations/evidence.json', 'evidence'), ('reports/result.bin', 'result'),
    ('selected-evaluation.json', 'evaluation'), ('selection.json', 'selection_metadata')])
def test_adding_an_excluded_file_cannot_be_silently_filtered_into_a_different_hash(path, role):
    files = {**INPUTS, path: b'produced by this check'}
    value = descriptor(inputs=files)
    original = value.source_bytes
    with pytest.raises(VerificationEvaluationError):
        assess(value, inputs=files, input_roles={**roles(), path: role})
    assert value.source_bytes == original
    assert value.state_sha256 != descriptor().state_sha256


@pytest.mark.parametrize('supplied', [None, {}, INPUTS])
def test_missing_descriptor_is_incomplete_and_never_inferred_from_other_data(supplied):
    report = assess(inputs=supplied).data
    assert report['binding_status'] == report['verification_result'] == 'incomplete'
    assert report['reasons'] == ['evaluation_required']
    assert report['diagnostics'] == [{'code': 'SRV176', 'severity': 'warning', 'reason': 'evaluation_required'}]
    assert report['evaluation_id'] is report['evaluation_sha256'] is None
    assert report['subject_id'] is report['state_sha256'] is report['input_observation'] is None
    assert not report['input_bytes_verified'] and not report['input_roles_checked']


def test_a_descriptor_file_among_available_bytes_does_not_select_itself():
    raw = descriptor().source_bytes
    report = assess(inputs={'selected-evaluation.json': raw}).data
    assert report['reasons'] == ['evaluation_required']
    assert report['evaluation_sha256'] is None and report['verification_result'] == 'incomplete'


@pytest.mark.parametrize('change,reason', [
    ('unavailable', 'evaluation_input_bytes_required'), ('missing', 'evaluation_input_missing'),
    ('changed', 'evaluation_input_changed'), ('extra', 'evaluation_input_unexpected')])
def test_unknown_or_nonmatching_product_bytes_are_incomplete(change, reason):
    files = dict(INPUTS)
    if change == 'unavailable': files = None
    if change == 'missing': files.pop('src/program.py')
    if change == 'changed': files['src/program.py'] = b'return 2\n'
    if change == 'extra': files['unexpected.bin'] = b'extra'
    value = descriptor()
    report = assess(value, inputs=files).data
    assert report['binding_status'] == report['verification_result'] == 'incomplete'
    assert report['reasons'] == [reason]
    assert report['diagnostics'] == [{'code': 'SRV176', 'severity': 'warning', 'reason': reason}]
    assert report['state_sha256'] == value.state_sha256
    assert report['input_roles_checked'] and not report['input_bytes_verified']
    if change == 'unavailable': assert report['input_observation'] is None


def test_all_unavailable_dimensions_remain_visible_in_stable_order():
    report = assess(descriptor(), inputs={'unexpected.bin': b'x', 'src/program.py': b'changed'},
                    input_roles={'omitted-input.bin': 'input'}).data
    assert report['reasons'] == ['evaluation_input_roles_missing', 'evaluation_inputs_not_listed',
        'evaluation_input_missing', 'evaluation_input_changed', 'evaluation_input_unexpected']
    assert [d['reason'] for d in report['diagnostics']] == report['reasons']
    assert report['missing_input_roles'] == ['inputs/settings.json', 'src/program.py']
    assert report['unlisted_inputs'] == ['omitted-input.bin']
    assert report['input_observation']['missing_inputs'] == ['inputs/settings.json']
    assert report['input_observation']['mismatched_inputs'] == ['src/program.py']


@pytest.mark.parametrize('mapping,reason', [
    (None, 'evaluation_input_roles_required'), ({}, 'evaluation_input_roles_missing'),
    ({'src/program.py': 'input'}, 'evaluation_input_roles_missing')])
def test_missing_role_information_does_not_claim_self_reference_safety(mapping, reason):
    report = assess(descriptor(), input_roles=mapping).data
    assert report['reasons'] == [reason]
    assert report['verification_result'] == 'incomplete' and not report['input_roles_checked']
    assert report['input_bytes_verified']
    if mapping is None: assert report['input_roles'] is report['input_roles_sha256'] is None


def test_independently_declared_input_must_not_disappear_from_the_manifest():
    report = assess(descriptor(), input_roles={**roles(), 'missing-from-manifest.bin': 'input'}).data
    assert report['reasons'] == ['evaluation_inputs_not_listed']
    assert report['unlisted_inputs'] == ['missing-from-manifest.bin']
    assert not report['input_roles_checked'] and report['verification_result'] == 'incomplete'


def test_roles_are_explicit_not_guessed_from_extension_or_json_like_content():
    files = {'documentation/evidence.json': b'input specification text', 'reports/requirements.out': b'{}'}
    report = assess(descriptor(inputs=files), inputs=files,
                    input_roles=dict.fromkeys(files, 'input')).data
    assert report['binding_status'] == 'ready'
    assert not report['input_roles_authenticated'] and report['verification_result'] is None


def test_role_inventory_is_sorted_and_bound_separately_from_product_and_descriptor_hashes():
    mapping = {**roles(), '\U00010000/result': 'result', '\ue000/evidence': 'evidence'}
    value = descriptor()
    first = assess(value, input_roles=mapping)
    reordered = assess(value, input_roles=dict(reversed(list(mapping.items()))))
    assert first.sha256 == reordered.sha256
    rows = first.data['input_roles']
    assert [r['logical_path'] for r in rows][-2:] == ['\ue000/evidence', '\U00010000/result']
    changed = assess(value, input_roles={**mapping, 'reports/result.bin': 'evidence'})
    assert changed.data['input_roles_sha256'] != first.data['input_roles_sha256']
    assert changed.sha256 != first.sha256
    for field in ('evaluation_sha256', 'state_sha256'):
        assert first.data[field] == changed.data[field]


@pytest.mark.parametrize('mapping', [[], 'input', {'file': None}, {'file': 1}, {'file': True},
    {'file': []}, {'file': 'unknown'}, {'file': 'Input'}, {'file': ' input '}, {1: 'input'},
    {'../outside': 'input'}, {'/absolute': 'evidence'}, {'.git/HEAD': 'result'}, {'a//b': 'evaluation'}])
def test_malformed_role_inventory_is_a_structured_descriptor_input_error(mapping):
    with no_write_attempts(), pytest.raises(VerificationEvaluationError) as caught:
        assess(descriptor(), input_roles=mapping)
    assert caught.value.code == 'SRV175' and caught.value.exit_code == 3


@pytest.mark.parametrize('bad', [b'{}', {}, False, [], 'auto'])
def test_only_explicit_none_means_missing_descriptor(bad):
    with pytest.raises(VerificationEvaluationError) as caught: assess(bad)
    assert caught.value.reason == 'typed_verification_evaluation_required'


@pytest.mark.parametrize('bad', [[], False, {'file': 'bytes'}, {'file': bytearray(b'x')}])
def test_only_explicit_none_means_unavailable_input_bytes(bad):
    with pytest.raises(VerificationEvaluationError): assess(descriptor(), inputs=bad)


def test_descriptor_source_is_revalidated_even_if_an_object_was_forged():
    value = descriptor()
    object.__setattr__(value, 'source_bytes', b'{}')
    with pytest.raises(VerificationEvaluationError): assess(value)
    value = descriptor(); object.__setattr__(value, '_encoded', b'{}')
    assert assess(value).data['binding_status'] == 'ready'


def test_binding_report_owns_nested_values_and_cannot_authorize_by_boolean_coercion():
    mapping = roles(); files = dict(INPUTS); value = descriptor()
    result = assess(value, input_roles=mapping, inputs=files)
    expected = result.data
    mapping.clear(); files.clear()
    result.data['input_roles'].clear(); result.data['input_observation']['matched_inputs'].clear()
    assert result.data == expected and result.sha256 == sha256(encode(expected)).hexdigest()
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(TypeError): EvaluationBindingAssessment()


@pytest.mark.parametrize('missing', [True, False])
def test_binding_gate_never_reads_project_files_environment_git_or_network(missing):
    value = None if missing else descriptor()
    with no_write_attempts(), patch('builtins.open', side_effect=AssertionError('file read')), \
            patch('subprocess.Popen', side_effect=AssertionError('process')), \
            patch('socket.socket', side_effect=AssertionError('network')), \
            patch('os.getenv', side_effect=AssertionError('environment')):
        report = assess(value).data
    assert report['verification_result'] == ('incomplete' if missing else None)


@pytest.mark.parametrize('runtime', ['core', 'pyz'])
def test_binding_gate_runs_in_isolated_core_and_pyz(runtime, tmp_path):
    value = descriptor()
    body = '''
from specroad.verification import VerificationEvaluation, assess_evaluation_binding
descriptor=VerificationEvaluation(RAW)
report=assess_evaluation_binding(descriptor, inputs=INPUTS, input_roles=ROLES).data
assert report['binding_status'] == 'ready' and report['verification_result'] is None
missing=assess_evaluation_binding(None, inputs=None, input_roles=None).data
assert missing['verification_result'] == 'incomplete' and missing['reasons'] == ['evaluation_required']
assert not missing['write_authorized'] and not missing['approval_granted']
'''.replace('RAW', repr(value.source_bytes)).replace('INPUTS', repr(INPUTS)).replace('ROLES', repr(roles()))
    if runtime == 'core': result = run_core(body, tmp_path)
    else:
        _, pyz = build_distribution(tmp_path / 'dist')
        prefix = 'import sys;sys.path.insert(0,' + repr(str(pyz)) + ');\n'
        result = run_python(['-I', '-S', '-B', '-c', prefix + body], tmp_path)
    assert result.returncode == 0, result.stderr
