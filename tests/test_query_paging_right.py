"""Exact pages from real external sort/delivery work and explicit owned storage."""
import errno
import json
import os

import pytest

from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, QueryWork, query_records
from specroad.security import ProjectBoundary, SafetyViolation
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.read_only import inventory, no_write_attempts
from support.relations import aid
from support.srx import binary, expression_document, field, literal


def requirement(number, **changes):
    value = domain_value('requirement', id=aid(number=number))
    value.update(changes)
    return value


def records(values):
    return [SourceRelations(artifact_bytes(value)) for value in values]


def protected(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'specroad.json').write_bytes(b'original project fixture\n')
    return (ProjectBoundary(project),)


def finish(work, units):
    while not work.advance(units)['complete']:
        pass
    return work.result


def ids(result):
    return [item['id'] for item in result.data['items']]


@pytest.mark.parametrize('count,offset,limit', [
    (0, 0, 0), (0, 7, 5), (3, 3, 5), (3, 8, 2), (3, 0, 0), (3, 2 ** 53, 1)])
def test_empty_and_beyond_end_pages_keep_exact_counts_in_single_and_many_steps(tmp_path, count, offset, limit):
    roots = protected(tmp_path)
    sources = records([requirement(n) for n in range(count, 0, -1)])
    query = NormalizedQuery(offset=offset, limit=limit)
    expected = {'items': [], 'total': count, 'offset': offset, 'limit': limit,
                'returned': 0, 'truncated': offset < count}
    assert query_records(sources, query, project={}).data == expected
    for name, units in [('single', 10000), ('many', 1)]:
        with QueryWork(tmp_path / name, sources, query, project={}, protected_roots=roots,
                       batch_bytes=1) as work:
            result = finish(work, units)
            assert result.data == expected
            assert result.query_sha256 == query.sha256 and result.source_count == count
            assert work.state['sort']['accepted_records'] == count
            assert work.state['sort']['complete'] and not work.state['durable_checkpoint']


@pytest.mark.parametrize('direction', ['asc', 'desc'])
@pytest.mark.parametrize('batch', [1, 4096])
def test_external_merge_keeps_scalar_types_and_key_directions(tmp_path, direction, batch):
    roots = protected(tmp_path)
    values = [requirement(1, extensions={'org.example': {}})]
    values += [requirement(n, extensions={'org.example': {'score': value}})
               for n, value in enumerate([None, False, True, -1, 2.5, 10, '2', 'a'], 2)]
    query = NormalizedQuery(sort=['/extensions/org.example/score:' + direction],
                            select=['/title', '/extensions/org.example/score'])
    sources = records(list(reversed(values)))
    order = list(range(1, 10)) if direction == 'asc' else list(range(9, 0, -1))
    with QueryWork(tmp_path / 'spool', sources, query, project={}, protected_roots=roots,
                   batch_bytes=batch) as work:
        result = finish(work, 3)
        assert ids(result) == [aid(number=n) for n in order]
        assert result.data == query_records(sources, query, project={}).data
        assert result.data['total'] == 9 and result.data['returned'] == 9
        assert result.data['truncated'] is False
        for item in result.data['items']:
            assert list(item['values']) == ['/title', '/extensions/org.example/score']


def test_unicode_mixed_keys_and_ascending_id_ties_survive_every_merge(tmp_path):
    roots = protected(tmp_path)
    values = [requirement(4, owner='b', title='Z'), requirement(3, owner='a', title='é'),
              requirement(2, owner='a', title='e\u0301'), requirement(1, owner='a', title='A')]
    sources = records(values)
    query = NormalizedQuery(sort=['owner', 'title:desc'], select=['/title', '/owner'])
    bindings = []
    for batch in (1, 65536):
        root = tmp_path / ('spool' + str(batch))
        with QueryWork(root, sources, query, project={}, protected_roots=roots,
                       batch_bytes=batch) as work:
            result = finish(work, 1)
            assert ids(result) == [aid(number=n) for n in (2, 3, 1, 4)]
            assert [item['values']['/title'] for item in result.data['items']] == ['e\u0301', 'é', 'A', 'Z']
            assert result.data == query_records(sources, query, project={}).data
            manifest = json.loads((root / 'spool.json').read_bytes())
            bindings.append((manifest['input_sha256'], manifest['result']['sha256']))
    assert bindings[0] == bindings[1]


def test_limit_one_waits_for_all_matches_and_real_sort_work_before_delivery(tmp_path):
    roots = protected(tmp_path)
    sources = records([requirement(n) for n in range(257, 0, -1)])
    query = NormalizedQuery(sort=['id:desc'], offset=1, limit=1)
    with QueryWork(tmp_path / 'spool', sources, query, project={}, protected_roots=roots,
                   batch_bytes=1024) as work:
        first = work.advance(1)
        assert first['sort']['accepted_records'] == 1 and first['retained_items'] == 0
        assert first['sort']['source_finished'] is False and not first['complete']
        with pytest.raises(ValueError):
            work.result
        while not work.state['complete']:
            before = work.state
            current = work.advance(1)
            assert current['units_completed'] == before['units_completed'] + 1
            if current['retained_items']:
                assert current['sort']['complete'] and current['sort']['accepted_records'] == 257
            if not current['complete']:
                with pytest.raises(ValueError):
                    work.result
        assert ids(work.result) == [aid(number=256)]
        assert {k: v for k, v in work.result.data.items() if k != 'items'} == {
            'total': 257, 'offset': 1, 'limit': 1, 'returned': 1, 'truncated': True}


def test_actual_collection_above_historical_soft_count_is_complete_in_both_runs(tmp_path):
    roots = protected(tmp_path)
    count = 10001
    sources = records([requirement(n) for n in range(count, 0, -1)])
    query = NormalizedQuery(sort=['id:desc'], select=['/title'], limit=count)
    results = []
    for name, units in [('single', 1000000), ('many', 37)]:
        root = tmp_path / name
        with QueryWork(root, sources, query, project={}, protected_roots=roots,
                       batch_bytes=16384) as work:
            results.append(finish(work, units))
            manifest = json.loads((root / 'spool.json').read_bytes())
            assert manifest['record_count'] == manifest['result']['records'] == count
            assert manifest['batch']['count'] > 1 and manifest['batch']['peak_encoded_bytes'] <= 16384
    assert results[0].data == results[1].data
    assert results[0].inputs_sha256 == results[1].inputs_sha256
    assert ids(results[0]) == [aid(number=n) for n in range(count, 0, -1)]
    assert results[0].data['total'] == results[0].data['returned'] == count
    assert results[0].data['limit'] == count and results[0].data['truncated'] is False


def test_filters_original_projection_and_bindings_precede_external_paging(tmp_path):
    roots = protected(tmp_path)
    sources = records([requirement(n, description='Cafe\u0301' if n != 4 else 'Tea',
                                    owner='a' if n != 5 else 'b') for n in (5, 4, 3, 2, 1)])
    original = tuple(sources)
    raw = [source.source_bytes for source in original]
    predicate = expression_document(binary('ne', field('/id'), literal(aid(number=2))))
    query = NormalizedQuery(filters={'owner': ['a'], 'full_text': ['café']},
                            srx_filters=[predicate], sort=['id:desc'],
                            select=['/description', '/owner'], offset=1, limit=1)
    configuration = {'configuration_id': 'owned', 'effective_values': {'platform': 'linux'}}
    expected = query_records(sources, query, project={}, configuration=configuration)
    with QueryWork(tmp_path / 'spool', sources, query, project={}, configuration=configuration,
                   protected_roots=roots, batch_bytes=1) as work:
        sources.clear()  # Membership and original input bindings were captured.
        detached = work.state
        detached['sort']['accepted_records'] = 999
        result = finish(work, 1)
        assert ids(result) == [aid(number=1)] and result.data['total'] == 2
        assert result.data == expected.data
        assert (result.query_sha256, result.inputs_sha256) == (expected.query_sha256, expected.inputs_sha256)
        assert result.data['items'][0]['values'] == {'/description': 'Cafe\u0301', '/owner': 'a'}
        changed = result.data
        changed['items'][0]['values']['/description'] = 'changed'
        assert result.data == expected.data
        assert work.state['sort']['accepted_records'] == 2
    assert [source.source_bytes for source in original] == raw


def test_unrepresentable_offset_keeps_the_existing_json_number_error():
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        NormalizedQuery(offset=2 ** 100, limit=1)
    assert (caught.value.reason, caught.value.pointer) == ('number_roundtrip_loss', '/offset')


@pytest.mark.parametrize('bad', [{}, []])
@pytest.mark.parametrize('limit', [0, 1])
def test_non_scalar_after_first_match_fails_without_any_complete_page(tmp_path, bad, limit):
    roots = protected(tmp_path)
    sources = records([requirement(1, extensions={'org.example': {'score': 1}}),
                       requirement(2, extensions={'org.example': {'score': bad}})])
    work = QueryWork(tmp_path / 'spool', sources,
                     NormalizedQuery(sort=['/extensions/org.example/score'], limit=limit),
                     project={}, protected_roots=roots, batch_bytes=1)
    with pytest.raises(ModelError) as caught:
        finish(work, 1)
    assert (caught.value.reason, caught.value.pointer) == ('query_sort_value_not_scalar', '/sort/0')
    assert work.state['phase'] == 'failed' and not work.state['complete']
    with pytest.raises(ValueError):
        work.result
    assert list((tmp_path / 'spool').iterdir())
    before = inventory(tmp_path / 'spool')
    work.close()
    assert inventory(tmp_path / 'spool') == before


@pytest.mark.parametrize('units', [0, -1, True, 1.5])
def test_invalid_step_budget_does_not_advance_or_cancel_owned_work(tmp_path, units):
    roots = protected(tmp_path)
    with QueryWork(tmp_path / 'spool', records([requirement(1)]), NormalizedQuery(),
                   project={}, protected_roots=roots) as work:
        before = work.state
        with no_write_attempts(), pytest.raises(ValueError):
            work.advance(units)
        assert work.state == before
        assert ids(finish(work, 1)) == [aid(number=1)]


@pytest.mark.parametrize('phase', ['input', 'merge'])
def test_cancellation_preserves_files_and_protected_project_without_a_result(tmp_path, phase):
    roots = protected(tmp_path)
    before = inventory(roots[0].root)
    work = QueryWork(tmp_path / 'spool', records([requirement(n) for n in (4, 3, 2, 1)]),
                     NormalizedQuery(), project={}, protected_roots=roots, batch_bytes=1)
    while True:
        state = work.advance(1)
        if state['sort']['phase'] == phase:
            break
        assert not state['complete']
    owned = inventory(tmp_path / 'spool')
    work.close()
    work.close()
    assert work.state['phase'] == 'cancelled' and not work.state['complete']
    with pytest.raises(ValueError):
        work.advance(1)
    with pytest.raises(ValueError):
        work.result
    assert inventory(tmp_path / 'spool') == owned and inventory(roots[0].root) == before


def test_run_tampering_between_sort_and_delivery_cannot_publish_a_page(tmp_path):
    roots = protected(tmp_path)
    root = tmp_path / 'spool'
    work = QueryWork(root, records([requirement(2), requirement(1)]), NormalizedQuery(),
                     project={}, protected_roots=roots, batch_bytes=1)
    while work.advance(1)['phase'] != 'delivery':
        assert not work.state['complete']
    manifest = json.loads((root / 'spool.json').read_bytes())
    path = root / manifest['result']['name']
    path.write_bytes(path.read_bytes() + b'changed')
    before = inventory(root)
    with pytest.raises(SafetyViolation):
        work.advance(1)
    assert work.state['phase'] == 'failed' and inventory(root) == before
    with pytest.raises(ValueError):
        work.result


def test_native_spool_write_failure_keeps_partial_state_and_no_complete_result(tmp_path, monkeypatch):
    roots = protected(tmp_path)
    work = QueryWork(tmp_path / 'spool', records([requirement(1)]), NormalizedQuery(),
                     project={}, protected_roots=roots, batch_bytes=1)
    work.advance(1)
    def full_disk(*args, **kwargs):
        raise OSError(errno.ENOSPC, 'owned fixture')
    with monkeypatch.context() as guard:
        guard.setattr(os, 'write', full_disk)
        with pytest.raises(OSError) as caught:
            work.advance(1)
    assert caught.value.errno == errno.ENOSPC and work.state['phase'] == 'failed'
    assert list((tmp_path / 'spool').iterdir())
    with pytest.raises(ValueError):
        work.result


@pytest.mark.parametrize('location', ['protected', 'existing', 'symlink'])
def test_spool_authority_never_comes_from_project_paths_existing_paths_or_links(tmp_path, location):
    roots = protected(tmp_path)
    existing = tmp_path / 'existing'
    existing.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(existing, target_is_directory=True)
    target = {'protected': roots[0].root / 'spool', 'existing': existing, 'symlink': link / 'spool'}[location]
    before = inventory(tmp_path)
    with pytest.raises((SafetyViolation, FileExistsError)):
        QueryWork(target, [], NormalizedQuery(), project={}, protected_roots=roots)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('empty', [True, False])
def test_unavailable_computed_sort_is_rejected_before_spool_creation(tmp_path, empty):
    roots = protected(tmp_path)
    sources = [] if empty else records([requirement(1)])
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        QueryWork(tmp_path / 'spool', sources, NormalizedQuery(sort=['verification_result']),
                   project={}, protected_roots=roots)
    assert (caught.value.reason, caught.value.pointer) == ('query_verification_provider_required', '/sort/0')
    assert not (tmp_path / 'spool').exists()
