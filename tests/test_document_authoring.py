"""Actual document Change Plans, native publication and byte-exact inventories."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from specroad.authoring.documents import (preview_document_create, preview_section_add,
                                         preview_section_move)
from specroad.authoring.execution import apply_authoring_plan
from specroad.authoring import execution
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.authoring.plans import preview_authoring_request
from specroad.changes import (AuthoringError, ChangePlan, PublicationAuthority,
                              PublicationCheckError, TargetError, inspect_project_lock)
from specroad.changes.receipt_values import TransactionReceipt
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.paths import artifact_path
from specroad.model.relation_values import RelationIdentity
from support.domain import domain_value
from support.inspection import inspection_project
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from test_authoring_inputs import fields
from test_document_structure import contains, section

ACTOR = {'actor_type': 'human', 'actor_id': 'document-editor'}
TIME = '2026-10-17T00:30:00Z'
CASES = ('first_document', 'supporting_document', 'root_section', 'nested_section',
         'move_document', 'move_section', 'reorder', 'promote')


def document_project(root, *, first=False, extra=()):
    values = [domain_value('goal')]
    if not first:
        values += [record_value('document', relations=[contains(ref('SEC'), '0', 4)]),
            record_value('document', id=ref('DOC', '1'), document_role='supporting',
                         relations=[contains(ref('SEC', '2'), '2', 8)]),
            section(relations=[contains(ref('SEC', '1'), '1', 2)]), section('1'), section('2')]
    model = inspection_project(root, artifacts=values + list(extra))
    (root / 'foreign.bin').write_bytes(b'unchanged\0\xff')
    return model


def preview_case(model, case, **overrides):
    options = {'actor': ACTOR, 'planned_at': TIME, 'change_plan_id': 'CP-document',
               'request_id': 'document-request', **overrides}
    edge = RelationIdentity('REL-' + '3' * 26, 'random128-v1')
    if case in ('first_document', 'supporting_document'):
        value = fields('document')
        if case == 'supporting_document': value['document_role'] = 'supporting'
        return preview_document_create(model, normalize_artifact_create_input('document', value),
            identity=ArtifactIdentity(ref('DOC', '2'), 'random128-v1', 'document', 'SR'), **options)
    if case in ('root_section', 'nested_section'):
        return preview_section_add(model, normalize_artifact_create_input('section', fields('section')),
            identity=ArtifactIdentity(ref('SEC', '3'), 'random128-v1', 'section', 'SR'),
            parent_id=ref('DOC') if case == 'root_section' else ref('SEC', '1'),
            relation_identity=edge, position=11, **options)
    child = ref('SEC', '1') if case == 'promote' else ref('SEC')
    parents = {'move_document': ref('DOC', '1'), 'move_section': ref('SEC', '2'),
               'reorder': ref('DOC'), 'promote': ref('DOC', '1')}
    original = next(edge for value in model.artifacts for edge in value['relations']
                    if edge['type'] == 'contains' and edge['target'] == child)
    return preview_section_move(model, child, parent_id=parents[case], relation_identity=edge,
        position=19, expected_relation_sha256=canonical_json_sha256(original),
        reason='Reorganize the document.', **options)


def saved(report):
    return ChangePlan(canonical_json_bytes(report['plan']))


def apply(root, model, report, *, authority=None, gates=(), transaction='txn-document'):
    if authority is None:
        def authorize(request):
            assert inspect_project_lock(root).data['record']['kind'] == 'writer'
            assert request.plan.source_bytes == saved(report).source_bytes
            return True
        authority = PublicationAuthority('owned-document-host', '1', authorize)
    return apply_authoring_plan(saved(report), model, command_id=report['command_id'],
        transaction_id=transaction, authority=authority, gates=gates)


@pytest.mark.parametrize('case', CASES)
def test_saved_document_plan_publishes_only_expected_files_and_replays(tmp_path, case):
    root = tmp_path / 'project'; model = document_project(root, first=case == 'first_document')
    before = inventory(root)
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('prepared IDs only')):
        report = preview_case(model, case, fail_on_change=True)
    assert inventory(root) == before
    assert report['target_validated'] and report['exit_code'] == 1 and report['would_change']
    assert report['dry_run'] and report['write_state'] == 'not_committed'
    assert not report['approval_granted'] and report['backend_receipt'] is None
    operations = report['plan']['operations']
    old = {value['id']: value for value in model.artifacts}; expected = deepcopy(old)
    affected, created = set(), set()
    for op in operations:
        if op['op'] == 'create':
            value = deepcopy(op['artifact']); expected[value['id']] = value; created.add(value['id'])
        elif op['op'] == 'relation_remove':
            affected.add(op['source'])
            expected[op['source']]['relations'] = [edge for edge in expected[op['source']]['relations']
                                                  if edge['relation_id'] != op['relation_id']]
        else:
            assert op['op'] == 'relation_add'
            affected.add(op['source']); expected[op['source']]['relations'].append(op['relation'])
    for identity in affected:
        expected[identity]['revision'] += 1
        expected[identity]['updated_by'] = ACTOR; expected[identity]['updated_at'] = TIME
    with patch('secrets.token_bytes', side_effect=AssertionError('no reallocation')):
        result = apply(root, model, report)
    assert result['write_state'] == 'committed' and result['exit_code'] == 0 and not result['replayed']
    assert result['target_model_root_sha256'] == report['expected_model_root']
    assert result['audit'] == {**report['audit'], 'dry_run': False, 'write_state': 'committed'}
    assert result['completion']['current_target_verified'] and result['completion']['cleanup_completed']
    paths = set()
    for identity in affected | created:
        value = expected[identity]; path = artifact_path(value['artifact_type'], identity, 'SR')
        paths.add(path)
        assert json.loads((root / path).read_bytes()) == value
        assert (root / path).read_bytes() == canonical_json_bytes(value)
    after = {entry[0]: entry[1:] for entry in inventory(root)}
    for path, *entry in before:
        if path not in paths: assert after[path] == tuple(entry)
    actual_artifact_paths = {str(path.relative_to(root)) for path in root.rglob('*.json')
                            if str(path.relative_to(root)).startswith('spec/')}
    assert actual_artifact_paths == {artifact_path(v['artifact_type'], v['id'], 'SR') for v in expected.values()}
    receipt_path = result['completion']['receipts']['transaction']['path']
    receipt = TransactionReceipt((root / receipt_path).read_bytes()).data
    assert receipt['journal']['plan_sha256'] == report['plan_sha256'] and receipt['operations'] == operations
    assert set(result['audit']['created_ids']) == created | {
        op['relation']['relation_id'] for op in operations if op['op'] == 'relation_add'}
    before_retry = inventory(root)
    with no_write_attempts(), patch.object(execution, 'project_lock', side_effect=AssertionError('replay before lock')):
        repeated = apply(root, model, report, transaction='txn-retry')
    assert repeated['replayed'] and repeated['completion']['receipts'] == result['completion']['receipts']
    assert not repeated['completion']['current_target_verified'] and inventory(root) == before_retry


@pytest.mark.parametrize('case', ['supporting_document', 'root_section', 'move_document'])
def test_host_denial_cannot_publish_document_changes(tmp_path, case):
    root = tmp_path / 'project'; model = document_project(root)
    report = preview_case(model, case); before = inventory(root)
    with pytest.raises(PublicationCheckError) as error:
        apply(root, model, report, authority=PublicationAuthority('denied-host', '1', lambda request: False))
    assert error.value.exit_code == 7 and inventory(root) == before


@pytest.mark.parametrize('kind', ['content_block', 'view'])
def test_unavailable_specialist_is_never_replaced_by_document_section_checks(tmp_path, kind):
    extra = record_value(kind)
    if kind == 'view':
        extra['scope_descriptor'] = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
            'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}
    root = tmp_path / 'project'; model = document_project(root, extra=[extra]); before = inventory(root)
    report = preview_case(model, 'root_section')
    assert not report['target_validated'] and report['exit_code'] == 1
    assert 'document_authoring_specialist_required' in {item['reason'] for stage in report['assessment']['validation']['source_report']['stages']
            for item in stage['diagnostics']}
    with pytest.raises(TargetError): apply(root, model, report)
    assert inventory(root) == before


@pytest.mark.parametrize('case', ['supporting_document', 'root_section', 'move_document'])
@pytest.mark.parametrize('actor,request_id,code', [('ai', 'request', 7), ('ci', None, 2)])
def test_document_preview_never_authorizes_direct_actor_writes(tmp_path, case, actor, request_id, code):
    root = tmp_path / 'project'; model = document_project(root)
    report = preview_case(model, case, actor={'actor_type': actor, 'actor_id': 'caller'}, request_id=request_id)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(AuthoringError) as error: apply(root, model, report)
    assert error.value.exit_code == code and inventory(root) == before


@pytest.mark.parametrize('case', ['supporting_document', 'root_section', 'move_document'])
def test_document_command_cannot_smuggle_an_unrelated_operation(tmp_path, case):
    root = tmp_path / 'project'; model = document_project(root); report = preview_case(model, case)
    operations = report['plan']['operations']
    operations.append({'op': 'relation_add', 'source': ref('DOC'), 'relation': contains(ref('SEC'), '6')})
    before = inventory(root)
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        preview_authoring_request(model, report['command_id'], operations, actor=ACTOR, planned_at=TIME,
                                  change_plan_id='CP-smuggled')
    assert error.value.reason == 'document_command_operation_mismatch' and inventory(root) == before


def test_existing_single_operation_family_does_not_gain_document_multioperation_permission(tmp_path):
    model = document_project(tmp_path / 'project'); report = preview_case(model, 'root_section')
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        preview_authoring_request(model, 'artifact.create', report['plan']['operations'], actor=ACTOR,
                                  planned_at=TIME, change_plan_id='CP-wrong-family')
    assert error.value.reason == 'one_authoring_operation_required'


@pytest.mark.parametrize('case', ['first_document', 'supporting_document'])
def test_create_enforces_the_actual_full_project_primary_role(tmp_path, case):
    root = tmp_path / 'project'; model = document_project(root, first=case == 'first_document')
    value = fields('document')
    value['document_role'] = 'supporting' if case == 'first_document' else 'primary_specification'
    before = inventory(root)
    report = preview_document_create(model, normalize_artifact_create_input('document', value),
        identity=ArtifactIdentity(ref('DOC', '2'), 'random128-v1', 'document', 'SR'), actor=ACTOR,
        planned_at=TIME, change_plan_id='CP-primary', request_id='primary-request')
    assert not report['target_validated'] and report['exit_code'] == 1
    reason = 'document_primary_missing' if case == 'first_document' else 'document_primary_multiple'
    assert reason in {item['reason'] for stage in report['assessment']['validation']['source_report']['stages']
            for item in stage['diagnostics']}
    with pytest.raises(TargetError): apply(root, model, report)
    assert inventory(root) == before


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_document_plan_and_native_writer_are_available_in_isolated_distributions(tmp_path, mode):
    root = tmp_path / 'project'; model = document_project(root, first=True)
    body = '''import json
from pathlib import Path
from specroad.authoring.documents import preview_document_create
from specroad.authoring.execution import apply_authoring_plan
from specroad.authoring.inputs import normalize_artifact_create_input
from specroad.changes import TargetModel, ChangePlan, PublicationAuthority
from specroad.model.canonical import canonical_json_bytes
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.language_registry import LanguageRegistry
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'root=Path(' + repr(str(root)) + ')\n'
    body += 'config=' + repr(model.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in model.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in model.resource_files]) + '\n'
    body += ('registry=LanguageRegistry(' + repr(model.language_registry.source_bytes)
             + ', expected_sha256=' + repr(model.language_registry.sha256)
             + ', expected_version=' + repr(model.language_registry.version) + ')\n')
    body += 'core_key=' + repr(model.profile.profile_chain[0]) + '\n'
    body += 'profiles=' + repr([profile.source_bytes for profile in model.profile_resources]) + '\n'
    body += 'fields=' + repr(fields('document')) + '\n'
    body += 'actor=' + repr(ACTOR) + '\n'
    body += 'planned_at=' + repr(TIME) + '\n'
    body += '''info=root.stat()
profile=compose_profiles([ProfileResource(raw) for raw in profiles],
 core_key=core_key,language_registry=registry)
owned=TargetModel(config,ProjectReadBinding(json.loads(config)['project_id'],str(root),(info.st_dev,info.st_ino)),
 [ModelDocument(path,raw) for path,raw in documents],profile=profile,
 resource_files=[ModelDocument(path,raw) for path,raw in resources])
identity=ArtifactIdentity('SR-DOC-'+'2'*26,'random128-v1','document','SR')
preview=preview_document_create(owned,normalize_artifact_create_input('document',fields),identity=identity,
 actor=actor,planned_at=planned_at,change_plan_id='CP-portable',request_id='portable-document')
result=apply_authoring_plan(ChangePlan(canonical_json_bytes(preview['plan'])),owned,
 command_id='document.create',transaction_id='txn-portable',
 authority=PublicationAuthority('owned-portable-host','1',lambda request: True))
print(json.dumps({'write_state':result['write_state'],'validated':preview['target_validated'],
 'verified':result['completion']['current_target_verified'],'artifact':json.loads((root/identity.path).read_bytes())}))
'''
    script = tmp_path / 'portable_document_authoring.py'
    script.write_text(body)
    loader = 'import runpy;runpy.run_path(' + repr(str(script)) + ')\n'
    if mode == 'core': result = run_core(loader, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + loader], tmp_path, capture=True)
    (tmp_path / 'portable_stderr.txt').write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    observed = json.loads(result.stdout)
    assert observed['write_state'] == 'committed' and observed['validated'] and observed['verified']
    artifact = observed['artifact']
    assert artifact['id'] == ref('DOC', '2') and artifact['revision'] == 1 and artifact['maturity'] == 'draft'
    assert {key: artifact[key] for key in fields('document')} == fields('document')
    assert artifact['created_at'] == artifact['updated_at'] == TIME
    assert artifact['created_by'] == artifact['updated_by'] == ACTOR
