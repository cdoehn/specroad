"""Real retry, ownership and receipt-race boundaries of normal adapters."""
import json
import os
from contextvars import Context

import pytest

from specroad.changes import project_lock, read_transaction_completion, transaction_preflight
from specroad.changes._lock_files import LockFiles
from specroad.changes.normal_access import require_normal_access
from specroad.changes.normal_completion import NormalCompletionProof
from specroad.changes.receipt_values import completion_marker_path, transaction_receipt_path
from specroad.changes.write_guard_values import MARKER_PATH
from specroad.cli.application import dispatch_result
from specroad.cli.contracts import CommandClass
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.storage.project import ProjectSource
from support.authoring_execution import KINDS
from support.publication import TRANSACTION, options
from support.read_only import inventory, no_write_attempts
from test_normal_write_adapters import adapter, ALLOW
from test_write_guard import setup, publish, FAILURES


@pytest.mark.parametrize('kind', KINDS)
def test_real_domain_retry_returns_original_without_second_revision_or_allocation(tmp_path, kind):
    root = tmp_path / 'project'; run = adapter(root, kind)
    first = run(ALLOW)
    before = inventory(tmp_path)
    with no_write_attempts():
        repeated = run(ALLOW)
    assert repeated['replayed'] and not repeated['completion']['current_target_verified']
    assert repeated['completion']['result_object'] == first['completion']['result_object']
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('part', ('extra', 'missing', 'noncanonical', 'symlink'))
def test_damaged_completed_receipts_cannot_authorize_a_normal_retry(tmp_path, part):
    root = tmp_path / 'project'; run = adapter(root, 'update'); first = run(ALLOW)
    transaction = first['completion']['transaction_id']
    path = root / transaction_receipt_path(transaction)
    if part == 'extra': path.with_name('unbound.json').write_bytes(b'{}')
    elif part == 'missing': (root / completion_marker_path(transaction)).unlink()
    elif part == 'noncanonical': path.write_bytes(path.read_bytes() + b'\n')
    else:
        saved = tmp_path.parent / (tmp_path.name + '-saved-receipt')
        saved.write_bytes(path.read_bytes()); path.unlink(); path.symlink_to(saved)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(FAILURES):
        run(ALLOW)
    assert inventory(tmp_path) == before


def test_current_target_claim_requires_original_preflight_and_live_matching_bytes(tmp_path):
    _, _, preflight = setup(tmp_path); first = publish(tmp_path, preflight).data
    before = inventory(tmp_path)
    with no_write_attempts():
        old = read_transaction_completion(ProjectSource(tmp_path), TRANSACTION).data
        live = read_transaction_completion(ProjectSource(tmp_path), TRANSACTION, preflight=preflight).data
    assert old['result_object'] == live['result_object'] == first['result_object']
    assert not old['current_target_verified'] and live['current_target_verified']
    assert not live['write_authorized'] and inventory(tmp_path) == before
    # A legitimate later source edit must not retroactively change old success.
    path = tmp_path / preflight.request.documents[0].path
    value = json.loads(path.read_bytes()); value['title'] = 'Later independent title'
    path.write_bytes(canonical_json_bytes(value))
    before = inventory(tmp_path)
    with no_write_attempts():
        historical = read_transaction_completion(ProjectSource(tmp_path), TRANSACTION).data
        with pytest.raises(FAILURES):
            read_transaction_completion(ProjectSource(tmp_path), TRANSACTION, preflight=preflight)
    assert historical['result_object'] == first['result_object']
    assert not historical['current_target_verified'] and inventory(tmp_path) == before


@pytest.mark.parametrize('replacement', ('same_bytes_new_inode', 'same_size_bytes', 'parent'))
def test_receipt_proof_never_rebinds_to_replaced_records(tmp_path, replacement):
    _, _, preflight = setup(tmp_path); publish(tmp_path, preflight)
    source = ProjectSource(tmp_path)
    path = tmp_path / transaction_receipt_path(TRANSACTION)
    with LockFiles(tmp_path) as files:
        proof = NormalCompletionProof(files, source, TRANSACTION)
        if replacement == 'same_bytes_new_inode':
            new = path.with_name('replacement'); new.write_bytes(path.read_bytes()); os.replace(new, path)
        elif replacement == 'same_size_bytes':
            raw = path.read_bytes(); changed = raw.replace(b'Changed', b'CHANGED')
            assert changed != raw and len(changed) == len(raw); path.write_bytes(changed)
        else:
            raw = {p.name: p.read_bytes() for p in path.parent.iterdir()}
            path.parent.rename(path.parent.with_name(path.parent.name + '-preserved'))
            path.parent.mkdir()
            for name, data in raw.items(): (path.parent / name).write_bytes(data)
        before = inventory(tmp_path)
        with no_write_attempts(), pytest.raises(FAILURES):
            proof.read(transaction_receipt_path(TRANSACTION))
        assert inventory(tmp_path) == before


def test_new_marker_during_completion_read_invalidates_the_observation(tmp_path, monkeypatch):
    _, _, preflight = setup(tmp_path); publish(tmp_path, preflight)
    real = NormalCompletionProof.read; seen = []
    def read(self, path, **kw):
        value = real(self, path, **kw)
        if not seen:
            seen.append(path)
            marker = tmp_path / MARKER_PATH
            marker.parent.mkdir(exist_ok=True); marker.write_bytes(b'{}')
        return value
    monkeypatch.setattr(NormalCompletionProof, 'read', read)
    with pytest.raises(ModelError) as error:
        read_transaction_completion(ProjectSource(tmp_path), TRANSACTION)
    assert error.value.exit_code == 5 and seen and (tmp_path / MARKER_PATH).read_bytes() == b'{}'


@pytest.mark.parametrize('kind', ('mutex_without_record', 'unverifiable_owner', 'foreign_owner'))
def test_unknown_owner_blocks_normal_calls_without_repair_or_model_loading(tmp_path, kind):
    _, _, preflight = setup(tmp_path)
    if kind != 'mutex_without_record':
        with project_lock(tmp_path, **options(preflight)) as held:
            record = held.record.data
        if kind == 'foreign_owner': record['host_id'] = 'synthetic-foreign-host'
        else: record['process_start_id'] = None
        (tmp_path / '.specroad/locks/project.json').write_bytes(canonical_json_bytes(record))
    with LockFiles(tmp_path) as native:
        if kind == 'mutex_without_record': native.acquire()
        before = inventory(tmp_path)
        with no_write_attempts():
            for command_class in (CommandClass.READ_ONLY, CommandClass.PLAN_OUTPUT, CommandClass.NORMATIVE_WRITE):
                facts = transaction_preflight(tmp_path, command_class=command_class,
                    expected_project_id='sample', dry_run=command_class is CommandClass.NORMATIVE_WRITE).data
                assert facts['exit_code'] == 5 and facts['reason'] == 'project_unknown'
                assert not facts['normal_operation_started'] and not facts['recovery_attempted']
            with pytest.raises(ModelError) as error: require_normal_access(tmp_path)
            assert error.value.exit_code == 5
            result = dispatch_result(['query', '--project', str(tmp_path)])
            assert result.exit_code == 5 and result.details['preflight']['reason'] == 'project_unknown'
            diagnosis = dispatch_result(['environment', 'check', '--project', str(tmp_path)])
            assert diagnosis.exit_code == 5 and diagnosis.result['compatible'] is False
        assert inventory(tmp_path) == before


def test_only_actual_writer_capability_may_read_its_own_inputs(tmp_path):
    _, _, preflight = setup(tmp_path)
    with project_lock(tmp_path, **options(preflight)):
        before = inventory(tmp_path)
        with no_write_attempts():
            require_normal_access(tmp_path, expected_project_id='sample')
            # Same PID and inode outside the actual capability context do not suffice.
            with pytest.raises(ModelError) as error:
                Context().run(require_normal_access, tmp_path, expected_project_id='sample')
        assert error.value.exit_code == 6 and error.value.diagnostic()['exit_code'] == 6
        assert inventory(tmp_path) == before
