"""Complete external diagnostic ordering and owned-directory safety contracts."""
from hashlib import sha256
import errno
import os
import stat
import tracemalloc

import pytest

from specroad.diagnostics import Diagnostic, diagnostic_key
from specroad.diagnostics.spooling import create_diagnostic_spool
from specroad.result_contract import ResultContractError
from specroad.security import ProjectBoundary, SafetyViolation
from support.read_only import inventory, no_write_attempts


def protected(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / '.specroad').mkdir()
    (project / '.specroad/journal.json').write_bytes(b'owned critical fixture\n')
    (project / 'specroad.json').write_bytes(b'owned normative fixture\n')
    return (ProjectBoundary(project),)


def finding(index):
    return Diagnostic('SPOOL-%02d' % (index % 9), ('error', 'warning', 'info')[index % 3],
                      'fixture', 'Befund \u03a9 %d' % (index % 17),
                      origin=('core_rule', 'analyzer_observation')[index % 2],
                      path=None if index % 7 == 0 else 'data/%02d.json' % (index % 13),
                      location={'line': 1 + index % 5, 'pointer': '/a~1b'},
                      related_ids=['SR-REQ-0002', 'SR-REQ-0001'])


@pytest.mark.parametrize('batch,page', [(1, 1), (1024, 7), (65536, 10000)])
def test_every_diagnostic_survives_small_batches_and_paged_delivery(tmp_path, batch, page):
    roots = protected(tmp_path)
    before = inventory(roots[0].root)
    values = [finding(n) for n in range(257, -1, -1)]
    values += [values[3], values[3], Diagnostic('SRV001', 'error', 'fixture', 'required')]
    consumed = []

    def once():
        for index, value in enumerate(values):
            consumed.append(index)
            yield value

    with create_diagnostic_spool(tmp_path / 'spool', once(), protected_roots=roots,
                                 batch_bytes=batch) as spool:
        manifest = spool.manifest
        assert consumed == list(range(len(values)))
        assert manifest['record_count'] == manifest['result']['records'] == len(values)
        assert manifest['state'] == 'sorted' and manifest['durable_checkpoint'] is False
        raw = (spool.root / manifest['result']['name']).read_bytes()
        assert sha256(raw).hexdigest() == manifest['result']['sha256']
        assert len(raw) == manifest['result']['size']
        if batch == 1:
            assert manifest['batch']['count'] == len(values)
            assert manifest['batch']['peak_records'] == 1
        result, states = [], []
        with spool.cursor() as cursor, no_write_attempts():
            while not cursor.state['complete']:
                old = cursor.state
                current = cursor.read_page(page)
                result.extend(current)
                state = cursor.state
                assert state['record_index'] == old['record_index'] + len(current)
                assert state['byte_offset'] > old['byte_offset']
                assert state['durable_checkpoint'] is False
                states.append(state)
            assert cursor.read_page(page) == []
        assert result == sorted(values, key=diagnostic_key)
        assert states[-1]['record_index'] == len(values)
        assert states[-1]['byte_offset'] == len(raw)
        assert len({state['spool_sha256'] for state in states}) == 1
    assert inventory(roots[0].root) == before
    assert (tmp_path / 'spool/spool.json').is_file()


def test_final_run_bytes_do_not_depend_on_batch_target(tmp_path):
    roots = protected(tmp_path)
    bindings = []
    for batch in (1, 4096, 1048576):
        with create_diagnostic_spool(tmp_path / ('s%d' % batch),
                                     (finding(n) for n in range(43, -1, -1)),
                                     protected_roots=roots, batch_bytes=batch) as spool:
            manifest = spool.manifest
            bindings.append((manifest['input_sha256'], manifest['result']['sha256'],
                             manifest['result']['size'], manifest['record_count']))
    assert len(set(bindings)) == 1


def test_large_single_record_exceeds_soft_goal_without_being_dropped(tmp_path):
    roots = protected(tmp_path)
    value = Diagnostic('SPOOL', 'error', 'fixture', '\u03a9' * 100000,
                       location={'byte_offset': 2 ** 100})
    with create_diagnostic_spool(tmp_path / 'spool', [value], protected_roots=roots,
                                 batch_bytes=1) as spool, spool.cursor() as cursor:
        assert cursor.read_page(1) == [value]
        assert cursor.state['complete']
        assert spool.manifest['batch']['peak_encoded_bytes'] > 65536


def test_streamed_collection_keeps_python_allocation_window_below_collection_size(tmp_path):
    roots = protected(tmp_path)
    count = 1025
    def source():
        for n in range(count):
            yield Diagnostic('SPOOL', 'warning', 'fixture', '%06d' % (count - n) + 'x' * 4096)
    tracemalloc.start()
    try:
        with create_diagnostic_spool(tmp_path / 'spool', source(), protected_roots=roots,
                                     batch_bytes=32768) as spool:
            _, peak = tracemalloc.get_traced_memory()
            assert spool.manifest['record_count'] == count
            assert spool.manifest['result']['size'] > 4 * 1024 * 1024
            assert spool.manifest['batch']['peak_encoded_bytes'] <= 32768
            assert peak < 2 * 1024 * 1024  # Selected Python window, not host RSS/quota.
            with spool.cursor() as cursor:
                delivered = 0
                previous = ''
                while not cursor.state['complete']:
                    for value in cursor.read_page(3):
                        assert value.message > previous
                        previous = value.message
                        delivered += 1
                assert delivered == count
    finally:
        tracemalloc.stop()


def test_empty_source_has_a_hashed_complete_empty_delivery(tmp_path):
    roots = protected(tmp_path)
    with create_diagnostic_spool(tmp_path / 'spool', (), protected_roots=roots) as spool:
        assert spool.manifest['result']['sha256'] == sha256(b'').hexdigest()
        with spool.cursor() as cursor:
            assert cursor.read_page(1) == []
            assert cursor.state['complete']
            assert cursor.state['record_index'] == cursor.state['byte_offset'] == 0


def test_owned_files_are_private_and_close_releases_handles_without_deletion(tmp_path):
    roots = protected(tmp_path)
    spool = create_diagnostic_spool(tmp_path / 'spool', [finding(2), finding(1)],
                                    protected_roots=roots, batch_bytes=1)
    cursor = spool.cursor()
    descriptor = cursor._stream.fileno()  # Observe actual ownership/lifetime.
    before = inventory(spool.root)
    assert stat.S_IMODE(spool.root.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in spool.root.iterdir())
    spool.close()
    spool.close()
    with pytest.raises(OSError):
        os.fstat(descriptor)
    with pytest.raises(ValueError):
        cursor.read_page(1)
    assert inventory(spool.root) == before


@pytest.mark.parametrize('target', [0, -1, True, 1.5])
def test_invalid_batch_option_is_rejected_before_directory_or_source_access(tmp_path, target):
    roots = protected(tmp_path)
    def source():
        raise AssertionError('Invalid option must not consume the source')
        yield
    with no_write_attempts(), pytest.raises(ValueError):
        create_diagnostic_spool(tmp_path / 'spool', source(), protected_roots=roots,
                                 batch_bytes=target)
    assert not (tmp_path / 'spool').exists()


@pytest.mark.parametrize('location', ['project', 'metadata', 'input'])
def test_protected_roots_cannot_receive_spool_files(tmp_path, location):
    roots = protected(tmp_path)
    extra = tmp_path / 'input'
    extra.mkdir()
    roots += (ProjectBoundary(extra),)
    target = {'project': roots[0].root / 'spool',
              'metadata': roots[0].root / '.specroad/spool', 'input': extra / 'spool'}[location]
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(SafetyViolation):
        create_diagnostic_spool(target, (), protected_roots=roots)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['directory', 'file', 'symlink', 'linked_parent'])
def test_existing_or_linked_locations_are_not_reused(tmp_path, kind):
    roots = protected(tmp_path)
    target = tmp_path / 'spool'
    if kind == 'directory':
        target.mkdir()
        (target / 'existing').write_bytes(b'retain')
    elif kind == 'file':
        target.write_bytes(b'retain')
    else:
        target.symlink_to(roots[0].root, target_is_directory=True)
        if kind == 'linked_parent':
            target = target / 'child'
    before = inventory(tmp_path)
    with pytest.raises((SafetyViolation, FileExistsError)):
        create_diagnostic_spool(target, (), protected_roots=roots)
    assert inventory(tmp_path) == before


def test_traversal_path_is_rejected_before_any_write(tmp_path):
    roots = protected(tmp_path)
    raw = str(tmp_path) + '/project/../spool'
    with no_write_attempts(), pytest.raises(SafetyViolation):
        create_diagnostic_spool(raw, (), protected_roots=roots)


def test_protected_boundaries_are_mandatory(tmp_path):
    with no_write_attempts(), pytest.raises(ValueError):
        create_diagnostic_spool(tmp_path / 'spool', (), protected_roots=())


@pytest.mark.parametrize('change', ['append', 'truncate', 'rewrite', 'replace', 'symlink', 'hardlink', 'mode'])
def test_changed_final_run_is_rejected_before_any_diagnostic_delivery(tmp_path, change):
    roots = protected(tmp_path)
    with create_diagnostic_spool(tmp_path / 'spool', [finding(1), finding(2)],
                                 protected_roots=roots, batch_bytes=1) as spool:
        path = spool.root / spool.manifest['result']['name']
        original = path.read_bytes()
        if change == 'append':
            with path.open('ab') as target:
                target.write(b'\n')
        elif change == 'truncate':
            path.write_bytes(original[:-1])
        elif change in ('rewrite', 'replace'):
            if change == 'replace':
                path.unlink()
                path.touch(mode=0o600)
            path.write_bytes(original.replace(b'Befund', b'Broken', 1))
        elif change == 'symlink':
            path.unlink()
            path.symlink_to(roots[0].root / 'specroad.json')
        elif change == 'hardlink':
            os.link(path, tmp_path / 'alias')
        else:
            path.chmod(0o644)
        before = inventory(tmp_path)
        with no_write_attempts(), pytest.raises(SafetyViolation):
            spool.cursor()
        assert inventory(tmp_path) == before


def test_changed_manifest_blocks_cursor_and_detached_description_has_no_authority(tmp_path):
    roots = protected(tmp_path)
    with create_diagnostic_spool(tmp_path / 'spool', [finding(1)], protected_roots=roots) as spool:
        description = spool.manifest
        description['result']['name'] = '../project/specroad.json'
        assert spool.manifest['result']['name'] != description['result']['name']
        manifest = spool.root / 'spool.json'
        manifest.write_bytes(manifest.read_bytes().replace(b'sorted', b'broken'))
        with pytest.raises(SafetyViolation):
            spool.cursor()


def test_change_between_pages_never_returns_a_partial_page_or_advances_cursor(tmp_path):
    roots = protected(tmp_path)
    with create_diagnostic_spool(tmp_path / 'spool', [finding(n) for n in range(5)],
                                 protected_roots=roots) as spool, spool.cursor() as cursor:
        assert len(cursor.read_page(1)) == 1
        old = cursor.state
        path = spool.root / spool.manifest['result']['name']
        with path.open('ab') as target:
            target.write(b'\n')
        with pytest.raises(SafetyViolation):
            cursor.read_page(4)
        assert cursor.state == old and not cursor.state['complete']
        with pytest.raises(ValueError):
            cursor.read_page(1)


def test_relocated_root_is_rejected_and_both_directories_are_retained(tmp_path):
    roots = protected(tmp_path)
    with create_diagnostic_spool(tmp_path / 'spool', [finding(1)], protected_roots=roots) as spool:
        spool.root.rename(tmp_path / 'moved')
        spool.root.mkdir(mode=0o700)
        before = inventory(tmp_path)
        with pytest.raises(SafetyViolation):
            spool.cursor()
        assert inventory(tmp_path) == before


def test_native_short_writes_preserve_every_byte_and_hash(tmp_path, monkeypatch):
    roots = protected(tmp_path)
    original = os.write
    counts = []
    def short(descriptor, raw):
        counts.append(len(raw))
        return original(descriptor, raw[:11])
    monkeypatch.setattr(os, 'write', short)
    values = [finding(n) for n in range(7)]
    with create_diagnostic_spool(tmp_path / 'spool', values, protected_roots=roots,
                                 batch_bytes=1024) as spool, spool.cursor() as cursor:
        assert cursor.read_page(100) == sorted(values, key=diagnostic_key)
    assert len(counts) > 100 and max(counts) <= 65536


def test_native_io_failure_retains_partial_owned_files_and_protected_bytes(tmp_path, monkeypatch):
    roots = protected(tmp_path)
    before = inventory(roots[0].root)
    original = os.write
    calls = []
    failure = OSError(errno.ENOSPC, 'labelled write refusal after actual bytes')
    def failing(descriptor, raw):
        calls.append(len(raw))
        if len(calls) == 2:
            raise failure
        return original(descriptor, raw[:11])
    monkeypatch.setattr(os, 'write', failing)
    with pytest.raises(OSError) as caught:
        create_diagnostic_spool(tmp_path / 'spool', [finding(1)], protected_roots=roots)
    assert caught.value is failure and len(calls) == 2
    files = list((tmp_path / 'spool').iterdir())
    assert len(files) == 1 and files[0].stat().st_size == 11
    assert not (tmp_path / 'spool/spool.json').exists()
    assert inventory(roots[0].root) == before


def test_invalid_source_does_not_publish_a_complete_spool_or_erase_finished_runs(tmp_path):
    roots = protected(tmp_path)
    with pytest.raises(ResultContractError):
        create_diagnostic_spool(tmp_path / 'spool', [finding(1), {'message': 'not a diagnostic'}],
                                 protected_roots=roots, batch_bytes=1)
    assert len(list((tmp_path / 'spool').iterdir())) == 1
    assert not (tmp_path / 'spool/spool.json').exists()


@pytest.mark.parametrize('count', [0, True, -1])
def test_invalid_page_size_cannot_create_empty_progress(tmp_path, count):
    roots = protected(tmp_path)
    with create_diagnostic_spool(tmp_path / 'spool', [finding(1)], protected_roots=roots) as spool:
        with spool.cursor() as cursor:
            old = cursor.state
            with pytest.raises(ValueError):
                cursor.read_page(count)
            assert cursor.state == old
            assert cursor.read_page(1) == [finding(1)]
