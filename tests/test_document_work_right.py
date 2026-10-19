"""Document closure, source-bound retained evidence and complete file delivery."""
from copy import deepcopy
import errno
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from specroad.documents import work
from specroad.documents.work import finalize_document_work
from specroad.documents.work_result import publish_document_result_files
from specroad.model.canonical import canonical_json_bytes
from specroad.security import ProjectBoundary, SafetyViolation
from specroad.work.checkpoints import CheckpointStore, CheckpointStorageError
from specroad.work.manifest import complete_work_manifest, create_work_manifest, partition_work_manifest
from specroad.work.resume import WorkResumeError
from specroad.work.root import WorkDirectory
from support.document_work import registry, artifacts, setup, advance
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from test_document_work import assert_native
from test_work_resume import recorded


def invoke(store, operation):
    if operation == 'advance': return advance(store)
    if operation == 'finalize': return finalize_document_work(store, registry=registry())
    return publish_document_result_files(store, registry=registry())


def repacked(tmp_path, mutate, operation, *, values=None):
    """Rehash altered evidence through the actual codec, not a broken file hash."""
    supplied, project, initial, actual = setup(tmp_path / 'actual', values=values)
    advance(actual, size=100)
    current = actual.read(); rows = [json.loads(current.objects[i['evidence']['sha256']])
                                   for i in current.entries('completed')]
    outcome = work._outcome(current).as_dict()
    mutate(rows)
    candidate = partition_work_manifest(initial, {r['unit_id']: canonical_json_bytes(r) for r in rows})
    store = CheckpointStore(WorkDirectory(initial, protected_roots=(ProjectBoundary(project),),
                            directory=tmp_path / 'repacked-work'), initial)
    store.publish(initial); store.publish(candidate)
    if operation == 'publish':
        candidate = complete_work_manifest(candidate, outcome, exit_code=0)
        store.publish(candidate)
    return supplied, store, candidate


@pytest.mark.parametrize('operation', ['advance', 'finalize', 'publish'])
@pytest.mark.parametrize('change', ['lost_include', 'lost_last_occurrence', 'extra_occurrence',
    'parent', 'boolean_index', 'edge_pointer', 'edge_hash', 'record_hash', 'include_inventory',
    'closure_flag', 'extra_field', 'malformed_occurrence'])
def test_rehashed_composition_requires_every_source_bound_occurrence(recorded, tmp_path, monkeypatch, operation, change):
    def mutate(rows):
        data = rows[0]['observation']; occurrences = data['occurrences']
        if change == 'lost_include':
            # Lose a whole repeated subtree, repairing counts, indices and the
            # retained-record set. Source edges must still expose the omission.
            start = next(i for i, o in enumerate(occurrences) if o['artifact_id'] == ref('BLOCK', '1'))
            del occurrences[start:]
            data['occurrence_count'] = len(occurrences)
            ids = {o['artifact_id'] for o in occurrences}
            data['records'] = {k: v for k, v in data['records'].items() if k in ids}
        elif change == 'lost_last_occurrence':
            occurrences.pop(); data['occurrence_count'] = len(occurrences)
        elif change == 'extra_occurrence':
            occurrences.append(deepcopy(occurrences[-1])); data['occurrence_count'] += 1
        elif change == 'parent': occurrences[-1]['parent_occurrence'] = 0
        elif change == 'boolean_index': occurrences[0]['occurrence_index'] = False
        elif change == 'edge_pointer': occurrences[1]['via']['pointer'] = '/relations/99'
        elif change == 'edge_hash': occurrences[1]['via']['relation_sha256'] = 'f' * 64
        elif change == 'record_hash': data['records'][ref('DOC')]['source_sha256'] = 'f' * 64
        elif change == 'include_inventory': data['include_edges'].pop()
        elif change == 'closure_flag': data['include_graph_checked'] = False
        elif change == 'extra_field': data['unknown_completion'] = True
        else: occurrences[1] = {'artifact_id': []}
    _, store, candidate = repacked(tmp_path, mutate, operation)
    def forbidden(*args, **kwargs): raise AssertionError('Invalid evidence reached execution')
    monkeypatch.setattr(work, '_evaluate', forbidden)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught: invoke(store, operation)
    assert caught.value.exit_code == 6 and store.read().raw == candidate.raw
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('operation', ['advance', 'finalize', 'publish'])
@pytest.mark.parametrize('change', ['literal_prefix', 'literal_swap', 'literal_value', 'boolean_count',
    'query_prefix', 'changed_limit', 'changed_offset', 'false_truncated', 'query_binding',
    'query_source_count', 'query_duplicate', 'query_order', 'query_cell', 'query_source_hash',
    'query_item', 'malformed_page', 'lost_query', 'view_hash'])
def test_rehashed_tables_preserve_literal_coverage_and_exact_bound_query_page(recorded, tmp_path, operation, change):
    def mutate(rows):
        literal = next(r['observation'] for r in rows if r['artifact_id'] == ref('BLOCK', '4'))
        data = next(r['observation'] for r in rows if r['artifact_id'] == ref('BLOCK', '3'))
        page = data['query_result']
        if change == 'literal_prefix': literal['rows'].pop(); literal['row_count'] -= 1
        elif change == 'literal_swap': literal['rows'][0], literal['rows'][1] = literal['rows'][1], literal['rows'][0]
        elif change == 'literal_value': literal['rows'][0]['cells'][1]['value']['present'] = 0
        elif change == 'boolean_count': literal['row_count'] = True
        elif change == 'query_prefix':
            data['rows'].pop(); data['row_count'] -= 1; page['items'].pop(); page['returned'] -= 1
        elif change == 'changed_limit':
            page['limit'] = 1; page['items'].pop(); page['returned'] = 1; page['truncated'] = True
            data['rows'].pop(); data['row_count'] = 1
        elif change == 'changed_offset': page['offset'] = 1
        elif change == 'false_truncated': page['truncated'] = True
        elif change == 'query_binding': data['query_binding']['inputs_sha256'] = 'f' * 64
        elif change == 'query_source_count': data['query_binding']['source_count'] -= 1
        elif change == 'query_duplicate':
            data['rows'][1] = deepcopy(data['rows'][0]); page['items'][1] = deepcopy(page['items'][0])
        elif change == 'query_order': data['rows'].reverse(); page['items'].reverse()
        elif change == 'query_cell': data['rows'][0]['cells'][0]['value'] = 'not the source'
        elif change == 'query_source_hash': data['rows'][0]['source_sha256'] = 'f' * 64
        elif change == 'query_item': page['items'][0]['revision'] += 1
        elif change == 'malformed_page': data['query_result'] = {'items': []}
        elif change == 'lost_query': data['query_result'] = None; data['query_binding'] = None
        else: data['view']['source_sha256'] = 'f' * 64
    values = artifacts(branch='query_view' if change == 'view_hash' else 'embedded')
    _, store, candidate = repacked(tmp_path, mutate, operation, values=values); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught: invoke(store, operation)
    assert caught.value.exit_code == 6 and store.read().raw == candidate.raw and inventory(tmp_path) == before


@pytest.mark.parametrize('operation', ['advance', 'finalize', 'publish'])
@pytest.mark.parametrize('change', ['reference_target', 'prose_hash', 'block_selection', 'new_authority'])
def test_other_retained_block_data_does_not_gain_false_sources_or_authority(recorded, tmp_path, operation, change):
    def mutate(rows):
        if change == 'reference_target':
            data = next(r['observation'] for r in rows if r['artifact_id'] == ref('BLOCK', '5'))
            data['target']['record']['title'] = 'a different artifact'
        elif change == 'prose_hash':
            data = next(r['observation'] for r in rows if r['artifact_id'] == ref('BLOCK', '2'))
            data['content']['children'] = []
        elif change == 'block_selection': rows[-1]['selected'] = True; rows[-1]['observation'] = {}
        else: rows[0]['observation']['write_authorized'] = True
    _, store, candidate = repacked(tmp_path, mutate, operation); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError): invoke(store, operation)
    assert store.read().raw == candidate.raw and inventory(tmp_path) == before


@pytest.mark.parametrize('operation', ['advance', 'finalize', 'publish'])
@pytest.mark.parametrize('change', ['block', 'occurrence'])
def test_global_completion_cannot_drop_data_from_successful_units(recorded, tmp_path, operation, change):
    _, _, _, store = setup(tmp_path); advance(store, size=100)
    current = store.read(); outcome = work._outcome(current).as_dict()
    if change == 'block': outcome['result']['blocks'].pop()
    else: outcome['result']['composition']['occurrences'].pop()
    candidate = complete_work_manifest(current, outcome, exit_code=0); store.publish(candidate)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught: invoke(store, operation)
    assert caught.value.reason == 'document_final_result_changed'
    assert store.read().raw == candidate.raw and inventory(tmp_path) == before


@pytest.mark.parametrize(('offset', 'limit'), [(0, 0), (1, 1), (8, 10)])
def test_explicit_empty_or_offset_page_is_complete_without_expanding_its_scope(recorded, tmp_path, offset, limit):
    values = artifacts(limit=limit)
    query = next(v for v in values if v['id'] == ref('BLOCK', '3'))
    query['payload']['query'].update(offset=offset, select=['/id', '/absent'])
    supplied, _, _, store = setup(tmp_path, values=values); advance(store, size=100)
    assert_native(json.loads(finalize_document_work(store, registry=registry()).outcome_bytes)['result'], supplied)


def test_configured_view_uses_the_same_saved_configuration_and_row_projection(recorded, tmp_path):
    from support.srx import binary, expression_document, field, literal
    values = artifacts(branch='table_view'); configuration = record_value('configuration')
    values.append(configuration)
    next(v for v in values if v['artifact_type'] == 'view')['scope_descriptor']['configuration_id'] = configuration['id']
    next(v for v in values if v['artifact_type'] == 'requirement')['applicability'] = expression_document(
        binary('eq', field('/effective_values/platform', 'configuration'), literal('windows')))
    supplied, _, _, store = setup(tmp_path, values=values); advance(store, size=100)
    result = json.loads(finalize_document_work(store, registry=registry()).outcome_bytes)['result']
    assert_native(result, supplied)
    query = next(b['observation'] for b in result['blocks'] if b['artifact_id'] == ref('BLOCK', '3'))
    assert query['row_count'] == 1
    assert query['query_binding']['configuration_binding']['configuration_id'] == configuration['id']


@pytest.mark.parametrize('change', ['attachments', 'reservations', 'reservation_list', 'overlap',
    'document_shape', 'profile_key'])
def test_invalid_saved_context_is_a_typed_conflict_before_any_write(recorded, tmp_path, change):
    from specroad.cli.requests import CommandRequest
    from specroad.work.resume import _runtime_build
    _, project, original, _ = setup(tmp_path / 'actual')
    inputs = [{**{k: i[k] for k in ('root_id', 'path')}, 'raw': original.objects[i['sha256']]}
              for i in original.entries('inputs')]
    item = next(i for i in inputs if i['root_id'] == 'context')
    context = json.loads(item['raw'])
    if change == 'attachments': context['attachments'] = None
    elif change == 'reservations': context['reservations'] = {'unexpected': []}
    elif change == 'reservation_list': context['reservations']['reserved_artifact_ids'] = [None]
    elif change == 'overlap': context['resources'].append(context['documents'][0])
    elif change == 'profile_key': context['profile_chain'][0] = ''
    else:
        next(i for i in inputs if i['path'] == context['documents'][0])['raw'] = b'{}'
    item['raw'] = canonical_json_bytes(context)
    initial = create_work_manifest(registry(), CommandRequest('document.project'), tool_build=_runtime_build(),
        source_bindings=original.as_dict()['source_bindings'], inputs=inputs,
        units=[{k: t[k] for k in ('key', 'phase', 'range')} for t in original.entries('tasks')])
    store = CheckpointStore(WorkDirectory(initial, protected_roots=(ProjectBoundary(project),),
        directory=tmp_path / 'repacked-work'), initial); store.publish(initial)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught: advance(store)
    assert caught.value.exit_code == 6 and store.read().raw == initial.raw and inventory(tmp_path) == before


@pytest.mark.parametrize('branch', ['embedded', 'table_view'])
def test_large_complete_projection_preserves_every_selected_row_and_external_hash(recorded, tmp_path, branch):
    values = artifacts(count=1000, branch=branch, limit=1000)
    original = next(v for v in values if v['artifact_type'] == 'requirement' and v.get('owner') == 'team')
    for number in range(10, 138):
        value = deepcopy(original); value.update(id='SR-REQ-' + format(number, '026X'), title='row ' + str(number))
        values.append(value)
    supplied, project, _, store = setup(tmp_path, values=values); before = inventory(project)
    for size in (1, 3, 6): advance(store, size=size)
    final = finalize_document_work(store, registry=registry()); result = json.loads(final.outcome_bytes)['result']
    assert_native(result, supplied)
    by_id = {b['artifact_id']: b['observation'] for b in result['blocks']}
    assert by_id[ref('BLOCK', '3')]['row_count'] == 130
    assert by_id[ref('BLOCK', '4')]['row_count'] == 1000
    delivered = publish_document_result_files(store, registry=registry()).as_dict()
    reference = delivered['command_outcome']['result_ref']; raw = Path(reference['path']).read_bytes()
    assert raw == canonical_json_bytes(result) and len(raw) == reference['size']
    assert sha256(raw).hexdigest() == reference['sha256'] and inventory(project) == before


def test_completed_native_kernels_are_not_reexecuted_by_checks_or_delivery(recorded, tmp_path, monkeypatch):
    _, _, _, store = setup(tmp_path); advance(store, size=100)
    expected = finalize_document_work(store, registry=registry())
    def forbidden(*args, **kwargs): raise AssertionError('Confirmed native kernel was repeated')
    for name in ('compose_document', 'resolve_table_block', 'resolve_artifact_reference', 'parse_prose', '_evaluate'):
        monkeypatch.setattr(work, name, forbidden)
    monkeypatch.setattr('specroad.query.paging.select_query', forbidden)
    monkeypatch.setattr('specroad.documents.prose._Parser.blocks', forbidden)
    monkeypatch.setattr('specroad.profiles.composition.compose_profiles', forbidden)
    before = inventory(tmp_path)
    assert advance(store)[0].executed_unit_ids == ()
    assert finalize_document_work(store, registry=registry()).outcome_bytes == expected.outcome_bytes
    assert inventory(tmp_path) == before
    delivered = publish_document_result_files(store, registry=registry()).as_dict()
    assert json.loads(Path(delivered['command_outcome']['result_ref']['path']).read_bytes()) == json.loads(expected.outcome_bytes)['result']


@pytest.mark.parametrize('file_kind', ['payload', 'manifest'])
@pytest.mark.parametrize('late', [False, True])
def test_output_failure_keeps_checkpoint_and_actual_files_for_explicit_retry(recorded, tmp_path, monkeypatch, file_kind, late):
    from specroad.work import result_files
    _, project, _, store = setup(tmp_path); advance(store, size=100)
    final = finalize_document_work(store, registry=registry()); before = inventory(project)
    native_write = result_files._write_new; native_replace = result_files.replace_bound_image
    writes = []; replacements = []; target_number = 1 if file_kind == 'payload' else 2
    def write(directory, name, raw):
        writes.append(raw)
        if not late and len(writes) == target_number:
            native_write(directory, name, raw[:7])
            raise OSError(errno.ENOSPC, 'Injected partial document output')
        return native_write(directory, name, raw)
    def replace(*args, **kwargs):
        result = native_replace(*args, **kwargs); replacements.append(args[3])
        if late and len(replacements) == target_number:
            raise OSError(errno.EIO, 'Injected error after actual document output replacement')
        return result
    with monkeypatch.context() as patcher:
        patcher.setattr(result_files, '_write_new', write)
        patcher.setattr(result_files, 'replace_bound_image', replace)
        with pytest.raises(OSError) as caught: publish_document_result_files(store, registry=registry())
    assert caught.value.errno == (errno.EIO if late else errno.ENOSPC)
    assert store.read().raw == final.manifest.raw and inventory(project) == before
    retained = {p.name: p.read_bytes() for p in (tmp_path / 'work/results').iterdir()}
    assert len(retained) == target_number
    assert (writes[-1] if late else writes[-1][:7]) in retained.values()
    delivery = publish_document_result_files(store, registry=registry()).as_dict()
    assert all((tmp_path / 'work/results' / name).read_bytes() == raw for name, raw in retained.items())
    reference = delivery['command_outcome']['result_ref']; raw = Path(reference['path']).read_bytes()
    assert raw == canonical_json_bytes(json.loads(final.outcome_bytes)['result'])
    assert len(raw) == reference['size'] and sha256(raw).hexdigest() == reference['sha256']
    assert store.read().raw == final.manifest.raw and inventory(project) == before


@pytest.mark.parametrize('file_kind', ['result_ref', 'delivery_manifest'])
@pytest.mark.parametrize('damage', ['missing', 'changed', 'symlink'])
def test_delivery_access_rechecks_both_files_without_repair(recorded, tmp_path, file_kind, damage):
    _, _, _, store = setup(tmp_path); advance(store, size=100); finalize_document_work(store, registry=registry())
    delivery = publish_document_result_files(store, registry=registry()); observed = delivery.as_dict()
    reference = observed['command_outcome']['result_ref'] if file_kind == 'result_ref' else observed[file_kind]
    path = Path(reference['path']); original = path.read_bytes()
    if damage == 'missing': path.unlink()
    elif damage == 'changed': path.write_bytes(original + b' ')
    else:
        outside = tmp_path / 'foreign'; outside.write_bytes(original); os.chmod(outside, 0o600)
        path.unlink(); path.symlink_to(outside)
    before = inventory(tmp_path)
    expected_error = SafetyViolation if damage == 'symlink' else (WorkResumeError, CheckpointStorageError)
    with no_write_attempts(), pytest.raises(expected_error): delivery.as_dict()
    assert inventory(tmp_path) == before
