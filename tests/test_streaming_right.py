"""Observed blockers, complete native hashes and retained critical inputs."""
from hashlib import sha256
import errno
import io
import json
import os
from pathlib import Path
import tempfile

import pytest

from specroad.runtime import controlled
from specroad.runtime.consumption import CounterSample, WorkConsumption
from specroad.runtime.payload_hashing import fingerprint_file_outcome
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.storage import byte_binding
from support.processes import run_core
from support.read_only import inventory, no_write_attempts


def work():
    return WorkConsumption(sampler=lambda: CounterSample(None, None, None))


def inputs(root):
    payload = bytes(range(256)) * 257
    (root / 'payload.bin').write_bytes(payload)
    (root / 'journal.json').write_bytes(b'critical active journal fixture')
    (root / 'before-image.bin').write_bytes(b'critical original input fixture')
    (root / 'checkpoint.bin').write_bytes(b'confirmed checkpoint fixture')
    return payload


def refuse_large_allocations(monkeypatch, largest):
    reserve = byte_binding.allocate_transfer_buffer

    def allocation(size):
        if size > largest:
            raise MemoryError('labelled buffer allocation injection')
        return bytearray(size)

    def bounded_reserve(block_size, *, attempts):
        with monkeypatch.context() as local:
            local.setattr(byte_binding, 'bytearray', allocation, raising=False)
            return reserve(block_size, attempts=attempts)

    monkeypatch.setattr(byte_binding, 'allocate_transfer_buffer', bounded_reserve)


@pytest.mark.parametrize('capacity', [1, 3, 1024, 65536, 1048576])
def test_complete_native_hash_outcome_is_independent_of_transfer_capacity(tmp_path, capacity):
    raw = inputs(tmp_path); before = inventory(tmp_path)
    call = work().begin()
    with no_write_attempts():
        outcome = fingerprint_file_outcome(ProjectBoundary(tmp_path), 'payload.bin', call, block_size=capacity)
    report = call.finish()
    assert outcome['state'] == 'completed' and outcome['exit_code'] == 0 and outcome['blocker'] is None
    assert outcome['fingerprint'] == {'size': len(raw), 'sha256': sha256(raw).hexdigest()}
    assert outcome['transfer'] == {'strategy': 'bounded_streaming', 'requested_block_bytes': capacity,
        'buffer_attempts_bytes': [min(capacity, 65536)], 'reserved_buffer_bytes': min(capacity, 65536)}
    assert report['invocation']['controls']['intervals']['payload_bytes']['last_completed'] == 65536
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('available', [32768, 1024, 1])
def test_successful_smaller_alternative_reports_only_actual_allocation_attempts(tmp_path, monkeypatch, available):
    raw = inputs(tmp_path); before = inventory(tmp_path)
    refuse_large_allocations(monkeypatch, available)
    call = work().begin()
    with no_write_attempts():
        outcome = fingerprint_file_outcome(ProjectBoundary(tmp_path), 'payload.bin', call)
    call.finish()
    attempts = outcome['transfer']['buffer_attempts_bytes']
    assert outcome['exit_code'] == 0 and outcome['blocker'] is None
    assert outcome['fingerprint'] == {'size': len(raw), 'sha256': sha256(raw).hexdigest()}
    assert attempts[0] == 65536 and attempts[-1] == outcome['transfer']['reserved_buffer_bytes'] == available
    assert all(after == before // 2 for before, after in zip(attempts, attempts[1:]))
    assert inventory(tmp_path) == before


def test_failed_one_byte_minimum_reports_finite_blocker_without_source_consumption(tmp_path, monkeypatch):
    inputs(tmp_path); before = inventory(tmp_path)
    refuse_large_allocations(monkeypatch, 0)

    def forbidden(*args, **kwargs):
        raise AssertionError('No stream may consume the input without a buffer')

    monkeypatch.setattr(controlled, 'FileIO', forbidden)
    ledger = work(); call = ledger.begin()
    with no_write_attempts():
        outcome = fingerprint_file_outcome(ProjectBoundary(tmp_path), 'payload.bin', call)
    report = call.finish()
    assert outcome['state'] == 'blocked' and outcome['exit_code'] == 5 and outcome['fingerprint'] is None
    assert outcome['transfer']['buffer_attempts_bytes'] == [2 ** n for n in range(16, -1, -1)]
    assert outcome['transfer']['reserved_buffer_bytes'] is None
    assert outcome['blocker'] == {'blocked_reason': 'memory_unavailable', 'failed_stage': 'buffer_allocation',
        'native_errno': None, 'required_action': 'make_memory_for_the_failed_step_available',
        'minimum_failed_buffer_bytes': 1, 'project_writes_performed': False, 'checkpoint': None,
        'retry_requires_input_revalidation': True, 'automatic_retry_performed': False}
    assert report['invocation']['accounted']['memory_peak_bytes']['value'] == 0
    assert report['invocation']['controls']['checks'] == 0 and inventory(tmp_path) == before


@pytest.mark.parametrize('number,reason', [
    (errno.ENOMEM, 'memory_unavailable'), (errno.EACCES, 'access_denied'),
    (errno.EIO, 'io_failure'), (errno.ENOSPC, 'storage_unavailable'),
    (errno.EMFILE, 'descriptor_unavailable'), (errno.ENFILE, 'descriptor_unavailable'),
], ids=['memory', 'permission', 'io', 'storage', 'process_descriptors', 'system_descriptors'])
def test_io_failure_after_actual_read_keeps_inputs_and_never_retries_or_returns_partial_hash(tmp_path, monkeypatch, number, reason):
    inputs(tmp_path); before = inventory(tmp_path); reads = []

    class FailingFile(io.FileIO):
        def readinto(self, target):
            reads.append(super().readinto(target))
            raise OSError(number, 'SENSITIVE native detail', '/SENSITIVE/source')

    monkeypatch.setattr(controlled, 'FileIO', FailingFile)
    ledger = work(); call = ledger.begin()
    with no_write_attempts():
        outcome = fingerprint_file_outcome(ProjectBoundary(tmp_path), 'payload.bin', call, block_size=1024)
    report = call.finish()
    assert outcome['exit_code'] == 5 and outcome['fingerprint'] is None and reads == [1024]
    blocker = outcome['blocker']
    assert blocker['blocked_reason'] == reason and blocker['native_errno'] == number
    assert blocker['failed_stage'] == 'bounded_hash_step' and blocker['minimum_failed_buffer_bytes'] is None
    assert blocker['automatic_retry_performed'] is False and blocker['retry_requires_input_revalidation'] is True
    assert blocker['checkpoint'] is None and blocker['project_writes_performed'] is False
    assert 'SENSITIVE' not in json.dumps(outcome)
    assert report['invocation']['controls']['phases']['payload_hash'] == {'start': 1, 'end': 0}
    assert ledger.begin().finish()['invocation']['accounted']['memory_peak_bytes']['value'] == 0
    assert inventory(tmp_path) == before


def test_memory_failure_after_read_does_not_restart_an_already_advanced_source(tmp_path, monkeypatch):
    inputs(tmp_path); before = inventory(tmp_path); reads = []

    class FailingFile(io.FileIO):
        def readinto(self, target):
            reads.append(super().readinto(target))
            raise MemoryError('labelled failure after native input advanced')

    monkeypatch.setattr(controlled, 'FileIO', FailingFile)
    ledger = work(); call = ledger.begin()
    with no_write_attempts():
        outcome = fingerprint_file_outcome(ProjectBoundary(tmp_path), 'payload.bin', call)
    call.finish()
    assert reads == [65536] and outcome['fingerprint'] is None
    assert outcome['blocker']['blocked_reason'] == 'memory_unavailable'
    assert outcome['blocker']['failed_stage'] == 'bounded_hash_step'
    assert outcome['blocker']['minimum_failed_buffer_bytes'] is None
    assert ledger.begin().finish()['invocation']['accounted']['memory_peak_bytes']['value'] == 0
    assert inventory(tmp_path) == before


_NATIVE_PREFIX = '''
import json, os, resource
from specroad.runtime.consumption import WorkConsumption, CounterSample
from specroad.runtime.payload_hashing import fingerprint_file_outcome
from specroad.security import ProjectBoundary
from specroad.security import resource_access
from specroad.storage import byte_binding
boundary = ProjectBoundary('.')
call = WorkConsumption(sampler=lambda: CounterSample(None, None, None)).begin()
'''


def test_real_descriptor_limit_blocks_guarded_open_without_touching_critical_files(tmp_path):
    inputs(tmp_path); before = inventory(tmp_path)
    body = _NATIVE_PREFIX + '''
previous = resource.getrlimit(resource.RLIMIT_NOFILE)
try:
    resource.setrlimit(resource.RLIMIT_NOFILE, (0, previous[1]))
    outcome = fingerprint_file_outcome(boundary, 'payload.bin', call)
finally:
    resource.setrlimit(resource.RLIMIT_NOFILE, previous)
call.finish()
print(json.dumps(outcome))
'''
    completed = run_core(body, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    outcome = json.loads(completed.stdout)
    assert outcome['exit_code'] == 5 and outcome['fingerprint'] is None
    assert outcome['blocker']['blocked_reason'] == 'descriptor_unavailable'
    assert outcome['blocker']['native_errno'] == errno.EMFILE
    assert outcome['blocker']['failed_stage'] == 'guarded_open'
    assert outcome['transfer']['buffer_attempts_bytes'] == [] and inventory(tmp_path) == before


def test_real_permission_denial_is_reported_without_bypassing_file_mode():
    # A top-level owned directory allows an initially root child to drop its
    # identity before the real guarded read; no permission-bypass oracle.
    with tempfile.TemporaryDirectory(prefix='specroad-streaming-denied-') as directory:
        root = Path(directory); root.chmod(0o755)
        inputs(root); before = inventory(root)
        target = root / 'payload.bin'; original_mode = target.stat().st_mode & 0o777
        target.chmod(0)
        body = _NATIVE_PREFIX + '''
if os.geteuid() == 0:
    import pwd
    nobody = pwd.getpwnam('nobody')
    os.setgroups([])
    os.setgid(nobody.pw_gid)
    os.setuid(nobody.pw_uid)
outcome = fingerprint_file_outcome(boundary, 'payload.bin', call)
call.finish()
print(json.dumps(outcome))
'''
        try:
            completed = run_core(body, root, capture=True)
        finally:
            target.chmod(original_mode)
        assert completed.returncode == 0, completed.stderr
        outcome = json.loads(completed.stdout)
        assert outcome['exit_code'] == 5 and outcome['fingerprint'] is None
        assert outcome['blocker']['blocked_reason'] == 'access_denied'
        assert outcome['blocker']['native_errno'] == errno.EACCES
        assert outcome['blocker']['required_action'] == 'restore_read_and_traverse_permission'
        assert inventory(root) == before


def test_native_memory_refusal_in_injected_indivisible_initializer_reports_no_invented_minimum(tmp_path):
    inputs(tmp_path); before = inventory(tmp_path)
    body = _NATIVE_PREFIX + '''
def native_refused_allocation():
    # A labelled stand-in for an indivisible initializer. The allocation really
    # fails under this child's address-space limit; it is not a SHA-256 memory
    # benchmark or a claim that SHA-256 requires this fixture-sized allocation.
    previous = resource.getrlimit(resource.RLIMIT_AS)
    try:
        resource.setrlimit(resource.RLIMIT_AS, (0, previous[1]))
        bytearray(1 << 40)
    finally:
        resource.setrlimit(resource.RLIMIT_AS, previous)
byte_binding.sha256 = native_refused_allocation
outcome = fingerprint_file_outcome(boundary, 'payload.bin', call)
report = call.finish()
print(json.dumps({'outcome': outcome, 'controls': report['invocation']['controls']}))
'''
    completed = run_core(body, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr
    data = json.loads(completed.stdout); outcome = data['outcome']
    assert outcome['exit_code'] == 5 and outcome['fingerprint'] is None
    assert outcome['blocker']['blocked_reason'] == 'memory_unavailable'
    assert outcome['blocker']['failed_stage'] == 'bounded_hash_step'
    assert outcome['blocker']['minimum_failed_buffer_bytes'] is None
    assert outcome['transfer']['reserved_buffer_bytes'] == 65536
    assert data['controls']['phases']['payload_hash'] == {'start': 1, 'end': 0}
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('invalid', [0, True, 1048577])
def test_invalid_buffer_request_is_not_reclassified_as_an_observed_host_blocker(tmp_path, invalid):
    call = work().begin()
    with pytest.raises(ValueError), no_write_attempts():
        fingerprint_file_outcome(ProjectBoundary(tmp_path), 'missing.bin', call, block_size=invalid)
    report = call.finish()
    assert report['invocation']['controls']['checks'] == 0


@pytest.mark.parametrize('failure', [ValueError('bad'), RuntimeError('bug'), OSError(errno.EBADF, 'bad descriptor'), KeyboardInterrupt()],
                         ids=['value', 'programming', 'descriptor_bug', 'interrupt'])
def test_unexpected_errors_and_interrupts_propagate_without_becoming_capacity_claims(tmp_path, monkeypatch, failure):
    inputs(tmp_path); before = inventory(tmp_path)

    class FailingFile(io.FileIO):
        def readinto(self, target):
            raise failure

    monkeypatch.setattr(controlled, 'FileIO', FailingFile)
    call = work().begin()
    with pytest.raises(type(failure)) as caught, no_write_attempts():
        fingerprint_file_outcome(ProjectBoundary(tmp_path), 'payload.bin', call)
    call.finish()
    assert caught.value is failure and inventory(tmp_path) == before


def test_safety_rejection_is_not_reclassified_as_a_resource_blocker(tmp_path):
    inputs(tmp_path); (tmp_path / 'link.bin').symlink_to(tmp_path / 'payload.bin')
    before = inventory(tmp_path); call = work().begin()
    with pytest.raises(SafetyViolation), no_write_attempts():
        fingerprint_file_outcome(ProjectBoundary(tmp_path), 'link.bin', call)
    call.finish()
    assert inventory(tmp_path) == before


def test_completed_outcome_is_detached_and_does_not_poison_another_hash(tmp_path):
    raw = inputs(tmp_path); ledger = work(); call = ledger.begin()
    first = fingerprint_file_outcome(ProjectBoundary(tmp_path), 'payload.bin', call)
    first['transfer']['buffer_attempts_bytes'].append(-1)
    first['fingerprint']['sha256'] = 'wrong'
    second = fingerprint_file_outcome(ProjectBoundary(tmp_path), 'payload.bin', call)
    call.finish()
    assert second['fingerprint'] == {'size': len(raw), 'sha256': sha256(raw).hexdigest()}
    assert second['transfer']['buffer_attempts_bytes'] == [65536]


def test_real_missing_source_reports_required_restoration_without_new_files(tmp_path):
    inputs(tmp_path); before = inventory(tmp_path); call = work().begin()
    outcome = fingerprint_file_outcome(ProjectBoundary(tmp_path), 'missing.bin', call)
    call.finish()
    assert outcome['exit_code'] == 5 and outcome['fingerprint'] is None
    assert outcome['blocker']['blocked_reason'] == 'source_missing'
    assert outcome['blocker']['required_action'] == 'restore_the_bound_input_then_revalidate'
    assert outcome['transfer']['buffer_attempts_bytes'] == [] and inventory(tmp_path) == before


def test_exceeded_soft_memory_target_does_not_refuse_a_small_complete_hash(tmp_path):
    raw = inputs(tmp_path); ledger = work(); call = ledger.begin({'--memory-budget-mib': 1})
    owned = bytearray(2 * 1024 * 1024)
    call.account_bytes('memory', len(owned))
    try:
        outcome = fingerprint_file_outcome(ProjectBoundary(tmp_path), 'payload.bin', call)
    finally:
        call.account_bytes('memory', len(owned), release=True)
        del owned
    report = call.finish()
    assert outcome['exit_code'] == 0 and outcome['fingerprint']['sha256'] == sha256(raw).hexdigest()
    assert report['soft_budget_exceeded'] is True
    assert any(event['metric'] == 'memory' for event in report['events'])
