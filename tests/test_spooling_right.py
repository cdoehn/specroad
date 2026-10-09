"""Resumable live merge work and complete delivery of prepared graph paths."""
import errno
import itertools
import os

import pytest

from specroad.diagnostics import Diagnostic, diagnostic_key
from specroad.diagnostics import spooling
from specroad.diagnostics.spooling import DiagnosticSort, create_diagnostic_spool
from specroad.graph.indices import RelationIndex
from specroad.graph.path_output import PathRecord, PathSort, create_path_spool
from specroad.graph.references import RelationReferences
from specroad.result_contract import ResultContractError
from specroad.security import ProjectBoundary, SafetyViolation
from support.read_only import inventory
from support.srx_graph import aid, artifact, edge, records


def roots(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / '.specroad').mkdir()
    (project / '.specroad/journal.json').write_bytes(b'owned operational fixture')
    (project / 'specroad.json').write_bytes(b'owned normative fixture')
    return (ProjectBoundary(project),)


def diagnostics(count):
    for n in range(count, 0, -1):
        yield Diagnostic('SPOOL-%d' % (n % 7), ('error', 'warning', 'info')[n % 3],
                         'fixture', 'required finding %d' % n, path='data/%03d.json' % (n % 11))


def finish(task, units):
    previous = task.state
    while not previous['complete']:
        current = task.advance(units)
        assert 0 < current['units_completed'] - previous['units_completed'] <= units
        assert current['accepted_records'] >= previous['accepted_records']
        assert current['durable_checkpoint'] is False
        previous = current
    return task.result


def delivered(spool, size):
    values = []
    with spool.cursor() as cursor:
        while not cursor.state['complete']:
            values.extend(cursor.read_page(size))
    return values


def pause_in_merge(task):
    while True:
        state = task.advance(1)
        assert not state['complete']
        operation = state['operation']
        if (state['phase'] == 'merge' and not operation['output']['sealed']
                and operation['output']['records_written'] > 0):
            return state


@pytest.mark.parametrize('units', [1, 7, 1000])
def test_open_merge_cursors_make_monotone_progress_and_preserve_every_diagnostic(tmp_path, units):
    protected = roots(tmp_path)
    before = inventory(protected[0].root)
    consumed = []
    def once():
        for n, value in enumerate(diagnostics(129)):
            consumed.append(n)
            yield value
    with DiagnosticSort(tmp_path / 'spool', once(), protected_roots=protected, batch_bytes=900) as task:
        assert consumed == []
        first = pause_in_merge(task)
        assert first['phase'] == 'merge' and not first['complete']
        assert sum(row['record_index'] for row in first['operation']['inputs']) == 1
        previous_by_output = {}
        while not task.state['complete']:
            state = task.state
            if state['phase'] == 'merge':
                operation = state['operation']
                written = operation['output']['records_written']
                assert sum(row['record_index'] for row in operation['inputs']) == written
                assert sum(row['byte_offset'] for row in operation['inputs']) == operation['output']['bytes_written']
                for row in operation['inputs']:
                    assert 0 <= row['record_index'] <= row['reference']['records']
                    assert 0 <= row['byte_offset'] <= row['reference']['size']
                name = operation['output']['name']
                assert written >= previous_by_output.get(name, 0)
                previous_by_output[name] = written
            with pytest.raises(ValueError):
                _ = task.result
            new = task.advance(units)
            assert 0 < new['units_completed'] - state['units_completed'] <= units
        assert len(previous_by_output) >= 1
        assert task.state['pending_runs'] == []
        assert task.state['source_finished']
        assert consumed == list(range(129))
        assert delivered(task.result, 2) == sorted(diagnostics(129), key=diagnostic_key)
    assert inventory(protected[0].root) == before


def test_pausing_preserves_the_same_final_run_and_manifest_as_synchronous_use(tmp_path):
    protected = roots(tmp_path)
    with create_diagnostic_spool(tmp_path / 'sync', diagnostics(47), protected_roots=protected,
                                 batch_bytes=1300) as reference:
        expected = reference.manifest
        values = delivered(reference, 100)
    with DiagnosticSort(tmp_path / 'paused', diagnostics(47), protected_roots=protected,
                         batch_bytes=1300) as task:
        actual = finish(task, 1)
        assert actual.manifest == expected
        assert delivered(actual, 1) == values


def test_pending_input_is_retained_while_a_previous_batch_is_flushed(tmp_path):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(11), protected_roots=protected,
                         batch_bytes=1000) as task:
        seen = False
        while not task.state['complete']:
            state = task.advance(1)
            if state['pending_input_sequence'] is not None:
                seen = True
                assert state['pending_input_sequence'] == state['accepted_records']
                assert not state['source_finished']
        assert seen
        assert delivered(task.result, 3) == sorted(diagnostics(11), key=diagnostic_key)


def test_mutating_a_cursor_snapshot_does_not_change_owned_work_or_file_targets(tmp_path):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(13), protected_roots=protected,
                         batch_bytes=1) as task:
        state = pause_in_merge(task)
        state['accepted_records'] = 99999
        state['operation']['output']['name'] = '../project/specroad.json'
        state['operation']['inputs'][0]['byte_offset'] = 99999
        assert task.state['accepted_records'] != 99999
        actual = finish(task, 1)
        assert delivered(actual, 1) == sorted(diagnostics(13), key=diagnostic_key)
        assert (protected[0].root / 'specroad.json').read_bytes() == b'owned normative fixture'


def test_closing_a_paused_merge_keeps_files_and_releases_its_owned_directory_handles(tmp_path):
    protected = roots(tmp_path)
    task = DiagnosticSort(tmp_path / 'spool', diagnostics(20), protected_roots=protected, batch_bytes=1)
    pause_in_merge(task)
    descriptors = tuple(task._spool._fds)
    before = inventory(tmp_path)
    task.close()
    task.close()
    assert task.state['phase'] == 'cancelled' and not task.state['complete']
    assert inventory(tmp_path) == before
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    with pytest.raises(ValueError):
        task.advance()
    with pytest.raises(ValueError):
        _ = task.result


@pytest.mark.parametrize('target', ['input', 'output', 'root'])
def test_change_during_paused_merge_cannot_publish_complete_spool(tmp_path, target):
    protected = roots(tmp_path)
    before = inventory(protected[0].root)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(33), protected_roots=protected,
                         batch_bytes=1) as task:
        state = pause_in_merge(task)
        if target == 'root':
            (tmp_path / 'spool').rename(tmp_path / 'moved')
            (tmp_path / 'spool').mkdir(mode=0o700)
        else:
            name = (state['operation']['inputs'][0]['reference']['name'] if target == 'input'
                    else state['operation']['output']['name'])
            path = tmp_path / 'spool' / name
            path.write_bytes(b'changed\n')
        with pytest.raises((SafetyViolation, OSError)):
            finish(task, 1)
        assert task.state['phase'] == 'failed' and not task.state['complete']
        with pytest.raises(ValueError):
            _ = task.result
        assert not (tmp_path / 'spool/spool.json').exists()
    assert inventory(protected[0].root) == before


@pytest.mark.parametrize('failure_kind', ['zero_write', 'storage', 'memory'])
def test_failed_resume_does_not_retry_or_count_failed_unit_as_completed(tmp_path, monkeypatch, failure_kind):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(21), protected_roots=protected,
                         batch_bytes=1) as task:
        old = pause_in_merge(task)
        calls = []
        error = MemoryError('labelled refusal') if failure_kind == 'memory' else OSError(errno.ENOSPC, 'labelled refusal')
        def fail(descriptor, raw):
            calls.append(len(raw))
            if failure_kind == 'zero_write':
                return 0
            raise error
        monkeypatch.setattr(os, 'write', fail)
        with pytest.raises((SafetyViolation, OSError, MemoryError)) as caught:
            task.advance(1)
        if failure_kind != 'zero_write':
            assert caught.value is error
        assert len(calls) == 1
        assert task.state['units_completed'] == old['units_completed']
        assert task.state['phase'] == 'failed'
        assert not (tmp_path / 'spool/spool.json').exists()
        assert list((tmp_path / 'spool').iterdir())
        with pytest.raises(ValueError):
            task.advance(1)
        assert len(calls) == 1


@pytest.mark.parametrize('units', [0, True, -1, 1.5])
def test_invalid_work_window_neither_consumes_source_nor_changes_state(tmp_path, units):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(4), protected_roots=protected) as task:
        before = inventory(tmp_path)
        state = task.state
        with pytest.raises(ValueError):
            task.advance(units)
        assert task.state == state and inventory(tmp_path) == before
        assert delivered(finish(task, 1), 1) == sorted(diagnostics(4), key=diagnostic_key)


def test_empty_task_finishes_with_positive_smallest_units_and_no_false_prefix(tmp_path):
    protected = roots(tmp_path)
    with DiagnosticSort(tmp_path / 'spool', (), protected_roots=protected, batch_bytes=1) as task:
        spool = finish(task, 1)
        assert 0 < task.state['units_completed'] < 10
        assert spool.manifest['record_count'] == 0 and delivered(spool, 1) == []


def test_failed_task_initialization_releases_real_handles_and_keeps_owned_root(tmp_path, monkeypatch):
    protected = roots(tmp_path)
    descriptors = []
    failure = MemoryError('labelled task-initialization refusal')
    def refuse(task):
        descriptors.extend(task._spool._fds)
        raise failure
    monkeypatch.setattr(DiagnosticSort, '_construct_steps', refuse)
    with pytest.raises(MemoryError) as caught:
        DiagnosticSort(tmp_path / 'spool', (), protected_roots=protected)
    assert caught.value is failure and descriptors
    assert list((tmp_path / 'spool').iterdir()) == []
    for descriptor in descriptors:
        with pytest.raises(OSError):
            os.fstat(descriptor)


def test_failed_run_hash_initialization_does_not_open_or_leak_a_writable_file(tmp_path, monkeypatch):
    protected = roots(tmp_path)
    original_hash, original_open = spooling.sha256, os.open
    calls, writable = [], []
    failure = MemoryError('labelled run-hash initializer refusal')
    def hashing(*args):
        calls.append(True)
        if len(calls) == 2:
            raise failure
        return original_hash(*args)
    def opening(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR):
            writable.append(path)
        return original_open(path, flags, *args, **kwargs)
    monkeypatch.setattr(spooling, 'sha256', hashing)
    monkeypatch.setattr(os, 'open', opening)
    with DiagnosticSort(tmp_path / 'spool', diagnostics(3), protected_roots=protected,
                         batch_bytes=1) as task:
        assert task.advance(1)['accepted_records'] == 1
        with pytest.raises(MemoryError) as caught:
            task.advance(1)
        assert caught.value is failure
        assert writable == [] and list((tmp_path / 'spool').iterdir()) == []
        assert task.state['phase'] == 'failed' and task.state['units_completed'] == 1


def layered_paths(layers):
    # Every edge crosses exactly one layer, so all 2**layers walks below are
    # shortest. This fixture supplies prepared paths; production does no search.
    groups = [(1,)] + [(2 + 2*n, 3 + 2*n) for n in range(layers)] + [(2 + 2*layers,)]
    values, relation_number = [], 1
    for index, group in enumerate(groups):
        for source in group:
            relations = []
            if index < len(groups) - 1:
                for target in groups[index + 1]:
                    relations.append(edge('depends_on', aid(number=target), number=relation_number))
                    relation_number += 1
            values.append(artifact(number=source, relations=relations))
    index = RelationIndex(RelationReferences(records(values)))
    nodes = {node.id: node for node in index.references.sources}
    views = {(view.source.id, view.target.id): view for node in nodes
             for view in index.for_artifact(node, direction='outgoing')}
    result = []
    for choices in itertools.product((0, 1), repeat=layers):
        ids = [aid(number=1)] + [aid(number=groups[n+1][choice]) for n, choice in enumerate(choices)]
        ids.append(aid(number=groups[-1][0]))
        route = tuple(views[pair] for pair in zip(ids, ids[1:]))
        result.append(PathRecord.from_views(nodes[ids[0]], route))
    return result, index


@pytest.mark.parametrize('batch,units,page', [(1, 1, 1), (8192, 17, 7), (65536, 10000, 1000)])
def test_all_prepared_shortest_paths_survive_tiny_work_and_output_windows(tmp_path, batch, units, page):
    protected = roots(tmp_path)
    before = inventory(protected[0].root)
    expected, _ = layered_paths(7)
    assert len(expected) == 128
    assert len({tuple(a.id for a in path.artifacts) for path in expected}) == 128
    assert {len(path.relations) for path in expected} == {8}
    # Reverse the producer order to prove that no incidental diagnostic or
    # lexicographic order replaces the bound path ordering.
    expected.reverse()
    with PathSort(tmp_path / 'spool', iter(expected), protected_roots=protected, batch_bytes=batch) as task:
        spool = finish(task, units)
        assert spool.manifest['format'] == 'path-spool-v1'
        assert spool.manifest['record_count'] == 128
        with spool.cursor() as cursor:
            assert cursor.state['format'] == 'path-cursor-v1'
        assert delivered(spool, page) == expected
    assert inventory(protected[0].root) == before


def test_path_spool_preserves_inverse_edges_zero_length_and_duplicate_paths(tmp_path):
    protected = roots(tmp_path)
    paths, index = layered_paths(1)
    target = paths[0].artifacts[-1]
    incoming = index.for_artifact(target.id, direction='incoming')[0]
    backwards = PathRecord.from_views(target, (incoming,))
    zero = PathRecord.from_views(target, ())
    expected = [backwards, zero, paths[0], backwards]
    with create_path_spool(tmp_path / 'spool', expected, protected_roots=protected,
                           batch_bytes=1) as spool:
        actual = delivered(spool, 1)
        assert actual == expected
        assert actual[0].inverse == (True,)
        assert actual[1].relations == ()


def test_disconnected_relation_views_cannot_become_a_path_record():
    paths, index = layered_paths(2)
    target = paths[0].artifacts[-1]
    first = index.for_artifact(paths[0].artifacts[0].id, direction='outgoing')[0]
    with pytest.raises(ResultContractError):
        PathRecord.from_views(target, (first,))


@pytest.mark.parametrize('mutation', ['missing_field', 'extra_field', 'bad_length', 'bool_not_int', 'foreign_object'])
def test_path_record_codec_rejects_malformed_or_unowned_data(mutation):
    paths, _ = layered_paths(1)
    value = paths[0].as_dict()
    if mutation == 'missing_field':
        del value['inverse']
    elif mutation == 'extra_field':
        value['script'] = 'never executable'
    elif mutation == 'bad_length':
        value['relations'].pop()
    elif mutation == 'bool_not_int':
        value['inverse'][0] = 0
    else:
        value['artifacts'][0] = object()
    with pytest.raises(ResultContractError):
        PathRecord.from_dict(value)


def test_path_projection_is_detached_from_owned_identity_values():
    paths, _ = layered_paths(1)
    value = paths[0].as_dict()
    restored = PathRecord.from_dict(value)
    value['inverse'][0] = True
    value['artifacts'][0]['id'] = 'changed'
    assert restored == paths[0]
    assert restored.as_dict() != value


def test_diagnostic_and_path_backends_reject_each_others_value_types(tmp_path):
    protected = roots(tmp_path)
    paths, _ = layered_paths(1)
    with pytest.raises(ResultContractError):
        create_path_spool(tmp_path / 'paths', list(diagnostics(1)), protected_roots=protected)
    with pytest.raises(ResultContractError):
        create_diagnostic_spool(tmp_path / 'diagnostics', paths, protected_roots=protected)
    assert not (tmp_path / 'paths/spool.json').exists()
    assert not (tmp_path / 'diagnostics/spool.json').exists()
