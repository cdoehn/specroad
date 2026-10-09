"""Saved authoring identity, real stale targets and hostile completion records."""

from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
from pathlib import Path

import pytest

from specroad import _build
from specroad.changes import ChangePlan, PublicationCheckError, TargetModel
from specroad.cli.application import execute_request
from specroad.cli.contracts import CommandClass, CommandSpec, EffectScope, OptionSpec, PreflightProfile
from specroad.cli.registry import CommandRegistry
from specroad.cli.requests import CommandRequest
from specroad.diagnostics import Diagnostic
from specroad.model.canonical import canonical_json_bytes
from specroad.model.model_manifest import ProjectReadBinding
from specroad.security import ProjectBoundary
from specroad.validation import ModelDocument
from specroad.work.checkpoints import CheckpointStore
from specroad.work.manifest import (WorkManifestError, create_normative_work_manifest,
    read_work_manifest, partition_work_manifest)
from specroad.work.resume import WorkResumeError, prepare_read_only_work, resume_read_only_work
from specroad.work.resume_checks import NormativeResumeCheck, prepare_normative_resume
from specroad.work.root import WorkDirectory
from support.publication import prepared
from support.read_only import inventory, no_write_attempts
from support.targets import POLICY
from test_work_checkpoints_right import documents, point_record, put
from test_work_manifest import sealed
from test_work_resume import recorded, setup as readonly_setup


def registry():
    # A test-owned host contract. Any handler invocation would violate this
    # purely diagnostic operation; no placeholder enters the product registry.
    def forbidden(invocation):
        raise AssertionError('normative handler invoked by resume preflight')
    return CommandRegistry((CommandSpec('change.apply', ('change', 'apply'),
        CommandClass.NORMATIVE_WRITE, PreflightProfile.PROJECT_WRITE,
        EffectScope.NORMATIVE_TRANSACTION, forbidden, requires_project=True,
        options=tuple(OptionSpec(name, takes_value=True) for name in
            ('--actor-type', '--actor-id', '--request-id'))),))


def prepare_work(reg, model, plan, *, sources=None):
    value = plan.data
    request = CommandRequest('change.apply', options={
        '--actor-type': value['actor']['actor_type'], '--actor-id': value['actor']['actor_id'],
        '--request-id': value['request_id']})
    build = prepare_read_only_work(CommandRequest('version')).as_dict()['tool_build']
    return create_normative_work_manifest(reg, request, plan=plan, tool_build=build,
        source_bindings=sources or {'project_id': model.binding.project_id, 'scope': ['project'],
            'model_root_sha256': value['base']['model_root_sha256']},
        inputs=[{'root_id': 'project', 'path': path, 'raw': raw}
                for path, raw in sorted(model.source_files.items())],
        units=[{'key': 'prepare', 'phase': 'prepare', 'range': {'plan_sha256': plan.sha256}},
               {'key': 'publish', 'phase': 'publish', 'range': {'plan_sha256': plan.sha256}}])


def setup(tmp_path, *, spaced_plan=False):
    model, plan, _ = prepared(tmp_path / 'project')
    if spaced_plan:
        plan = ChangePlan(json.dumps(plan.data, indent=3).encode())
    reg = registry();initial = prepare_work(reg, model, plan)
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(model.binding.source_root),),
                             directory=tmp_path / 'work')
    store = CheckpointStore(location, initial);store.publish(initial)
    return model, plan, reg, initial, location, store


def check(store, reg, model, plan, **changes):
    arguments = {'registry': reg, 'model': model, 'policy': POLICY,
                 'actor': plan.data['actor'], 'request_id': plan.data['request_id']}
    arguments.update(changes)
    return prepare_normative_resume(store, **arguments)


@pytest.mark.parametrize('spaced_plan', [False, True])
def test_normative_resume_preserves_original_plan_and_authoring_without_write_authority(recorded, tmp_path, spaced_plan):
    model, plan, reg, initial, _, store = setup(tmp_path, spaced_plan=spaced_plan)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = check(store, reg, model, plan)
    assert inventory(tmp_path) == before
    assert result.plan.source_bytes == plan.source_bytes and result.plan.sha256 == plan.sha256
    assert result.manifest.raw == initial.raw
    value = result.as_dict()
    assert value['actor'] == plan.data['actor'] and value['request_id'] == plan.data['request_id']
    assert value['plan_binding']['change_plan_id'] == plan.data['change_plan_id']
    assert value['plan_binding']['source']['sha256'] == sha256(plan.source_bytes).hexdigest()
    assert value['write_authorized'] is False and value['final_locked_check_required'] is True
    assert value['normative_writes'] == 0 and value['checkpoint_changed'] is False
    assert result.preflight.request.plan.source_bytes == plan.source_bytes
    with pytest.raises(TypeError):
        bool(result)
    with pytest.raises(TypeError):
        NormativeResumeCheck()
    with pytest.raises(FrozenInstanceError):
        result.plan = None
    value['actor']['actor_id'] = 'foreign'
    assert result.as_dict()['actor'] == plan.data['actor']


def test_normative_successor_keeps_all_original_ids_plan_bytes_and_operation_binding(recorded, tmp_path):
    model, plan, reg, initial, _, store = setup(tmp_path)
    task = initial.entries('remaining')[0]
    following = partition_work_manifest(initial, {task['unit_id']: b'{"fixture_preparation":true}'})
    store.publish(following)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = check(store, registry(), model.snapshot(), plan)
    assert result.manifest.raw == following.raw and inventory(tmp_path) == before
    for name in ('work_id', 'actor', 'request_id', 'operations_sha256', 'plan_binding', 'normalized_arguments'):
        assert result.manifest.as_dict()[name] == initial.as_dict()[name]
    assert result.plan.source_bytes == plan.source_bytes


@pytest.mark.parametrize('actor', [
    {'actor_type': 'human', 'actor_id': 'another-human'},
    {'actor_type': 'ai', 'actor_id': 'planner'},
    {'actor_type': 'ci', 'actor_id': 'planner'}])
def test_current_actor_cannot_relabel_the_saved_normative_work(recorded, tmp_path, actor):
    model, plan, reg, _, _, store = setup(tmp_path);before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        check(store, reg, model, plan, actor=actor)
    assert caught.value.reason == 'resume_actor_changed' and caught.value.exit_code == 6
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('identity', [None, 'other-request', 'REQUEST-1'])
def test_current_request_never_replaces_the_original_id(recorded, tmp_path, identity):
    model, plan, reg, _, _, store = setup(tmp_path);before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        check(store, reg, model, plan, request_id=identity)
    assert caught.value.reason == 'resume_request_changed' and caught.value.exit_code == 6
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['bytes', 'missing', 'extra_json', 'configuration'])
def test_changed_actual_target_is_code_six_and_never_rebases_or_loses_work(recorded, tmp_path, change):
    model, plan, reg, initial, _, store = setup(tmp_path)
    project = Path(model.binding.source_root);path = project / model.documents[0].path
    if change == 'bytes':
        path.write_bytes(path.read_bytes() + b' ')
    elif change == 'missing':
        path.unlink()
    elif change == 'extra_json':
        extra = project / 'rules/unexpected.json';extra.parent.mkdir();extra.write_bytes(b'{}')
    else:
        path = project / 'specroad.json';path.write_bytes(path.read_bytes() + b' ')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((PublicationCheckError, WorkResumeError)) as caught:
        check(store, reg, model, plan)
    assert caught.value.exit_code == 6 and inventory(tmp_path) == before
    assert store.read().raw == initial.raw
    assert store.read().objects[initial.as_dict()['plan_binding']['source']['sha256']] == plan.source_bytes


def test_changed_reconstructed_model_is_a_conflict_before_any_target_publication(recorded, tmp_path):
    model, plan, reg, _, _, store = setup(tmp_path)
    first = model.documents[0];value = json.loads(first.content);value['statement'] = 'Different current target'
    raw = canonical_json_bytes(value);(Path(model.binding.source_root) / first.path).write_bytes(raw)
    current = TargetModel(model.configuration_bytes, model.binding,
        [ModelDocument(first.path, raw)], profile=model.profile, resource_files=model.resource_files,
        attachments=model.attachment_descriptors, language_packages=model.language_packages, **model.reservations)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        check(store, reg, current, plan)
    assert caught.value.as_dict() == {'reason': 'stale_resume_target', 'exit_code': 6}
    assert inventory(tmp_path) == before


def test_lost_current_parent_write_permission_is_checked_without_probe_writes(recorded, tmp_path):
    model, plan, reg, _, _, store = setup(tmp_path)
    parent = (Path(model.binding.source_root) / model.documents[0].path).parent
    original = parent.stat().st_mode & 0o777;parent.chmod(0o500)
    before = inventory(tmp_path)
    try:
        with no_write_attempts(), pytest.raises(PublicationCheckError) as caught:
            check(store, reg, model, plan)
        assert caught.value.exit_code == 7 and inventory(tmp_path) == before
    finally:
        parent.chmod(original)


def test_unprotected_current_target_cannot_be_promoted_by_a_resume_check(recorded, tmp_path):
    model, plan, reg, initial, location, _ = setup(tmp_path)
    other = tmp_path / 'other';other.mkdir()
    different = WorkDirectory(initial, protected_roots=(ProjectBoundary(other),), directory=location.path)
    store = CheckpointStore(different, initial);before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        check(store, reg, model, plan)
    assert caught.value.reason == 'unprotected_resume_target' and caught.value.exit_code == 7
    assert inventory(tmp_path) == before


def test_relocated_current_target_uses_a_fresh_binding_and_the_original_plan(recorded, tmp_path):
    model, plan, reg, initial, location, _ = setup(tmp_path)
    old = Path(model.binding.source_root);new = tmp_path / 'relocated-project';old.rename(new)
    info = new.stat()
    current = TargetModel(model.configuration_bytes,
        ProjectReadBinding(model.binding.project_id, str(new), (info.st_dev, info.st_ino)),
        model.documents, profile=model.profile, resource_files=model.resource_files,
        attachments=model.attachment_descriptors, language_packages=model.language_packages, **model.reservations)
    store = CheckpointStore(WorkDirectory(initial, protected_roots=(ProjectBoundary(new),),
                                         directory=location.path), initial)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = check(store, registry(), current, plan)
    assert result.plan.source_bytes == plan.source_bytes and result.manifest.raw == initial.raw
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('field', ['actor', 'request_id', 'operations_sha256', 'plan_binding', 'normalized_arguments'])
def test_rehashed_normative_metadata_cannot_override_original_plan_bytes(recorded, tmp_path, field):
    _, _, reg, initial, _, _ = setup(tmp_path)
    value = initial.as_dict()
    if field == 'actor':value[field]['actor_id'] = 'another'
    elif field == 'request_id':value[field] = 'another'
    elif field == 'operations_sha256':value[field] = '0' * 64
    elif field == 'plan_binding':value[field]['change_plan_id'] = 'CP-another'
    else:value[field]['options']['--actor-id'] = 'another'
    with no_write_attempts(), pytest.raises(WorkManifestError):
        read_work_manifest(sealed(value), initial.objects, registry=reg,
                           expected_tool_build=initial.as_dict()['tool_build'])


@pytest.mark.parametrize('change', ['missing', 'changed'])
def test_normative_plan_requires_the_exact_original_bytes(recorded, tmp_path, change):
    _, _, reg, initial, _, _ = setup(tmp_path)
    objects = dict(initial.objects)
    digest = initial.as_dict()['plan_binding']['source']['sha256']
    if change == 'missing':
        del objects[digest]
    else:
        objects[digest] += b' '
    with no_write_attempts(), pytest.raises(WorkManifestError):
        read_work_manifest(initial.raw, objects, registry=reg,
                           expected_tool_build=initial.as_dict()['tool_build'])


def test_normative_resume_requires_a_compatible_current_registered_contract(recorded, tmp_path):
    from specroad.cli.commands import builtin_registry
    model, plan, _, _, _, store = setup(tmp_path);before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        check(store, builtin_registry(), model, plan)
    assert caught.value.reason == 'incompatible_work_contract' and caught.value.exit_code == 6
    assert inventory(tmp_path) == before


def test_current_project_identity_must_match_the_saved_work(recorded, tmp_path):
    model, plan, _ = prepared(tmp_path / 'project');reg = registry()
    initial = prepare_work(reg, model, plan, sources={'project_id': 'another-project',
        'scope': ['project'], 'model_root_sha256': plan.data['base']['model_root_sha256']})
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(model.binding.source_root),),
                             directory=tmp_path / 'work')
    store = CheckpointStore(location, initial);store.publish(initial)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        check(store, reg, model, plan)
    assert caught.value.reason == 'resume_project_changed' and caught.value.exit_code == 6
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('field', ['algorithm_versions', 'schema_versions', 'actor', 'request_id'])
def test_rehashed_incompatible_saved_contract_is_a_resume_conflict(recorded, tmp_path, field):
    initial, _, location, store = readonly_setup(tmp_path)
    value = initial.as_dict()
    value[field] = {'unknown': 'future'} if field.endswith('versions') else 'foreign'
    raw = sealed(value);semantic = json.loads(raw)['checkpoint_sha256']
    pointer, record = documents(location.path)
    record['manifest'] = put(location.path, 'objects', raw)
    record['checkpoint_sha256'] = semantic;pointer['checkpoint_sha256'] = semantic
    point_record(location.path, pointer, record)
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        resume_read_only_work(store)
    assert caught.value.exit_code == 6 and caught.value.reason == 'incompatible_work_contract'
    assert inventory(location.path) == before


@pytest.mark.parametrize('change', ['format', 'unit', 'request', 'build', 'exit_bool',
    'undeclared_exit', 'command', 'incomplete', 'external', 'diagnostic', 'result_schema', 'extra_field'])
def test_self_consistent_saved_completion_must_obey_request_and_handler_contract(recorded, tmp_path, change):
    initial, _, location, store = readonly_setup(tmp_path)
    request = CommandRequest('version');unit = initial.entries('tasks')[0]['unit_id']
    record = {'format_version': 'read-only-handler-evidence-v1', 'unit_id': unit,
        'request': request.as_dict(), 'tool_build': initial.as_dict()['tool_build'],
        'exit_code': 0, 'outcome': execute_request(request).result.as_dict()}
    if change == 'format':record['format_version'] = 'future'
    elif change == 'unit':record['unit_id'] = 'another'
    elif change == 'request':record['request']['command_id'] = 'help'
    elif change == 'build':record['tool_build']['build_sha256'] = 'f' * 64
    elif change == 'exit_bool':record['exit_code'] = False
    elif change == 'undeclared_exit':
        record['exit_code'] = 2;record['outcome']['status'] = 'failed'
        record['outcome']['summary']['failure_kind'] = 'usage'
    elif change == 'command':record['outcome']['command'] = 'help'
    elif change == 'incomplete':record['outcome']['summary']['complete'] = False
    elif change == 'external':
        record['outcome']['result_ref'] = {'path': '/untrusted/report', 'media_type': 'application/json',
            'size': 1, 'sha256': '0' * 64, 'result_schema': 'version-info-v1'}
    elif change == 'diagnostic':
        record['outcome']['diagnostics'] = [Diagnostic('FOREIGN', 'info', 'foreign', 'fixture').as_dict()]
    elif change == 'result_schema':record['outcome']['result']['python_support'] = None
    else:record['unexpected'] = True
    following = partition_work_manifest(initial, {unit: canonical_json_bytes(record)})
    store.publish(following);before = inventory(location.path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        resume_read_only_work(store)
    assert caught.value.exit_code == 6 and inventory(location.path) == before


@pytest.mark.parametrize('saved', [False, True])
def test_runtime_build_change_during_current_context_check_prevents_confirmation(recorded, tmp_path, monkeypatch, saved):
    initial, _, location, store = readonly_setup(tmp_path)
    if saved:resume_read_only_work(store)
    original = store.read().raw
    from specroad.cli.invocation_context import InvocationContextBuilder
    native = InvocationContextBuilder.prepare
    def changed(self, *args, **kwargs):
        result = native(self, *args, **kwargs)
        monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
            'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': 'c' * 64})
        return result
    before = inventory(location.path)
    monkeypatch.setattr(InvocationContextBuilder, 'prepare', changed)
    with pytest.raises(WorkResumeError) as caught:
        resume_read_only_work(store)
    assert caught.value.exit_code == 6
    assert store.read().raw == original and inventory(location.path) == before
