"""A complete Generic measurement set uses one native saved-plan transaction."""
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.authoring.evidence_import import preview_generic_import, import_evidence
from specroad.authoring.plans import preview_authoring_request
from specroad.changes import ChangePlan, TargetModel, PublicationAuthority, read_transaction_completion
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.storage.project import ProjectSource
from specroad.validation import ModelDocument
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import ref
from test_evidence_recording import project, measurement, ACTOR, TIME, ALLOW

SOURCE = 'attachments/import.json'


def import_project(root, *, with_test=False, configured=False, attachment=False,
                   outcome='failed', mutate=None):
    model = project(root, with_test=with_test, configured=configured, attachment=attachment)
    record = measurement(model, result=outcome).data
    observation = {'target_id': ref('VER'), 'check_id': 'overall',
        'test_id': record['run_context']['test_id'], 'result': outcome,
        'produced_at': record['produced_at'], 'subject_ids': [s['artifact_id'] for s in record['subjects']],
        'attachment_paths': [a['path'] for a in record.get('attachments', [])]}
    value = {'format_version': 'specroad-evidence-exchange-v1',
        'producer': record['producer'], 'tool': record['tool'],
        'run': {k: record['run_context'][k] for k in ('subject_id', 'subject_state_sha256', 'run_id')},
        'subjects': record['subjects'], 'results': [observation, {**observation,
            'produced_at': '2026-10-19T21:01:00Z'}], 'environment': record['environment'],
        'attachments': record.get('attachments', []), 'configuration_hash': record['configuration_hash'],
        'configuration_policy': record['configuration_policy']}
    if mutate:
        mutate(value)
    raw = canonical_json_bytes(value)
    descriptor = AttachmentDescriptor(SOURCE, 'application/json', len(raw), sha256(raw).hexdigest())
    model = TargetModel(model.configuration_bytes, model.binding, model.documents,
        profile=model.profile, resource_files=(*model.resource_files, ModelDocument(SOURCE, raw)),
        attachments=(*model.attachment_descriptors, descriptor))
    put(root, SOURCE, raw)
    return model


def preview(model, **extra):
    options = dict(source_path=SOURCE, policy='abort_import',
        evidence_ids=[ref('EVD', '1'), ref('EVD', '2')], title='Imported measurement',
        actor=ACTOR, planned_at=TIME, change_plan_id='CP-import', request_id='import-1',
        configuration_id=ref('CFG') if any(a['artifact_type'] == 'configuration'
            for a in model.artifacts) else None)
    options.update(extra)
    return preview_generic_import(model, **options)


def saved(model, **extra):
    result = preview(model, **extra)
    assert result['target_validated'], result
    return ChangePlan(canonical_json_bytes(result['plan']))


def apply(plan, model, **extra):
    options = dict(transaction_id='txn-import', authority=ALLOW)
    options.update(extra)
    return import_evidence(plan, model, **options)


@pytest.mark.parametrize('with_test,configured,attachment',
    [(False, False, False), (True, False, True), (True, True, True)])
@pytest.mark.parametrize('outcome', ['passed', 'failed', 'incomplete', 'skipped', 'unclassified'])
def test_complete_import_is_one_transaction_preserving_subjects_and_originals(
        tmp_path, with_test, configured, attachment, outcome):
    root = tmp_path / 'project'
    model = import_project(root, with_test=with_test, configured=configured,
        attachment=attachment, outcome=outcome)
    original = dict(model.source_files)
    plan = saved(model)
    response = apply(plan, model)
    assert response['command_id'] == 'evidence.import'
    assert response['write_state'] == 'committed' and not response['approval_granted']
    assert response['audit']['created_ids'] == [ref('EVD', '1'), ref('EVD', '2')]
    contexts = [op['import_context'] for op in plan.data['operations']]
    assert contexts[0] == contexts[1]
    assert contexts[0]['source_sha256'] == sha256(original[SOURCE]).hexdigest()
    for op in plan.data['operations']:
        record = op['evidence']
        raw = (root / artifact_path('evidence', record['id'], 'SR')).read_bytes()
        assert raw == canonical_json_bytes(record)
        assert record['result'] == outcome and record['origin'] == 'imported_generic'
        assert any(a['path'] == SOURCE and a['sha256'] == sha256(original[SOURCE]).hexdigest()
                   for a in record['attachments'])
        provenance, = record['provenance']
        assert provenance['content_sha256'] == contexts[0]['source_sha256']
        assert provenance['extensions']['specroad.evidence-import']['preparation_sha256'] == contexts[0]['preparation_sha256']
        assert record['revision'] == 1 and record['evidence_state'] == 'recorded'
    for path, raw in original.items():
        assert (root / path).read_bytes() == raw
    assert (root / 'foreign.bin').read_bytes() == b'untouched\0\xff'
    proof = read_transaction_completion(ProjectSource(root), 'txn-import').data
    assert proof['receipt_verified'] and proof['commit_completed'] and proof['cleanup_completed']


def test_preview_is_read_only_and_replay_returns_original_complete_set(tmp_path):
    root = tmp_path / 'project'; model = import_project(root)
    before = inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no IDs')):
        plan = saved(model)
    assert inventory(root) == before
    first = apply(plan, model)
    before = inventory(root)
    with no_write_attempts(), patch('specroad.authoring.execution.project_lock',
            side_effect=AssertionError('no new lock')), patch(
            'specroad.authoring.execution.assess_change_target', side_effect=AssertionError('no replanning')):
        replay = apply(ChangePlan(plan.source_bytes), model, transaction_id='another-transaction')
    assert replay['replayed']
    assert replay['audit']['created_ids'] == first['audit']['created_ids']
    assert replay['completion']['transaction_id'] == 'txn-import'
    assert not replay['completion']['current_target_verified']
    assert inventory(root) == before


@pytest.mark.parametrize('mutation', ['drop', 'reorder', 'source_hash', 'preparation_hash',
                                     'provenance', 'configuration', 'plain_record', 'mixed'])
def test_incomplete_or_forged_set_is_rejected_before_publication(tmp_path, mutation):
    root = tmp_path / 'project'; model = import_project(root)
    operations = saved(model).data['operations']
    if mutation == 'drop': operations.pop()
    elif mutation == 'reorder': operations.reverse()
    elif mutation == 'source_hash': operations[0]['import_context']['source_sha256'] = 'f' * 64
    elif mutation == 'preparation_hash':
        for op in operations: op['import_context']['preparation_sha256'] = 'f' * 64
    elif mutation == 'provenance': operations[0]['evidence']['provenance'][0]['content_sha256'] = 'f' * 64
    elif mutation == 'configuration': operations[1]['configuration_id'] = ref('CFG')
    elif mutation == 'plain_record':
        for op in operations: op.pop('import_context')
    else: operations[1].pop('import_context')
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError):
        preview_authoring_request(model, 'evidence.import', operations, actor=ACTOR,
            planned_at=TIME, change_plan_id='CP-forged', request_id='forged')
    assert inventory(root) == before


@pytest.mark.parametrize('mutation', ['contract', 'slot', 'empty', 'missing_attachment'])
def test_unusable_source_has_no_partial_set_or_write(tmp_path, mutation):
    def mutate(value):
        if mutation == 'contract': value['results'][1]['target_id'] = ref()
        elif mutation == 'slot': value['results'][1]['check_id'] = 'absent'
        elif mutation == 'empty': value['results'] = []
        else:
            value['attachments'] = [{'path': 'attachments/absent.txt', 'size': 3,
                'sha256': sha256(b'abc').hexdigest(), 'media_type': 'text/plain'}]
            value['results'][1]['attachment_paths'] = ['attachments/absent.txt']
    root = tmp_path / 'project'; model = import_project(root, mutate=mutate)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError):
        preview(model)
    assert inventory(root) == before


def test_explicit_skip_policy_plans_all_and_only_accepted_observations(tmp_path):
    def mutate(value):
        value['results'].append({**value['results'][0], 'target_id': ref('VER', '3')})
    root = tmp_path / 'project'; model = import_project(root, mutate=mutate)
    with no_write_attempts(), pytest.raises(ModelError):
        preview(model)
    prepared = preview(model, policy='skip_invalid_with_diagnostic')
    assert prepared['target_validated']
    details = prepared['import_preparation']
    assert details['candidate_count'] == 2 and details['diagnostics']
    assert details['rejected_occurrences'] == ['/results/2']
    assert not details['write_authorized'] and not details['approval_granted']
    plan = ChangePlan(canonical_json_bytes(prepared['plan']))
    assert all(op['import_context']['preparation_sha256'] == canonical_json_sha256(details)
               for op in plan.data['operations'])
    details['candidates'].clear()
    result = apply(plan, model)
    assert result['audit']['created_ids'] == [ref('EVD', '1'), ref('EVD', '2')]
    assert len(plan.data['operations']) == 2
    assert all(op['import_context']['policy'] == 'skip_invalid_with_diagnostic' for op in plan.data['operations'])


@pytest.mark.parametrize('evidence_ids', [[], [ref('EVD', '1')],
    [ref('EVD', '1'), ref('EVD', '1')], [ref('REQ'), ref('EVD', '2')]])
def test_caller_must_supply_distinct_evidence_ids_for_exact_complete_set(tmp_path, evidence_ids):
    root = tmp_path / 'project'; model = import_project(root); before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError):
        preview(model, evidence_ids=evidence_ids)
    assert inventory(root) == before


def test_authority_denial_keeps_entire_set_and_project_unwritten(tmp_path):
    root = tmp_path / 'project'; model = import_project(root); plan = saved(model)
    before = inventory(root); seen = []
    def deny(request):
        seen.append(request.data['changed_paths'])
        return False
    with pytest.raises(ModelError) as caught:
        apply(plan, model, authority=PublicationAuthority('import-deny', '1', deny))
    assert caught.value.exit_code == 7 and seen
    assert set(seen[0]) == {artifact_path('evidence', ref('EVD', token), 'SR') for token in ('1', '2')}
    assert inventory(root) == before


def test_changed_live_original_blocks_the_entire_saved_import(tmp_path):
    root = tmp_path / 'project'; model = import_project(root); plan = saved(model)
    (root / SOURCE).write_bytes(b'changed source')
    before = inventory(root)
    with pytest.raises(ModelError):
        apply(plan, model)
    assert inventory(root) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_saved_set_and_durable_replay_survive_separate_isolated_processes(tmp_path, mode):
    root = tmp_path / 'project'
    model = import_project(root, configured=True, with_test=True, attachment=True)
    plan = saved(model)
    body = '''import json
from pathlib import Path
from specroad.authoring.evidence_import import import_evidence
from specroad.changes import ChangePlan, TargetModel, PublicationAuthority
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.language_registry import LanguageRegistry
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'root=Path(' + repr(str(root)) + ')\n'
    body += 'documents=' + repr([d.path for d in model.documents]) + '\n'
    body += 'resources=' + repr([d.path for d in model.resource_files]) + '\n'
    body += 'attachments=' + repr([a.data for a in model.attachment_descriptors]) + '\n'
    body += 'plan=ChangePlan(' + repr(plan.source_bytes) + ')\n'
    body += '''configuration=(root/'specroad.json').read_bytes()
config=json.loads(configuration)
binding=config['language_registry']
registry=LanguageRegistry((root/binding['path']).read_bytes(),
    expected_sha256=binding['sha256'],expected_version=binding['registry_version'])
profile=ProfileResource((root/'profiles/core.json').read_bytes())
effective=compose_profiles([profile],core_key=profile.key,language_registry=registry)
info=root.stat()
model=TargetModel(configuration,ProjectReadBinding(config['project_id'],str(root),(info.st_dev,info.st_ino)),
    [ModelDocument(n,(root/n).read_bytes()) for n in documents],profile=effective,
    resource_files=[ModelDocument(n,(root/n).read_bytes()) for n in resources],
    attachments=[AttachmentDescriptor.from_data(a) for a in attachments])
authority=PublicationAuthority('isolated-import','1',lambda request: True)
print(json.dumps(import_evidence(plan,model,transaction_id='isolated-import',authority=authority)))
'''
    if mode == 'pyz':
        _, package = build_distribution(tmp_path / 'distribution')
    def run():
        if mode == 'core':
            return run_core(body, tmp_path, capture=True)
        return run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    first = run()
    assert first.returncode == 0, first.stderr
    before = inventory(root)
    second = run()
    assert second.returncode == 0, second.stderr
    first, second = json.loads(first.stdout), json.loads(second.stdout)
    assert first['write_state'] == 'committed' and not first['replayed']
    assert second['replayed'] and second['audit']['created_ids'] == first['audit']['created_ids']
    assert second['audit']['created_ids'] == [ref('EVD', '1'), ref('EVD', '2')]
    assert inventory(root) == before
