"""17.b.R: complete stored-plan verification and exact absence semantics."""
from hashlib import sha256
import json

import pytest

from specroad.merge import (SourceRequest, load_merge_sources, build_merge_inventory,
                            read_merge_inventory)
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from specroad.model.errors import ModelError
from specroad.bundles import BundleError
from support.model import put
from support.read_only import inventory
from support.relations import edge
from test_project_bundle import project
from test_merge_sources import KINDS, read_only_sources, sources
from test_merge_inventory import PLAN_ID, ROLES, bind_files, row_for


@pytest.mark.parametrize('kind', KINDS)
def test_stored_inventory_is_rebuilt_from_each_native_source_kind(tmp_path, kind):
    requests, _, _, _ = sources(tmp_path)
    with read_only_sources():
        observed = load_merge_sources(*(requests[kind] for _ in ROLES))
        plan = build_merge_inventory(observed, plan_id=PLAN_ID)
        loaded = read_merge_inventory(plan.canonical_bytes, observed)
    assert loaded.canonical_bytes == plan.canonical_bytes
    assert loaded.sha256 == plan.sha256
    assert loaded.ready is False and loaded.write_authorized is False


FORGERIES = ('omitted_row', 'extra_row', 'duplicate_row', 'reordered_rows',
    'identity', 'byte_hash', 'value_hash', 'size', 'path', 'pointer', 'owner',
    'scheme', 'storage', 'domain', 'absence', 'classification', 'deletion',
    'reasons', 'source_binding', 'source_inventory', 'source_scope',
    'target_root', 'ready', 'write_authorized', 'numeric_false', 'extra_field',
    'missing_field', 'extra_identity_field', 'extra_binding_field', 'policy')


@pytest.mark.parametrize('change', FORGERIES)
def test_rehashing_a_forged_inventory_never_replaces_original_source_proof(tmp_path, change):
    root = tmp_path/'source'; project(root)
    observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
    plan = build_merge_inventory(observed, plan_id=PLAN_ID)
    value = plan.data; row = value['resources'][0]
    if change == 'omitted_row': value['resources'].pop()
    elif change == 'extra_row':
        extra = json.loads(json.dumps(row)); extra['identity']['id'] = 'invented'
        value['resources'].append(extra)
    elif change == 'duplicate_row': value['resources'].append(row)
    elif change == 'reordered_rows': value['resources'].reverse()
    elif change == 'identity': row['identity']['id'] = 'invented'
    elif change == 'byte_hash': row['ours']['byte_sha256'] = '0'*64
    elif change == 'value_hash': row['ours']['value_sha256'] = '0'*64
    elif change == 'size': row['ours']['size'] += 1
    elif change == 'path': row['ours']['path'] = 'spec/other.json'
    elif change == 'pointer': row['ours']['pointer'] = '/relations/0'
    elif change == 'owner': row['ours']['owner_id'] = 'invented'
    elif change == 'scheme': row['ours']['id_scheme'] = 'unknown-v1'
    elif change == 'storage': row['ours']['storage_class'] = 'invented'
    elif change == 'domain': row['ours']['value_domain'] = 'invented'
    elif change == 'absence': row['ours'] = {k: 'absent' if k == 'state' else None for k in row['ours']}
    elif change == 'classification': row['target_classification'] = 'adopt_existing'
    elif change == 'deletion': row['delete'] = True
    elif change == 'reasons': row['pending_reasons'] = ['semantic_planning_required']
    elif change == 'source_binding': value['source_bindings']['ours']['source_root'] = '/invented'
    elif change == 'source_inventory': value['source_bindings']['ours']['resources'].pop()
    elif change == 'source_scope': value['source_bindings']['ours']['scope_descriptor'] = {'scope':'selected'}
    elif change == 'target_root': value['expected_target_model_root_sha256'] = '0'*64
    elif change == 'ready': value['ready'] = True
    elif change == 'write_authorized': value['write_authorized'] = True
    elif change == 'numeric_false': value['ready'] = 0
    elif change == 'extra_field': value['implicit_resolution'] = 'ours'
    elif change == 'missing_field': del value['metadata_policy_version']
    elif change == 'extra_identity_field': row['identity']['owner'] = 'invented'
    elif change == 'extra_binding_field': row['ours']['delete_allowed'] = True
    elif change == 'policy': value['metadata_policy_version'] = 'invented'
    value['inventory_sha256'] = digest(value['resources'])
    value['source_bindings_sha256'] = digest(value['source_bindings'])
    raw = jcs(value)
    assert raw != plan.canonical_bytes and sha256(raw).hexdigest() != plan.sha256
    before = inventory(root)
    with read_only_sources(), pytest.raises(ModelError):
        read_merge_inventory(raw, observed)
    assert inventory(root) == before


@pytest.mark.parametrize('encoding', ['text', 'bytearray', 'array', 'invalid_json',
    'duplicate_key', 'future_version', 'absent_version', 'noncanonical', 'missing_id'])
def test_reader_rejects_unknown_versions_malformed_types_and_noncanonical_bytes(tmp_path, encoding):
    root = tmp_path/'source'; project(root)
    observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
    raw = build_merge_inventory(observed, plan_id=PLAN_ID).canonical_bytes
    value = json.loads(raw)
    if encoding == 'text': raw = raw.decode()
    elif encoding == 'bytearray': raw = bytearray(raw)
    elif encoding == 'array': raw = b'[]'
    elif encoding == 'invalid_json': raw = b'{'
    elif encoding == 'duplicate_key': raw = b'{"ready":false,' + raw[1:]
    elif encoding == 'future_version': value['inventory_format_version'] = 'merge-inventory-v99'; raw = jcs(value)
    elif encoding == 'absent_version': del value['inventory_format_version']; raw = jcs(value)
    elif encoding == 'noncanonical': raw = json.dumps(value, indent=2).encode()
    elif encoding == 'missing_id': del value['plan_id']; raw = jcs(value)
    with read_only_sources(), pytest.raises(ModelError):
        read_merge_inventory(raw, observed)


def test_empty_attachment_and_json_null_are_present_not_absent(tmp_path):
    files = project(tmp_path/'seed').raw
    evidence_path = next(p for p in files if p.startswith('spec/evidence/'))
    evidence = json.loads(files[evidence_path])
    evidence['attachments'][0].update(size=0, sha256=sha256(b'').hexdigest())
    files['attachments/owned.bin'] = b''; files[evidence_path] = jcs(evidence)
    goal_path = next(p for p in files if p.startswith('spec/goals/'))
    variants = []
    for extension in ({}, {'example.inventory':None}, {'example.inventory':None}):
        variant = dict(files); goal = json.loads(files[goal_path])
        goal['extensions'] = extension; variant[goal_path] = jcs(goal); variants.append(variant)
    observed = bind_files(tmp_path, variants)
    with read_only_sources(): value = build_merge_inventory(observed, plan_id=PLAN_ID).data
    attachment = row_for(value, 'attachment', 'attachments/owned.bin')
    assert attachment['ours']['state'] == 'present' and attachment['ours']['size'] == 0
    assert attachment['ours']['byte_sha256'] == sha256(b'').hexdigest()
    assert attachment['target_classification'] == 'unchanged_ours'
    goal = row_for(value, 'artifact', json.loads(files[goal_path])['id'])
    assert all(goal[role]['state'] == 'present' for role in ROLES)
    assert goal['base']['value_sha256'] != goal['ours']['value_sha256']
    assert goal['pending_reasons'] == ['semantic_planning_required']


def test_relation_order_does_not_replace_relation_identity_or_parent_byte_binding(tmp_path):
    files = project(tmp_path/'seed').raw
    path = next(p for p in files if p.startswith('spec/goals/'))
    target = json.loads(next(raw for p,raw in files.items() if p.startswith('spec/requirements/')))['id']
    other_target = json.loads(next(raw for p,raw in files.items() if p.startswith('spec/proposals/')))['id']
    edges = [edge(kind='conflicts_with', target=target, number=1),
             edge(kind='conflicts_with', target=other_target, number=2)]
    variants = []
    for ordered in (edges, list(reversed(edges)), edges):
        variant = dict(files); goal = json.loads(files[path]); goal['relations'] = ordered
        variant[path] = jcs(goal); variants.append(variant)
    observed = bind_files(tmp_path, variants)
    with read_only_sources(): value = build_merge_inventory(observed, plan_id=PLAN_ID).data
    rows = [row for row in value['resources'] if row['identity']['kind'] == 'relation']
    assert len(rows) == 2
    for index, relation in enumerate(edges):
        row = row_for(value, 'relation', relation['relation_id'])
        assert row['base']['pointer'] == '/relations/'+str(index)
        assert row['ours']['pointer'] == '/relations/'+str(1-index)
        assert row['base']['byte_sha256'] != row['ours']['byte_sha256']
        assert row['base']['value_sha256'] == row['ours']['value_sha256'] == digest(relation)
        assert row['target_classification'] == 'unchanged_ours'
    assert value['expected_target_model_root_sha256'] is None


@pytest.mark.parametrize('mutation', ['deleted', 'changed'])
def test_source_changes_after_capture_fail_instead_of_becoming_absence(tmp_path, mutation):
    root = tmp_path/'source'; files = project(root).raw
    observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
    plan = build_merge_inventory(observed, plan_id=PLAN_ID)
    path = next(p for p in files if p.startswith('spec/goals/'))
    if mutation == 'deleted': (root/path).unlink()
    else:
        value = json.loads(files[path]); value['title'] = 'Changed after capture'; put(root,path,jcs(value))
    before = inventory(root)
    with read_only_sources(), pytest.raises((ModelError, BundleError)):
        read_merge_inventory(plan.canonical_bytes, observed)
    assert inventory(root) == before


def test_missing_required_attachment_does_not_become_a_plan_absence(tmp_path):
    root = tmp_path/'source'; project(root); (root/'attachments/owned.bin').unlink()
    with read_only_sources(), pytest.raises((ModelError, BundleError, FileNotFoundError)):
        observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
        build_merge_inventory(observed, plan_id=PLAN_ID)


def test_same_relation_id_in_different_owners_is_not_silently_disambiguated(tmp_path):
    root = tmp_path/'source'; files = project(root).raw
    paths = [next(p for p in files if p.startswith(prefix)) for prefix in ('spec/goals/','spec/requirements/')]
    target = json.loads(files[paths[1]])['id']
    for path in paths:
        value = json.loads(files[path]); value['relations'] = [edge(kind='conflicts_with', target=target)]; put(root,path,jcs(value))
    with read_only_sources(), pytest.raises(ModelError) as caught:
        observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
        build_merge_inventory(observed, plan_id=PLAN_ID)
    assert caught.value.reason in ('merge_inventory_duplicate_identity','duplicate_relation_id')


def test_qualified_legacy_originals_have_raw_byte_hashes_and_manifest_bound_navigation(tmp_path):
    from support.legacy_manifest import migrated, write_files, MANIFEST
    _, files, _ = migrated(); root = tmp_path/'source'; write_files(root, files)
    registered = json.loads(files[MANIFEST])['entries']
    before = inventory(root)
    with read_only_sources():
        observed = load_merge_sources(*(SourceRequest(root) for _ in ROLES))
        plan = build_merge_inventory(observed, plan_id=PLAN_ID)
        value = read_merge_inventory(plan.canonical_bytes, observed).data
    rows = [row for row in value['resources'] if row['identity']['kind'] != 'relation']
    assert {row['ours']['path'] for row in rows} == set(observed.ours.files)
    originals, archives, archived_artifacts = set(), set(), set()
    for entry in registered:
        path = entry['path']; row = next(row for row in rows if row['ours']['path'] == path)
        for role in ROLES:
            assert row[role]['state'] == 'present' and row[role]['pointer'] == ''
            assert row[role]['size'] == len(files[path]) == entry['original_size']
            assert row[role]['byte_sha256'] == sha256(files[path]).hexdigest() == entry['original_byte_sha256']
        if path.startswith('archive/objects/'):
            # The manifest's role describes historical content, not its current
            # physical resource kind. Archived JSON stays an opaque byte object.
            archives.add(path)
            if entry['role'] == 'artifact': archived_artifacts.add(path)
            assert row['identity'] == {'kind':'archive', 'id':path, 'version':None}
            for role in ROLES:
                assert row[role]['storage_class'] == 'current'
                assert row[role]['value_domain'] == 'bytes-v1'
                assert row[role]['value_sha256'] == entry['original_byte_sha256']
                assert row[role]['id_scheme'] is None and row[role]['owner_id'] is None
            continue
        if entry['role'] != 'artifact': continue
        originals.add(path)
        assert path.startswith('spec/')
        assert row['identity'] == {'kind':'artifact', 'id':entry['artifact_id'], 'version':None}
        assert row['ours']['storage_class'] == 'legacy_immutable'
        assert row['ours']['value_domain'] == 'json-v1'
        assert row['ours']['value_sha256'] == digest(json.loads(files[path])) == entry['original_canonical_sha256']
        for relation in entry['relation_projections']:
            observed_relation = row_for(value, 'relation', relation['relation_id'])
            expected = {**relation['original'], 'relation_id':relation['relation_id'], 'id_scheme':relation['id_scheme']}
            assert observed_relation['ours']['path'] == path
            assert observed_relation['ours']['byte_sha256'] == entry['original_byte_sha256']
            assert observed_relation['ours']['value_domain'] == 'relation-navigation-v1'
            assert observed_relation['ours']['value_sha256'] == digest(expected)
            assert observed_relation['ours']['storage_class'] == 'legacy_immutable'
    assert originals and archives and archived_artifacts
    assert not any(row['ours']['path'] in archives for row in value['resources']
                   if row['identity']['kind'] == 'relation')
    assert any(row['ours']['path'] == MANIFEST for row in rows)
    assert value['ready'] is False and value['write_authorized'] is False
    assert inventory(root) == before
