"""15.j.R: independent current evidence, closed contracts and native failures."""
import json
import os

import pytest

from specroad.archive.project_snapshot import build_project_baseline_manifest
from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.bundles import prepare_partial_bundle, prepare_project_bundle, verify_bundle
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.recovery import RestoreError, RestorePlan, verify_restore_plan
from specroad.recovery import planning as service
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.restore import restore_case, plan_for
from support.scopes import descriptor
from test_restore_plan import decode_files, resign


def retain_baseline(options, raw):
    files = {options['source_path']: raw}
    files.update({row['object_path']: (options['source_root'] / row['object_path']).read_bytes()
                  for row in json.loads(raw)['manifest']})
    for path, content in files.items():
        put(options['project_root'], path, content)
    return files


def retained_case(tmp_path, kind='baseline'):
    options, original, raw = restore_case(tmp_path, 'baseline')
    evidence = retain_baseline(options, raw)
    if kind == 'project_bundle':
        raw = prepare_project_bundle(options['source_root']).source_bytes
        put(options['source_root'], 'retained.zip', raw)
        options.update(source_kind=kind, source_path='retained.zip')
        del options['default_locale'], options['generated_path']
    return options, original, evidence


def save_snapshot(root, *, identity=None):
    identity = identity or ref('BASE')
    model = InspectionSnapshot(root, None, include_archive_objects=True).model
    snapshot = build_project_baseline_manifest(model, baseline_id=identity)
    record = record_value('baseline', id=identity, **{k: snapshot.data[k] for k in (
        'scope_descriptor', 'manifest', 'model_root_sha256', 'configuration_hash', 'profiles', 'tool_version')})
    path = artifact_path('baseline', identity, model.configuration.id_prefix)
    files = {path: canonical_json_bytes(record), **{o.reference.path: o.content for o in snapshot.objects}}
    for path, raw in files.items():
        put(root, path, raw)
    return files


def rejected(options, code):
    before = inventory(options['project_root'].parent)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        plan_for(options)
    assert failure.value.exit_code == code
    assert inventory(options['project_root'].parent) == before
    return failure.value


@pytest.mark.parametrize('kind', ['baseline', 'project_bundle'])
@pytest.mark.parametrize('damage', ['invalid_bytes', 'missing', 'schema'])
def test_retained_original_baseline_independently_proves_damaged_configuration(tmp_path, kind, damage):
    options, original, evidence = retained_case(tmp_path, kind)
    path = options['project_root'] / 'specroad.json'
    raw = b'{broken\x00\xff' if damage == 'invalid_bytes' else b'{"project_id":false}'
    if damage == 'missing':
        path.unlink()
    else:
        path.write_bytes(raw)
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = plan_for(options)
        reopened = RestorePlan(plan.source_bytes)
        verified = verify_restore_plan(plan.source_bytes)
    assert inventory(tmp_path) == before
    assert reopened.source_bytes == verified.source_bytes == plan.source_bytes
    target, backup = decode_files(plan), decode_files(plan, 'backup')
    assert all(target[p] == content for p, content in evidence.items())
    assert plan.data['project_id'] == json.loads(original['specroad.json'])['project_id']
    configuration = json.loads(target['specroad.json'])
    if kind == 'baseline':
        assert configuration['default_locale'] == 'en-GB' and configuration['generated_path'] == 'output'
    else:
        assert target['specroad.json'] == original['specroad.json']
    if damage == 'missing':
        assert 'specroad.json' not in backup
        assert {'path': 'specroad.json', 'kind': 'missing'} in plan.data['inventory']['entries']
    else:
        assert backup['specroad.json'] == raw
    independent = tmp_path / 'independent'; independent.mkdir()
    for path, raw in target.items():
        put(independent, path, raw)
    native = InspectionSnapshot(independent, None, include_archive_objects=True).model
    assert native.manifest(native.artifacts, descriptor('project')).sha256 == plan.data['expected_target_root']


def test_old_managed_coverage_is_observed_even_when_source_no_longer_declares_it(tmp_path):
    options, original, _ = restore_case(tmp_path)
    value = json.loads(original['specroad.json']); value['managed_paths'].append('old-managed')
    put(options['source_root'], 'specroad.json', canonical_json_bytes(value))
    evidence = save_snapshot(options['source_root'])
    for path, raw in evidence.items():
        put(options['project_root'], path, raw)
    put(options['source_root'], 'specroad.json', original['specroad.json'])
    raw = prepare_project_bundle(options['source_root']).source_bytes
    put(options['source_root'], options['source_path'], raw)
    put(options['project_root'], 'specroad.json', b'broken')
    (options['project_root'] / 'old-managed').mkdir()
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = plan_for(options)
    assert inventory(tmp_path) == before
    assert 'old-managed' in plan.data['inventory']['roots']
    assert {'path': 'old-managed', 'kind': 'directory'} in plan.data['inventory']['entries']
    put(options['project_root'], 'old-managed/new.bin', b'must not be ignored')
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        verify_restore_plan(plan.source_bytes)
    assert failure.value.exit_code == 6
    assert rejected(options, 3).reason == 'restore_managed_content_unsupported'


@pytest.mark.parametrize('fault', ['missing_record', 'damaged_record', 'missing_object', 'changed_object', 'identity_path'])
def test_chosen_source_cannot_replace_missing_or_invalid_current_evidence(tmp_path, fault):
    options, _, evidence = retained_case(tmp_path)
    put(options['project_root'], 'specroad.json', b'broken')
    path = options['project_root'] / options['source_path']
    if fault == 'missing_record': path.unlink()
    elif fault == 'damaged_record': path.write_bytes(b'{broken')
    elif fault == 'identity_path': path.rename(path.with_name(ref('BASE', '1') + '.json'))
    else:
        target = options['project_root'] / next(p for p in evidence if p.startswith('archive/'))
        if fault == 'missing_object': target.unlink()
        else: target.write_bytes(b'not the original object')
    rejected(options, 6 if fault == 'identity_path' else 3)


@pytest.mark.parametrize('conflict', ['identity', 'coverage'])
def test_conflicting_retained_declarations_are_not_resolved_by_timestamp_or_order(tmp_path, conflict):
    options, _, _ = retained_case(tmp_path)
    (tmp_path / 'other').mkdir()
    other, original, _ = restore_case(tmp_path / 'other')
    value = json.loads(original['specroad.json'])
    if conflict == 'identity': value['project_id'] = 'different-project'
    else: value['managed_paths'].append('other-managed')
    put(other['source_root'], 'specroad.json', canonical_json_bytes(value))
    files = save_snapshot(other['source_root'], identity=ref('BASE', '1'))
    for path, raw in files.items():
        put(options['project_root'], path, raw)
    put(options['project_root'], 'specroad.json', b'broken')
    rejected(options, 6 if conflict == 'identity' else 3)


@pytest.mark.parametrize('path', ['../outside', '.git', 'spec/CON'])
def test_unsafe_current_configuration_is_not_hidden_by_retained_baseline(tmp_path, path):
    options, original, _ = retained_case(tmp_path)
    value = json.loads(original['specroad.json']); value['managed_paths'].append(path)
    put(options['project_root'], 'specroad.json', canonical_json_bytes(value))
    rejected(options, 7)


@pytest.mark.parametrize('kind', ['document', 'release', 'configured'])
def test_native_verified_partial_bundle_never_qualifies_as_restore_source(tmp_path, kind):
    from test_partial_bundle import project, scope
    from test_partial_bundle_right import configured
    options, _, _ = restore_case(tmp_path)
    origin = tmp_path / 'partial-origin'
    if kind == 'configured':
        _, chain, _ = configured(origin)
        selection = scope('document', configuration_id=chain[-1]['id'])
    else:
        project(origin, kind)
        selection = scope(kind)
    bundle = prepare_partial_bundle(origin, selection)
    verify_bundle(bundle.source_bytes)
    assert bundle.manifest['read_only'] and bundle.manifest['boundary_references']
    put(origin, 'partial.zip', bundle.source_bytes)
    options.update(source_root=origin, source_path='partial.zip')
    assert rejected(options, 3).reason == 'restore_full_project_source_required'


@pytest.mark.parametrize('kind', ['working', 'release'])
@pytest.mark.parametrize('scope', ['specification', 'release', 'document', 'query', 'explicit', 'configured', 'boundary'])
def test_baseline_label_does_not_override_source_scope_or_configuration(tmp_path, kind, scope):
    options, _, raw = restore_case(tmp_path, 'baseline', baseline_kind=kind)
    value = json.loads(raw)
    selectors = {'release': {'release_id': ref('REL')}, 'document': {'document_id': ref('DOC')},
                 'query': {'query_id': ref('QRY')}, 'explicit': {'artifact_ids': [ref('GOAL')]}}
    if scope == 'configured': value['scope_descriptor']['configuration_id'] = ref('CFG')
    elif scope == 'boundary': value['scope_descriptor']['boundary_policy'] = 'partial'
    else: value['scope_descriptor'] = descriptor(scope, selectors.get(scope, {}))
    # The descriptor gate precedes object loading: rehashing this source file
    # cannot turn a partial/configured declaration into the full project scope.
    put(options['source_root'], options['source_path'], canonical_json_bytes(value))
    rejected(options, 3)


@pytest.mark.parametrize('fault', ['missing', 'hash', 'size', 'object_path', 'snapshot_root', 'configuration_hash'])
def test_baseline_original_object_and_native_root_bindings_are_mandatory(tmp_path, fault):
    options, _, raw = restore_case(tmp_path, 'baseline')
    value = json.loads(raw); row = next(r for r in value['manifest'] if r['role'] == 'artifact')
    if fault == 'missing': (options['source_root'] / row['object_path']).unlink()
    elif fault == 'hash': put(options['source_root'], row['object_path'], b'changed')
    elif fault == 'size': row['size'] += 1
    elif fault == 'object_path': row['object_path'] = 'archive/objects/00/' + '0' * 64
    elif fault == 'snapshot_root': value['model_root_sha256'] = '0' * 64
    else: value['configuration_hash'] = '0' * 64
    put(options['source_root'], options['source_path'], canonical_json_bytes(value))
    rejected(options, 3)


@pytest.mark.parametrize('fault', [
    'version', 'policy', 'source_extra', 'source_type', 'descriptor_extra',
    'roots_empty', 'roots_duplicate', 'root_missing', 'missing_child', 'file_parent',
    'inventory_extra', 'inventory_size', 'inventory_duplicate', 'target_extra',
    'target_type', 'target_size', 'target_hash', 'backup_extra', 'reasons_empty',
    'reason_unknown', 'reason_duplicate', 'object_missing', 'object_extra_field',
    'object_size', 'object_hash', 'object_encoding', 'outer_hash'])
def test_closed_wire_rejects_nested_malformed_contracts_after_outer_resigning(tmp_path, fault):
    options, _, _ = restore_case(tmp_path, 'baseline')
    data = plan_for(options).data
    if fault == 'version': data['format_version'] = 'restore-plan-v2'
    elif fault == 'policy': data['policy_version'] = None
    elif fault == 'source_extra': data['source']['verified'] = True
    elif fault == 'source_type': data['source']['kind'] = []
    elif fault == 'descriptor_extra': data['source_descriptor']['trusted'] = True
    elif fault == 'roots_empty': data['inventory']['roots'] = []
    elif fault == 'roots_duplicate': data['inventory']['roots'] *= 2
    elif fault == 'root_missing':
        data['inventory']['entries'] = [r for r in data['inventory']['entries'] if r['path'] != 'spec']
    elif fault == 'missing_child': data['inventory']['entries'].append({'path': 'spec/absent', 'kind': 'missing'})
    elif fault == 'file_parent':
        row = next(r for r in data['inventory']['entries'] if r['path'] == 'spec')
        row.update(kind='file', sha256='0' * 64, size=0)
    elif fault == 'inventory_extra': data['inventory']['complete'] = True
    elif fault == 'inventory_size': next(r for r in data['inventory']['entries'] if r['kind'] == 'file')['size'] = True
    elif fault == 'inventory_duplicate': data['inventory']['entries'].append(data['inventory']['entries'][-1])
    elif fault == 'target_extra': data['target']['entries'][0]['optional'] = True
    elif fault == 'target_type': data['target']['entries'] = {}
    elif fault == 'target_size': data['target']['entries'][0]['size'] = -1
    elif fault == 'target_hash': data['target']['sha256'] = '0' * 64
    elif fault == 'backup_extra': data['backup']['entries'].append(data['target']['entries'][0])
    elif fault == 'reasons_empty': data['preserved'][0]['reasons'] = []
    elif fault == 'reason_unknown': data['preserved'][0]['reasons'] = ['source_claim']
    elif fault == 'reason_duplicate': data['preserved'][0]['reasons'] *= 2
    elif fault == 'object_missing': data['objects'].pop()
    elif fault == 'object_extra_field': data['objects'][0]['verified'] = True
    elif fault == 'object_size': data['objects'][0]['size'] += 1
    elif fault == 'object_hash': data['objects'][0]['sha256'] = '0' * 64
    elif fault == 'object_encoding': data['objects'][0]['data_base64'] = '\u00ff'
    raw = resign(data)
    if fault == 'outer_hash':
        data['restore_plan_sha256'] = '0' * 64; raw = canonical_json_bytes(data)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        RestorePlan(raw)
    assert failure.value.exit_code == 3


@pytest.mark.parametrize('fault', ['bom', 'trailing', 'duplicate_key', 'nan', 'surrogate', 'utf8', 'float_size'])
def test_wire_json_syntax_and_encoding_fail_without_any_project_access(tmp_path, fault, monkeypatch):
    options, _, _ = restore_case(tmp_path)
    raw = plan_for(options).source_bytes
    if fault == 'bom': raw = b'\xef\xbb\xbf' + raw
    elif fault == 'trailing': raw += b'{}'
    elif fault == 'duplicate_key': raw = b'{"project_id":"x",' + raw[1:]
    elif fault == 'nan': raw = raw.replace(b'"size":', b'"size":NaN,"unused":', 1)
    elif fault == 'surrogate': raw = b'{"project_id":"\\ud800"}'
    elif fault == 'utf8': raw = b'\xff'
    else:
        data = json.loads(raw); data['source']['size'] = float(data['source']['size'])
        raw = json.dumps(data, separators=(',', ':'), sort_keys=True).encode()
    monkeypatch.setattr(service, 'boundary', lambda *a: pytest.fail('Malformed wire accessed a project'))
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        verify_restore_plan(raw)
    assert failure.value.exit_code == 3


@pytest.mark.parametrize('fault', ['source_symlink', 'source_hardlink', 'dependency_symlink', 'root_replaced', 'nested_root'])
def test_native_security_remains_separate_from_invalid_source_and_stale_data(tmp_path, fault, monkeypatch):
    options, _, raw = restore_case(tmp_path, 'baseline')
    if fault == 'source_symlink':
        source = options['source_root'] / options['source_path']; source.unlink(); source.symlink_to(tmp_path / 'absent')
    elif fault == 'source_hardlink':
        os.link(options['source_root'] / options['source_path'], tmp_path / 'linked')
    elif fault == 'dependency_symlink':
        row = json.loads(raw)['manifest'][0]; source = options['source_root'] / row['object_path']
        elsewhere = tmp_path / 'outside'; elsewhere.write_bytes(source.read_bytes())
        source.unlink(); source.symlink_to(elsewhere)
    elif fault == 'nested_root': put(options['project_root'], 'spec/nested/specroad.json', b'{}')
    else:
        original = service._verify_live
        def changed(plan, project, origin):
            root = options['project_root']; root.rename(tmp_path / 'former-root'); root.mkdir()
            return original(plan, project, origin)
        monkeypatch.setattr(service, '_verify_live', changed)
        with pytest.raises(RestoreError) as failure:
            plan_for(options)
        assert failure.value.exit_code == 7
        assert list(options['project_root'].iterdir()) == []
        return
    rejected(options, 7)


@pytest.mark.parametrize('operation', ['prepare', 'verify'])
def test_actual_read_failure_is_io_error_and_never_a_complete_plan(tmp_path, operation, monkeypatch):
    options, _, _ = restore_case(tmp_path)
    plan = plan_for(options)
    def denied(fd, length):
        raise OSError(5, 'synthetic read failure')
    monkeypatch.setattr(os, 'read', denied)
    with no_write_attempts(), pytest.raises(RestoreError) as failure:
        if operation == 'prepare': plan_for(options)
        else: verify_restore_plan(plan.source_bytes)
    assert failure.value.exit_code == 5


def test_changes_between_current_evidence_discovery_and_inventory_are_stale(tmp_path, monkeypatch):
    options, _, evidence = retained_case(tmp_path)
    put(options['project_root'], 'specroad.json', b'broken')
    original = service.observe
    path = options['source_path']; changed_bytes = evidence[path] + b'\n'
    def changed(bound, roots):
        put(options['project_root'], path, changed_bytes)
        return original(bound, roots)
    monkeypatch.setattr(service, 'observe', changed)
    with pytest.raises(RestoreError) as failure:
        plan_for(options)
    assert failure.value.exit_code == 6
    assert (options['project_root'] / path).read_bytes() == changed_bytes
    assert not (options['project_root'] / '.specroad').exists()
