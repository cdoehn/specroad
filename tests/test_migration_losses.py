"""16.h: complete preservation inventory, original bytes and literal losses."""
import copy
import json
from dataclasses import FrozenInstanceError
from hashlib import sha256
from unittest.mock import patch
import pytest

from specroad.migration.planning import plan_migration, migration_inputs
from specroad.migration.losses import MigrationLossReport
from specroad.migration.plan_recheck import recheck_migration_plan
from support.migration_plans import FIELDS, target_inputs, mapped_inputs, planned_files, vector_source
from support.reference01 import encoded, digest, put, full_project, finish_proposal
from support.migration_losses import (REQ, OPAQUE, extension_source, with_config_extensions,
    target_with_extensions, candidate, assess)


def test_unknown_nested_extensions_and_external_provenance_remain_exact():
    files, inputs, target, result = candidate()
    old, new = json.loads(files[REQ]), json.loads(target[REQ])
    for key in ('id', 'created_at', 'created_by', 'extensions', 'external_identities'):
        assert new[key] == old[key]
    assert new['relations'][0]['extensions'] == old['relations'][0]['extensions']
    assert new['extensions']['未知.namespace'] == OPAQUE
    assert target['notes.bin'] == files['notes.bin']
    report = assess(files, target, inputs)
    assert report.lossless and report.data['losses'] == []
    assert result.data['loss_report'] == report.data
    assert not report.write_authorized and report.data['approval_granted'] is False


def test_missing_configuration_namespace_is_visible_and_blocks_the_entire_plan():
    files = extension_source(); with_config_extensions(files, {'未知.config': OPAQUE})
    inputs = target_inputs(files); before = copy.deepcopy((files, inputs))
    result = plan_migration(files, inputs=inputs, **FIELDS)
    assert not result.ready and result.change_plan is None
    assert result.data['expected_target_model_root_sha256'] is None
    assert result.data['blockers'] == [{'reason': 'migration_lossless_contract_violation', 'path': 'specroad.json'}]
    losses = result.data['loss_report']['losses']
    assert len(losses) == 1 and losses[0]['path'] == 'specroad.json'
    # The entire absent member is inventoried once, retaining its actual content.
    assert losses[0]['pointer'] == '/extensions'
    assert losses[0]['before'] == {'present': True, 'value': {'未知.config': OPAQUE}}
    assert losses[0]['after'] == {'present': False, 'value': None}
    assert (files, inputs) == before


def test_explicit_configuration_preserves_old_namespaces_and_can_add_new_ones():
    files = extension_source(); with_config_extensions(files, {'unknown.config': OPAQUE})
    inputs = target_with_extensions(files, {'unknown.config': OPAQUE, 'new.namespace': {'enabled': True}})
    files, inputs, target, result = candidate(files, inputs)
    assert json.loads(target['specroad.json'])['extensions'] == {
        'unknown.config': OPAQUE, 'new.namespace': {'enabled': True}}
    assert result.data['loss_report']['lossless'] is True


def test_conflicting_configuration_values_are_not_silently_repaired():
    files = extension_source(); with_config_extensions(files, {'unknown.config': {'a': 7, 'b': None}})
    inputs = target_with_extensions(files, {'unknown.config': {'a': 8}})
    before = copy.deepcopy(inputs)
    result = plan_migration(files, inputs=inputs, **FIELDS)
    assert not result.ready and result.change_plan is None and inputs == before
    assert [(r['pointer'], r['reason']) for r in result.data['loss_report']['losses']] == [
        ('/extensions/unknown.config/a', 'changed'), ('/extensions/unknown.config/b', 'missing')]


def test_missing_inputs_do_not_claim_an_empty_successful_loss_inventory():
    result = plan_migration(extension_source(), inputs=migration_inputs(), **FIELDS)
    assert not result.ready and result.data['loss_report'] is None


def test_multiple_losses_have_literal_values_and_fully_bound_independent_ids():
    files, inputs, target, _ = candidate()
    value = json.loads(target[REQ]); value['title'] = 'different'
    del value['extensions']['example.note']; target[REQ] = encoded(value)
    del target['notes.bin']
    before = copy.deepcopy((files, target, inputs)); report = assess(files, target, inputs); data = report.data
    observed = [(r['path'], r['pointer'], r['reason'], r['hash_domain']) for r in data['losses']]
    assert observed == [('notes.bin', '', 'missing', 'bytes'),
        (REQ, '/extensions/example.note', 'missing', 'json'), (REQ, '/title', 'changed', 'json')]
    assert data['losses'][2]['before'] == {'present': True, 'value': 'Preserve original data'}
    assert data['losses'][2]['after'] == {'present': True, 'value': 'different'}
    assert data['losses'][0]['before']['value'] == {'size': len(files['notes.bin']),
        'sha256': sha256(files['notes.bin']).hexdigest()}
    for row in data['losses']:
        unsigned = {k: v for k, v in row.items() if k != 'loss_id'}
        assert row['loss_id'] == 'LOSS-' + digest(['migration-loss-v1', data['binding'], unsigned])
    assert data['report_sha256'] == digest({k: v for k, v in data.items() if k != 'report_sha256'})
    assert data['binding']['source_files_sha256'] == digest([
        {'path': p, 'size': len(raw), 'sha256': sha256(raw).hexdigest()} for p, raw in sorted(files.items())])
    assert data['binding']['inputs_sha256'] == digest(inputs)
    assert not report.lossless and (files, target, inputs) == before


def test_inventory_is_deterministic_and_owns_nested_values():
    files, inputs, target, _ = candidate()
    value = json.loads(target[REQ]); value['title'] = 'different'; target[REQ] = encoded(value)
    first = assess(files, target, inputs)
    second = assess(dict(reversed(list(files.items()))), dict(reversed(list(target.items()))), copy.deepcopy(inputs))
    assert first.data == second.data
    changed = first.data; changed['losses'][0]['before']['value'] = 'forged'
    assert first.data['losses'][0]['before']['value'] == 'Preserve original data'
    with pytest.raises(TypeError): bool(first)
    with pytest.raises(FrozenInstanceError): first._encoded = b'{}'


@pytest.mark.parametrize('status', ['applied', 'rejected', 'stale'])
def test_closed_history_originals_payloads_and_audit_remain_byte_identical(status):
    files = full_project(); finish_proposal(files, status)
    inputs = mapped_inputs(files); files, inputs, target, result = candidate(files, inputs)
    for path, raw in files.items():
        if path.startswith(('spec/evidence/', 'spec/relation_reviews/', 'spec/baselines/',
                            'spec/proposals/', 'archive/', 'attachments/')) or path == 'src/reference.py':
            assert target[path] == raw
    assert assess(files, target, inputs).lossless
    assert result.data['current_readiness_verified'] is False


def test_open_proposal_keeps_original_audit_and_its_original_archive():
    files = full_project(); inputs = mapped_inputs(files)
    files, inputs, target, _ = candidate(files, inputs)
    path = 'spec/proposals/SR-PROP-0001.json'; old = json.loads(files[path]); new = json.loads(target[path])
    for key in ('reviews', 'control_history', 'created_by', 'created_at'):
        assert new.get(key) == old.get(key)
    address = sha256(files[path]).hexdigest()
    assert target['archive/objects/'+address[:2]+'/'+address] == files[path]
    assert assess(files, target, inputs).lossless


@pytest.mark.parametrize('where', ['original', 'payload', 'archive', 'manifest'])
def test_each_protected_location_is_inventoried_without_rewriting(where):
    files = full_project(); inputs = mapped_inputs(files); files, inputs, target, _ = candidate(files, inputs)
    path = {'original': 'spec/evidence/SR-EVD-0001.json', 'payload': 'src/reference.py',
        'archive': next(p for p in sorted(target) if p.startswith('archive/objects/')),
        'manifest': 'mappings/legacy-manifest.json'}[where]
    if where == 'manifest':
        value = json.loads(target[path]); value['source']['project_id'] = 'forged'; target[path] = encoded(value)
    else: target[path] += b' '
    before = dict(target); report = assess(files, target, inputs)
    assert any(r['path'] == path for r in report.data['losses']) and target == before
    assert not report.lossless


def test_planner_detects_accidental_transformer_loss_before_releasing_a_change_plan():
    from specroad.migration.plan_target import _stamp
    def broken(old, actor, at):
        value = _stamp(old, actor, at)
        if old['artifact_type'] == 'requirement': value['extensions'] = {}
        return value
    files = extension_source(); before = dict(files)
    with patch('specroad.migration.planning._stamp', broken):
        result = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    assert not result.ready and result.change_plan is None and files == before
    assert len(result.data['loss_report']['losses']) == 2


def test_lossless_plan_still_passes_native_recheck_without_any_write_permission():
    files, inputs, target, result = candidate()
    verified = recheck_migration_plan(result.change_plan.canonical_bytes, files,
        expected_target_version='0.2.0', expected_inputs_sha256=result.data['inputs_sha256'],
        expected_plan_sha256=result.change_plan.sha256)
    assert not verified.write_authorized and assess(files, target, inputs).lossless


def test_declared_target_resource_cannot_disappear_after_transformation():
    files, inputs, target, _ = candidate()
    del target['profiles/core.json']
    rows = assess(files, target, inputs).data['losses']
    assert len(rows) == 1 and rows[0]['path'] == 'profiles/core.json'
    assert rows[0]['reason'] == 'missing' and rows[0]['hash_domain'] == 'bytes'
