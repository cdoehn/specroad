"""Explicit unknown provenance, immutable inputs and native recording refusals."""
from io import BytesIO, StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.authoring.evidence import (read_evidence_record_input,
    parse_evidence_record_input, prepare_evidence_operation, preview_evidence_record)
from specroad.changes import TargetModel
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.storage.record_artifact import RecordArtifact
from specroad.validation import ModelDocument
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref
from test_evidence_recording import project, measurement, changed, plan_for, preview, apply, ACTOR, TIME


def unbound_input(root, **options):
    model = project(root, **options)
    record = measurement(model, unknown=True)
    value = record.data
    value.pop('run_context')
    return model, record, value


def read(value, **options):
    return read_evidence_record_input(ref('VER'), input='-',
        stdin=BytesIO(canonical_json_bytes(value)), **options)


def rebind(model, identity, **fields):
    """Own revised native source bytes without constructing replacement Evidence."""
    documents = []
    for document in model.documents:
        value = json.loads(document.content)
        if value['id'] == identity:
            value.update(fields)
            raw = (json.dumps(value, indent=1, ensure_ascii=False) + '\n').encode()
            document = ModelDocument(document.path, raw)
            put(Path(model.binding.source_root), document.path, raw)
        documents.append(document)
    return TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files,
        attachments=model.attachment_descriptors)


@pytest.mark.parametrize('route', ['file', 'stdin', 'argv'])
@pytest.mark.parametrize('configured', [False, True])
def test_omitted_whole_run_with_explicit_reason_records_unknown_without_inference(tmp_path, route, configured):
    root = tmp_path / 'project'; model, record, value = unbound_input(root, configured=configured, with_test=True)
    path = tmp_path / 'record.json'; path.write_bytes(canonical_json_bytes(value))
    options = {'configuration_id': ref('CFG') if configured else None}
    original = dict(model.source_files); input_bytes = path.read_bytes()
    with no_write_attempts(), patch('time.time', side_effect=AssertionError('no clock inference')), \
            patch('secrets.token_bytes', side_effect=AssertionError('no new identity')):
        if route == 'argv':
            argv = [ref('VER'), '--input', str(path)]
            if configured: argv += ['--configuration', ref('CFG')]
            operation = parse_evidence_record_input(argv)
        elif route == 'file': operation = read_evidence_record_input(ref('VER'), input=str(path), **options)
        else: operation = read(value, **options)
        normalized = RecordArtifact(canonical_json_bytes(operation.data['evidence']), expected_type='evidence')
        plan = plan_for(model, normalized)
    assert normalized.source_bytes == record.source_bytes
    response = apply(plan, model)
    actual = json.loads((root / artifact_path('evidence', record.id, 'SR')).read_bytes())
    assert actual == record.data and actual['run_context'] is None
    assert actual['unbound_reason'] == value['unbound_reason']
    assert response['audit']['created_ids'] == [record.id] and not response['approval_granted']
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
    assert path.read_bytes() == input_bytes


@pytest.mark.parametrize('reason', [None, '', ' ', '\t\r\n', '\u2003', 0, False, {}, []])
def test_missing_whole_context_requires_a_supplied_nonblank_reason(tmp_path, reason):
    root = tmp_path / 'project'; _, _, value = unbound_input(root)
    if reason is None: value.pop('unbound_reason')
    else: value['unbound_reason'] = reason
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught: read(value)
    assert caught.value.exit_code == 3 and caught.value.reason == 'evidence_unbound_reason_required'
    assert 'run_context' not in value and inventory(root) == before


@pytest.mark.parametrize('field', ['subject_id', 'subject_state_sha256', 'run_id', 'check_id', 'test_id'])
@pytest.mark.parametrize('reason', [False, True])
def test_partial_run_is_not_completed_from_subjects_or_downgraded_to_unknown(tmp_path, field, reason):
    root = tmp_path / 'project'; model = project(root, with_test=True)
    value = measurement(model).data; value['run_context'].pop(field)
    if reason: value['unbound_reason'] = 'The source omitted part of its run metadata.'
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught: read(value)
    assert caught.value.exit_code == 3
    assert field not in value['run_context'] and inventory(root) == before


@pytest.mark.parametrize('field', ['produced_at', 'producer', 'tool', 'environment', 'origin', 'created_at', 'created_by'])
def test_other_required_measurement_and_audit_fields_are_never_inferred(tmp_path, field):
    root = tmp_path / 'project'; _, _, value = unbound_input(root); value.pop(field)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught: read(value)
    assert caught.value.exit_code == 3 and field not in value and inventory(root) == before


@pytest.mark.parametrize('verification_id,configuration_id', [
    ('invalid', None), (ref(), None), (None, None), (ref('VER'), ref()),
    (ref('VER'), 'invalid'), (ref('VER'), {})])
def test_invalid_operand_identities_are_refused_before_reading_any_input(verification_id, configuration_id):
    stream = BytesIO(b'must not be consumed')
    with no_write_attempts(), patch('specroad.authoring.evidence._read_input',
            side_effect=AssertionError('no source read')), pytest.raises(ModelError) as caught:
        read_evidence_record_input(verification_id, input='-', stdin=stream,
            run_context='not-opened.json', configuration_id=configuration_id)
    assert caught.value.exit_code == 3 and stream.tell() == 0


@pytest.mark.parametrize('argv', [[], [ref('VER')], [ref('VER'), '--unknown'],
    [ref('VER'), '--input'], [ref('VER'), '--input', '-', '--input', '-']])
def test_invalid_argument_tails_do_not_read_implicit_stdin(argv):
    stream = BytesIO(b'unrelated input')
    with no_write_attempts(), pytest.raises(ModelError): parse_evidence_record_input(argv, stdin=stream)
    assert stream.tell() == 0


def test_two_stdin_sources_are_rejected_without_consuming_either():
    stream = BytesIO(b'unrelated input')
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        read_evidence_record_input(ref('VER'), input='-', run_context='-', stdin=stream)
    assert caught.value.reason == 'multiple_stdin_inputs' and stream.tell() == 0


@pytest.mark.parametrize('source,expected_code', [('text', 7), ('closed', 5)])
def test_stdin_byte_and_io_failures_remain_machine_readable(source, expected_code):
    stream = StringIO('{}') if source == 'text' else BytesIO(b'{}')
    if source == 'closed': stream.close()
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        read_evidence_record_input(ref('VER'), input='-', stdin=stream)
    assert caught.value.exit_code == expected_code


@pytest.mark.parametrize('source,expected_code', [('absent', 5), ('link', 7)])
def test_file_failures_do_not_fall_back_to_stdin(tmp_path, source, expected_code):
    path = tmp_path / 'input.json'
    if source == 'link':
        target = tmp_path / 'target.json'; target.write_bytes(b'{}'); path.symlink_to(target)
    stream = BytesIO(b'not a fallback'); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        read_evidence_record_input(ref('VER'), input=str(path), stdin=stream)
    assert caught.value.exit_code == expected_code and stream.tell() == 0
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('field,new', [('subject_id', 'other-product'), ('subject_state_sha256', 'f' * 64),
    ('run_id', 'other:run'), ('check_id', 'other'), ('test_id', ref('TEST', '2'))])
def test_run_file_cannot_replace_any_conflicting_declared_binding(tmp_path, field, new):
    model = project(tmp_path / 'project', with_test=True); record = measurement(model)
    value = record.data; run = dict(value['run_context']); run[field] = new
    run_path = tmp_path / 'run.json'; run_path.write_bytes(canonical_json_bytes(run))
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as caught: read(value, run_context=str(run_path))
    assert caught.value.exit_code == 3 and caught.value.reason == 'evidence_run_context_conflict'
    assert inventory(tmp_path) == before


def test_explicit_unknown_context_cannot_be_replaced_by_a_run_file(tmp_path):
    model = project(tmp_path / 'project'); record = measurement(model, unknown=True)
    path = tmp_path / 'run.json'; path.write_bytes(canonical_json_bytes(measurement(model).data['run_context']))
    with no_write_attempts(), pytest.raises(ModelError) as caught: read(record.data, run_context=str(path))
    assert caught.value.reason == 'evidence_run_context_conflict' and record.data['run_context'] is None


@pytest.mark.parametrize('status', ['not_planned', 'planned', 'running', 'not_applicable'])
def test_recording_preserves_subject_revision_plan_status_and_original_noncanonical_bytes(tmp_path, status):
    root = tmp_path / 'project'; model = project(root, with_test=True)
    model = rebind(model, ref(), revision=7, verification_plan_status=status)
    model = rebind(model, ref('VER'), revision=4)
    model = rebind(model, ref('TEST'), revision=9)
    original = dict(model.source_files); record = measurement(model, unknown=True, result='passed')
    response = apply(plan_for(model, record), model)
    assert response['write_state'] == 'committed' and not response['approval_granted']
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
    subject = json.loads((root / artifact_path('requirement', ref(), 'SR')).read_bytes())
    assert subject['revision'] == 7 and subject['verification_plan_status'] == status
    assert 'verification_result' not in subject and record.data['run_context'] is None
    revisions = {v['artifact_id']: v['revision'] for v in record.data['subjects']}
    assert revisions == {ref(): 7, ref('VER'): 4, ref('TEST'): 9}


@pytest.mark.parametrize('identity', [ref(), ref('VER'), ref('TEST')])
def test_earlier_measurement_is_not_rebound_to_revised_subject_contract_or_test(tmp_path, identity):
    root = tmp_path / 'project'; model = project(root, with_test=True)
    record = measurement(model); raw = record.source_bytes
    model = rebind(model, identity, revision=2, title='Revised after measurement')
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught: preview(model, record)
    assert caught.value.reason == 'evidence_record_binding_mismatch'
    assert inventory(root) == before and record.source_bytes == raw


def test_omitted_and_explicit_null_context_have_the_same_durable_request_identity(tmp_path):
    root = tmp_path / 'project'; model, record, value = unbound_input(root)
    absent = read(value); explicit = prepare_evidence_operation(ref('VER'), record)
    assert absent.data == explicit.data
    first = plan_for(model, RecordArtifact(canonical_json_bytes(absent.data['evidence'])))
    repeated = plan_for(model, record, change_plan_id='CP-repeated')
    response = apply(first, model); before = inventory(root)
    with no_write_attempts(): replayed = apply(repeated, model, transaction_id='repeated-evidence')
    assert replayed['replayed'] and replayed['audit']['created_ids'] == response['audit']['created_ids'] == [record.id]
    assert inventory(root) == before


def test_replay_does_not_rewrite_later_subject_changes_or_claim_a_new_current_measurement(tmp_path):
    root = tmp_path / 'project'; model = project(root); record = measurement(model, unknown=True)
    plan = plan_for(model, record); apply(plan, model)
    rebind(model, ref(), revision=5, verification_plan_status='running')
    before = inventory(root)
    with no_write_attempts(): response = apply(plan, model, transaction_id='repeated-evidence')
    assert response['replayed'] and not response['completion']['current_target_verified']
    assert response['audit']['created_ids'] == [record.id] and inventory(root) == before


def test_changed_unknown_reason_is_a_request_conflict_not_an_update(tmp_path):
    root = tmp_path / 'project'; model = project(root); record = measurement(model, unknown=True)
    first = plan_for(model, record)
    second = plan_for(model, changed(record, unbound_reason='Different measured-input provenance.'))
    apply(first, model); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught: apply(second, model)
    assert caught.value.exit_code == 6 and inventory(root) == before


def test_bound_configuration_is_not_selected_just_because_one_configuration_exists(tmp_path):
    root = tmp_path / 'project'; model, _, value = unbound_input(root, configured=True)
    operation = read(value)
    assert operation.data['configuration_id'] is None
    record = RecordArtifact(canonical_json_bytes(operation.data['evidence']))
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError):
        preview_evidence_record(model, ref('VER'), record, actor=ACTOR, planned_at=TIME,
            change_plan_id='CP-no-implicit-configuration', request_id='record-1')
    assert inventory(root) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_unknown_input_normalization_is_identical_in_isolated_core_and_pyz(tmp_path, mode):
    _, record, value = unbound_input(tmp_path / 'project')
    path = tmp_path / 'record.json'; path.write_bytes(canonical_json_bytes(value))
    body = 'import json\nfrom specroad.authoring.evidence import read_evidence_record_input\n'
    body += 'result=read_evidence_record_input(' + repr(ref('VER')) + ',input=' + repr(str(path)) + ')\n'
    body += 'print(json.dumps(result.data))\n'
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == prepare_evidence_operation(ref('VER'), record).data
    assert path.read_bytes() == canonical_json_bytes(value)
