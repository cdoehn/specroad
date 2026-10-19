"""Native Evidence publication, exact inputs, durable replay and write refusals."""
from hashlib import sha256
from io import BytesIO
import json
import os
from unittest.mock import patch

import pytest

from specroad.authoring.evidence import (prepare_evidence_operation, preview_evidence_record,
    record_evidence, read_evidence_record_input, parse_evidence_record_input)
from specroad.changes import (ChangePlan, ChangeOperation, TargetModel, TargetPolicy,
    PublicationAuthority, prepare_change_plan, assess_change_target,
    inspect_project_lock, read_transaction_completion)
from specroad.configurations import resolve_configuration
from specroad.graph.relations import SourceRelations
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.identities import ArtifactIdentity, IdentityAllocation, IdentityInventory
from specroad.model.paths import artifact_path
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.project import ProjectSource
from specroad.storage.record_artifact import RecordArtifact
from specroad.validation import ModelDocument
from specroad.verification import VerificationContract, VerificationTest, prepare_evidence_record
from support.domain import domain_value, approved_value
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.portable import build_distribution
from support.processes import run_core, run_python
from test_baseline_creation import project as base_project

ACTOR = {'actor_type': 'human', 'actor_id': 'recorder'}
TIME = '2026-10-19T21:30:00Z'
ALLOW = PublicationAuthority('evidence-test-host', '1', lambda request: True)


def project(root, *, with_test=False, attachment=False, configured=False):
    base = base_project(root)
    values = [domain_value('requirement'), record_value('verification',
        configuration_policy='bound' if configured else 'independent',
        evidence_slots=[{'check_id': 'overall', 'test_id': ref('TEST') if with_test else None,
                         'dimension': 'overall'}])]
    if with_test:
        values.append(record_value('test'))
    if configured:
        values.append(record_value('configuration'))
    documents = [*base.documents, *(ModelDocument(artifact_path(v['artifact_type'], v['id'], 'SR'),
        canonical_json_bytes(v)) for v in values)]
    attachments, resources = [], list(base.resource_files)
    if attachment:
        raw = b'raw measurement\0\xff'
        attachments.append(AttachmentDescriptor('attachments/measurement.bin',
            'application/octet-stream', len(raw), sha256(raw).hexdigest()))
        resources.append(ModelDocument(attachments[0].path, raw))
    model = TargetModel(base.configuration_bytes, base.binding, documents,
        profile=base.profile, resource_files=resources, attachments=attachments)
    for name, raw in model.source_files.items():
        put(root, name, raw)
    return model


def measurement(model, *, actor=ACTOR, result='failed', unknown=False, token='1'):
    records = {r.identity.id: r for r in (SourceRelations(d.content, path=d.path) for d in model.documents)}
    requirement = DomainArtifact(records[ref()].source_bytes, expected_type='requirement')
    contract = VerificationContract(records[ref('VER')].source_bytes)
    test = VerificationTest(records[ref('TEST')].source_bytes) if ref('TEST') in records else None
    configuration = resolve_configuration(tuple(records.values()), ref('CFG')) if ref('CFG') in records else None
    identity = ArtifactIdentity(ref('EVD', token), 'random128-v1', 'evidence', 'SR')
    allocation = IdentityAllocation(identity, IdentityInventory('SR', list(records), (), (identity.id,)))
    record = prepare_evidence_record([requirement], contract, allocation=allocation,
        configuration=configuration, actor=actor, planned_at=TIME, title='Explicit measurement',
        result=result, produced_at='2026-10-19T21:00:00Z',
        producer={'producer_type': 'tool', 'producer_id': 'synthetic-meter'},
        tool={'name': 'meter', 'version': '1.0'}, environment={'platform': 'synthetic'},
        origin='recorded_manual', run_context=None if unknown else {
            'subject_id': 'measured-product', 'subject_state_sha256': 'a' * 64,
            'run_id': 'synthetic-meter:run-1', 'check_id': 'overall',
            'test_id': None if test is None else test.data['id']},
        test=test, unbound_reason='Product provenance unavailable.' if unknown else None)
    if model.attachment_descriptors:
        record = RecordArtifact(canonical_json_bytes({**record.data,
            'attachments': [item.data for item in model.attachment_descriptors]}), expected_type='evidence')
    return record


def preview(model, record, **extra):
    options = dict(actor=record.data['created_by'], planned_at=TIME, change_plan_id='CP-evidence',
        request_id='record-1', configuration_id=ref('CFG') if any(
            a['artifact_type'] == 'configuration' for a in model.artifacts) else None)
    options.update(extra)
    return preview_evidence_record(model, ref('VER'), record, **options)


def plan_for(model, record, **extra):
    result = preview(model, record, **extra)
    assert result['target_validated'], result
    return ChangePlan(canonical_json_bytes(result['plan']))


def apply(plan, model, **extra):
    options = dict(transaction_id='txn-evidence', authority=ALLOW)
    options.update(extra)
    return record_evidence(plan, model, **options)


def changed(record, **fields):
    return RecordArtifact(canonical_json_bytes({**record.data, **fields}), expected_type='evidence')


def extend(model, value):
    document = ModelDocument(artifact_path(value['artifact_type'], value['id'], 'SR'), canonical_json_bytes(value))
    return TargetModel(model.configuration_bytes, model.binding, (*model.documents, document),
        profile=model.profile, resource_files=model.resource_files,
        attachments=model.attachment_descriptors)


@pytest.mark.parametrize('actor_type', ['human', 'tool', 'ci'])
@pytest.mark.parametrize('with_test,attachment', [(False, False), (False, True), (True, False), (True, True)])
def test_native_record_publishes_one_exact_immutable_measurement(tmp_path, actor_type, with_test, attachment):
    root = tmp_path / 'project'; model = project(root, with_test=with_test, attachment=attachment)
    record = measurement(model, actor={'actor_type': actor_type, 'actor_id': 'recorder'})
    original = dict(model.source_files); plan = plan_for(model, record)
    result = apply(plan, model); path = artifact_path('evidence', record.id, 'SR')
    assert (root / path).read_bytes() == record.source_bytes
    assert result['command_id'] == 'evidence.record' and result['write_state'] == 'committed'
    assert result['audit']['created_ids'] == [record.id] and not result['approval_granted']
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    assert result['completion']['current_target_verified'] and not result['replayed']
    for name, raw in original.items():
        assert (root / name).read_bytes() == raw
    assert (root / 'foreign.bin').read_bytes() == b'untouched\0\xff'
    data = json.loads((root / path).read_bytes())
    assert (data['revision'], data['maturity'], data['evidence_state']) == (1, 'approved', 'recorded')
    assert data['result'] == 'failed' and data['run_context'] == record.data['run_context']
    for binding in data['subjects']:
        original_value = next(value for value in model.artifacts if value['id'] == binding['artifact_id'])
        assert binding['artifact_sha256'] == canonical_json_sha256(original_value)
        assert binding['revision'] == original_value['revision']
    proof = read_transaction_completion(ProjectSource(root), 'txn-evidence').data
    assert proof['receipt_verified'] and proof['commit_completed']


@pytest.mark.parametrize('unknown', [False, True])
@pytest.mark.parametrize('result', ['passed', 'failed', 'incomplete', 'skipped'])
def test_explicit_configuration_and_unknown_run_survive_native_publication(tmp_path, unknown, result):
    root = tmp_path / 'project'; model = project(root, configured=True)
    record = measurement(model, unknown=unknown, result=result)
    plan = plan_for(model, record); response = apply(plan, model)
    assert response['write_state'] == 'committed'
    stored = json.loads((root / artifact_path('evidence', record.id, 'SR')).read_bytes())
    effective = resolve_configuration(tuple(SourceRelations(d.content) for d in model.documents), ref('CFG'))
    assert stored['configuration_hash'] == effective.sha256 and stored['configuration_policy'] == 'bound'
    assert stored['run_context'] == record.data['run_context'] and stored['result'] == result
    assert not response['approval_granted'] and 'verification_result' not in stored


def test_preview_never_locks_allocates_or_publishes_and_can_fail_on_change(tmp_path):
    root = tmp_path / 'project'; model = project(root, attachment=True); record = measurement(model)
    before = inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
        result = preview(model, record, fail_on_change=True)
    assert result['target_validated'] and result['dry_run'] and result['exit_code'] == 1
    assert result['write_state'] == 'not_committed' and not result['audit']['approval_granted']
    assert inventory(root) == before


def test_identical_saved_request_replays_without_another_record_lock_or_replanning(tmp_path):
    root = tmp_path / 'project'; model = project(root); record = measurement(model); plan = plan_for(model, record)
    first = apply(plan, model); before = inventory(root)
    with no_write_attempts(), patch('specroad.authoring.execution.project_lock', side_effect=AssertionError('no new lock')), \
            patch('specroad.authoring.execution.assess_change_target', side_effect=AssertionError('no replan')):
        repeated = apply(plan, model, transaction_id='other-transaction')
    assert repeated['replayed'] and repeated['audit']['created_ids'] == first['audit']['created_ids']
    assert repeated['completion']['transaction_id'] == 'txn-evidence'
    assert not repeated['completion']['current_target_verified'] and inventory(root) == before


def test_same_request_with_changed_measurement_is_a_conflict(tmp_path):
    root = tmp_path / 'project'; model = project(root); record = measurement(model)
    first = plan_for(model, record); different = plan_for(model, changed(record, result='passed'))
    apply(first, model); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        apply(different, model)
    assert caught.value.exit_code == 6 and inventory(root) == before


@pytest.mark.parametrize('actor_type,request_id,code', [('ai', 'record-1', 7), ('ci', None, 2)])
def test_actor_and_request_rules_are_not_bypassed_by_recorded_approved_state(tmp_path, actor_type, request_id, code):
    root = tmp_path / 'project'; model = project(root)
    record = measurement(model, actor={'actor_type': actor_type, 'actor_id': 'caller'})
    plan = plan_for(model, record, request_id=request_id); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        apply(plan, model)
    assert caught.value.exit_code == code and inventory(root) == before


def test_authority_sees_real_writer_lock_and_denial_preserves_all_project_bytes(tmp_path):
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model, measurement(model))
    before = inventory(root); seen = []
    def deny(request):
        lock = inspect_project_lock(root).data['record']
        assert lock['kind'] == 'writer' and lock['transaction_id'] == 'txn-evidence'
        seen.append(request.data['changed_paths'])
        return False
    with pytest.raises(ModelError) as caught:
        apply(plan, model, authority=PublicationAuthority('deny', '1', deny))
    assert caught.value.exit_code == 7 and seen and inventory(root) == before


@pytest.mark.parametrize('tamper', ['subject_hash', 'contract_hash', 'configuration_hash', 'actor', 'time', 'extensions'])
def test_actual_model_and_plan_metadata_are_required_not_caller_hash_labels(tmp_path, tamper):
    root = tmp_path / 'project'; model = project(root, configured=True); record = measurement(model)
    value = record.data
    if tamper.endswith('_hash') and tamper != 'configuration_hash':
        token = ref() if tamper == 'subject_hash' else ref('VER')
        next(item for item in value['subjects'] if item['artifact_id'] == token)['artifact_sha256'] = 'f' * 64
    elif tamper == 'configuration_hash': value['configuration_hash'] = 'f' * 64
    elif tamper == 'actor': value['updated_by'] = {'actor_type': 'human', 'actor_id': 'other'}
    elif tamper == 'time': value['updated_at'] = '2026-10-19T21:31:00Z'
    else: value['extensions'] = {'sample.hidden': {'value': 'not a constructor input'}}
    forged = RecordArtifact(canonical_json_bytes(value), expected_type='evidence'); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        preview(model, forged)
    assert caught.value.reason == 'evidence_record_binding_mismatch' and inventory(root) == before


@pytest.mark.parametrize('change', ['digest', 'size', 'missing'])
def test_attachment_declarations_must_match_actual_bound_project_resources(tmp_path, change):
    root = tmp_path / 'project'; model = project(root, attachment=True); value = measurement(model).data
    if change == 'digest': value['attachments'][0]['sha256'] = 'f' * 64
    elif change == 'size': value['attachments'][0]['size'] += 1
    else: value['attachments'][0]['path'] = 'attachments/absent.bin'
    record = RecordArtifact(canonical_json_bytes(value), expected_type='evidence'); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught: preview(model, record)
    assert caught.value.reason == 'evidence_attachment_binding_mismatch' and inventory(root) == before


@pytest.mark.parametrize('resource', ['subject', 'attachment', 'extra'])
def test_live_inventory_and_resource_drift_prevent_publication(tmp_path, resource):
    root = tmp_path / 'project'; model = project(root, attachment=True); plan = plan_for(model, measurement(model))
    if resource == 'subject':
        put(root, artifact_path('requirement', ref(), 'SR'), canonical_json_bytes(domain_value('requirement', title='changed')))
    elif resource == 'attachment': (root / 'attachments/measurement.bin').write_bytes(b'changed')
    else:
        extra = domain_value('goal', id=ref('GOAL', '3'))
        put(root, artifact_path('goal', extra['id'], 'SR'), canonical_json_bytes(extra))
    before = inventory(root)
    with pytest.raises(ModelError): apply(plan, model)
    assert inventory(root) == before


@pytest.mark.parametrize('field', ['subject_id', 'subject_state_sha256'])
def test_same_namespaced_run_cannot_claim_another_measured_state(tmp_path, field):
    root = tmp_path / 'project'; model = project(root); record = measurement(model)
    previous = changed(record, id=ref('EVD', '2')).data
    previous['run_context'][field] = 'different-product' if field == 'subject_id' else 'f' * 64
    model = extend(model, previous)
    with no_write_attempts(), pytest.raises(ModelError) as caught: preview(model, record)
    assert caught.value.reason == 'evidence_run_identity_conflict'


def test_existing_approved_artifacts_still_require_their_real_semantic_service(tmp_path):
    root = tmp_path / 'project'; model = project(root); record = measurement(model)
    model = extend(model, approved_value('goal', id=ref('GOAL', '3')))
    result = preview(model, record)
    assert not result['target_validated']
    assert any(item['rationale'] == 'evidence_existing_subjects_require_service' for item in result['diagnostics'])


def test_generic_target_policy_cannot_omit_the_evidence_command_gate(tmp_path):
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model, measurement(model))
    checked = assess_change_target(plan, model, policy=TargetPolicy('change.apply', '1', ()))
    assert not checked.target_validated
    assert checked.data['missing_command_gates'] == ['extension:evidence-record']


def test_record_becomes_visible_only_as_complete_valid_json(tmp_path, monkeypatch):
    root = tmp_path / 'project'; model = project(root); record = measurement(model); plan = plan_for(model, record)
    native = os.replace; seen = []
    def replace(source, target, **options):
        if str(target).startswith('SR-EVD-'):
            assert inspect_project_lock(root).data['record']['kind'] == 'writer'
            result = native(source, target, **options)
            actual = (root / artifact_path('evidence', record.id, 'SR')).read_bytes()
            assert RecordArtifact(actual, expected_type='evidence').data == record.data
            seen.append(actual)
            return result
        return native(source, target, **options)
    monkeypatch.setattr(os, 'replace', replace)
    apply(plan, model)
    assert seen == [record.source_bytes]


@pytest.mark.parametrize('route', ['mapping', 'file', 'stdin', 'argv'])
def test_record_input_routes_share_exact_operation_and_explicit_run_contents(tmp_path, route):
    root = tmp_path / 'project'; model = project(root); record = measurement(model)
    path = tmp_path / 'record.json'; value = record.data; run = value.pop('run_context')
    path.write_bytes(canonical_json_bytes(value)); run_path = tmp_path / 'run.json'
    run_path.write_bytes(canonical_json_bytes(run))
    expected = prepare_evidence_operation(ref('VER'), record)
    before = inventory(root)
    with no_write_attempts():
        if route == 'mapping': actual = prepare_evidence_operation(ref('VER'), record)
        elif route == 'argv': actual = parse_evidence_record_input([ref('VER'), '--input', str(path), '--run-context', str(run_path)])
        else: actual = read_evidence_record_input(ref('VER'), input=str(path) if route == 'file' else '-',
            run_context=str(run_path), stdin=BytesIO(path.read_bytes()))
    assert actual.data == expected.data and inventory(root) == before


def test_conflicting_explicit_run_file_does_not_overwrite_record_provenance(tmp_path):
    root = tmp_path / 'project'; model = project(root); record = measurement(model)
    path = tmp_path / 'record.json'; path.write_bytes(record.source_bytes)
    run = tmp_path / 'run.json'; run.write_bytes(canonical_json_bytes({**record.data['run_context'], 'run_id': 'other:run'}))
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        read_evidence_record_input(ref('VER'), input=str(path), run_context=str(run))
    assert caught.value.reason == 'evidence_run_context_conflict' and caught.value.exit_code == 3
    assert path.read_bytes() == record.source_bytes and inventory(root) == before


@pytest.mark.parametrize('verification_id', [ref('VER', '2'), ref()])
def test_named_verification_must_be_the_recorded_contract(tmp_path, verification_id):
    model = project(tmp_path / 'project'); record = measurement(model)
    with pytest.raises(ModelError): prepare_evidence_operation(verification_id, record)


@pytest.mark.parametrize('reservation', ['current', 'reserved_artifact_ids', 'previously_approved_ids'])
def test_record_identity_cannot_overwrite_or_reuse_known_project_history(tmp_path, reservation):
    root = tmp_path / 'project'; model = project(root); record = measurement(model)
    if reservation == 'current':
        model = extend(model, record.data)
    else:
        model = TargetModel(model.configuration_bytes, model.binding, model.documents,
            profile=model.profile, resource_files=model.resource_files,
            **{reservation: [record.id]})
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as caught: preview(model, record)
    assert caught.value.reason == 'evidence_identity_exists' and inventory(root) == before


@pytest.mark.parametrize('selection', [None, ref('CFG', '2')])
def test_bound_configuration_must_be_selected_explicitly_from_actual_model(tmp_path, selection):
    root = tmp_path / 'project'; model = project(root, configured=True); record = measurement(model)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError):
        preview(model, record, configuration_id=selection)
    assert inventory(root) == before


def test_saved_plan_does_not_authorize_changed_measurement_bytes(tmp_path):
    root = tmp_path / 'project'; model = project(root); plan = plan_for(model, measurement(model))
    value = plan.data; value['operations'][0]['evidence']['result'] = 'passed'
    value['result_artifacts'][0]['artifact'] = value['operations'][0]['evidence']
    value['result_artifacts'][0]['sha256'] = canonical_json_sha256(value['operations'][0]['evidence'])
    value.pop('change_plan_sha256')
    forged = prepare_change_plan(value); before = inventory(root)
    with pytest.raises(ModelError): apply(forged, model)
    assert inventory(root) == before


def test_attachment_change_during_authorization_is_rechecked_before_any_record_write(tmp_path):
    root = tmp_path / 'project'; model = project(root, attachment=True)
    record = measurement(model); plan = plan_for(model, record); before = inventory(root)
    seen = []
    def allow_after_change(request):
        assert inspect_project_lock(root).data['record']['kind'] == 'writer'
        (root / 'attachments/measurement.bin').write_bytes(b'changed by host callback')
        seen.append(request.data)
        return True
    with pytest.raises(ModelError):
        apply(plan, model, authority=PublicationAuthority('drifting-host', '1', allow_after_change))
    assert seen and not (root / artifact_path('evidence', record.id, 'SR')).exists()
    after = inventory(root)
    assert tuple(item for item in after if item[0] != 'attachments/measurement.bin') == tuple(
        item for item in before if item[0] != 'attachments/measurement.bin')


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_real_evidence_recording_and_replay_work_in_isolated_core_and_pyz(tmp_path, mode):
    root = tmp_path / 'project'; model = project(root, configured=True, with_test=True, attachment=True)
    record = measurement(model); original = dict(model.source_files)
    body = '''import json
from pathlib import Path
from specroad.authoring.evidence import preview_evidence_record, record_evidence
from specroad.changes import ChangePlan, TargetModel, PublicationAuthority
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes
from specroad.model.language_registry import LanguageRegistry
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.storage.record_artifact import RecordArtifact
from specroad.validation import ModelDocument
'''
    body += 'root=Path(' + repr(str(root)) + ')\n'
    body += 'documents=' + repr([d.path for d in model.documents]) + '\n'
    body += 'resources=' + repr([d.path for d in model.resource_files]) + '\n'
    body += 'attachments=' + repr([a.data for a in model.attachment_descriptors]) + '\n'
    body += 'record=RecordArtifact(' + repr(record.source_bytes) + ',expected_type="evidence")\n'
    body += '''configuration=(root / 'specroad.json').read_bytes()
config=json.loads(configuration)
binding=config['language_registry']
registry=LanguageRegistry((root / binding['path']).read_bytes(),
    expected_sha256=binding['sha256'],expected_version=binding['registry_version'])
profile=ProfileResource((root / 'profiles/core.json').read_bytes())
effective=compose_profiles([profile],core_key=profile.key,language_registry=registry)
info=root.stat()
model=TargetModel(configuration,ProjectReadBinding(config['project_id'],str(root),(info.st_dev,info.st_ino)),
    [ModelDocument(name,(root/name).read_bytes()) for name in documents],profile=effective,
    resource_files=[ModelDocument(name,(root/name).read_bytes()) for name in resources],
    attachments=[AttachmentDescriptor.from_data(a) for a in attachments])
'''
    body += 'preview=preview_evidence_record(model,' + repr(ref('VER')) + ',record,actor=' + repr(ACTOR)
    body += ',planned_at=' + repr(TIME) + ',change_plan_id="CP-isolated",request_id="record-isolated",configuration_id=' + repr(ref('CFG')) + ')\n'
    body += '''assert preview['target_validated'], preview
plan=ChangePlan(canonical_json_bytes(preview['plan']))
authority=PublicationAuthority('isolated-host','1',lambda request: True)
first=record_evidence(plan,model,transaction_id='isolated-evidence',authority=authority)
second=record_evidence(plan,model,transaction_id='repeat-evidence',authority=authority)
print(json.dumps([first,second]))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    first, repeated = json.loads(result.stdout)
    assert first['write_state'] == 'committed' and first['audit']['created_ids'] == [record.id]
    assert repeated['replayed'] and repeated['audit']['created_ids'] == [record.id]
    assert (root / artifact_path('evidence', record.id, 'SR')).read_bytes() == record.source_bytes
    assert all((root / name).read_bytes() == raw for name, raw in original.items())
