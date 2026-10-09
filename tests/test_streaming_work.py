"""Bounded native payload reads and smaller pre-read allocation alternatives."""
from hashlib import sha256
import io
import os
import tracemalloc

import pytest

from specroad.runtime import controlled
from specroad.runtime.consumption import CounterSample, WorkConsumption
from specroad.runtime.control_points import ControlPoint, PhaseBoundary
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.storage import byte_binding
from support.read_only import inventory, no_write_attempts


def work():
    return WorkConsumption(sampler=lambda: CounterSample(None, None, None))


def consume(steps):
    points = []
    while True:
        try:
            points.append(next(steps))
        except StopIteration as done:
            return done.value, points


@pytest.mark.parametrize('capacity', [65536, 4096])
def test_large_guarded_attachment_uses_one_buffer_without_a_payload_copy(tmp_path, monkeypatch, capacity):
    (tmp_path / 'attachments').mkdir()
    path = tmp_path / 'attachments/large.bin'
    chunk = bytes(range(256)) * 256
    expected = sha256()
    with path.open('wb') as output:
        for _ in range(512):
            output.write(chunk)
            expected.update(chunk)
    size = len(chunk) * 512
    before = path.stat()
    seen = {'object': None, 'requests': 0, 'bytes': 0, 'descriptor': None}

    class ObservedFile(io.FileIO):
        def __init__(self, descriptor, mode, *, closefd):
            assert type(descriptor) is int and mode == 'rb' and closefd is False
            seen['descriptor'] = descriptor
            super().__init__(descriptor, mode, closefd=closefd)

        def readinto(self, target):
            assert type(target) is memoryview and type(target.obj) is bytearray
            assert len(target.obj) == capacity and 0 < len(target) <= capacity
            if seen['object'] is None:
                seen['object'] = id(target.obj)
            assert id(target.obj) == seen['object']
            count = super().readinto(target)
            seen['requests'] += 1
            seen['bytes'] += count
            return count

        def read(self, *args):
            raise AssertionError('Payload must use the existing buffer')

        def readall(self):
            raise AssertionError('Whole payload reads are forbidden')

        def close(self):
            if not self.closed:
                descriptor = self.fileno()
                super().close()
                os.fstat(descriptor)  # The guard still owns the live descriptor.

    monkeypatch.setattr(controlled, 'FileIO', ObservedFile)
    call = work().begin()
    boundary = ProjectBoundary(tmp_path)
    with no_write_attempts():
        tracemalloc.start()
        try:
            actual = controlled.fingerprint_file(boundary, 'attachments/large.bin', call, block_size=capacity)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    with pytest.raises(OSError):
        os.fstat(seen['descriptor'])  # The guard has now closed it.
    report = call.finish()
    assert actual.size == seen['bytes'] == size == 32 * 1024 * 1024
    assert actual.sha256 == expected.hexdigest()
    assert seen['requests'] == size // capacity + 1
    assert peak < 2 * 1024 * 1024  # This measured Python window, not total RSS.
    measured = report['invocation']['accounted']['memory_peak_bytes']
    assert measured['value'] == capacity and measured['measurement_kind'] == 'accounted'
    assert report['invocation']['measured']['rss_peak_bytes']['value'] is None
    assert report['invocation']['controls']['intervals']['payload_bytes']['checks'] == 512
    after = path.stat()
    assert (after.st_ino, after.st_size, after.st_mtime_ns) == (before.st_ino, before.st_size, before.st_mtime_ns)
    assert sorted(p.name for p in path.parent.iterdir()) == ['large.bin']


@pytest.mark.parametrize('size,capacity,short', [
    (0, 65536, 10003), (65535, 65536, 10003), (65536, 65536, 10003),
    (65537, 65536, 10003), (131089, 4096, 997), (65539, 1, 1),
], ids=['empty', 'below', 'exact', 'over', 'small', 'one_byte'])
def test_short_readinto_preserves_hash_and_actual_control_boundaries(size, capacity, short):
    raw = bytes(n % 251 for n in range(size))
    source = io.BytesIO(raw)
    buffer = bytearray(capacity)
    positions = []

    def readinto(target):
        assert target.obj is buffer and len(target) <= capacity
        with target[:min(short, len(target))] as selected:
            return source.readinto(selected)

    steps = byte_binding.fingerprint_into_steps(readinto, size, buffer)
    while True:
        try:
            point = next(steps)
            if type(point) is ControlPoint:
                positions.append((point.completed, source.tell()))
        except StopIteration as done:
            result = done.value
            break
    assert positions == [(n, n) for n in range(65536, size + 1, 65536)]
    assert result.size == size and result.sha256 == sha256(raw).hexdigest()
    buffer.extend(b'x')  # No unreleased memoryview survives completion.


@pytest.mark.parametrize('available', [32768, 1024, 1])
def test_allocation_fallback_uses_smaller_buffer_before_consuming_input(monkeypatch, available):
    attempts = []
    raw = b'complete payload\0' * 17
    source = io.BytesIO(raw)

    def allocate(size):
        assert source.tell() == 0
        attempts.append(size)
        if size > available:
            raise MemoryError('fixture-labelled allocation refusal')
        return bytearray(size)

    monkeypatch.setattr(byte_binding, 'bytearray', allocate, raising=False)
    buffer = byte_binding.allocate_transfer_buffer(1048576)
    monkeypatch.delattr(byte_binding, 'bytearray')
    actual, points = consume(byte_binding.fingerprint_into_steps(source.readinto, len(raw), buffer))
    assert attempts[0] == 65536 and attempts[-1] == len(buffer) == available
    assert all(after == before // 2 for before, after in zip(attempts, attempts[1:]))
    assert actual.size == len(raw) and actual.sha256 == sha256(raw).hexdigest()
    assert points == [PhaseBoundary('payload_hash', 'start'), PhaseBoundary('payload_hash', 'end')]


@pytest.mark.parametrize('returned', [None, True, -1, 65537, '1'])
def test_invalid_readinto_count_cannot_complete_or_hash_unread_bytes(returned):
    buffer = bytearray(65536)
    points = []
    with pytest.raises(SafetyViolation) as caught:
        for point in byte_binding.fingerprint_into_steps(lambda view: returned, 10, buffer):
            points.append(point)
    assert type(caught.value) is SafetyViolation
    assert points == [PhaseBoundary('payload_hash', 'start')]
    buffer.extend(b'x')


@pytest.mark.parametrize('declared', [2, 4], ids=['growing', 'short'])
def test_readinto_size_mismatch_keeps_safety_failure_without_successful_end(declared):
    points = []
    with pytest.raises(SafetyViolation):
        for point in byte_binding.fingerprint_into_steps(io.BytesIO(b'abc').readinto, declared, bytearray(2)):
            points.append(point)
    assert points == [PhaseBoundary('payload_hash', 'start')]


def test_unavailable_minimum_buffer_stops_without_reading_or_removing_inputs(tmp_path, monkeypatch):
    (tmp_path / 'payload.bin').write_bytes(b'original bytes')
    (tmp_path / 'before-image.bin').write_bytes(b'critical saved state')
    before = inventory(tmp_path)
    attempts = []
    failure = MemoryError('fixture-labelled minimum allocation refusal')

    def allocate(size):
        attempts.append(size)
        raise failure

    def forbidden(*args, **kwargs):
        raise AssertionError('No stream may consume input after allocation failure')

    monkeypatch.setattr(byte_binding, 'bytearray', allocate, raising=False)
    monkeypatch.setattr(controlled, 'FileIO', forbidden)
    ledger = work(); call = ledger.begin()
    with pytest.raises(MemoryError) as caught, no_write_attempts():
        controlled.fingerprint_file(ProjectBoundary(tmp_path), 'payload.bin', call)
    assert caught.value is failure and attempts == [2 ** n for n in range(16, -1, -1)]
    report = call.finish()
    assert report['invocation']['controls']['checks'] == 0
    assert report['invocation']['accounted']['memory_peak_bytes']['value'] == 0
    assert inventory(tmp_path) == before


def test_native_smaller_buffer_is_accounted_and_released_before_next_invocation(tmp_path, monkeypatch):
    raw = bytes(range(256)) * 513
    (tmp_path / 'payload.bin').write_bytes(raw)
    before = inventory(tmp_path)
    attempts = []
    original_allocate = byte_binding.allocate_transfer_buffer

    def allocate(size):
        attempts.append(size)
        if size > 1024:
            raise MemoryError('fixture-labelled allocation refusal')
        return bytearray(size)

    def reserve(block_size):
        with monkeypatch.context() as local:
            local.setattr(byte_binding, 'bytearray', allocate, raising=False)
            return original_allocate(block_size)

    monkeypatch.setattr(byte_binding, 'allocate_transfer_buffer', reserve)
    ledger = work(); call = ledger.begin()
    with no_write_attempts():
        actual = controlled.fingerprint_file(ProjectBoundary(tmp_path), 'payload.bin', call, block_size=1048576)
    first = call.finish()
    second = ledger.begin().finish()
    assert actual.size == len(raw) and actual.sha256 == sha256(raw).hexdigest()
    assert attempts == [65536, 32768, 16384, 8192, 4096, 2048, 1024]
    assert first['invocation']['accounted']['memory_peak_bytes']['value'] == 1024
    assert second['invocation']['accounted']['memory_peak_bytes']['value'] == 0
    assert second['cumulative']['accounted']['memory_peak_bytes']['value'] == 1024
    assert inventory(tmp_path) == before


def test_native_source_replacement_is_rejected_by_existing_descriptor_guard(tmp_path, monkeypatch):
    path = tmp_path / 'payload.bin'; path.write_bytes(b'original')
    replacement = tmp_path / 'replacement.bin'; replacement.write_bytes(b'replacement')

    class ReplacingFile(io.FileIO):
        def readinto(self, target):
            count = super().readinto(target)
            if count:
                replacement.replace(path)  # Explicit adversarial fixture action.
            return count

    monkeypatch.setattr(controlled, 'FileIO', ReplacingFile)
    ledger = work(); call = ledger.begin()
    with pytest.raises(SafetyViolation):
        controlled.fingerprint_file(ProjectBoundary(tmp_path), 'payload.bin', call)
    call.finish()
    assert ledger.begin().finish()['invocation']['accounted']['memory_peak_bytes']['value'] == 0
    assert path.read_bytes() == b'replacement'


def test_error_after_source_advances_is_not_retried_and_registration_is_released(tmp_path, monkeypatch):
    (tmp_path / 'payload.bin').write_bytes(b'unchanged source')
    (tmp_path / 'journal.json').write_bytes(b'critical journal fixture')
    before = inventory(tmp_path); reads = []; failure = MemoryError('fixture after native read')

    class FailingFile(io.FileIO):
        def readinto(self, target):
            reads.append(super().readinto(target))
            raise failure

    monkeypatch.setattr(controlled, 'FileIO', FailingFile)
    ledger = work(); call = ledger.begin()
    with pytest.raises(MemoryError) as caught, no_write_attempts():
        controlled.fingerprint_file(ProjectBoundary(tmp_path), 'payload.bin', call)
    report = call.finish()
    assert caught.value is failure and reads == [len(b'unchanged source')]
    assert report['invocation']['controls']['phases']['payload_hash'] == {'start': 1, 'end': 0}
    assert ledger.begin().finish()['invocation']['accounted']['memory_peak_bytes']['value'] == 0
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('buffer', [b'x', bytearray(), bytearray(65537)], ids=['readonly', 'empty', 'oversized'])
def test_invalid_buffer_is_rejected_before_any_source_access(buffer):
    def forbidden(view):
        raise AssertionError('Invalid buffer reached the source')
    with pytest.raises(ValueError):
        consume(byte_binding.fingerprint_into_steps(forbidden, 0, buffer))
