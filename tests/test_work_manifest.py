"""Inert work data retains the complete declared plan and original byte bindings."""

from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import json

import pytest

from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandClass, CommandSpec, EffectScope, PreflightProfile
from specroad.cli.registry import CommandRegistry
from specroad.cli.requests import CommandRequest
from specroad.cli.results import VerifiedContinuation
from specroad.cli.self_description import describe_command
from specroad.model.canonical import canonical_json_bytes
from specroad.model.identity_tokens import decode128
from specroad.work.manifest import (
    WorkManifestError, create_work_manifest, partition_work_manifest, read_work_manifest,
)
from support.read_only import inventory, no_write_attempts


BUILD = {'version': 'fixture-version', 'build_sha256': 'a' * 64,
         'hash_algorithm': 'specroad-dev-payload-v1'}
SOURCES = {'project_id': None, 'scope': ['declared-fixture'], 'model_root_sha256': None}


def inputs():
    return [{'root_id': 'source', 'path': 'second.json', 'raw': b'{"value":2}\n'},
            {'root_id': 'source', 'path': 'first.json', 'raw': b'{"value":1}\n'}]


def units(count=5):
    return [{'key': 'unit-%d' % i, 'phase': 'fixture_processing', 'range': {'start': i, 'end': i + 1}}
            for i in range(count)]


def create(*, registry=None, request=None, data=None, plan=None, sources=None):
    return create_work_manifest(registry or builtin_registry(), request or CommandRequest('version'),
        tool_build=BUILD, source_bindings=SOURCES if sources is None else sources,
        inputs=inputs() if data is None else data, units=units() if plan is None else plan)


def read(raw, objects, *, registry=None, build=None):
    return read_work_manifest(raw, objects, registry=registry or builtin_registry(),
                              expected_tool_build=BUILD if build is None else build)


def sealed(value):
    value = dict(value)
    value.pop('checkpoint_sha256', None)
    value['checkpoint_sha256'] = sha256(canonical_json_bytes(value)).hexdigest()
    return canonical_json_bytes(value)


def evidence(task):
    # Declared planner evidence, not a proof that a production command ran.
    return canonical_json_bytes({'fixture_unit': task['key'], 'observed': True})


def test_real_input_bytes_and_complete_declared_plan_survive_roundtrip_without_effects(tmp_path):
    original = inputs()
    for item in original:
        (tmp_path / item['path']).write_bytes(item['raw'])
    before = inventory(tmp_path)
    data = [{**item, 'raw': (tmp_path / item['path']).read_bytes()} for item in original]
    with no_write_attempts():
        manifest = create(data=data)
        loaded = read(manifest.raw, manifest.objects)
    assert loaded.raw == manifest.raw and loaded.as_dict() == manifest.as_dict()
    assert inventory(tmp_path) == before
    assert len(decode128(loaded.as_dict()['work_id'][5:])) == 16
    assert loaded.as_dict()['progress'] == {'completed_units': 0, 'total_units': 5}
    assert loaded.entries('tasks') == loaded.entries('remaining')
    assert loaded.entries('completed') == []
    for row in loaded.entries('inputs'):
        raw = (tmp_path / row['path']).read_bytes()
        assert row['sha256'] == sha256(raw).hexdigest() and row['size'] == len(raw)
        assert loaded.objects[row['sha256']] == raw


def test_partitions_preserve_identity_bindings_every_unit_and_previous_bytes(monkeypatch):
    calls = []
    def entropy(size):
        calls.append(size)
        return bytes(range(16))
    monkeypatch.setattr('specroad.work.manifest.secrets.token_bytes', entropy)
    manifest = create()
    original = manifest
    tasks = manifest.entries('tasks')
    identity = manifest.as_dict()['work_id']
    completed = set()
    for generation, task in enumerate(reversed(tasks), 1):
        prior = manifest
        manifest = partition_work_manifest(manifest, {task['unit_id']: evidence(task)})
        completed.add(task['unit_id'])
        value = manifest.as_dict()
        assert value['work_id'] == identity and value['checkpoint_generation'] == generation
        assert value['task_manifest_sha256'] == original.as_dict()['task_manifest_sha256']
        assert value['input_manifest_sha256'] == original.as_dict()['input_manifest_sha256']
        assert value['normalized_arguments'] == original.as_dict()['normalized_arguments']
        assert manifest.entries('tasks') == tasks
        done = {row['unit_id'] for row in manifest.entries('completed')}
        remaining = {row['unit_id'] for row in manifest.entries('remaining')}
        assert done == completed and not done & remaining
        assert done | remaining == {row['unit_id'] for row in tasks}
        assert all(manifest.objects[key] == raw for key, raw in prior.objects.items())
        assert read(manifest.raw, manifest.objects).raw == manifest.raw
    assert calls == [16]
    assert manifest.entries('remaining') == []
    assert manifest.as_dict()['next_action'] == {'operation': 'finalize_declared_work'}
    assert manifest.as_dict()['state'] == 'running'
    assert not isinstance(manifest, VerifiedContinuation)
    assert original.as_dict()['progress']['completed_units'] == 0


def test_input_order_and_relocated_source_do_not_change_declared_task_binding(tmp_path):
    first = create()
    moved = tmp_path / 'moved'; moved.mkdir()
    for item in inputs():
        (moved / item['path']).write_bytes(item['raw'])
    second = create(data=[{**item, 'raw': (moved / item['path']).read_bytes()} for item in reversed(inputs())])
    assert first.as_dict()['work_id'] != second.as_dict()['work_id']
    assert first.as_dict()['input_manifest_sha256'] == second.as_dict()['input_manifest_sha256']
    assert first.entries('tasks') == second.entries('tasks')
    assert str(tmp_path).encode() not in second.raw


@pytest.mark.parametrize('count', [1, 64, 65, 4097])
def test_segment_tree_retains_every_declared_unit_with_bounded_control_and_nodes(count):
    manifest = create(plan=units(count))
    assert len(manifest.raw) < 8000
    tasks = manifest.entries('tasks')
    assert [task['key'] for task in tasks] == [unit['key'] for unit in units(count)]
    assert manifest.entries('remaining') == tasks
    for raw in manifest.objects.values():
        value = json.loads(raw)
        if value.get('format_version') == 'work-manifest-segment-v1':
            assert len(value.get('entries', value.get('children'))) <= 64
    changed = partition_work_manifest(manifest, {tasks[-1]['unit_id']: evidence(tasks[-1])})
    assert len(changed.entries('remaining')) == count - 1
    assert changed.entries('tasks') == tasks


def test_registry_binding_does_not_execute_handlers_or_change_published_continuation():
    calls = []
    original = builtin_registry()
    def handler(invocation):
        calls.append(invocation)
        raise AssertionError('Manifest data executed a handler')
    registry = CommandRegistry(tuple(replace(command, handler=handler) for command in original.commands))
    with no_write_attempts():
        manifest = create(registry=registry, request=CommandRequest('command.describe', arguments={'command': 'version'}))
        read(manifest.raw, manifest.objects, registry=registry)
        description = describe_command(registry, 'version')
    assert calls == []
    assert manifest.as_dict()['normalized_arguments'] == {'arguments': {'command': 'version'}, 'options': {}}
    assert not description['work']['continuation_supported']
    assert description['work']['checkpoint_algorithms'] == []


@pytest.mark.parametrize('command', ['work.resume', 'not.registered', 'version; echo unsafe'])
def test_unknown_or_shell_command_text_is_not_an_executable_binding(command):
    with pytest.raises(ValueError), no_write_attempts():
        create(request=CommandRequest(command))


def test_registered_writer_does_not_acquire_authority_from_manifest_data():
    called = []
    command = CommandSpec('fixture.write', ('fixture', 'write'), CommandClass.NORMATIVE_WRITE,
        PreflightProfile.PROJECT_WRITE, EffectScope.NORMATIVE_TRANSACTION,
        handler=lambda invocation: called.append(invocation), requires_project=True)
    with pytest.raises(WorkManifestError), no_write_attempts():
        create(registry=CommandRegistry((command,)), request=CommandRequest('fixture.write'))
    assert called == []


@pytest.mark.parametrize('options', [{'--format': 'json'}, {'--no-color': True}, {'--quiet': True}])
def test_first_codec_refuses_operational_options_instead_of_guessing_semantic_identity(options):
    with pytest.raises(WorkManifestError), no_write_attempts():
        create(request=CommandRequest('version', options=options))


@pytest.mark.parametrize('path', ['/absolute', '../escape', 'a/../b', 'a//b', 'a\\b', 'C:drive'])
def test_input_locations_cannot_introduce_absolute_or_escaping_paths(path):
    with pytest.raises(WorkManifestError), no_write_attempts():
        create(data=[{'root_id': 'source', 'path': path, 'raw': b'bytes'}])


def test_duplicate_input_or_unit_declarations_do_not_silently_reduce_the_plan():
    for data, plan in ((inputs() + inputs()[:1], units()), (inputs(), units() + units()[:1])):
        with pytest.raises(WorkManifestError), no_write_attempts():
            create(data=data, plan=plan)


def test_changed_input_content_changes_bound_units_even_at_the_same_size():
    first = create()
    changed = inputs(); changed[0] = {**changed[0], 'raw': b'{"value":3}\n'}
    second = create(data=changed)
    assert first.as_dict()['input_manifest_sha256'] != second.as_dict()['input_manifest_sha256']
    assert first.as_dict()['task_manifest_sha256'] != second.as_dict()['task_manifest_sha256']
    assert {row['unit_id'] for row in first.entries('tasks')}.isdisjoint(
        row['unit_id'] for row in second.entries('tasks'))


@pytest.mark.parametrize('kind', ['inputs', 'tasks', 'completed', 'remaining'])
def test_missing_or_changed_referenced_segment_prevents_read(kind):
    manifest = create(); reference = manifest.as_dict()['manifests'][kind]
    for replacement in (None, b'{}'):
        objects = dict(manifest.objects)
        if replacement is None:
            objects.pop(reference['sha256'])
        else:
            objects[reference['sha256']] = replacement
        with pytest.raises(WorkManifestError), no_write_attempts():
            read(manifest.raw, objects)


def test_missing_original_bytes_are_not_reconstructed_from_hashes():
    manifest = create(); objects = dict(manifest.objects)
    objects.pop(manifest.entries('inputs')[0]['sha256'])
    with pytest.raises(WorkManifestError), no_write_attempts():
        read(manifest.raw, objects)


@pytest.mark.parametrize('change', [
    {'work_format_version': '9.0.0'}, {'checkpoint_generation': True},
    {'command_class': 'normative_write'}, {'actor': {'id': 'injected'}},
    {'state': 'completed'}, {'frontier': []}, {'unknown_required_field': True},
])
def test_rehashed_false_metadata_is_rejected_before_execution(change):
    manifest = create(); value = manifest.as_dict(); value.update(change)
    with pytest.raises(WorkManifestError), no_write_attempts():
        read(sealed(value), manifest.objects)


def test_a_new_build_requires_an_explicit_matching_reader_binding():
    manifest = create()
    with pytest.raises(WorkManifestError), no_write_attempts():
        read(manifest.raw, manifest.objects, build={**BUILD, 'build_sha256': 'b' * 64})


def test_duplicate_unknown_or_empty_completion_cannot_drop_or_double_count_units():
    original = create(); task = original.entries('tasks')[0]
    completed = partition_work_manifest(original, {task['unit_id']: evidence(task)})
    for mapping in ({task['unit_id']: evidence(task)}, {'UNIT-' + 'f' * 64: b'{}'}, {}):
        with pytest.raises(WorkManifestError), no_write_attempts():
            partition_work_manifest(completed, mapping)
    assert completed.as_dict()['progress'] == {'completed_units': 1, 'total_units': 5}
    assert original.as_dict()['progress']['completed_units'] == 0


def test_detached_values_and_frozen_objects_cannot_mutate_an_earlier_candidate():
    manifest = create(); before = manifest.raw
    value = manifest.as_dict(); value['normalized_arguments']['arguments']['injected'] = 'value'
    rows = manifest.entries('tasks'); rows[0]['range']['start'] = -100
    with pytest.raises(FrozenInstanceError):
        manifest.raw = b'{}'
    with pytest.raises(TypeError):
        manifest.objects['x'] = b'unsafe'
    assert manifest.raw == before and read(manifest.raw, manifest.objects).raw == before


@pytest.mark.parametrize('raw', [b'\x80\x04N.', b'import os\nos.system("echo unsafe")', b'{"a":1,"a":2}', b'{"a":NaN}'])
def test_non_json_executable_or_ambiguous_serialization_is_never_loaded(raw):
    with pytest.raises(WorkManifestError), no_write_attempts():
        read(raw, {})


def test_foreign_python_range_cannot_serialize_or_execute_custom_hooks():
    called = []
    class Foreign:
        def __reduce__(self):
            called.append('reduce')
            raise AssertionError('foreign deserialization')
        def __iter__(self):
            called.append('iterate')
            raise AssertionError('foreign iteration')
    with pytest.raises(WorkManifestError), no_write_attempts():
        create(plan=[{'key': 'one', 'phase': 'fixture', 'range': {'foreign': Foreign()}}])
    assert called == []
