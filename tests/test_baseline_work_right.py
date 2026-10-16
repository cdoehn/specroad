"""Real Baseline Work interruption, unchanged archives and receipt precedence."""
from base64 import b64decode
from contextlib import nullcontext
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from specroad.archive import SnapshotObject, baseline_integrity_gate, verify_baseline_snapshot
from specroad.archive.work import (BaselineSnapshotTask, advance_baseline_work,
    publish_baseline_work)
from specroad.changes import TargetModel, ChangePlan, PublicationAuthority, PublicationCheckError
from specroad.changes.baselines import prepare_baseline_operation
from specroad.changes._target_materialization import materialize_target
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.security import ProjectBoundary
from specroad.validation import ModelDocument, ModelGate
from specroad.work.checkpoints import CheckpointStorageError
from specroad.work.resume import WorkResumeError
from specroad.work._normative_binding import read_plan
from support.read_only import inventory, no_write_attempts
from support.relations import aid
from support.records import ref
from test_baseline_creation import project, preview, apply, ACTOR, ALLOW
from test_baseline_work import options, finish, checkpoint
from test_configured_baseline_right import variant_project
from test_work_resume import recorded
from test_work_resume_right import registry


def history_gates(model, fields):
    # The older records come from real native publication below. This fixture's
    # host accepts only those exact records and the exact new native operation;
    # the separate integrity provider verifies the actual archived bytes.
    operation = prepare_baseline_operation(model, **{key: fields[key] for key in
        ('baseline_id', 'name', 'actor', 'planned_at')}, configuration_id=fields.get('configuration_id'))
    expected = {a['id']: a for a in model.artifacts if a['artifact_type'] == 'baseline'}
    expected[operation['record']['id']] = operation['record']
    bound = canonical_json_sha256(expected)
    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})
    def check(context):
        actual = {key: context.artifact(key) for key in context.subjects}
        findings = [] if canonical_json_sha256(actual) == bound else [
            {'reason': 'native_baseline_history_changed', 'severity': 'error'}]
        return context.result(findings)
    objects = tuple(SnapshotObject(b64decode(item['bytes_base64'])) for item in operation['objects'])
    return (ModelGate('lifecycle', 'native-baseline-history', dependencies, check, bound),
            baseline_integrity_gate(objects))


def work_setup(folder, *, configured=False, with_history=False):
    root = folder / 'project'; model = variant_project(root) if configured else project(root)
    fields = options(**({'configuration_id': aid('configuration', 2)} if configured else {}))
    if with_history:
        old = ChangePlan(canonical_json_bytes(preview(model)['plan']))
        assert apply(old, model)['completion']['commit_completed']
        model = published_model(model, old)
        fields.update(baseline_id=ref('BASE', '1'), request_id='baseline-2', change_plan_id='CP-baseline-2')
        fields['gates'] = history_gates(model, fields)
    with BaselineSnapshotTask(model) as task:
        finish(task); initial = task.prepare_work(registry(), **fields)
    plan = read_plan(initial.as_dict(), initial.objects)
    store = checkpoint(root, initial, folder / 'work'); store.publish(initial)
    arguments = dict(registry=registry(), model=model, actor=ACTOR, request_id=fields['request_id'],
        gates=fields.get('gates', ()))
    return root, model, plan, store, arguments


def ready(store, arguments):
    advance_baseline_work(store, **arguments)
    return advance_baseline_work(store, **arguments)


def publish(store, arguments, **changes):
    fields = dict(transaction_id='txn-baseline-work', authority=ALLOW); fields.update(changes)
    return publish_baseline_work(store, **arguments, **fields).as_dict()


def published_model(model, plan):
    operation = plan.data['operations'][0]; record = operation['record']
    documents = [ModelDocument(item['path'], b64decode(item['bytes_base64']))
                 for item in operation['objects']]
    documents.append(ModelDocument(artifact_path('baseline', record['id'], 'SR'), canonical_json_bytes(record)))
    return materialize_target(model, tuple(documents))


def retained_hashes(root, model):
    paths = set()
    for artifact in model.artifacts:
        if artifact['artifact_type'] == 'baseline':
            paths.add(artifact_path('baseline', artifact['id'], 'SR'))
            paths.update(row['object_path'] for row in artifact['manifest'])
    assert paths
    return {path: sha256((root / path).read_bytes()).hexdigest() for path in sorted(paths)}


def remove_configurations(root, current):
    retained = []
    for document in current.documents:
        if document.path.startswith('spec/configurations/'):
            (root / document.path).unlink()
        else: retained.append(document)
    assert len(retained) < len(current.documents)
    return TargetModel(current.configuration_bytes, current.binding, retained,
        profile=current.profile, resource_files=current.resource_files)


def test_confirmed_configured_receipt_replays_without_resolving_a_removed_current_selection(recorded, tmp_path):
    root, model, plan, store, arguments = work_setup(tmp_path, configured=True)
    ready(store, arguments); first = publish(store, arguments)
    assert first['publication_performed']
    current = remove_configurations(root, published_model(model, plan))
    before = inventory(tmp_path)
    with no_write_attempts(): repeated = publish(store, {**arguments, 'model': current})
    assert not repeated['publication_performed']
    assert repeated['result_object'] == first['result_object']
    assert inventory(tmp_path) == before


def test_new_publication_still_requires_its_real_current_configuration_gate(recorded, tmp_path):
    root, model, plan, store, arguments = work_setup(tmp_path, configured=True)
    ready(store, arguments); current = remove_configurations(root, model); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        publish(store, {**arguments, 'model': current})
    assert error.value.reason == 'configuration_missing' and inventory(tmp_path) == before
    assert not (root / artifact_path('baseline', plan.data['operations'][0]['record']['id'], 'SR')).exists()


def test_new_work_publication_preserves_real_older_baseline_and_shared_objects(recorded, tmp_path):
    root, model, plan, store, arguments = work_setup(tmp_path, with_history=True)
    before = retained_hashes(root, model); ready(store, arguments)
    result = publish(store, arguments)
    assert result['publication_performed'] and result['transaction']['commit_completed']
    assert retained_hashes(root, model) == before
    current = published_model(model, plan)
    for artifact in current.artifacts:
        if artifact['artifact_type'] == 'baseline':
            report = verify_baseline_snapshot(ProjectBoundary(root), canonical_json_bytes(artifact))
            assert report['snapshot_integrity_verified']


def test_cancelled_partial_capture_preserves_all_existing_baseline_hashes(recorded, tmp_path):
    root, model, _, _, _ = work_setup(tmp_path, with_history=True)
    before = inventory(tmp_path); retained = retained_hashes(root, model)
    with no_write_attempts(), BaselineSnapshotTask(model, block_bytes=1) as task:
        task.advance(5); task.close()
        with pytest.raises(ModelError) as error: task.prepare_working_plan(**options())
    assert error.value.reason == 'baseline_snapshot_incomplete'
    assert inventory(tmp_path) == before and retained_hashes(root, model) == retained


@pytest.mark.parametrize('phases', [0, 1, 2])
def test_stale_work_basis_never_rebases_or_changes_an_older_baseline(recorded, tmp_path, phases):
    root, model, _, store, arguments = work_setup(tmp_path, with_history=True)
    for _ in range(phases): advance_baseline_work(store, **arguments)
    point = store.read().raw; retained = retained_hashes(root, model)
    source = next(d for d in model.documents if json.loads(d.content)['artifact_type'] == 'goal')
    value = json.loads(source.content); value['statement'] = 'Later unrelated content.'
    changed = ModelDocument(source.path, canonical_json_bytes(value))
    (root / source.path).write_bytes(changed.content)
    current = materialize_target(model, (changed,)); before = inventory(tmp_path)
    # Preparation acquires and releases the native Work lease before assessing
    # the current model; it must not advance any checkpoint or project bytes.
    with (no_write_attempts() if phases == 2 else nullcontext()), pytest.raises(WorkResumeError) as error:
        if phases == 2: publish(store, {**arguments, 'model': current})
        else: advance_baseline_work(store, **{**arguments, 'model': current})
    assert error.value.reason == 'stale_resume_target' and error.value.exit_code == 6
    assert store.read().raw == point and inventory(tmp_path) == before
    assert retained_hashes(root, model) == retained


@pytest.mark.parametrize('phases', [0, 2])
@pytest.mark.parametrize('route', ['advance', 'publish'])
def test_missing_work_object_never_falls_back_to_live_inputs_or_mutates_history(recorded, tmp_path, phases, route):
    root, model, _, store, arguments = work_setup(tmp_path, with_history=True)
    for _ in range(phases): advance_baseline_work(store, **arguments)
    row = next(row for row in store._initial.entries('inputs') if row['path'].startswith('spec/'))
    assert sha256((root / row['path']).read_bytes()).hexdigest() == row['sha256']
    missing = store._location.path / 'objects' / row['sha256']; missing.unlink()
    retained = retained_hashes(root, model); before = inventory(tmp_path); calls = []
    with no_write_attempts(), pytest.raises((CheckpointStorageError, FileNotFoundError)):
        if route == 'advance': advance_baseline_work(store, **arguments)
        else: publish(store, arguments, authority=PublicationAuthority('host', '1', lambda request: calls.append(request) or True))
    assert not missing.exists() and calls == [] and inventory(tmp_path) == before
    assert retained_hashes(root, model) == retained


def test_denied_native_authority_retains_existing_baseline_and_work_checkpoint(recorded, tmp_path):
    root, model, _, store, arguments = work_setup(tmp_path, with_history=True)
    point = ready(store, arguments).raw; before = inventory(tmp_path); retained = retained_hashes(root, model)
    with pytest.raises(PublicationCheckError) as error:
        publish(store, arguments, authority=PublicationAuthority('denied', '1', lambda request: False))
    assert error.value.exit_code == 7 and store.read().raw == point
    assert retained_hashes(root, model) == retained and inventory(tmp_path) == before


def restore_cut(folder, packet):
    from specroad.model.model_manifest import ProjectReadBinding
    from specroad.model.language_registry import LanguageRegistry
    from specroad.profiles import ProfileResource, compose_profiles
    from specroad.work.checkpoints import CheckpointStore
    from specroad.work.manifest import read_work_manifest
    from specroad.work.resume import _runtime_build
    from specroad.work.root import WorkDirectory
    root = folder / 'project'; info = root.stat(); raw = bytes.fromhex(packet['configuration'])
    configuration = json.loads(raw)
    resources = {p: bytes.fromhex(b) for p, b in packet['resources'].items()}
    binding = configuration['language_registry']
    languages = LanguageRegistry(resources[binding['path']], expected_sha256=binding['sha256'],
                                 expected_version=binding['registry_version'])
    profile = ProfileResource(resources['profiles/core.json'])
    # Reconstruct only the independently emitted pre-publication fixture data.
    # This does not grant regular project-read permission during native Recovery.
    model = TargetModel(raw, ProjectReadBinding(configuration['project_id'], str(root),
        (info.st_dev, info.st_ino)),
        [ModelDocument(p, bytes.fromhex(b)) for p, b in packet['documents'].items()],
        profile=compose_profiles([profile], core_key=profile.key, language_registry=languages),
        resource_files=[ModelDocument(p, b) for p, b in resources.items()])
    reg = registry()
    initial = read_work_manifest(bytes.fromhex(packet['initial']),
        {p: bytes.fromhex(b) for p, b in packet['initial_objects'].items()},
        registry=reg, expected_tool_build=_runtime_build())
    store = CheckpointStore(WorkDirectory(initial, protected_roots=(ProjectBoundary(root),),
                                         directory=folder / 'work'), initial)
    plan = ChangePlan(bytes.fromhex(packet['plan']))
    record = plan.data['operations'][0]['record']
    gates = history_gates(model, dict(baseline_id=record['id'], name=record['title'],
        actor=plan.data['actor'], planned_at=plan.data['planned_at']))
    return model, plan, store, dict(registry=reg, model=model, actor=ACTOR,
        request_id=plan.data['request_id'], gates=gates)


@pytest.mark.parametrize('cut', ['prepared', 'first_object', 'baseline_record', 'committed', 'cleanup'])
def test_real_process_loss_preserves_history_and_never_promotes_partial_completion(recorded, tmp_path, cut):
    from specroad.changes import transaction_preflight, read_transaction_completion
    from specroad.cli.contracts import CommandClass
    from specroad.storage.project import ProjectSource
    from support.baseline_work_process import child
    packet, stopped = child(tmp_path, cut)
    assert packet['pid'] == stopped['pid'] != os.getpid() and stopped['cut'] == cut
    root = tmp_path / 'project'; model, plan, store, arguments = restore_cut(tmp_path, packet)
    point = store.read()
    assert point.raw == bytes.fromhex(packet['checkpoint'])
    assert point.as_dict()['checkpoint_generation'] == 2 and point.as_dict()['state'] == 'running'
    assert retained_hashes(root, model) == packet['retained']
    gate = transaction_preflight(root, command_class=CommandClass.READ_ONLY).data
    assert (root / '.specroad/locks/project.json').is_file()
    assert gate['exit_code'] == 5 and gate['recovery_required']
    record = plan.data['operations'][0]['record']
    path = root / artifact_path('baseline', record['id'], 'SR')
    assert path.exists() == (cut in ('baseline_record', 'committed', 'cleanup'))
    if path.exists():
        assert path.read_bytes() == canonical_json_bytes(record)
        assert verify_baseline_snapshot(ProjectBoundary(root), path.read_bytes())['snapshot_integrity_verified']
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as error:
        advance_baseline_work(store, **arguments)
    assert error.value.as_dict() == {'reason': 'normative_transaction_requires_recovery', 'exit_code': 5}
    if cut in ('committed', 'cleanup'):
        with no_write_attempts(): replay = publish(store, arguments)
        assert not replay['publication_performed']
        assert replay['result_object']['transaction_id'] == 'txn-baseline-work'
        assert replay['transaction']['cleanup_required'] == (cut == 'committed')
    else:
        with no_write_attempts(), pytest.raises(WorkResumeError) as error:
            publish(store, arguments)
        assert error.value.exit_code == 5
        with no_write_attempts(), pytest.raises(ModelError):
            read_transaction_completion(ProjectSource(root), 'txn-baseline-work')
    assert inventory(tmp_path) == before and store.read().raw == point.raw
    assert retained_hashes(root, model) == packet['retained']
