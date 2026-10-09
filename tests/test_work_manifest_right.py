"""Hostile work data stays inert and cannot replace a caller-bound work order."""

from collections.abc import Mapping
from dataclasses import replace
from hashlib import sha256
from types import MappingProxyType
import json

import pytest

from specroad.cli.commands import builtin_registry
from specroad.cli.registry import CommandRegistry
from specroad.cli.requests import CommandRequest
from specroad.model.canonical import canonical_json_bytes
from specroad.work.manifest import (
    WorkManifestError, create_work_manifest, partition_work_manifest,
    read_work_manifest, read_work_successor,
)
from support.read_only import no_write_attempts


BUILD = {'version': 'fixture-version', 'build_sha256': 'a' * 64,
         'hash_algorithm': 'specroad-dev-payload-v1'}
SOURCES = {'project_id': None, 'scope': ['fixture'], 'model_root_sha256': None}


def create(*, request=None, registry=None, data=None, plan=None, sources=None, build=None):
    return create_work_manifest(registry or builtin_registry(), request or CommandRequest('version'),
        tool_build=BUILD if build is None else build,
        source_bindings=SOURCES if sources is None else sources,
        inputs=[{'root_id': 'source', 'path': 'one.json', 'raw': b'{"source":1}\n'}] if data is None else data,
        units=[{'key': str(i), 'phase': 'fixture', 'range': {'start': i, 'end': i + 1}}
               for i in range(4)] if plan is None else plan)


def step(value, index=0):
    task = value.entries('remaining')[index]
    # This is explicit fixture planner evidence, not a production execution.
    return partition_work_manifest(value, {task['unit_id']: canonical_json_bytes({'fixture': task['key']})})


def read(raw, objects, *, build=None, registry=None):
    return read_work_manifest(raw, objects, registry=registry or builtin_registry(),
                              expected_tool_build=BUILD if build is None else build)


def successor(previous, raw, objects, *, build=None, registry=None):
    return read_work_successor(raw, objects, previous=previous,
        registry=registry or builtin_registry(), expected_tool_build=BUILD if build is None else build)


def seal(value):
    value = dict(value); value.pop('checkpoint_sha256', None)
    value['checkpoint_sha256'] = sha256(canonical_json_bytes(value)).hexdigest()
    return canonical_json_bytes(value)


def put(raw, objects):
    digest = sha256(raw).hexdigest(); objects[digest] = raw
    return {'sha256': digest, 'size': len(raw)}


def replace_rows(value, objects, kind, rows):
    raw = canonical_json_bytes({'format_version': 'work-manifest-segment-v1', 'kind': kind, 'entries': rows})
    reference = put(raw, objects)
    value['manifests'][kind] = {'id': 'SEG-' + reference['sha256'], **reference, 'count': len(rows)}
    field = 'input' if kind == 'inputs' else 'task' if kind == 'tasks' else kind
    value[field + '_manifest_sha256'] = reference['sha256']


def test_bound_successive_partitions_preserve_all_previous_data_without_handler_execution():
    called = []
    def forbidden(invocation):
        called.append(invocation)
        raise AssertionError('handler execution from work data')
    registry = CommandRegistry(tuple(replace(c, handler=forbidden) for c in builtin_registry().commands))
    with no_write_attempts():
        original = previous = create(registry=registry)
        for generation in range(1, 5):
            candidate = step(previous, -1)
            current = successor(previous, candidate.raw, candidate.objects, registry=registry)
            assert current.as_dict()['checkpoint_generation'] == generation
            assert current.entries('tasks') == original.entries('tasks')
            assert all(current.objects[k] == v for k, v in previous.objects.items())
            previous = current
    assert called == [] and previous.as_dict()['state'] == 'running'
    assert previous.as_dict()['progress'] == {'completed_units': 4, 'total_units': 4}


@pytest.mark.parametrize('alteration', ['identity', 'command', 'arguments', 'input', 'scope', 'project', 'plan', 'build'])
def test_self_consistent_foreign_work_cannot_replace_the_expected_order(alteration):
    request = CommandRequest('command.describe', arguments={'command': 'version'})
    previous = create(request=request)
    kwargs = {'request': request}
    if alteration == 'command': kwargs['request'] = CommandRequest('version')
    if alteration == 'arguments': kwargs['request'] = CommandRequest('command.describe', arguments={'command': 'command.list'})
    if alteration == 'input': kwargs['data'] = [{'root_id': 'source', 'path': 'one.json', 'raw': b'{"source":2}\n'}]
    if alteration == 'scope': kwargs['sources'] = {**SOURCES, 'scope': ['other-fixture']}
    if alteration == 'project': kwargs['sources'] = {**SOURCES, 'project_id': 'other-declared-project'}
    if alteration == 'plan': kwargs['plan'] = [{'key': 'other', 'phase': 'other', 'range': {'start': 0, 'end': 10}}]
    if alteration == 'build': kwargs['build'] = {**BUILD, 'build_sha256': 'b' * 64}
    candidate = step(create(**kwargs)); value = candidate.as_dict()
    if alteration != 'identity': value['work_id'] = previous.as_dict()['work_id']
    raw = seal(value)
    with no_write_attempts():
        # The replacement is internally valid inert data with freshly computed hashes.
        assert read(raw, candidate.objects, build=kwargs.get('build')).raw == raw
        with pytest.raises(WorkManifestError):
            successor(previous, raw, candidate.objects, build=kwargs.get('build'))
    assert previous.as_dict()['checkpoint_generation'] == 0


@pytest.mark.parametrize('generation', [0, 2, 2**53 - 1])
def test_successor_rejects_replay_or_skipped_generation(generation):
    previous = create(); candidate = step(previous); value = candidate.as_dict()
    value['checkpoint_generation'] = generation
    with pytest.raises(WorkManifestError), no_write_attempts():
        successor(previous, seal(value), candidate.objects)


def test_incremented_generation_without_new_declared_completion_is_not_progress():
    previous = create(); value = previous.as_dict(); value['checkpoint_generation'] = 1
    with pytest.raises(WorkManifestError), no_write_attempts():
        successor(previous, seal(value), previous.objects)


def test_successor_rejects_rewritten_prior_evidence_even_with_valid_new_hashes():
    previous = step(create()); candidate = step(previous); value = candidate.as_dict()
    objects = dict(candidate.objects); rows = candidate.entries('completed')
    rows[0]['evidence'] = put(b'{"forged":true}', objects)
    replace_rows(value, objects, 'completed', rows)
    raw = seal(value)
    assert read(raw, objects).entries('completed')[0] != previous.entries('completed')[0]
    with pytest.raises(WorkManifestError), no_write_attempts():
        successor(previous, raw, objects)


def test_successor_cannot_turn_a_previously_completed_unit_back_into_open_work():
    original = create(); previous = step(original); candidate = step(step(original, -1), -1)
    value = candidate.as_dict(); value['checkpoint_generation'] = 2
    with pytest.raises(WorkManifestError), no_write_attempts():
        successor(previous, seal(value), candidate.objects)


def test_successor_preserves_even_previously_referenced_bytes_not_in_the_new_root():
    previous = create(); candidate = step(previous); objects = dict(candidate.objects)
    old_empty_completed = previous.as_dict()['manifests']['completed']['sha256']
    objects.pop(old_empty_completed)
    assert read(candidate.raw, objects).raw == candidate.raw
    with pytest.raises(WorkManifestError), no_write_attempts():
        successor(previous, candidate.raw, objects)


@pytest.mark.parametrize('field,value', [
    ('normalized_arguments', {'options': [], 'arguments': {}}),
    ('normalized_arguments', {'options': {}, 'arguments': []}),
    ('normalized_arguments', {'options': {}, 'arguments': {'extra': True}}),
    ('command_id', []), ('command_id', 'unknown.command'), ('command_id', 'os.system'),
    ('work_id', 'WORK-' + 'Z' * 26), ('work_id', 'WORK-' + '0' * 25),
    ('checkpoint_generation', False), ('checkpoint_generation', -1),
    ('progress', {'completed_units': False, 'total_units': 4}),
    ('actor', 'new-actor'), ('request_id', 'new-request'), ('operations_sha256', 'f' * 64),
    ('plan_binding', {}), ('algorithm_versions', {'work_manifest': 'foreign-loader'}),
    ('schema_versions', {'work': '2.0.0'}), ('result_parts', [{'module': 'os'}]),
    ('diagnostic_parts', [{'script': 'raise SystemExit'}]), ('cursors', {'python_object': 'pickle'}),
    ('next_action', {'operation': 'execute', 'command': 'os.system'}),
])
def test_rehashed_malformed_or_unauthorized_control_data_has_a_typed_refusal(field, value):
    manifest = create(); root = manifest.as_dict(); root[field] = value
    with pytest.raises(WorkManifestError) as error, no_write_attempts():
        read(seal(root), manifest.objects)
    assert error.value.exit_code == 4


def test_boolean_range_substitution_cannot_compare_equal_to_an_integer_task():
    manifest = create(); value = manifest.as_dict(); objects = dict(manifest.objects)
    rows = manifest.entries('remaining'); rows[1]['range']['start'] = True
    replace_rows(value, objects, 'remaining', rows)
    with pytest.raises(WorkManifestError), no_write_attempts():
        read(seal(value), objects)


def test_completed_manifest_must_follow_the_bound_task_order():
    manifest = step(step(create())); value = manifest.as_dict(); objects = dict(manifest.objects)
    replace_rows(value, objects, 'completed', list(reversed(manifest.entries('completed'))))
    with pytest.raises(WorkManifestError), no_write_attempts():
        read(seal(value), objects)


@pytest.mark.parametrize('member', ['unknown', 'count', 'size', 'id', 'kind', 'format_version'])
def test_rehashed_bad_segment_metadata_is_rejected(member):
    manifest = create(); value = manifest.as_dict(); objects = dict(manifest.objects)
    reference = value['manifests']['tasks']
    segment = json.loads(objects[reference['sha256']])
    if member in ('kind', 'format_version', 'unknown'):
        segment[member] = 'foreign'
        data = put(canonical_json_bytes(segment), objects)
        reference.update(data); reference['id'] = 'SEG-' + data['sha256']
        value['task_manifest_sha256'] = data['sha256']
    else:
        reference[member] = True if member != 'id' else 'SEG-' + '0' * 64
    with pytest.raises(WorkManifestError), no_write_attempts():
        read(seal(value), objects)


def test_shared_segment_amplification_is_rejected_before_repeated_leaf_decoding(monkeypatch):
    import specroad.work.manifest as codec
    manifest = create(); value = manifest.as_dict(); objects = dict(manifest.objects)
    leaf = value['manifests']['tasks']; leaf_raw = objects[leaf['sha256']]
    reference = leaf
    for _ in range(7):
        raw = canonical_json_bytes({'format_version': 'work-manifest-segment-v1', 'kind': 'tasks',
                                    'children': [reference] * 64})
        data = put(raw, objects)
        reference = {'id': 'SEG-' + data['sha256'], **data, 'count': reference['count'] * 64}
    value['manifests']['tasks'] = reference; value['task_manifest_sha256'] = reference['sha256']
    parsed = []; original = codec._parse
    def observe(raw):
        parsed.append(raw)
        return original(raw)
    monkeypatch.setattr(codec, '_parse', observe)
    with pytest.raises(WorkManifestError), no_write_attempts():
        read(seal(value), objects)
    assert parsed.count(leaf_raw) == 1 and len(parsed) <= 12


@pytest.mark.parametrize('bad', ['proxy', 'dict_subclass', 'byte_subclass', 'foreign_value', 'foreign_key', 'wrong_hash'])
def test_all_object_store_entries_are_native_hashed_bytes_without_foreign_hooks(bad):
    manifest = create(); called = []
    class Foreign:
        def __hash__(self):
            called.append('hash'); return 7
        def __eq__(self, other):
            called.append('eq'); raise AssertionError('foreign equality')
        def __bytes__(self):
            called.append('bytes'); raise AssertionError('foreign bytes')
    class ForeignMapping(Mapping):
        def __iter__(self):
            called.append('iter'); raise AssertionError('foreign iteration')
        def __getitem__(self, key):
            called.append('get'); raise AssertionError('foreign lookup')
        def __len__(self):
            called.append('len'); raise AssertionError('foreign length')
    class ForeignDict(dict):
        def items(self):
            called.append('items'); raise AssertionError('foreign items')
    class ForeignBytes(bytes):
        def __bytes__(self):
            called.append('bytes'); raise AssertionError('foreign bytes')
    objects = dict(manifest.objects)
    if bad == 'proxy': objects = MappingProxyType(ForeignMapping())
    if bad == 'dict_subclass': objects = ForeignDict(objects)
    if bad == 'byte_subclass': objects[sha256(b'extra').hexdigest()] = ForeignBytes(b'extra')
    if bad == 'foreign_value': objects[sha256(b'extra').hexdigest()] = Foreign()
    if bad == 'foreign_key': objects[Foreign()] = b'extra'
    if bad == 'wrong_hash': objects['f' * 64] = b'extra'
    called.clear()
    with pytest.raises(WorkManifestError), no_write_attempts():
        read(manifest.raw, objects)
    assert called == []


@pytest.mark.parametrize('where', ['field_key', 'algorithm', 'completion_key', 'kind', 'range'])
def test_foreign_values_cannot_execute_hooks_at_public_codec_boundaries(where):
    manifest = create(); called = []
    class Foreign:
        def __hash__(self):
            called.append('hash'); return 9
        def __eq__(self, other):
            called.append('eq'); raise AssertionError('foreign equality')
        def __bool__(self):
            called.append('bool'); raise AssertionError('foreign truth')
        def __iter__(self):
            called.append('iter'); raise AssertionError('foreign iteration')
    foreign = Foreign()
    if where == 'field_key':
        data = {foreign: 'value'}; operation = lambda: create(build=data)
    elif where == 'algorithm': operation = lambda: create(build={**BUILD, 'hash_algorithm': foreign})
    elif where == 'completion_key':
        data = {foreign: b'{}'}; operation = lambda: partition_work_manifest(manifest, data)
    elif where == 'kind': operation = lambda: manifest.entries(foreign)
    else: operation = lambda: create(plan=[{'key': 'one', 'phase': 'fixture', 'range': {'value': foreign}}])
    called.clear()
    with pytest.raises(WorkManifestError), no_write_attempts():
        operation()
    assert called == []


def test_script_like_json_text_remains_data_without_a_loader_or_handler():
    text = '__import__("os").system("echo forbidden")'
    with no_write_attempts():
        value = create(plan=[{'key': 'one', 'phase': 'fixture', 'range': {'literal': text}}])
        loaded = read(value.raw, value.objects)
    assert loaded.entries('tasks')[0]['range'] == {'literal': text}


def test_cyclic_in_memory_json_is_rejected_without_serializing_foreign_state():
    value = {}; value['self'] = value
    with pytest.raises(WorkManifestError), no_write_attempts():
        create(plan=[{'key': 'one', 'phase': 'fixture', 'range': value}])


@pytest.mark.parametrize('where', ['store', 'nested_range'])
def test_foreign_metaclass_is_not_compared_or_evaluated_during_type_admission(where):
    manifest = create(); called = []
    class ForeignType(type):
        def __eq__(cls, other):
            called.append('metaclass equality')
            raise AssertionError('foreign type comparison')
        __hash__ = type.__hash__
    class Foreign(metaclass=ForeignType):
        pass
    foreign = Foreign()
    with pytest.raises(WorkManifestError), no_write_attempts():
        if where == 'store':
            read(manifest.raw, foreign)
        else:
            create(plan=[{'key': 'one', 'phase': 'fixture', 'range': {'nested': [foreign]}}])
    assert called == []


@pytest.mark.parametrize('raw', [b'{"x":"\xff"}', b'{"x":"\\ud800"}', b'[]', b'null', b'{"x":Infinity}', b'{"x":1e9999}'])
def test_invalid_json_values_are_typed_failures_without_side_effects(raw):
    with pytest.raises(WorkManifestError), no_write_attempts():
        read(raw, {})
