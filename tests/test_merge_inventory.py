"""17.b.W: actual complete resources and original three-way observations."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.merge import SourceRequest, load_merge_sources, build_merge_inventory
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from specroad.model.errors import ModelError
from support.model import put
from support.profiles import profile_data
from support.read_only import inventory
from support.relations import edge
from test_merge_sources import KINDS, read_only_sources, sources
from test_project_bundle import project, baseline_project


PLAN_ID = 'MP-' + '0' * 25 + '1'
ROLES = ('base', 'ours', 'theirs')


def bind_files(root, variants):
    requests = []
    for role, files in zip(ROLES, variants):
        folder = root/role; folder.mkdir()
        for path, raw in files.items():
            put(folder, path, raw)
        requests.append(SourceRequest(folder))
    return load_merge_sources(*requests)


def row_for(value, kind, identifier):
    return next(row for row in value['resources']
                if row['identity']['kind'] == kind and row['identity']['id'] == identifier)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('position', range(3))
def test_every_native_source_kind_and_role_has_complete_original_file_bindings(tmp_path, kind, position):
    requests, files, _, _ = sources(tmp_path)
    selected = [requests['local']] * 3; selected[position] = requests[kind]
    before = inventory(tmp_path)
    with read_only_sources():
        observed = load_merge_sources(*selected)
        result = build_merge_inventory(observed, plan_id=PLAN_ID)
    value = result.data
    assert inventory(tmp_path) == before
    assert value['inventory_format_version'] == 'merge-inventory-v1'
    assert value['metadata_policy_version'] == 'merge-metadata-v1'
    assert value['source_bindings'] == observed.binding
    assert value['source_bindings_sha256'] == digest(observed.binding)
    assert value['inventory_sha256'] == digest(value['resources'])
    assert result.sha256 == sha256(result.canonical_bytes).hexdigest()
    assert result.canonical_bytes == jcs(value)
    for role in ROLES:
        file_rows = [row[role] for row in value['resources'] if row['identity']['kind'] != 'relation']
        assert {row['path'] for row in file_rows} == set(files)
        assert len(file_rows) == len(files)
        for row in file_rows:
            assert row['state'] == 'present' and row['pointer'] == ''
            assert row['size'] == len(files[row['path']])
            assert row['byte_sha256'] == sha256(files[row['path']]).hexdigest()
    assert all(row['target_classification'] == 'unchanged_ours' and not row['pending_reasons']
               for row in value['resources'])
    assert value['expected_target_model_root_sha256'] == observed.ours.binding['model_root_sha256']
    assert value['ready'] is False and value['write_authorized'] is False


def test_all_resource_kinds_and_relations_are_individually_addressed(tmp_path):
    root = tmp_path/'project'; original = project(root)
    goal_path = next(path for path in original.raw if path.startswith('spec/goals/'))
    requirement_path = next(path for path in original.raw if path.startswith('spec/requirements/'))
    goal = json.loads(original.raw[goal_path])
    relation = edge(kind='conflicts_with', target=json.loads(original.raw[requirement_path])['id'])
    goal['relations'] = [relation]; put(root, goal_path, jcs(goal))
    put(root, 'profiles/unused.json', jcs(profile_data(profile_id='unused')))
    put(root, 'rules/unused.json', jcs({'schema_version':'0.2.0','rule_id':'unused',
                                     'version':'1.0.0','payload':{'enabled':False}}))
    before = inventory(root)
    with read_only_sources():
        observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
        result = build_merge_inventory(observed, plan_id=PLAN_ID)
    value = result.data
    assert {'configuration','artifact','relation','profile','rule','mapping',
            'attachment','language_registry'} <= {row['identity']['kind'] for row in value['resources']}
    row = row_for(value, 'relation', relation['relation_id'])
    assert row['ours']['owner_id'] == goal['id']
    assert row['ours']['pointer'] == '/relations/0'
    assert row['ours']['byte_sha256'] == sha256(jcs(goal)).hexdigest()
    assert row['ours']['value_sha256'] == digest(relation)
    assert row['ours']['value_domain'] == 'relation-navigation-v1'
    assert row_for(value, 'profile', 'unused')['identity']['version'] == '0.2.0'
    assert row_for(value, 'rule', 'unused')['identity']['version'] == '1.0.0'
    assert inventory(root) == before


def test_every_language_package_and_registry_is_retained(tmp_path):
    from specroad.cli.application import dispatch_result
    root = tmp_path/'project'; assert dispatch_result(['init',str(root)]).exit_code == 0
    with read_only_sources():
        observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
        value = build_merge_inventory(observed, plan_id=PLAN_ID).data
    packages = [row for row in value['resources'] if row['identity']['kind'] == 'language_package']
    assert len(packages) == 9
    assert {row['ours']['path'] for row in packages} == {
        path for path in observed.ours.files if path.startswith('profiles/language-data/packages/')}
    registry = next(row for row in value['resources'] if row['identity']['kind'] == 'language_registry')
    assert registry['ours']['value_domain'] == 'bytes-v1'
    assert registry['ours']['value_sha256'] == registry['ours']['byte_sha256']


def test_bound_baseline_archives_are_not_an_invisible_secondary_namespace(tmp_path):
    root = tmp_path/'source'; baseline = baseline_project(root)
    with read_only_sources():
        observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
        value = build_merge_inventory(observed, plan_id=PLAN_ID).data
    archive_rows = [row for row in value['resources'] if row['identity']['kind'] == 'archive']
    assert {row['identity']['id'] for row in archive_rows} == {obj['path'] for obj in baseline['objects']}
    assert all(row['ours']['value_domain'] == 'bytes-v1' for row in archive_rows)
    assert row_for(value, 'artifact', baseline['record']['id'])['ours']['state'] == 'present'


@pytest.mark.parametrize('presence', [(True,False,True),(True,True,False),(True,False,False),
    (False,True,False),(False,False,True),(False,True,True)])
def test_absence_is_observed_in_each_role_without_inventing_a_deletion(tmp_path, presence):
    original = project(tmp_path/'seed').raw
    path = next(path for path in original if path.startswith('spec/goals/'))
    goal = json.loads(original[path]); variants = []
    for present in presence:
        files = dict(original)
        if not present: del files[path]
        variants.append(files)
    observed = bind_files(tmp_path, variants)
    with read_only_sources(): value = build_merge_inventory(observed, plan_id=PLAN_ID).data
    row = row_for(value, 'artifact', goal['id'])
    for role, present in zip(ROLES, presence):
        assert row[role]['state'] == ('present' if present else 'absent')
        if not present:
            assert all(item is None for key,item in row[role].items() if key != 'state')
    assert row['target_classification'] == 'conflict'
    assert row['pending_reasons'] == ['semantic_planning_required','absence_not_deletion']
    assert value['expected_target_model_root_sha256'] is None
    assert value['ready'] is False and value['write_authorized'] is False


def test_changed_fields_are_retained_but_not_prematurely_merged(tmp_path):
    original = project(tmp_path/'seed').raw
    path = next(path for path in original if path.startswith('spec/goals/'))
    variants = []
    for title in ('Base title','Our title','Their title'):
        files = dict(original); value = json.loads(files[path]); value['title'] = title
        files[path] = jcs(value); variants.append(files)
    observed = bind_files(tmp_path, variants)
    with read_only_sources(): value = build_merge_inventory(observed, plan_id=PLAN_ID).data
    row = row_for(value, 'artifact', json.loads(original[path])['id'])
    assert [row[role]['byte_sha256'] for role in ROLES] == [sha256(files[path]).hexdigest() for files in variants]
    assert row['target_classification'] == 'conflict'
    assert row['pending_reasons'] == ['semantic_planning_required']
    assert value['expected_target_model_root_sha256'] is None
    assert all(observed_source.files == expected for observed_source,expected in
               zip((observed.base,observed.ours,observed.theirs), variants))


def test_plan_is_deterministic_owned_and_never_a_truthy_write_capability(tmp_path):
    root = tmp_path/'source'; project(root)
    observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
    with read_only_sources():
        first = build_merge_inventory(observed, plan_id=PLAN_ID)
        second = build_merge_inventory(observed, plan_id=PLAN_ID)
    assert first.canonical_bytes == second.canonical_bytes and first.sha256 == second.sha256
    detached = first.data; detached['resources'].clear(); detached['source_bindings'].clear()
    assert first.data['resources'] and first.data['source_bindings'] == observed.binding
    assert first.ready is False and first.write_authorized is False
    with pytest.raises(TypeError): bool(first)
    with pytest.raises(FrozenInstanceError): first._encoded = b'{}'
    assert [jcs(row['identity']) for row in first.data['resources']] == sorted(jcs(row['identity']) for row in first.data['resources'])


@pytest.mark.parametrize('plan_id', [None,True,1,{},'','CP-'+'0'*26,'MP-'+'8'*26,'MP-'+'i'*26])
def test_plan_identity_is_explicit_and_canonical(tmp_path, plan_id):
    root = tmp_path/'source'; project(root)
    observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
    with read_only_sources(), pytest.raises(ModelError):
        build_merge_inventory(observed, plan_id=plan_id)


def test_dictionary_assertions_do_not_replace_native_three_source_values():
    with pytest.raises(ModelError) as caught:
        build_merge_inventory({'base':{},'ours':{},'theirs':{}}, plan_id=PLAN_ID)
    assert caught.value.reason == 'merge_sources_required'
