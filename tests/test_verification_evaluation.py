"""An explicit product-input manifest is neither a model root nor a test pass."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.verification import (VerificationEvaluation, VerificationEvaluationError,
    EvaluationInputAssessment, prepare_verification_evaluation, assess_evaluation_inputs)
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import ref
from test_evidence_construction import inputs as evidence_inputs

EVALUATION_ID = 'EVAL-' + '0' * 25 + '1'
CREATED_AT = '2026-10-20T21:00:00Z'
ACTOR = {'actor_type': 'human', 'actor_id': 'declared-evaluator'}
INPUTS = {'src/program.py': b'return 1\n', 'inputs/settings.json': b'{ "limit": 3 }\n'}


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def runs():
    return [{'subject_artifact_id': ref(), 'contract_id': ref('VER'),
             'test_id': None, 'check_id': 'overall', 'run_ids': ['meter:second', 'meter:first']}]


def descriptor(**extra):
    options = dict(evaluation_id=EVALUATION_ID, subject_id='measured-product', inputs=dict(INPUTS),
        configuration=None, required_runs=runs(), created_at=CREATED_AT, created_by=dict(ACTOR))
    options.update(extra)
    return prepare_verification_evaluation(**options)


def expected_subject(inputs=INPUTS, subject_id='measured-product'):
    manifest = [{'logical_path': path, 'size': len(inputs[path]),
                 'sha256': sha256(inputs[path]).hexdigest()}
                for path in sorted(inputs, key=lambda p: p.encode('utf-8'))]
    subject = {'subject_id': subject_id, 'manifest': manifest}
    return {**subject, 'state_sha256': sha256(encode(subject)).hexdigest()}


def test_descriptor_binds_actual_input_bytes_with_exact_independent_manifest_hash():
    with no_write_attempts():
        value = descriptor()
        report = assess_evaluation_inputs(value, inputs=INPUTS).data
    expected = {'format_version': '1.0.0', 'evaluation_id': EVALUATION_ID,
        'evaluated_subject': expected_subject(), 'configuration_hash': None,
        'required_runs': [{**runs()[0], 'run_ids': ['meter:first', 'meter:second']}],
        'replacements': [], 'created_at': CREATED_AT, 'created_by': ACTOR}
    assert value.data == expected
    assert value.canonical_bytes == encode(expected)
    assert value.sha256 == sha256(encode(expected)).hexdigest()
    assert value.state_sha256 == expected['evaluated_subject']['state_sha256']
    assert report['evaluation_sha256'] == value.sha256
    assert report['state_sha256'] == value.state_sha256 and report['input_bytes_verified']
    assert report['matched_inputs'] == ['inputs/settings.json', 'src/program.py']
    assert report['missing_inputs'] == report['mismatched_inputs'] == report['unexpected_inputs'] == []
    for flag in ('input_roles_verified', 'project_required_checks_complete',
            'configuration_applicability_evaluated', 'run_selection_evaluated',
            'full_verification_evaluated', 'external_run_verified', 'release_readiness_evaluated',
            'test_code_executed', 'write_authorized', 'approval_granted'):
        assert report[flag] is False
    assert 'verification_result' not in report


@pytest.mark.parametrize('change', ['same_size', 'size', 'path', 'added', 'removed', 'subject'])
def test_changed_actual_input_or_product_identity_changes_state(change):
    files = dict(INPUTS); subject_id = 'measured-product'
    if change == 'same_size': files['src/program.py'] = b'return 2\n'
    if change == 'size': files['src/program.py'] += b'\n'
    if change == 'path': files['renamed.py'] = files.pop('src/program.py')
    if change == 'added': files['input.bin'] = b'\0\xff'
    if change == 'removed': del files['src/program.py']
    if change == 'subject': subject_id = 'another-product'
    changed = descriptor(inputs=files, subject_id=subject_id)
    assert changed.state_sha256 != descriptor().state_sha256
    assert changed.data['evaluated_subject'] == expected_subject(files, subject_id)


@pytest.mark.parametrize('change', ['actor', 'time', 'evaluation_id', 'run', 'configuration'])
def test_evaluation_metadata_changes_descriptor_hash_without_self_dependency(change):
    options = {}
    if change == 'actor': options['created_by'] = {'actor_type': 'ci', 'actor_id': 'other-client'}
    if change == 'time': options['created_at'] = '2026-10-21T00:00:00Z'
    if change == 'evaluation_id': options['evaluation_id'] = 'EVAL-' + '0' * 25 + '2'
    if change == 'run': options['required_runs'] = [{**runs()[0], 'run_ids': ['meter:new']}]
    if change == 'configuration': options['configuration'] = evidence_inputs(with_test=True)[2]['configuration']
    changed, original = descriptor(**options), descriptor()
    assert changed.state_sha256 == original.state_sha256
    assert changed.sha256 != original.sha256
    if change == 'configuration':
        assert changed.data['configuration_hash'] == options['configuration'].sha256


def test_normalization_preserves_bytes_and_sorts_paths_keys_and_runs_by_utf8():
    files = {'\U00010000/input': b'x', '\ue000/input': b'y', 'a/empty': b''}
    declarations = [{**runs()[0], 'test_id': ref('TEST')}, runs()[0],
                    {**runs()[0], 'contract_id': ref('VER', '2')}]
    first = descriptor(inputs=files, required_runs=declarations)
    value = first.data
    value['evaluated_subject']['manifest'].reverse()
    value['required_runs'].reverse()
    for row in value['required_runs']:
        row['run_ids'].reverse()
    raw = json.dumps(value, indent=2, ensure_ascii=True).encode()
    second = VerificationEvaluation(raw)
    assert second.source_bytes == raw and second.canonical_bytes == first.canonical_bytes
    assert second.sha256 == first.sha256
    assert [e['logical_path'] for e in second.data['evaluated_subject']['manifest']] == [
        'a/empty', '\ue000/input', '\U00010000/input']
    assert [r['test_id'] for r in second.data['required_runs'][:2]] == [None, ref('TEST')]
    assert second.data['required_runs'][2]['contract_id'] == ref('VER', '2')


def test_loaded_descriptor_selfhash_does_not_verify_unavailable_or_changed_bytes():
    value = descriptor()
    report = assess_evaluation_inputs(VerificationEvaluation(value.source_bytes), inputs={
        'src/program.py': b'return 2\n', 'extra/input': b'extra'}).data
    assert not report['input_bytes_verified']
    assert report['missing_inputs'] == ['inputs/settings.json']
    assert report['mismatched_inputs'] == ['src/program.py']
    assert report['unexpected_inputs'] == ['extra/input']
    assert report['matched_inputs'] == []
    absent = assess_evaluation_inputs(value, inputs={}).data
    assert absent['missing_inputs'] == ['inputs/settings.json', 'src/program.py']
    assert not absent['input_bytes_verified']
    assert value.state_sha256 == descriptor().state_sha256


def test_owned_input_and_assessment_values_are_detached_and_never_boolean_approval():
    files = dict(INPUTS); rows = runs(); actor = dict(ACTOR)
    value = descriptor(inputs=files, required_runs=rows, created_by=actor)
    original = value.canonical_bytes
    observation = assess_evaluation_inputs(value, inputs=files)
    files.clear(); rows[0]['run_ids'].clear(); actor['actor_id'] = 'changed'
    value.data['evaluated_subject']['manifest'].clear()
    observation.data['matched_inputs'].clear()
    assert value.canonical_bytes == original
    assert observation.data['matched_inputs'] == ['inputs/settings.json', 'src/program.py']
    assert observation.sha256 == sha256(encode(observation.data)).hexdigest()
    for owned in (value, observation):
        with pytest.raises(TypeError): bool(owned)
        with pytest.raises(FrozenInstanceError): owned._encoded = b'{}'
    with pytest.raises(TypeError): EvaluationInputAssessment()


@pytest.mark.parametrize('field', ['format_version', 'evaluation_id', 'evaluated_subject',
    'configuration_hash', 'required_runs', 'replacements', 'created_at', 'created_by'])
def test_missing_descriptor_field_is_not_inferred(field):
    value = descriptor().data; del value[field]
    with no_write_attempts(), pytest.raises(VerificationEvaluationError) as caught:
        VerificationEvaluation(encode(value))
    assert caught.value.diagnostic()['code'] == 'SRV175'
    assert caught.value.diagnostic()['exit_code'] == 3


@pytest.mark.parametrize('path,replacement', [
    (('format_version',), '2.0.0'), (('evaluation_id',), 'EVAL-0001'),
    (('evaluation_id',), 'EVAL-8' + '0' * 25), (('evaluation_id',), EVALUATION_ID.lower()),
    (('evaluated_subject', 'subject_id'), ''), (('evaluated_subject', 'manifest'), []),
    (('evaluated_subject', 'manifest', 0, 'size'), -1),
    (('evaluated_subject', 'manifest', 0, 'size'), True),
    (('evaluated_subject', 'manifest', 0, 'size'), 1.25),
    (('evaluated_subject', 'manifest', 0, 'sha256'), 'A' * 64),
    (('evaluated_subject', 'state_sha256'), '0' * 64),
    (('configuration_hash',), 'bad'), (('required_runs',), []),
    (('required_runs', 0, 'subject_artifact_id'), 'not-an-artifact'),
    (('required_runs', 0, 'contract_id'), ref('EVD')),
    (('required_runs', 0, 'test_id'), ref('REQ')),
    (('required_runs', 0, 'check_id'), 'bad check'),
    (('required_runs', 0, 'run_ids'), []),
    (('required_runs', 0, 'run_ids'), ['meter:x', 'meter:x']),
    (('required_runs', 0, 'run_ids'), ['unqualified']),
    (('required_runs', 0, 'run_ids'), [' : ']),
    (('replacements',), [{'authorized_by': ACTOR}]),
    (('created_at',), '2026-10-20T20:00:00+01:00'),
    (('created_by', 'actor_type'), 'guessed')])
def test_malformed_or_unsupported_descriptor_has_structured_error(path, replacement):
    value = descriptor().data; parent = value
    for key in path[:-1]: parent = parent[key]
    parent[path[-1]] = replacement
    with no_write_attempts(), pytest.raises(VerificationEvaluationError) as caught:
        VerificationEvaluation(encode(value))
    diagnostic = caught.value.diagnostic()
    assert diagnostic['code'] == 'SRV175' and diagnostic['exit_code'] == 3
    assert diagnostic['pointer']


@pytest.mark.parametrize('where', ['root', 'subject', 'manifest', 'run', 'actor'])
def test_unknown_fields_cannot_smuggle_success_or_host_state(where):
    value = descriptor().data
    target = {'root': value, 'subject': value['evaluated_subject'],
        'manifest': value['evaluated_subject']['manifest'][0],
        'run': value['required_runs'][0], 'actor': value['created_by']}[where]
    target['verified'] = True
    with pytest.raises(VerificationEvaluationError): VerificationEvaluation(encode(value))


@pytest.mark.parametrize('kind,reason', [
    ('manifest', 'duplicate_evaluation_input_path'), ('run', 'duplicate_evaluation_required_key')])
def test_duplicate_bindings_are_errors_instead_of_silent_deduplication(kind, reason):
    value = descriptor().data
    if kind == 'manifest': value['evaluated_subject']['manifest'].append(value['evaluated_subject']['manifest'][0])
    else: value['required_runs'].append({**value['required_runs'][0], 'run_ids': ['meter:different']})
    with pytest.raises(VerificationEvaluationError) as caught: VerificationEvaluation(encode(value))
    assert caught.value.reason == reason


@pytest.mark.parametrize('path', ['/absolute', '../outside', 'a/../b', './input',
    'a//input', 'a\\input', 'C:/input', '.git/HEAD', 'input\0name'])
def test_unsafe_logical_paths_are_rejected_without_reading_them(path):
    with no_write_attempts(), pytest.raises(VerificationEvaluationError):
        descriptor(inputs={path: b'passive'})
    value = descriptor().data
    value['evaluated_subject']['manifest'][0]['logical_path'] = path
    with no_write_attempts(), pytest.raises(VerificationEvaluationError):
        VerificationEvaluation(encode(value))


@pytest.mark.parametrize('inputs', [None, [], {'file': 'not-bytes'}, {'file': bytearray(b'x')}, {1: b'x'}])
def test_inputs_require_an_explicit_owned_path_to_bytes_mapping(inputs):
    with pytest.raises(VerificationEvaluationError): descriptor(inputs=inputs)


def test_empty_input_set_cannot_describe_a_known_product_state():
    with pytest.raises(VerificationEvaluationError): descriptor(inputs={})
    with pytest.raises(VerificationEvaluationError): descriptor(configuration={'sha256': 'a' * 64})
    with pytest.raises(VerificationEvaluationError): assess_evaluation_inputs(None, inputs=INPUTS)


@pytest.mark.parametrize('raw', [b'{}{}', b'\xef\xbb\xbf{}', b'\xff', b'[]',
    b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":"\\ud800"}'])
def test_untrusted_json_bytes_fail_before_producing_a_descriptor(raw):
    with pytest.raises(VerificationEvaluationError): VerificationEvaluation(raw)


def test_pure_binding_uses_no_file_process_entropy_network_or_implicit_clock():
    with no_write_attempts(), patch('builtins.open', side_effect=AssertionError('read')), \
            patch('subprocess.Popen', side_effect=AssertionError('process')), \
            patch('socket.socket', side_effect=AssertionError('network')), \
            patch('secrets.token_bytes', side_effect=AssertionError('identity')):
        value = descriptor()
        assert assess_evaluation_inputs(value, inputs=INPUTS).data['input_bytes_verified']
        assert value.data['created_at'] == CREATED_AT


@pytest.mark.parametrize('runtime', ['core', 'pyz'])
def test_descriptor_and_byte_assessment_run_in_isolated_core_and_pyz(tmp_path, runtime):
    value = descriptor()
    body = '''
from specroad.verification import VerificationEvaluation, assess_evaluation_inputs
document=VerificationEvaluation(RAW)
assert document.sha256 == HASH
assert document.state_sha256 == STATE
report=assess_evaluation_inputs(document, inputs=INPUTS).data
assert report['input_bytes_verified'] and not report['full_verification_evaluated']
assert not report['write_authorized'] and not report['approval_granted']
'''.replace('RAW', repr(value.source_bytes)).replace('HASH', repr(value.sha256)).replace(
    'STATE', repr(value.state_sha256)).replace('INPUTS', repr(INPUTS))
    if runtime == 'core':
        result = run_core(body, tmp_path)
    else:
        _, pyz = build_distribution(tmp_path / 'dist')
        prefix = 'import sys;sys.path.insert(0,' + repr(str(pyz)) + ');\n'
        result = run_python(['-I', '-S', '-B', '-c', prefix + body], tmp_path)
    assert result.returncode == 0, result.stderr
