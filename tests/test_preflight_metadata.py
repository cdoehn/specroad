"""Native bounded reads, phase progress and history exclusion at real entrypoints."""
from contextlib import contextmanager
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.changes import RecoveryAuthority, transaction_preflight
from specroad.cli.application import execute_request
from specroad.cli.contracts import CommandClass
from support.automatic_recovery import writer
from support.model import configuration_file, put
from support.read_only import inventory, no_write_attempts
from support.targets import ACTOR
from test_preflight_profiles import registry, request, startup_access

LIMIT = 1024 * 1024


def padded_configuration(root, size, **values):
    configuration_file(root, **values)
    path = root / 'specroad.json'
    raw = path.read_bytes()
    assert len(raw) < size
    raw += b' ' * (size - len(raw))
    path.write_bytes(raw)
    return raw


@contextmanager
def configuration_reads(root, *, short_reads=False):
    """Observe the actual descriptor offsets and returned bytes, not a mock reader."""
    reads = []
    native = os.read

    def observe(fd, size):
        path = Path(os.readlink('/proc/self/fd/' + str(fd)))
        if path != root / 'specroad.json':
            return native(fd, size)
        offset = os.lseek(fd, 0, os.SEEK_CUR)
        raw = native(fd, min(size, 997) if short_reads else size)
        reads.append((offset, size, len(raw)))
        return raw

    with patch.object(os, 'read', observe):
        yield reads


def assert_phases(data, total):
    phases = data['metadata_phases']
    assert data['metadata_bytes_read'] == total
    assert data['metadata_phase_limit_bytes'] == LIMIT
    assert [p['phase'] for p in phases] == list(range(len(phases)))
    assert [p['kind'] for p in phases] == ['short_preflight'] + ['metadata_detail'] * (len(phases) - 1)
    assert [p['metadata_bytes_read'] for p in phases] == (
        [LIMIT] * ((total - 1) // LIMIT) + [(total - 1) % LIMIT + 1])
    assert data['preflight_detail_required'] is (total > LIMIT)
    assert data['continuation_scope'] == 'current_invocation'
    assert not data['checkpoint_persisted']


@pytest.mark.parametrize('kind', ['read', 'dryrun', 'metadata'])
@pytest.mark.parametrize('size', [65536, LIMIT // 2, LIMIT // 2 + 1, LIMIT, LIMIT + 1, 3 * LIMIT + 17])
def test_metadata_phases_cover_exact_bytes_without_restarting_capture(tmp_path, kind, size):
    raw = padded_configuration(tmp_path, size, validation_policy={'fail_on': 'warning'})
    before = inventory(tmp_path)
    calls = []
    selected_kind = 'read' if kind == 'metadata' else kind
    with configuration_reads(tmp_path) as reads, startup_access(tmp_path):
        outcome = execute_request(request(tmp_path, selected_kind),
            registry=registry(calls, selected_kind, metadata=kind == 'metadata')).result
    assert outcome.exit_code == 0 and len(calls) == 1
    assert calls[0].values['fail_on'] == 'warning'
    passes = 1 if kind == 'metadata' else 2
    assert sum(length for offset, requested, length in reads) == passes * size
    assert sum(offset == 0 for offset, requested, length in reads) == passes
    position, remaining_phase = 0, LIMIT
    for offset, requested, length in reads:
        assert offset == position % size
        assert 0 < length == requested <= min(65536, remaining_phase)
        position += length
        remaining_phase -= length
        if remaining_phase == 0:
            remaining_phase = LIMIT
    data = outcome.as_dict()['summary']['preflight']
    assert_phases(data, passes * size)
    assert [(d.code, d.severity, d.category) for d in outcome.diagnostics] == (
        [('SRV167', 'info', 'preflight_detail_required')] if passes * size > LIMIT else [])
    assert calls[0].preflight['metadata_bytes_read'] == data['metadata_bytes_read']
    with pytest.raises(TypeError):
        calls[0].preflight['metadata_phases'][0]['metadata_bytes_read'] = 0
    assert (tmp_path / 'specroad.json').read_bytes() == raw
    assert inventory(tmp_path) == before


def test_short_native_reads_advance_without_repeating_or_losing_bytes(tmp_path):
    size = LIMIT + 73
    padded_configuration(tmp_path, size)
    calls = []
    with configuration_reads(tmp_path, short_reads=True) as reads, startup_access(tmp_path):
        result = execute_request(request(tmp_path), registry=registry(calls)).result
    assert result.exit_code == 0 and len(calls) == 1
    position = 0
    for offset, requested, length in reads:
        assert offset == position % size and 0 < length <= min(requested, 997)
        position += length
    assert position == 2 * size
    assert_phases(result.as_dict()['summary']['preflight'], 2 * size)


@pytest.mark.parametrize('extra', [-1, 0, 1])
def test_directory_names_and_configuration_share_the_same_phase_limit(tmp_path, extra):
    (tmp_path / '.specroad/transactions/receipts').mkdir(parents=True)
    name_bytes = len(b'transactions') + len(b'receipts')
    size = LIMIT // 2 - name_bytes + extra
    padded_configuration(tmp_path, size)
    calls = []
    with configuration_reads(tmp_path) as reads, startup_access(tmp_path):
        result = execute_request(request(tmp_path), registry=registry(calls)).result
    assert result.exit_code == 0 and len(calls) == 1
    total = sum(length for offset, requested, length in reads) + 2 * name_bytes
    assert total == LIMIT + 2 * extra
    assert_phases(result.as_dict()['summary']['preflight'], total)
    assert len(result.diagnostics) == (1 if extra == 1 else 0)


@pytest.mark.parametrize('kind', ['read', 'dryrun', 'metadata'])
def test_large_completed_history_does_not_change_startup_accesses_or_work(tmp_path, kind):
    configuration_file(tmp_path)
    history = ['.specroad/transactions/receipts', '.specroad/recovery/lock-audit',
               '.specroad/recovery/transaction-audit', '.specroad/cache', '.specroad/requests']
    for path in history:
        (tmp_path / path).mkdir(parents=True, exist_ok=True)
    calls = []
    selected_kind = 'read' if kind == 'metadata' else kind
    commands = registry(calls, selected_kind, metadata=kind == 'metadata')
    with startup_access(tmp_path) as empty_accesses:
        empty = execute_request(request(tmp_path, selected_kind), registry=commands).result
    for path in history:
        for number in range(1000):
            put(tmp_path, path + '/history-' + str(number), b'Invalid and irrelevant completed history')
    before = inventory(tmp_path)
    with configuration_reads(tmp_path) as reads, startup_access(tmp_path) as full_accesses:
        full = execute_request(request(tmp_path, selected_kind), registry=commands).result
    assert empty.exit_code == full.exit_code == 0 and len(calls) == 2
    assert empty_accesses == full_accesses
    assert empty.details['preflight'] == full.details['preflight']
    data = full.as_dict()['summary']['preflight']
    names = 0 if kind == 'metadata' else 2 * sum(
        len(item['path'].rsplit('/', 1)[-1].encode('utf-8'))
        for item in data['operational']['observed_entries'])
    assert_phases(data, names + sum(length for offset, requested, length in reads))
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('count', [16, 17, 400])
def test_active_entry_bound_stops_classification_without_opening_any_journal(tmp_path, monkeypatch, count):
    configuration_file(tmp_path)
    for number in range(count):
        put(tmp_path, '.specroad/transactions/active-' + str(number) + '/journal.json', b'Unopened')
    before = inventory(tmp_path)
    native = os.stat
    scan = os.scandir
    inspected, yielded = [], []

    def observe(path, *args, **kwargs):
        if isinstance(path, str) and path.startswith('active-'):
            inspected.append(path)
        return native(path, *args, **kwargs)

    def entry(value):
        if value.name.startswith('active-'):
            yielded.append(value.name)
        return value

    @contextmanager
    def scanning(path):
        with scan(path) as entries:
            yield (entry(value) for value in entries)

    monkeypatch.setattr(os, 'stat', observe)
    monkeypatch.setattr(os, 'scandir', scanning)
    calls = []
    with startup_access(tmp_path):
        result = execute_request(request(tmp_path), registry=registry(calls)).result
    assert result.exit_code == 5 and calls == []
    data = result.as_dict()['summary']['preflight']
    assert data['reason'] == 'recovery_required'
    assert len(data['operational']['unresolved_paths']) == 16
    assert not data['operational']['inspection_complete']
    assert len(inspected) == 32 and len(set(inspected)) == 16
    assert len(yielded) == 32 and len(set(yielded)) == 16
    assert not data['preflight_detail_required']
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['grow', 'truncate', 'replace', 'early_eof'])
def test_configuration_read_changes_fail_before_handler_and_retain_actual_bytes(tmp_path, monkeypatch, change):
    original = padded_configuration(tmp_path, 2 * LIMIT + 17)
    put(tmp_path, 'unrelated.bin', b'Untouched')
    path = tmp_path / 'specroad.json'
    native = os.read
    changed = False
    retained = original

    def observe(fd, size):
        nonlocal changed, retained
        current = Path(os.readlink('/proc/self/fd/' + str(fd)))
        offset = os.lseek(fd, 0, os.SEEK_CUR) if current == path else 0
        if current == path and change == 'early_eof' and offset:
            changed = True
            return b''
        raw = native(fd, size)
        if current == path and not changed:
            changed = True
            if change == 'grow':
                retained = original + b' '
                path.write_bytes(retained)
            elif change == 'truncate':
                retained = original[:31]
                path.write_bytes(retained)
            elif change == 'replace':
                retained = original + b'  '
                replacement = tmp_path / 'replacement.json'
                replacement.write_bytes(retained)
                replacement.replace(path)
        return raw

    monkeypatch.setattr(os, 'read', observe)
    calls = []
    result = execute_request(request(tmp_path), registry=registry(calls)).result
    assert changed and result.exit_code == 7 and calls == []
    assert path.read_bytes() == retained
    assert (tmp_path / 'unrelated.bin').read_bytes() == b'Untouched'
    assert {p.name for p in tmp_path.iterdir()} == {'specroad.json', 'unrelated.bin'}


@pytest.mark.parametrize('failure', ['syntax', 'schema', 'pending'])
def test_detail_phase_keeps_actual_failure_class_and_diagnostic(tmp_path, failure):
    raw = padded_configuration(tmp_path, LIMIT + 37,
                               **({'schema_version': '99.0.0'} if failure == 'schema' else {}))
    if failure == 'syntax':
        (tmp_path / 'specroad.json').write_bytes(raw + b'invalid')
    if failure == 'pending':
        put(tmp_path, '.specroad/transactions/pending/journal.json', b'Unopened')
    before = inventory(tmp_path)
    calls = []
    with startup_access(tmp_path):
        result = execute_request(request(tmp_path), registry=registry(calls)).result
    assert result.exit_code == (5 if failure == 'pending' else 3) and calls == []
    assert result.details['preflight']['preflight_detail_required']
    assert [(d.code, d.severity) for d in result.diagnostics if d.code == 'SRV167'] == [('SRV167', 'info')]
    assert not result.details['preflight']['normal_operation_started']
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('policy,authorized,expected', [(True, True, 5), (True, False, 7), (False, True, 5)])
def test_large_recovery_policy_reaches_real_authority_and_owner_decision(tmp_path, policy, authorized, expected):
    with writer(tmp_path, auto_recover=policy):
        path = tmp_path / 'specroad.json'
        raw = path.read_bytes()
        path.write_bytes(raw + b' ' * (LIMIT + 31 - len(raw)))
        before = inventory(tmp_path)
        calls = []
        authority = RecoveryAuthority('bounded-policy-host', '1', lambda value: calls.append(value) or authorized)
        with no_write_attempts():
            result = transaction_preflight(tmp_path, command_class=CommandClass.NORMATIVE_WRITE,
                request_id='not-started', authority=authority, actor=ACTOR).data
        assert result['exit_code'] == expected and not result['recovery_attempted']
        assert len(calls) == (1 if policy else 0)
        if policy and authorized:
            assert result['owner_state'] == 'alive'
        elif not policy:
            assert result['reason'] == 'automatic_recovery_disabled'
        else:
            assert result['reason'] == 'automatic_recovery_not_authorized'
        assert result['preflight_detail_required'] and result['diagnostic_codes'] == ['SRV167']
        assert_phases(result, result['metadata_bytes_read'])
        assert result['metadata_bytes_read'] > LIMIT
        assert not result['request_consumed'] and not result['normal_operation_started']
        assert inventory(tmp_path) == before
