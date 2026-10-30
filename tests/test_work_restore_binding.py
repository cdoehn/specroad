"""Passive native Restore inputs survive real checkpoints without write authority."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.cli._restore_options import RESTORE_OPTIONS
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import (CommandClass, CommandSpec, CommandUsageError,
    EffectScope, OptionSpec, PreflightProfile)
from specroad.cli.registry import CommandRegistry
from specroad.cli.requests import CommandRequest
from specroad.model.canonical import canonical_json_bytes
from specroad.recovery import RestoreError
from specroad.security import ProjectBoundary
from specroad.work.checkpoints import CheckpointStore
from specroad.work.manifest import (partition_work_manifest,
    read_work_manifest, read_work_successor, _tree)
from specroad.work.restore import create_restore_work_manifest, read_restore_work_manifest
from specroad.work.root import WorkDirectory
from support.model import put
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for
from test_restore_execution import selected
from test_restore_invocation_options import no_io_attempts, PLAN
from test_work_manifest import BUILD, sealed


def forbidden_handler(invocation):
    raise AssertionError('Passive work data invoked a recovery handler')


def registry(**overrides):
    # Synthetic host contract, not production CLI registration or an authorizer.
    arguments = dict(command_id='recover.restore', words=('recover', 'restore'),
        command_class=CommandClass.RECOVERY_WRITE, preflight_profile=PreflightProfile.RECOVERY,
        effect_scope=EffectScope.RECOVERY_TRANSACTION, handler=forbidden_handler,
        requires_project=True, options=RESTORE_OPTIONS)
    arguments.update(overrides)
    return CommandRegistry((CommandSpec(**arguments),))


def setup(tmp_path, kind='project_bundle', *, journal=False):
    options, files, _ = restore_case(tmp_path, kind)
    broken = next(path for path in files if path.startswith('spec/goals/'))
    put(options['project_root'], broken, b'\xff{broken')
    if journal:
        put(options['project_root'], '.specroad/transactions/old/journal.json', b'{broken')
    plan = plan_for(options)
    request = CommandRequest('recover.restore', options={
        '--project': str(options['project_root']), '--plan-root': str(tmp_path / 'external'),
        '--plan': 'plan.json', '--expected-target-root': plan.data['expected_target_root'],
        '--actor-type': 'human', '--actor-id': 'synthetic-original-operator'})
    return options, plan, request


def create(plan, request, *, selection=None):
    return create_restore_work_manifest(registry(), request, plan=plan, tool_build=BUILD,
        affected_journals=selection,
        units=[{'key': 'check_original', 'phase': 'prepare', 'range': {'input': 'plan'}},
               {'key': 'check_selection', 'phase': 'prepare', 'range': {'input': 'selection'}}])


def read(raw, objects):
    return read_restore_work_manifest(raw, objects, registry=registry(), expected_tool_build=BUILD)


def with_options(request, **options):
    return CommandRequest('recover.restore', options={**request.options, **options})


@pytest.mark.parametrize('kind', ['project_bundle', 'baseline'])
@pytest.mark.parametrize('journal', [False, True])
def test_original_plan_and_selection_are_complete_inputs_without_handler_or_io(tmp_path, kind, journal):
    options, plan, request = setup(tmp_path, kind, journal=journal)
    selection = None
    if journal:
        request = with_options(request, **{'--selection-root': '/unopened', '--affected-journals': 'chosen.json'})
        selection = selected(plan, ['.specroad/transactions/old'])
    before = inventory(tmp_path)
    with no_io_attempts():
        initial = create(plan, request, selection=selection)
        restored = read(initial.raw, initial.objects)
    value = restored.as_dict()
    assert restored.raw == initial.raw and inventory(tmp_path) == before
    assert value['command_id'] == 'recover.restore' and value['command_class'] == 'recovery_write'
    assert value['source_bindings'] == {'project_id': plan.data['project_id'],
                                      'scope': ['project'], 'model_root_sha256': None}
    assert value['actor'] == {'actor_type': 'human', 'actor_id': 'synthetic-original-operator'}
    assert value['request_id'] is None and value['operations_sha256'] is None
    assert value['normalized_arguments'] == {'arguments': {}, 'options': dict(request.options)}
    assert value['state'] == 'running' and value['result_parts'] == []
    assert value['plan_binding']['restore_plan_sha256'] == plan.data['restore_plan_sha256']
    assert plan.sha256 != plan.data['restore_plan_sha256']
    expected_selection = selection if selection is not None else selected(plan, [])
    for field, raw in [('plan_source', plan.source_bytes), ('journal_selection', expected_selection)]:
        reference = value['plan_binding'][field]
        assert reference == {'sha256': sha256(raw).hexdigest(), 'size': len(raw)}
        assert restored.objects[reference['sha256']] == raw
        assert any(row['sha256'] == reference['sha256'] and row['size'] == len(raw)
                   for row in restored.entries('inputs'))
    assert not (options['project_root'] / '.specroad/recovery').exists()
    with pytest.raises(FrozenInstanceError):
        restored.raw = b'{}'
    with pytest.raises(TypeError):
        restored.objects[plan.sha256] = b'{}'
    value['actor']['actor_id'] = 'replacement'
    assert restored.as_dict()['actor']['actor_id'] == 'synthetic-original-operator'


@pytest.mark.parametrize('actor', ['human', 'tool', 'ai', 'ci'])
@pytest.mark.parametrize('identity', [None, 'explicit-original-request'])
def test_original_actor_and_optional_request_keep_native_rules(tmp_path, actor, identity):
    _, plan, request = setup(tmp_path)
    request = with_options(request, **{'--actor-type': actor},
        **({} if identity is None else {'--request-id': identity}))
    with no_io_attempts():
        if actor in ('ai', 'ci') and identity is None:
            with pytest.raises(RestoreError) as error:
                create(plan, request)
            assert error.value.exit_code == 2
        else:
            initial = create(plan, request)
            assert read(initial.raw, initial.objects).as_dict()['request_id'] == identity
            assert initial.as_dict()['actor']['actor_type'] == actor


def test_real_checkpoint_chain_retains_original_binding_without_external_plan_or_source(tmp_path):
    options, plan, request = setup(tmp_path)
    initial = create(plan, request)
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(options['project_root']),),
                             directory=tmp_path / 'work')
    store = CheckpointStore(location, initial)
    store.publish(initial)
    following = partition_work_manifest(initial,
        {initial.entries('tasks')[0]['unit_id']: b'{"synthetic_preparation":true}'})
    store.publish(following)
    (options['source_root'] / options['source_path']).unlink()
    before = inventory(tmp_path)
    fresh_initial = read(initial.raw, dict(initial.objects))
    reopened = CheckpointStore(WorkDirectory(fresh_initial,
        protected_roots=(ProjectBoundary(options['project_root']),), directory=tmp_path / 'work'), fresh_initial)
    with no_write_attempts():
        loaded = reopened.read()
    assert loaded.raw == following.raw and inventory(tmp_path) == before
    assert loaded.objects[plan.sha256] == plan.source_bytes
    assert loaded.as_dict()['plan_binding'] == initial.as_dict()['plan_binding']
    assert loaded.as_dict()['normalized_arguments'] == initial.as_dict()['normalized_arguments']
    assert loaded.as_dict()['checkpoint_generation'] == 1
    assert loaded.as_dict()['state'] == 'running' and len(loaded.entries('remaining')) == 1


def test_transport_relocation_preserves_units_but_cannot_rewrite_a_trusted_successor(tmp_path):
    _, plan, request = setup(tmp_path)
    initial = create(plan, request)
    moved = create(plan, with_options(request, **{'--plan-root': '/different/transport', '--plan': 'moved.json'}))
    assert initial.entries('tasks') == moved.entries('tasks')
    assert initial.as_dict()['input_manifest_sha256'] == moved.as_dict()['input_manifest_sha256']
    following = partition_work_manifest(moved, {moved.entries('tasks')[0]['unit_id']: b'{}'})
    value = following.as_dict(); value['work_id'] = initial.as_dict()['work_id']
    with no_io_attempts(), pytest.raises(RestoreError) as error:
        read_work_successor(sealed(value), following.objects, previous=initial,
                            registry=registry(), expected_tool_build=BUILD)
    assert error.value.exit_code == 6


@pytest.mark.parametrize('replacement', [{'--actor-id': 'different-operator'}, {'--request-id': 'different-request'}])
def test_consistently_rehashed_other_request_cannot_replace_a_trusted_work(tmp_path, replacement):
    _, plan, request = setup(tmp_path)
    initial = create(plan, request)
    other = create(plan, with_options(request, **replacement))
    assert initial.entries('inputs') == other.entries('inputs')
    assert initial.entries('tasks') != other.entries('tasks')
    following = partition_work_manifest(other, {other.entries('tasks')[0]['unit_id']: b'{}'})
    value = following.as_dict(); value['work_id'] = initial.as_dict()['work_id']
    with no_io_attempts():
        assert read(sealed(value), following.objects).as_dict()['actor'] == other.as_dict()['actor']
        with pytest.raises(RestoreError) as error:
            read_work_successor(sealed(value), following.objects, previous=initial,
                                registry=registry(), expected_tool_build=BUILD)
        assert error.value.exit_code == 6


@pytest.mark.parametrize('field', ['actor', 'request_id', 'source_project', 'source_scope', 'model_root',
                                  'inner_hash', 'operations', 'target', 'project'])
def test_resealed_inconsistent_original_binding_is_a_conflict(tmp_path, field):
    _, plan, request = setup(tmp_path)
    initial = create(plan, request); value = initial.as_dict()
    if field == 'actor': value['actor']['actor_id'] = 'replacement'
    elif field == 'request_id': value['request_id'] = 'invented'
    elif field == 'source_project': value['source_bindings']['project_id'] = 'foreign-project'
    elif field == 'source_scope': value['source_bindings']['scope'] = ['specification']
    elif field == 'model_root': value['source_bindings']['model_root_sha256'] = 'a' * 64
    elif field == 'inner_hash': value['plan_binding']['restore_plan_sha256'] = plan.sha256
    elif field == 'operations': value['operations_sha256'] = plan.sha256
    else: value['normalized_arguments']['options']['--' + ('expected-target-root' if field == 'target' else field)] = (
        'a' * 64 if field == 'target' else '/other/project')
    with no_io_attempts(), pytest.raises(RestoreError) as error:
        read(sealed(value), initial.objects)
    assert error.value.exit_code == 6 and not error.value.mutation_possible


@pytest.mark.parametrize('field', ['plan_source', 'journal_selection'])
@pytest.mark.parametrize('damage', ['missing', 'bytes', 'size', 'bool_size', 'not_input'])
def test_every_referenced_byte_must_be_present_and_bound_as_an_input(tmp_path, field, damage):
    _, plan, request = setup(tmp_path)
    initial = create(plan, request); value = initial.as_dict(); objects = dict(initial.objects)
    reference = value['plan_binding'][field]
    if damage == 'missing': del objects[reference['sha256']]
    elif damage == 'bytes': objects[reference['sha256']] += b' '
    elif damage == 'size': reference['size'] += 1
    elif damage == 'bool_size': reference['size'] = True
    else:
        # Even an intact object is insufficient when removed from the input tree.
        rows = [row for row in initial.entries('inputs') if row['sha256'] != reference['sha256']]
        tree = _tree('inputs', rows, objects)
        value['manifests']['inputs'] = tree; value['input_manifest_sha256'] = tree['sha256']
    with no_io_attempts(), pytest.raises(RestoreError) as error:
        read(sealed(value), objects)
    assert error.value.exit_code == 3 and not error.value.mutation_possible


@pytest.mark.parametrize('damage', ['unknown_binding', 'foreign_binding', 'extra_field', 'missing_actor',
                                   'missing_request', 'planning', 'saved_authority'])
def test_invalid_stored_contract_is_not_a_new_call_or_authority(tmp_path, damage):
    _, plan, request = setup(tmp_path)
    initial = create(plan, request); value = initial.as_dict()
    if damage == 'unknown_binding': value['plan_binding']['format_version'] = 'future-binding'
    elif damage == 'foreign_binding': value['plan_binding']['format_version'] = 'work-change-plan-v1'
    elif damage == 'extra_field': value['plan_binding']['authority_id'] = 'saved-allow'
    elif damage == 'missing_actor': del value['normalized_arguments']['options']['--actor-id']
    elif damage == 'missing_request': value['normalized_arguments']['options']['--actor-type'] = 'ai'
    elif damage == 'planning': value['normalized_arguments']['options'] = dict(PLAN)
    else: value['authority'] = {'approved': True}
    with no_io_attempts(), pytest.raises(RestoreError) as error:
        read(sealed(value), initial.objects)
    assert error.value.exit_code == 3
    if damage == 'unknown_binding':
        # A malformed hash is invalid saved data (3); a different valid hash
        # is the separately tested original-binding conflict (6).
        for invalid in (None, True, 1, '', 'A' * 64, 'a' * 63):
            value = initial.as_dict()
            value['plan_binding']['restore_plan_sha256'] = invalid
            with no_io_attempts(), pytest.raises(RestoreError) as error:
                read(sealed(value), initial.objects)
            assert error.value.exit_code == 3


def test_nonempty_selection_is_never_inferred_from_original_journals(tmp_path):
    _, plan, request = setup(tmp_path, journal=True)
    with no_io_attempts(), pytest.raises(RestoreError) as error:
        create(plan, request)
    assert error.value.exit_code == 5 and error.value.recovery_required
    request = with_options(request, **{'--selection-root': '/unopened', '--affected-journals': 'chosen.json'})
    with no_io_attempts(), pytest.raises(RestoreError) as error:
        create(plan, request)
    assert error.value.exit_code == 2
    with no_io_attempts(), pytest.raises(RestoreError) as error:
        create(plan, request, selection=selected(plan, []))
    assert error.value.exit_code == 5 and error.value.recovery_required


@pytest.mark.parametrize('damage,code', [('noncanonical', 3), ('wrong_plan', 6), ('wrong_inventory', 6), ('unsafe', 7)])
def test_native_selection_checks_apply_to_work_inputs(tmp_path, damage, code):
    _, plan, request = setup(tmp_path, journal=True)
    request = with_options(request, **{'--selection-root': '/unopened', '--affected-journals': 'chosen.json'})
    value = json.loads(selected(plan, ['.specroad/transactions/old']))
    if damage == 'wrong_plan': value['restore_plan_sha256'] = 'a' * 64
    elif damage == 'wrong_inventory': value['entries'][0]['sha256'] = 'a' * 64
    elif damage == 'unsafe': value['entries'][0]['path'] = '../outside'
    raw = json.dumps(value, indent=2).encode() if damage == 'noncanonical' else canonical_json_bytes(value)
    with no_io_attempts(), pytest.raises(RestoreError) as error:
        create(plan, request, selection=raw)
    assert error.value.exit_code == code and not error.value.mutation_possible


@pytest.mark.parametrize('override', [
    {'command_id': 'recover.other'}, {'words': ('recover', 'other')},
    {'command_class': CommandClass.READ_ONLY, 'effect_scope': EffectScope.NONE},
    {'preflight_profile': PreflightProfile.PROJECT_WRITE},
    {'options': RESTORE_OPTIONS + (OptionSpec('--as-proposal'),)}])
def test_restore_actor_options_do_not_spread_to_other_command_contracts(override):
    with no_io_attempts(), pytest.raises(CommandUsageError):
        registry(**override)


def test_fixture_host_registration_grants_no_public_command_or_recovery_authority(tmp_path):
    _, plan, request = setup(tmp_path)
    with no_io_attempts():
        initial = create(plan, request)
        # The public R integration now supplies its own native handler.
        # Reading fixture-created inert data cannot install its forbidden
        # fixture handler or turn retained actor/plan fields into authority.
        public = builtin_registry()
        assert public.resolve('recover.restore').handler is not forbidden_handler
        assert read_restore_work_manifest(initial.raw, initial.objects,
            registry=public, expected_tool_build=BUILD).raw == initial.raw
        from specroad.cli._restore_adapter import run_restore
        with pytest.raises(RestoreError) as missing:
            run_restore(request)
        assert missing.value.reason == 'restore_authority_required'
        assert missing.value.exit_code == 2 and not missing.value.mutation_possible
        assert read_work_manifest(initial.raw, initial.objects, registry=registry(),
                                  expected_tool_build=BUILD).raw == initial.raw
