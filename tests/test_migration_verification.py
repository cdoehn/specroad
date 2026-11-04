"""Full observed source/target verification, with no saved success shortcuts."""
from hashlib import sha256
import json
from pathlib import Path

import pytest

from specroad.bundles.errors import BundleError
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from specroad.migration.plan_values import file_bindings
from specroad.migration.verification import verify_migration, verify_migration_project
from specroad.changes.schema_transition_values import SchemaTransitionError
from support.migration_transaction import apply
from support.migration_verification import case, verify
from support.migration_history import evidence_source, historical_contract_host, BASELINE, EVIDENCE
from support.read_only import inventory, no_write_attempts


def test_complete_byte_inventory_and_native_target_validation_are_read_only(tmp_path):
    data = case(tmp_path); before = inventory(tmp_path)
    with no_write_attempts():
        result = verify(data)
    value = result.data
    assert value['verified'] and value['observation'] == 'provided_target_bytes'
    assert value['source_files'] == file_bindings(data[1])
    assert value['target_files'] == file_bindings(data[6])
    assert value['target_files_sha256'] == digest(file_bindings(data[6]))
    assert value['binding']['target_model_root_sha256'] == data[2].data['operations'][0]['target_model_root_sha256']
    assert value['validation']['checks_complete'] and value['validation']['model_valid']
    assert value['loss_report']['lossless']
    assert inventory(tmp_path) == before
    assert not any(value[key] for key in ('atomic_snapshot', 'current_context_verified',
        'external_run_verified', 'current_readiness_verified', 'write_authorized',
        'approval_granted', 'release_authorized'))
    value['verified'] = False
    assert result.data['verified'] and result.sha256 == sha256(jcs(result.data)).hexdigest()
    with pytest.raises(TypeError): bool(result)


def test_live_verifier_qualifies_real_transaction_and_current_target(tmp_path):
    data = case(tmp_path); root, source, plan, execution, backup, report, target, bindings = data
    applied = apply(root, plan, execution)
    assert applied['write_state'] == 'committed'
    before = inventory(root)
    with no_write_attempts():
        value = verify_migration_project(root, backup, plan.source_bytes, report.canonical_bytes,
            transaction_id=execution['transaction_id'], **bindings).data
    assert value['observation'] == 'stable_live_target' and not value['atomic_snapshot']
    assert value['target_files'] == file_bindings(target)
    assert value['operational_evidence']['files']
    assert value['operational_evidence']['transaction_id'] == execution['transaction_id']
    assert inventory(root) == before


@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('result', ['passed', 'failed', 'incomplete', 'skipped'])
def test_historical_originals_and_hashes_survive_full_verification(tmp_path, nested, result):
    data = case(tmp_path, files=evidence_source(nested=nested, result=result))
    observed = []; gate = historical_contract_host(observed)
    value = verify(data, gates=(gate,)).data
    old, target = data[1], data[6]
    for path in (BASELINE, EVIDENCE):
        assert old[path] == target[path]
        identity = json.loads(old[path])['id']
        row = next(row for row in value['historical']['historical']['records'] if row['artifact_id'] == identity)
        assert row['original_byte_sha256'] == sha256(old[path]).hexdigest()
    assert value['historical']['historical_integrity_verified']
    assert not value['historical']['current_context_verified'] and observed


@pytest.mark.parametrize('binding', ['expected_backup_sha256','expected_source_files_sha256',
    'expected_plan_sha256','expected_inputs_sha256','expected_report_sha256','expected_target_version'])
def test_every_external_binding_is_required(tmp_path, binding):
    data = case(tmp_path); bindings = dict(data[-1])
    bindings[binding] = '9' * 64 if binding != 'expected_target_version' else '0.1.0'
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((BundleError, ModelError)):
        verify_migration(data[4], data[2].source_bytes, data[5].canonical_bytes, data[6], **bindings)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['missing','additional','changed','legacy','archive','configuration'])
def test_no_source_or_target_byte_can_be_omitted_from_validation(tmp_path, change):
    data = case(tmp_path); target = dict(data[6])
    if change == 'missing': target.pop(next(p for p in target if p.startswith('spec/')))
    elif change == 'additional': target['unexpected.json'] = b'{}'
    elif change == 'changed':
        path = next(p for p in target if p.startswith('spec/')); target[path] += b' '
    elif change == 'legacy': target['mappings/legacy-manifest.json'] += b' '
    elif change == 'configuration': target['specroad.json'] += b' '
    else:
        path = next(p for p in target if p.startswith('archive/')); target[path] += b'changed'
    with no_write_attempts(), pytest.raises(ModelError):
        verify_migration(data[4], data[2].source_bytes, data[5].canonical_bytes, target, **data[-1])


@pytest.mark.parametrize('field', ['ready','write_authorized','loss_report','expected_target_model_root_sha256'])
def test_rehashed_positive_report_is_recomputed_not_trusted(tmp_path, field):
    data = case(tmp_path); report = data[5].data
    report[field] = True if field in ('ready','write_authorized') else {}
    if field == 'ready': report[field] = False
    raw = jcs(report); bindings = {**data[-1], 'expected_report_sha256': sha256(raw).hexdigest()}
    with no_write_attempts(), pytest.raises(ModelError, match='migration_report_recomputation_mismatch'):
        verify_migration(data[4], data[2].source_bytes, raw, data[6], **bindings)


def test_old_history_does_not_replace_required_current_semantic_service(tmp_path):
    data = case(tmp_path, files=evidence_source())
    with no_write_attempts(), pytest.raises(ModelError, match='migration_target_validation_failed'):
        verify(data)


@pytest.mark.parametrize('change', ['target','receipt','extra','symlink','active'])
def test_live_target_and_receipts_must_still_exist_unchanged(tmp_path, change):
    data = case(tmp_path); root, _, plan, args, backup, report, target, bindings = data
    applied = apply(root, plan, args)
    if change == 'target': (root/'specroad.json').write_bytes(target['specroad.json'] + b' ')
    elif change == 'receipt':
        reference = applied['receipts']['transaction']
        path = root/reference['path']
        assert path.is_file()
        assert sha256(path.read_bytes()).hexdigest() == reference['sha256']
        path.write_bytes(b'{}')
    elif change == 'extra': (root/'unplanned.json').write_bytes(b'{}')
    elif change == 'active':
        path = root/'.specroad/transactions/foreign'; path.mkdir(parents=True); (path/'journal.json').write_bytes(b'{}')
    else: (root/'foreign-link').symlink_to(tmp_path/'backup/source.zip')
    before = inventory(root)
    # Boundary safety errors deliberately keep their native typed class.
    from specroad.security import SafetyViolation
    with no_write_attempts(), pytest.raises((ModelError, SchemaTransitionError, BundleError, SafetyViolation)) as caught:
        verify_migration_project(root, backup, plan.source_bytes, report.canonical_bytes,
            transaction_id=args['transaction_id'], **bindings)
    if change == 'receipt':
        assert isinstance(caught.value, SchemaTransitionError)
        assert caught.value.reason == 'transition_receipt_changed'
    assert inventory(root) == before
