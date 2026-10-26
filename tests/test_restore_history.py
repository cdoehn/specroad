"""15.k.W: preserve real synthetic immutable bytes, never fabricate success."""
from hashlib import sha256
import json

import pytest

from specroad.bundles import prepare_project_bundle
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.paths import artifact_path
from specroad.recovery import RestoreError, RestorePlan, verify_restore_plan
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.record_artifact import RecordArtifact
from specroad.verification import prepare_evidence_record
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.restore import restore_case, plan_for
from test_evidence_construction import inputs
from test_restore_plan import decode_files, resign
from test_restore_plan_right import save_snapshot


def evidence_case(tmp_path, kind='project_bundle', *, stale=False, result='failed', with_test=False, canonical=False):
    subjects, contract, args = inputs(with_test=with_test)
    values = [record_value('document'), subjects[0].data, contract.data]
    if args['test'] is not None:
        values.append(args['test'].data)
    options, source_files, source_raw = restore_case(tmp_path, kind, values=values)
    if stale:
        value = subjects[0].data
        value['title'] = 'A different measured context'
        subjects = [DomainArtifact(canonical_json_bytes(value))]
    content = b'original measurement\x00\xff\r\n'
    attachment = {'path': 'attachments/measurement.bin', 'media_type': 'application/octet-stream',
                  'size': len(content), 'sha256': sha256(content).hexdigest()}
    record = prepare_evidence_record(subjects, contract, **{**args, 'result': result})
    record = RecordArtifact(canonical_json_bytes({**record.data, 'attachments': [attachment]}))
    path = artifact_path('evidence', record.id, 'SR')
    raw = record.source_bytes if canonical else json.dumps(record.data, indent=4).encode('utf-8') + b'\n'
    history = {path: raw, attachment['path']: content}
    for name, data in history.items():
        put(options['project_root'], name, data)
    return options, source_files, source_raw, history


@pytest.mark.parametrize('kind', ['baseline', 'project_bundle'])
@pytest.mark.parametrize('stale', [False, True])
@pytest.mark.parametrize('result', ['passed', 'failed'])
@pytest.mark.parametrize('with_test', [False, True])
def test_original_evidence_and_attachment_survive_with_honest_findings(tmp_path, kind, stale, result, with_test):
    options, source_files, source_raw, history = evidence_case(tmp_path, kind,
        stale=stale, result=result, with_test=with_test)
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = plan_for(options)
        restored = RestorePlan(plan.source_bytes)
        assert verify_restore_plan(plan.source_bytes).source_bytes == plan.source_bytes
        reports = plan.history_assessments
        assert restored.history_assessments == reports
    assert inventory(tmp_path) == before
    data = plan.data
    target = decode_files(plan)
    assert all(target[p] == raw for p, raw in {**source_files, **history}.items() if p != 'specroad.json')
    assert (options['source_root'] / options['source_path']).read_bytes() == source_raw
    assert data['source_snapshot_root'] != data['expected_target_root']
    reasons = {row['path']: row['reasons'] for row in data['preserved']}
    for path in history:
        assert reasons[path] == ['protected_history' if path.startswith('spec/') else 'protected_dependency']
    assert not set(history) & {row['path'] for row in data['backup']['entries']}
    assert {r['evidence_result'] for r in reports} == {result}
    # The full-project restore scope is explicitly unconfigured. A historical
    # configured measurement cannot become current by dropping that binding.
    assert all(r['freshness'] == 'stale' and 'configuration_changed' in r['reasons'] for r in reports)
    assert any('subject_context_changed' in r['reasons'] for r in reports) is stale
    for report in reports:
        assert not any(report[key] for key in ('full_verification_evaluated', 'run_selection_evaluated',
            'release_readiness_evaluated', 'test_code_executed', 'write_authorized', 'approval_granted'))
    reports[0]['evidence_result'] = 'forged'
    assert plan.history_assessments[0]['evidence_result'] == result
    target_root = tmp_path / 'reconstructed'
    for path, raw in target.items():
        put(target_root, path, raw)
    native = prepare_project_bundle(target_root)
    assert native.manifest['bundle_model_root_sha256'] == data['expected_target_root']


@pytest.mark.parametrize('kind', ['baseline', 'project_bundle'])
def test_younger_baseline_and_recursive_original_objects_are_explicit_history(tmp_path, kind):
    options, _, source_raw = restore_case(tmp_path, kind)
    first = save_snapshot(options['project_root'], identity=ref('BASE', '1'))
    second = save_snapshot(options['project_root'], identity=ref('BASE', '2'))
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = plan_for(options)
    target = decode_files(plan)
    assert all(target[p] == raw for p, raw in {**first, **second}.items())
    assert (options['source_root'] / options['source_path']).read_bytes() == source_raw
    assert inventory(tmp_path) == before
    assert plan.data['source_snapshot_root'] != plan.data['expected_target_root']
    assert plan.history_assessments == ()


@pytest.mark.parametrize('missing_attachment', [False, True])
def test_baseline_archive_retains_missing_immutable_evidence_file(tmp_path, missing_attachment):
    options, _, _, history = evidence_case(tmp_path, canonical=True)
    originals = save_snapshot(options['project_root'], identity=ref('BASE', '2'))
    evidence_path = next(p for p in history if p.startswith('spec/'))
    (options['project_root'] / evidence_path).unlink()
    if missing_attachment:
        (options['project_root'] / 'attachments/measurement.bin').unlink()
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = plan_for(options)
    target = decode_files(plan)
    assert target[evidence_path] == history[evidence_path]
    assert target['attachments/measurement.bin'] == history['attachments/measurement.bin']
    assert all(target[p] == raw for p, raw in originals.items())
    assert inventory(tmp_path) == before


def test_identical_history_in_source_is_deduplicated_without_extra_preservation_rows(tmp_path):
    options, _, _, history = evidence_case(tmp_path, canonical=True)
    for path, raw in history.items():
        put(options['source_root'], path, raw)
    raw = prepare_project_bundle(options['source_root']).source_bytes
    put(options['source_root'], options['source_path'], raw)
    with no_write_attempts():
        plan = plan_for(options)
    assert plan.data['preserved'] == []
    assert plan.data['expected_target_root'] == plan.data['source_snapshot_root']


@pytest.mark.parametrize('kind', ['baseline', 'evidence'])
def test_same_immutable_identity_with_different_bytes_is_a_conflict(tmp_path, kind):
    if kind == 'baseline':
        options, _, raw = restore_case(tmp_path, 'baseline')
        path = options['source_path']
    else:
        options, _, _, history = evidence_case(tmp_path)
        path, raw = next((p, b) for p, b in history.items() if p.startswith('spec/'))
        for name, content in history.items():
            put(options['source_root'], name, content)
        put(options['source_root'], options['source_path'], prepare_project_bundle(options['source_root']).source_bytes)
    changed = json.loads(raw)
    changed['title'] = 'Conflicting immutable identity'
    put(options['project_root'], path, canonical_json_bytes(changed))
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        plan_for(options)
    assert failure.value.exit_code == 6
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('damage', ['missing_attachment', 'changed_attachment', 'missing_archive', 'changed_archive'])
def test_history_with_unavailable_original_bytes_never_yields_a_complete_plan(tmp_path, damage):
    options, _, _, history = evidence_case(tmp_path)
    if damage.endswith('archive'):
        originals = save_snapshot(options['project_root'], identity=ref('BASE', '2'))
        path = next(p for p in originals if p.startswith('archive/'))
    else:
        path = next(p for p in history if p.startswith('attachments/'))
    if damage.startswith('missing'):
        (options['project_root'] / path).unlink()
    else:
        put(options['project_root'], path, b'not the original')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        plan_for(options)
    assert failure.value.exit_code == 3
    assert inventory(tmp_path) == before


def test_current_mutable_subjects_cannot_fill_a_complete_source(tmp_path):
    (tmp_path / 'full').mkdir()
    (tmp_path / 'old').mkdir()
    options, _, _, history = evidence_case(tmp_path / 'full')
    old_options, _, _ = restore_case(tmp_path / 'old')
    options.update(source_root=old_options['source_root'], source_path=old_options['source_path'])
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        plan_for(options)
    assert failure.value.exit_code == 3
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['drop_history', 'reason', 'live_bytes'])
def test_resigning_or_stale_inventory_cannot_erase_the_preservation_obligation(tmp_path, change):
    options, _, _, history = evidence_case(tmp_path)
    plan = plan_for(options)
    data = plan.data
    path = next(p for p in history if p.startswith('spec/'))
    if change == 'live_bytes':
        put(options['project_root'], path, history[path] + b' ')
        with no_write_attempts(), pytest.raises(RestoreError) as failure:
            verify_restore_plan(plan.source_bytes)
        assert failure.value.exit_code == 6
        return
    if change == 'reason':
        next(r for r in data['preserved'] if r['path'] == path)['reasons'] = ['source_archive']
    else:
        removed = next(r for r in data['target']['entries'] if r['path'] == path)
        data['target']['entries'].remove(removed)
        data['target']['sha256'] = canonical_json_sha256(data['target']['entries'])
        data['preserved'] = [r for r in data['preserved'] if r['path'] != path]
        data['backup']['entries'].append(removed)
        data['backup']['entries'].sort(key=lambda r: r['path'].encode('utf-8'))
        data['backup']['sha256'] = canonical_json_sha256(data['backup']['entries'])
    with no_write_attempts(), pytest.raises(RestoreError):
        RestorePlan(resign(data))


@pytest.mark.parametrize('case', ['independent', 'approved_subject', 'run_conflict'])
def test_missing_specialists_and_contradictory_run_history_are_not_faked(tmp_path, case):
    options, files, _, history = evidence_case(tmp_path)
    path = next(p for p in history if p.startswith('spec/'))
    value = json.loads(history[path])
    if case == 'independent':
        value['configuration_policy'] = 'independent'
    elif case == 'approved_subject':
        subject_path = next(p for p in files if p.startswith('spec/requirements/'))
        subject = json.loads(files[subject_path]); subject['maturity'] = 'approved'
        # Make the synthetic stored fields valid, without supplying any real
        # approval evidence. The restore lifecycle specialist must still block.
        subject['rationale'] = 'Synthetic approval-shaped input, not an approval proof'
        put(options['source_root'], subject_path, canonical_json_bytes(subject))
        put(options['source_root'], options['source_path'], prepare_project_bundle(options['source_root']).source_bytes)
    else:
        value['id'] = ref('EVD', '2')
        value['run_context']['subject_state_sha256'] = 'd' * 64
        path = artifact_path('evidence', value['id'], 'SR')
    put(options['project_root'], path, canonical_json_bytes(value))
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        plan_for(options)
    assert failure.value.exit_code == 3
    assert inventory(tmp_path) == before
