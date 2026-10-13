"""Failure boundaries retain complete read scope and never authorize writes."""
import io
import json
import os
from pathlib import Path

import pytest

from specroad.cli import main
from specroad.cli.application import dispatch_result
from specroad.cli.results import serialize_result
from specroad.model.paths import artifact_path
from specroad.query import NormalizedQuery, ReadCommandWork, diff_project, query_project
from specroad.runtime.consumption import WorkConsumption
from specroad.storage.project import ProjectSource
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.relations import aid
from support.srx import expression_document, literal
from test_query_read_integration import COMMANDS, arguments, direct, inputs, project_pair, ticking


class ShortSink:
    def __init__(self, limit, *, fail_write=False, fail_flush=False):
        self.limit, self.fail_write, self.fail_flush = limit, fail_write, fail_flush
        self.parts = []
        self.flushed = False

    def write(self, value):
        if self.fail_write and self.parts:
            raise BrokenPipeError('owned destination failed after its accepted prefix')
        accepted = value[:self.limit]
        self.parts.append(accepted)
        return len(accepted)

    def flush(self):
        if self.fail_flush:
            raise OSError('owned destination did not confirm flush')
        self.flushed = True

    @property
    def text(self):
        return ''.join(self.parts)


@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('limit', [1, 7, 4096])
def test_machine_short_writes_deliver_the_whole_exact_read_result(tmp_path, command, limit):
    root, before, _ = project_pair(tmp_path)
    argv = arguments(command, root, before)
    expected = dispatch_result(argv)
    protected = inventory(tmp_path)
    sink = ShortSink(limit)
    with no_write_attempts():
        code = main(argv, stdout=sink, stderr=io.StringIO())
    assert code == expected.exit_code == 0 and sink.flushed
    assert sink.text == serialize_result(expected) + '\n'
    assert json.loads(sink.text)['result'] == direct(command, root, before).as_dict()['result']
    assert inventory(tmp_path) == protected


@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('bad_count', [None, 0, -1, True, 1.5, 'oversized'])
def test_unconfirmed_output_progress_cannot_be_success_or_spin(tmp_path, command, bad_count):
    root, before, _ = project_pair(tmp_path)
    protected = inventory(tmp_path)
    calls = []
    class BadSink:
        def write(self, value):
            calls.append(value)
            assert len(calls) == 1, 'unconfirmed progress must not loop'
            return len(value) + 1 if bad_count == 'oversized' else bad_count
        def flush(self):
            raise AssertionError('unconfirmed output was flushed as complete')
    assert main(arguments(command, root, before), stdout=BadSink(), stderr=io.StringIO()) == 5
    assert len(calls) == 1 and inventory(tmp_path) == protected


@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('failure', ['write', 'flush'])
def test_failed_destination_keeps_project_and_fresh_retry_result(tmp_path, command, failure):
    root, before, _ = project_pair(tmp_path)
    argv = arguments(command, root, before)
    expected = serialize_result(dispatch_result(argv)) + '\n'
    protected = inventory(tmp_path)
    sink = ShortSink(11, fail_write=failure == 'write', fail_flush=failure == 'flush')
    assert main(argv, stdout=sink, stderr=io.StringIO()) == 5
    assert expected.startswith(sink.text) and not sink.flushed
    assert (sink.text == expected) == (failure == 'flush')
    retry = ShortSink(17)
    assert main(argv, stdout=retry, stderr=io.StringIO()) == 0
    assert retry.text == expected and retry.flushed and inventory(tmp_path) == protected


def test_real_broken_pipe_is_an_io_failure_without_project_change(tmp_path):
    root, before, _ = project_pair(tmp_path)
    protected = inventory(tmp_path)
    reader, writer = os.pipe(); os.close(reader)
    sink = io.TextIOWrapper(io.FileIO(writer, 'w'), encoding='utf-8', write_through=True)
    try:
        assert main(arguments('query', root, before), stdout=sink, stderr=io.StringIO()) == 5
    finally:
        sink.close()
    assert inventory(tmp_path) == protected


@pytest.mark.parametrize('command', COMMANDS)
def test_retained_relative_project_and_local_base_do_not_follow_later_cwd(tmp_path, monkeypatch, command):
    root, before, _ = project_pair(tmp_path)
    other = tmp_path / 'other'; other.mkdir()
    expected = direct(command, root, before).as_dict()
    options = inputs(command, before)
    if command == 'diff':
        options['against'] = 'before'
    monkeypatch.chdir(tmp_path)
    with ReadCommandWork(command, Path('current'), **options) as work:
        monkeypatch.chdir(other)
        assert work.advance(3) and work.result.as_dict() == expected


def test_retained_query_options_are_owned_before_first_loading_phase(tmp_path):
    root, _, _ = project_pair(tmp_path)
    options = {'--type': ['requirement'], '--select': ['/title'], '--limit': '100'}
    expected = query_project(root, NormalizedQuery(filters={'type': ['requirement']},
                                                  select=['/title'], limit=100)).as_dict()
    with ReadCommandWork('query', root, options=options) as work:
        options['--type'].append('goal'); options['--select'].append('/owner'); options['--limit'] = '0'
        assert work.advance(3)
        assert work.result.as_dict() == expected and work.result.result['total'] == 1


@pytest.mark.parametrize('explicit_cwd', [False, True])
def test_relative_query_filter_origin_is_retained_before_first_read(tmp_path, monkeypatch, explicit_cwd):
    root, _, _ = project_pair(tmp_path)
    filters = tmp_path / 'filters'; filters.mkdir()
    other = tmp_path / 'other'; other.mkdir()
    (filters / 'filter.json').write_bytes(artifact_bytes(expression_document(literal(True))))
    (other / 'filter.json').write_bytes(artifact_bytes(expression_document(literal(False))))
    monkeypatch.chdir(tmp_path if explicit_cwd else filters)
    kwargs = {'cwd': 'filters'} if explicit_cwd else {}
    with ReadCommandWork('query', root, options={'--filter': ['filter.json'], '--limit': '100'}, **kwargs) as work:
        monkeypatch.chdir(other)
        assert work.advance(3) and work.result.exit_code == 0
        assert work.result.result['total'] == work.result.result['returned'] == 2


@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('boundary', range(1, 7))
def test_failed_runtime_boundary_exposes_no_result_and_cannot_resume_as_success(tmp_path, monkeypatch, command, boundary):
    root, before, _ = project_pair(tmp_path)
    protected = inventory(tmp_path)
    ledger = WorkConsumption(sampler=ticking()); call = ledger.begin()
    native = call.control; count = 0
    def control(point):
        nonlocal count
        count += 1
        if count == boundary:
            raise OSError('owned observer boundary failure')
        return native(point)
    monkeypatch.setattr(call, 'control', control)
    with ReadCommandWork(command, root, **inputs(command, before)) as work:
        try:
            with pytest.raises(OSError), no_write_attempts():
                while not work.advance(1, call=call):
                    pass
        finally:
            call.finish()
        assert work.state['phase'] == 'failed' and not work.state['finished']
        assert work.state['command_exit_code'] is None and work.state['command_complete'] is None
        with pytest.raises(ValueError):
            work.result
        with pytest.raises(ValueError):
            work.advance()
    assert inventory(tmp_path) == protected
    assert direct(command, root, before).exit_code == 0


@pytest.mark.parametrize('command', COMMANDS)
def test_reentrant_advance_and_close_cannot_change_an_active_scope(tmp_path, monkeypatch, command):
    root, before, _ = project_pair(tmp_path)
    expected = direct(command, root, before).as_dict()
    call = WorkConsumption(sampler=ticking()).begin(); native = call.control
    with ReadCommandWork(command, root, **inputs(command, before)) as work:
        def control(point):
            state = work.state
            with pytest.raises(ValueError):
                work.advance()
            with pytest.raises(ValueError):
                work.close()
            assert work.state == state
            return native(point)
        monkeypatch.setattr(call, 'control', control)
        try:
            while not work.advance(2, call=call):
                pass
        finally:
            call.finish()
        assert work.result.as_dict() == expected


@pytest.mark.parametrize('command', COMMANDS)
@pytest.mark.parametrize('completed', [0, 1, 2])
def test_cancellation_before_completion_has_no_success_and_preserves_project(tmp_path, command, completed):
    root, before, _ = project_pair(tmp_path)
    expected = direct(command, root, before).as_dict(); protected = inventory(tmp_path)
    work = ReadCommandWork(command, root, **inputs(command, before))
    if completed:
        assert not work.advance(completed)
    work.close(); work.close()
    assert work.state['phase'] == 'cancelled' and not work.state['finished']
    with pytest.raises(ValueError):
        work.result
    with pytest.raises(ValueError):
        work.advance()
    assert inventory(tmp_path) == protected and direct(command, root, before).as_dict() == expected


@pytest.mark.parametrize('command', COMMANDS)
def test_unavailable_measurements_do_not_disable_or_cut_read_work(tmp_path, command):
    root, before, _ = project_pair(tmp_path)
    expected = direct(command, root, before).as_dict()
    def unavailable():
        raise OSError('optional measurement is unavailable')
    call = WorkConsumption(sampler=unavailable).begin({'--step-wall-ms': 1})
    with ReadCommandWork(command, root, **inputs(command, before)) as work:
        assert work.advance(100, call=call) and work.result.as_dict() == expected
    report = call.finish()
    assert not report['soft_budget_exceeded']
    assert report['invocation']['measured']['wall_ns']['value'] is None


@pytest.mark.parametrize('change', ['bytes', 'membership'])
def test_concurrent_diff_capture_is_a_conflict_without_partial_comparison(tmp_path, monkeypatch, change):
    root, before, _ = project_pair(tmp_path)
    native = ProjectSource.read_normative; changed = False
    target = artifact_path('requirement', aid(), 'SR')
    def read(source, path, **kwargs):
        nonlocal changed
        raw = native(source, path, **kwargs)
        if source.boundary.root == before and path == target and not changed:
            changed = True
            if change == 'bytes':
                value = json.loads(raw); value['title'] = 'Changed during capture'
                put(before, target, artifact_bytes(value))
            else:
                value = domain_value('requirement', id=aid(number=2))
                put(before, artifact_path('requirement', value['id'], 'SR'), artifact_bytes(value))
        return raw
    monkeypatch.setattr(ProjectSource, 'read_normative', read)
    result = diff_project(root, str(before), against_kind='local')
    assert changed and result.exit_code == 6 and not result.complete and result.result is None
    reason = 'comparison_source_changed' if change == 'bytes' else 'comparison_source_membership_changed'
    assert any(d.rationale == reason for d in result.diagnostics)


@pytest.mark.parametrize('against', ['', ' ', None, True, 'bad\0path'])
def test_scope_binding_does_not_turn_invalid_local_bases_into_current_directory(tmp_path, against):
    root, _, _ = project_pair(tmp_path)
    with ReadCommandWork('diff', root, against=against, against_kind='local') as work:
        assert work.advance() and work.result.exit_code == 3 and work.result.result is None
