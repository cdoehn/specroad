"""15.j.W: byte-bound full-source plans, independently checked and read-only."""
from base64 import b64decode
from hashlib import sha256
import json
import os
import socket
import subprocess

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.recovery import RestoreError, RestorePlan, verify_restore_plan
from support.domain import domain_value, approved_value
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.restore import restore_case, plan_for
from support.scopes import descriptor


def decode_files(plan, table='target'):
    data = plan.data
    objects = {row['sha256']: b64decode(row['data_base64'], validate=True) for row in data['objects']}
    return {row['path']: objects[row['sha256']] for row in data[table]['entries']}


def resign(data):
    data.pop('restore_plan_sha256', None)
    data['restore_plan_sha256'] = sha256(canonical_json_bytes(data)).hexdigest()
    return canonical_json_bytes(data)


@pytest.mark.parametrize('source', ['project_bundle', 'working', 'release'])
def test_complete_sources_bind_original_bytes_and_independent_native_target(tmp_path, source, monkeypatch):
    options, original, raw = restore_case(tmp_path, 'project_bundle' if source == 'project_bundle' else 'baseline',
                                         baseline_kind=source if source != 'project_bundle' else 'working')
    damaged_path = next(p for p in original if p.startswith('spec/goals/'))
    before_image = b'{invalid JSON\x00\xff\r\n'
    put(options['project_root'], damaged_path, before_image)
    put(options['project_root'], '.git/private', b'not a model resource')
    before = inventory(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('Restore planning needs no processes or network')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    monkeypatch.setattr(socket, 'socket', forbidden)
    with no_write_attempts():
        plan = plan_for(options)
        reopened = RestorePlan(plan.source_bytes)
        checked = verify_restore_plan(plan.source_bytes)
    assert inventory(tmp_path) == before
    assert reopened.source_bytes == checked.source_bytes == plan.source_bytes
    data = plan.data
    assert data['format_version'] == 'restore-plan-v1'
    assert data['policy_version'] == 'restore-preserve-v1'
    assert data['source_descriptor'] == descriptor('project')
    assert data['source']['sha256'] == sha256(raw).hexdigest() and data['source']['size'] == len(raw)
    assert data['source']['path'] == options['source_path']
    assert data['source']['root'] == str(options['source_root'])
    assert data['project_root'] == str(options['project_root'])
    assert sha256(plan.source_bytes).hexdigest() == plan.sha256
    assert resign(data) == plan.source_bytes
    assert decode_files(plan, 'backup')[damaged_path] == before_image
    reconstructed = tmp_path / 'independent'; reconstructed.mkdir()
    target = decode_files(plan)
    for path, content in target.items():
        put(reconstructed, path, content)
    native = InspectionSnapshot(reconstructed, None, include_archive_objects=True)
    assert native.raw == target
    assert native.model.manifest(native.model.artifacts, descriptor('project')).sha256 == data['expected_target_root']
    assert data['expected_target_root'] != data['target']['sha256']
    if source == 'project_bundle':
        assert target == original and not data['preserved'] and not data['source']['dependencies']
        assert data['source_snapshot_root'] == data['expected_target_root']
    else:
        assert data['source_snapshot_root'] == json.loads(raw)['model_root_sha256']
        assert data['source_snapshot_root'] != data['expected_target_root']
        assert target[options['source_path']] == raw
        assert {r['reasons'][0] for r in data['preserved']} == {'source_baseline', 'source_archive'}
        for row in data['source']['dependencies']:
            content = (options['source_root'] / row['path']).read_bytes()
            assert content == target[row['path']]
            assert len(content) == row['size'] and sha256(content).hexdigest() == row['sha256']
    assert '.git/private' not in target
    for table in ('target', 'backup'):
        assert data[table]['sha256'] == sha256(canonical_json_bytes(data[table]['entries'])).hexdigest()
    assert data['inventory']['sha256'] == sha256(canonical_json_bytes(
        {k: data['inventory'][k] for k in ('roots', 'entries')})).hexdigest()
    detached = plan.data; detached['target']['entries'].clear()
    assert plan.data['target']['entries']
    with pytest.raises(TypeError):
        bool(plan)


def test_raw_baseline_representation_and_explicit_operational_fields_are_retained(tmp_path):
    options, _, raw = restore_case(tmp_path, 'baseline')
    raw = json.dumps(json.loads(raw), indent=3).encode() + b'\n'
    put(options['source_root'], options['source_path'], raw)
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = plan_for(options)
    assert inventory(tmp_path) == before
    target = decode_files(plan)
    assert target[options['source_path']] == raw
    assert plan.data['source']['sha256'] == sha256(raw).hexdigest()
    configuration = json.loads(target['specroad.json'])
    assert configuration['default_locale'] == 'en-GB' and configuration['generated_path'] == 'output'
    assert decode_files(plan, 'backup')['specroad.json'] == (options['project_root'] / 'specroad.json').read_bytes()


def test_inventory_has_empty_directories_and_missing_roots_but_no_unrelated_bytes(tmp_path):
    options, _, _ = restore_case(tmp_path)
    (options['project_root'] / 'spec/empty').mkdir()
    put(options['project_root'], 'src/untouched.py', b'unrelated')
    with no_write_attempts():
        data = plan_for(options).data
    entries = {r['path']: r for r in data['inventory']['entries']}
    assert entries['spec/empty'] == {'path': 'spec/empty', 'kind': 'directory'}
    for path in ('.specroad/transactions', '.specroad/requests', '.specroad/recovery', 'mappings'):
        assert entries[path] == {'path': path, 'kind': 'missing'}
    assert not any(p.startswith(('src/', '.git/')) for p in entries)
    assert data['backup']['entries'] == []


@pytest.mark.parametrize('case', ['primary', 'reference', 'approval', 'specialist'])
def test_container_integrity_is_not_full_project_qualification(tmp_path, case):
    values = [record_value('document'), domain_value('goal')]
    if case == 'primary':
        values = [domain_value('goal')]
    elif case == 'reference':
        values.append(domain_value('milestone'))
    elif case == 'approval':
        # A stored Requirement approval needs its actual human review inputs.
        # Ordinary approved Goals now use the completed native stored-state gates.
        values[1] = approved_value('requirement')
    else:
        # An explicit content binding requires the unavailable native provider;
        # valid unapproved locator-only metadata does not require observation.
        values.append(record_value('source', locator='urn:synthetic:external-source',
            content_sha256=sha256(b'Bound external source content').hexdigest()))
    # A missing reference cannot even be packaged by the native project creator;
    # start with a hash-consistent explicit container to exercise model gates.
    if case == 'reference':
        from specroad.bundles.container import BundleContainer, encode_bundle
        options, _, _ = restore_case(tmp_path)
        container = BundleContainer((options['source_root'] / options['source_path']).read_bytes())
        files = container.files
        value = domain_value('milestone')
        files[artifact_path('milestone', value['id'], 'SR')] = canonical_json_bytes(value)
        metadata = {k: v for k, v in container.manifest.items() if k != 'entries'}
        put(options['source_root'], options['source_path'], encode_bundle(metadata, files))
    else:
        options, _, _ = restore_case(tmp_path, values=values)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        plan_for(options)
    assert error.value.exit_code == 3
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('field', ['default_locale', 'generated_path'])
def test_baseline_does_not_guess_operational_configuration(tmp_path, field):
    options, _, _ = restore_case(tmp_path, 'baseline')
    del options[field]
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        plan_for(options)
    assert error.value.exit_code == 2


@pytest.mark.parametrize('case', ['project_id', 'revision', 'history', 'journal', 'damaged_config', 'unknown_managed'])
def test_unproved_identity_history_or_inventory_prevents_a_complete_plan(tmp_path, case):
    options, files, _ = restore_case(tmp_path)
    root = options['project_root']
    path = 'specroad.json'
    if case == 'project_id':
        value = json.loads(files[path]); value['project_id'] = 'other'; raw = canonical_json_bytes(value)
    elif case == 'revision':
        path = next(p for p in files if p.startswith('spec/goals/'))
        value = json.loads(files[path]); value['revision'] += 1; raw = canonical_json_bytes(value)
    elif case == 'history':
        value = record_value('evidence'); path = artifact_path('evidence', value['id'], 'SR'); raw = canonical_json_bytes(value)
    elif case == 'journal':
        path, raw = '.specroad/transactions/broken/journal.json', b'{broken'
    elif case == 'damaged_config':
        raw = b'{broken'
    else:
        path, raw = 'spec/unrecognized.bin', b'not silently omitted'
    put(root, path, raw)
    before = inventory(tmp_path)
    if case == 'journal':
        # 15.l.W now inventories corrupt active bytes as backup originals;
        # this read-only observation does not select or authorize them.
        with no_write_attempts():
            plan = plan_for(options)
        assert decode_files(plan, 'backup')[path] == raw
        assert inventory(tmp_path) == before
        return
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        plan_for(options)
    # 15.k now inventories Evidence; this synthetic record lacks the native
    # configuration/subject proof and is invalid input, not an ID collision.
    assert error.value.exit_code == (3 if case in ('damaged_config', 'unknown_managed', 'history') else 6)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['source_change', 'source_missing', 'target_change', 'target_added', 'target_removed', 'empty_directory'])
def test_live_recheck_detects_changed_origin_or_complete_inventory(tmp_path, change):
    options, files, raw = restore_case(tmp_path)
    plan = plan_for(options)
    origin = options['source_root'] / options['source_path']
    path = options['project_root'] / next(p for p in files if p.startswith('spec/goals/'))
    if change == 'source_change': origin.write_bytes(raw + b'x')
    elif change == 'source_missing': origin.unlink()
    elif change == 'target_change': path.write_bytes(b'changed')
    elif change == 'target_added': put(options['project_root'], 'spec/additional.bin', b'new')
    elif change == 'target_removed': path.unlink()
    else: (options['project_root'] / 'spec/empty').mkdir()
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        verify_restore_plan(plan.source_bytes)
    assert error.value.exit_code == 6
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('case', ['source', 'backup', 'target', 'source_root', 'target_root', 'inventory_hash', 'preserved', 'extra_object'])
def test_resigning_outer_hash_cannot_repair_inner_contract_or_native_roots(tmp_path, case):
    options, _, _ = restore_case(tmp_path)
    plan = plan_for(options); data = plan.data
    if case == 'source': data['source']['size'] += 1
    elif case == 'backup':
        data['backup'] = data['target']
    elif case == 'target':
        data['target']['entries'].pop()
        data['target']['sha256'] = sha256(canonical_json_bytes(data['target']['entries'])).hexdigest()
    elif case == 'source_root': data['source_snapshot_root'] = '0' * 64
    elif case == 'target_root': data['expected_target_root'] = '0' * 64
    elif case == 'inventory_hash': data['inventory']['sha256'] = '0' * 64
    elif case == 'preserved': data['preserved'] = [{**data['target']['entries'][0], 'reasons': ['protected_history']}]
    else:
        data['objects'].append({'sha256': sha256(b'').hexdigest(), 'size': 0, 'data_base64': ''})
        data['objects'].sort(key=lambda r: r['sha256'])
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        RestorePlan(resign(data))
    assert error.value.exit_code == 3


@pytest.mark.parametrize('case', ['symlink', 'hardlink', 'fifo', 'alias', 'root_alias'])
def test_native_safety_prevents_link_special_and_alias_inputs(tmp_path, case):
    options, _, _ = restore_case(tmp_path)
    root = options['project_root']
    if case == 'symlink': (root / 'spec/linked').symlink_to(tmp_path)
    elif case == 'hardlink': os.link(root / 'specroad.json', root / 'spec/linked.json')
    elif case == 'fifo': os.mkfifo(root / 'spec/special')
    elif case == 'alias': (root / 'Spec').mkdir()
    else:
        alias = tmp_path / 'alias'; alias.symlink_to(root); options['project_root'] = alias
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        plan_for(options)
    assert error.value.exit_code == 7
    assert inventory(tmp_path) == before


def test_missing_baseline_dependency_cannot_be_filled_from_current_project(tmp_path):
    options, original, raw = restore_case(tmp_path, 'baseline')
    row = next(r for r in json.loads(raw)['manifest'] if r['role'] == 'artifact')
    (options['source_root'] / row['object_path']).unlink()
    assert (options['project_root'] / row['source_path']).read_bytes() == original[row['source_path']]
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        plan_for(options)
    assert error.value.exit_code == 3
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('case', ['revision', 'approval'])
def test_archived_publication_evidence_cannot_hide_behind_current_draft_bytes(tmp_path, case):
    from specroad.bundles import prepare_project_bundle, verify_bundle
    value = domain_value('goal', revision=2) if case == 'revision' else approved_value('goal')
    options, _, _ = restore_case(tmp_path, 'baseline', values=[record_value('document'), value])
    path = artifact_path('goal', value['id'], 'SR')
    for root in (options['source_root'], options['project_root']):
        if case == 'revision':
            put(root, path, canonical_json_bytes(domain_value('goal')))
        else:
            (root / path).unlink()
    # Native container and archived-object integrity alone do not prove that
    # the mutable target preserves its own recorded publication history.
    raw = prepare_project_bundle(options['source_root']).source_bytes
    verify_bundle(raw)
    options.update(source_kind='project_bundle', source_path='history.zip')
    del options['default_locale'], options['generated_path']
    put(options['source_root'], options['source_path'], raw)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        plan_for(options)
    assert error.value.exit_code == 6  # Protected published identity/revision conflict, §10.7.1.
    assert error.value.reason == ('restore_archived_revision_conflict' if case == 'revision'
                                  else 'restore_archived_approval_conflict')
    assert inventory(tmp_path) == before


def test_nested_baseline_objects_are_qualified_and_retained_without_changing_old_records(tmp_path):
    from specroad.archive.project_snapshot import build_project_baseline_manifest
    from specroad.bundles._payload_model import owned_payload_model
    options, _, first_raw = restore_case(tmp_path, 'baseline')
    first = plan_for(options)
    files = decode_files(first)
    model = owned_payload_model(files, source_label='synthetic-nested-baseline')
    snapshot = build_project_baseline_manifest(model, baseline_id=ref('BASE', '1'))
    record = record_value('baseline', id=ref('BASE', '1'), **{k: snapshot.data[k] for k in (
        'scope_descriptor', 'manifest', 'model_root_sha256', 'configuration_hash', 'profiles', 'tool_version')})
    path = artifact_path('baseline', record['id'], 'SR')
    raw = canonical_json_bytes(record)
    put(options['source_root'], path, raw)
    for item in snapshot.objects:
        put(options['source_root'], item.reference.path, item.content)
    options['source_path'] = path
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = plan_for(options)
        RestorePlan(plan.source_bytes)
    assert inventory(tmp_path) == before
    target = decode_files(plan)
    assert all(target[p] == b for p, b in files.items() if p != 'specroad.json')
    assert target[artifact_path('baseline', ref('BASE'), 'SR')] == first_raw
    assert target[path] == raw
    assert plan.data['source_snapshot_root'] == first.data['expected_target_root']
    assert plan.data['expected_target_root'] != plan.data['source_snapshot_root']


@pytest.mark.parametrize('case', ['extra_field', 'boolean_size', 'base64_whitespace', 'duplicate', 'unsafe_path', 'noncanonical'])
def test_closed_plan_reader_rejects_invalid_wire_values(tmp_path, case):
    options, _, _ = restore_case(tmp_path)
    plan = plan_for(options); data = plan.data
    if case == 'extra_field': data['approval_granted'] = True
    elif case == 'boolean_size': data['objects'][0]['size'] = True
    elif case == 'base64_whitespace': data['objects'][0]['data_base64'] += '\n'
    elif case == 'duplicate': data['objects'].append(data['objects'][-1])
    elif case == 'unsafe_path': data['target']['entries'][0]['path'] = '../escape'
    raw = json.dumps(data, indent=2).encode() if case == 'noncanonical' else resign(data)
    with no_write_attempts(), pytest.raises(RestoreError) as error:
        RestorePlan(raw)
    assert error.value.exit_code == (7 if case == 'unsafe_path' else 3)
