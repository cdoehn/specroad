"""Real locked allocation, native publication, target gates and historical retry."""
from io import BytesIO
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.authoring import creation
from specroad.authoring.creation import create_artifact
from specroad.authoring.inputs import normalize_artifact_create_input, read_artifact_create_input
from specroad.changes import (AuthoringError, ChangePlanError, TargetError, TargetModel,
    PublicationAuthority, inspect_project_lock, read_transaction_completion)
from specroad.model.canonical import canonical_json_bytes
from specroad.model.identities import IdentityInventory
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.profiles import ProfileResource, compose_profiles
from specroad.storage.language_registry import bundled_language_registry, registry_binding
from specroad.storage.project import ProjectSource
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.model import configuration_value, put
from support.profiles import profile_data
from support.read_only import inventory as file_inventory, no_write_attempts
from test_authoring_inputs import fields

ACTOR = {'actor_type': 'human', 'actor_id': 'creator'}
TIME = '2026-10-10T11:00:00Z'
ALLOW = PublicationAuthority('owned-test-host', '1', lambda request: True)
AVAILABLE = ('goal', 'need', 'capability', 'requirement', 'scenario', 'decision', 'risk',
             'assumption', 'component', 'interface', 'release', 'milestone', 'task', 'term', 'issue')
SPECIALIST_GATES = ('source', 'verification', 'test', 'document', 'section',
                    'content_block', 'view', 'code_ref', 'configuration')


def project(root, kind='goal', *, broken=False):
    root.mkdir()
    registry = bundled_language_registry(); binding = registry_binding(registry)
    config = configuration_value(language_registry=binding)
    profile = ProfileResource(canonical_json_bytes(profile_data(profile_id='core')))
    effective = compose_profiles([profile], core_key=profile.key, language_registry=registry)
    values = [domain_value('goal')]
    if kind == 'interface':
        values += [domain_value('component'),
                   domain_value('component', id='SR-COMP-' + '1' * 26)]
    if kind == 'milestone': values.append(domain_value('release'))
    if kind == 'verification': values.append(domain_value('requirement'))
    if broken: values[0].pop('statement')
    state = root.stat()
    model = TargetModel(canonical_json_bytes(config),
        ProjectReadBinding(config['project_id'], str(root), (state.st_dev, state.st_ino)),
        [ModelDocument(artifact_path(v['artifact_type'], v['id'], 'SR'), canonical_json_bytes(v))
         for v in values], profile=effective,
        resource_files=[ModelDocument('profiles/core.json', profile.source_bytes),
                        ModelDocument(binding['path'], registry.source_bytes)])
    for name, raw in model.source_files.items(): put(root, name, raw)
    (root / '.specroad/locks').mkdir(parents=True)
    (root / 'foreign.bin').write_bytes(b'untouched\0\xff')
    ids = IdentityInventory('SR', [v['id'] for v in values], (), ())
    return model, ids


def arguments(model, ids):
    return dict(inventory=ids, actor=ACTOR, planned_at=TIME, change_plan_id='CP-create',
        transaction_id='txn-create', authority=ALLOW, request_id='create-1')


@pytest.mark.parametrize('kind', AVAILABLE)
@pytest.mark.parametrize('route', ['mapping', 'file', 'stdin'])
def test_native_create_publishes_exact_draft_under_its_allocated_path(tmp_path, kind, route):
    root = tmp_path / 'project'; model, ids = project(root, kind)
    value = fields(kind); raw = json.dumps(value).encode()
    path = tmp_path / 'fields.json'; path.write_bytes(raw)
    prepared = (normalize_artifact_create_input(kind, value) if route == 'mapping'
        else read_artifact_create_input(kind, input=str(path) if route == 'file' else '-', stdin=BytesIO(raw)))
    original = file_inventory(root); allocations = []
    def entropy(size):
        status = inspect_project_lock(root).data
        assert status['record']['kind'] == 'writer' and status['record']['transaction_id'] == 'txn-create'
        assert size == 16
        allocations.append(size)
        return b'\x55' * size
    with patch('secrets.token_bytes', side_effect=entropy):
        result = create_artifact(model, prepared, **arguments(model, ids))
    target = root / result['path']; artifact = json.loads(target.read_bytes())
    assert target.read_bytes() == canonical_json_bytes(artifact)
    assert {k: artifact[k] for k in value} == value
    assert result['format_version'] == '1.0.0' and result['write_state'] == 'committed'
    assert artifact['id'] == result['artifact_id'] and artifact['id'] not in ids.current_ids
    assert result['path'] == artifact_path(kind, artifact['id'], 'SR')
    assert artifact['maturity'] == result['maturity'] == 'draft'
    assert artifact['revision'] == result['revision'] == 1
    assert artifact['created_by'] == artifact['updated_by'] == ACTOR
    assert artifact['created_at'] == artifact['updated_at'] == TIME
    assert result['completion']['commit_completed'] and result['completion']['cleanup_completed']
    assert result['completion']['current_target_verified'] and not result['replayed']
    assert allocations == [16] and not (root / '.specroad/locks/project.json').exists()
    after = {entry[0]: entry[1:] for entry in file_inventory(root)}
    for name, *old in original: assert after[name] == tuple(old)
    assert path.read_bytes() == raw
    proof = read_transaction_completion(ProjectSource(root), 'txn-create').data
    assert proof['receipt_verified'] and proof['commit_completed'] and proof['cleanup_completed']


@pytest.mark.parametrize('kind', SPECIALIST_GATES)
def test_missing_real_semantic_service_blocks_publication(tmp_path, kind):
    root = tmp_path / 'project'; model, ids = project(root, kind); before = file_inventory(root)
    prepared = normalize_artifact_create_input(kind, fields(kind))
    with pytest.raises(TargetError) as error:
        create_artifact(model, prepared, **arguments(model, ids))
    assert error.value.reason == 'complete_target_validation_required'
    assert file_inventory(root) == before


def test_unrelated_invalid_artifact_blocks_the_whole_target(tmp_path):
    root = tmp_path / 'project'; model, ids = project(root, broken=True); before = file_inventory(root)
    with pytest.raises(ChangePlanError) as error:
        create_artifact(model, normalize_artifact_create_input('goal', fields('goal')), **arguments(model, ids))
    assert error.value.exit_code == 3 and error.value.reason == 'missing_field'
    assert error.value.pointer == '/artifacts/0/statement'
    assert file_inventory(root) == before


@pytest.mark.parametrize('kind,request_id,code', [('ai', 'create-1', 7), ('ci', None, 2)])
def test_authoring_policy_precedes_allocation_and_lock(tmp_path, kind, request_id, code):
    root = tmp_path / 'project'; model, ids = project(root); before = file_inventory(root)
    options = arguments(model, ids); options.update(actor={'actor_type': kind, 'actor_id': 'caller'}, request_id=request_id)
    prepared = normalize_artifact_create_input('goal', fields('goal'))
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no allocation')):
        with pytest.raises(AuthoringError) as error: create_artifact(model, prepared, **options)
    assert error.value.exit_code == code and file_inventory(root) == before


def test_host_denial_does_not_create_a_journal_or_normative_file(tmp_path):
    root = tmp_path / 'project'; model, ids = project(root); before = file_inventory(root)
    options = arguments(model, ids)
    options['authority'] = PublicationAuthority('denied-host', '1', lambda request: False)
    from specroad.changes import PublicationCheckError
    with pytest.raises(PublicationCheckError) as error:
        create_artifact(model, normalize_artifact_create_input('goal', fields('goal')), **options)
    assert error.value.exit_code == 7 and file_inventory(root) == before


@pytest.mark.parametrize('changed', [False, True])
def test_completed_request_is_checked_before_new_entropy_plan_or_lock(tmp_path, changed):
    root = tmp_path / 'project'; model, ids = project(root); value = fields('goal')
    options = arguments(model, ids); prepared = normalize_artifact_create_input('goal', value)
    first = create_artifact(model, prepared, **options); before = file_inventory(root)
    if changed: value['statement'] = 'A different requested result.'
    retry = normalize_artifact_create_input('goal', value)
    options['planned_at'] = '2026-10-11T00:00:00Z'
    with no_write_attempts(), patch('secrets.token_bytes', side_effect=AssertionError('no reallocation')), \
            patch.object(creation, 'prepare_change_target', side_effect=AssertionError('no replan')), \
            patch.object(creation, 'project_lock', side_effect=AssertionError('no writer lock')):
        if changed:
            from specroad.changes import RequestIdConflict
            with pytest.raises(RequestIdConflict) as error: create_artifact(model, retry, **options)
            assert error.value.exit_code == 6
        else:
            repeated = create_artifact(model, retry, **options)
            assert repeated['replayed'] and not repeated['completion']['current_target_verified']
            for key in ('artifact_id', 'path', 'revision', 'maturity'): assert repeated[key] == first[key]
            assert repeated['completion']['transaction_id'] == first['completion']['transaction_id']
    assert file_inventory(root) == before


def test_actual_target_becomes_visible_only_as_complete_json(tmp_path, monkeypatch):
    root = tmp_path / 'project'; model, ids = project(root); native = os.replace; seen = []
    def replace(src, dst, **kw):
        if str(dst).startswith('SR-GOAL-'):
            parent = Path(os.readlink('/proc/self/fd/' + str(kw['dst_dir_fd'])))
            target = parent / dst
            assert not target.exists()
            result = native(src, dst, **kw)
            content = json.loads(target.read_bytes())
            assert content['statement'] == fields('goal')['statement'] and content['revision'] == 1
            seen.append(content['id'])
            return result
        return native(src, dst, **kw)
    monkeypatch.setattr(os, 'replace', replace)
    result = create_artifact(model, normalize_artifact_create_input('goal', fields('goal')), **arguments(model, ids))
    assert seen == [result['artifact_id']]
