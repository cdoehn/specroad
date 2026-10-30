"""Same native historical Proposal checks through public and Work entrypoints."""
from dataclasses import replace
import shutil

import pytest

from specroad.bundles import prepare_project_bundle
from specroad.cli.application import execute, execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.requests import CommandRequest
from specroad.cli.results import thaw
from specroad.recovery import RestoreServices, prepare_restore_plan, RestorePlan
from support.model import put
from support.read_only import inventory, no_write_attempts
from test_proposal_history import history, verifier
from test_proposal_completion import completed
from test_restore_invocation import planning, execution, authority
from test_restore_invocation_options import invocation
from test_work_resume import recorded


def project(tmp_path, status):
    inputs, model = (completed(tmp_path) if status == 'applied'
                     else history(tmp_path, status=status, decision='rejected' if status == 'rejected' else 'approved'))
    origin, current = tmp_path / 'origin', tmp_path / 'current'
    current.mkdir()
    for path, raw in model.source_files.items():
        put(origin, path, raw)
        put(current, path, raw)
    for proof in inputs.publications:
        for item in proof.receipts:
            put(origin, item.path, item.content)
            put(current, item.path, item.content)
    put(origin, 'project.zip', prepare_project_bundle(origin).source_bytes)
    calls = []
    def provide(model, original):
        calls.append(original.sha256)
        return inputs
    return ({'project_root': current, 'source_root': origin,
             'source_path': 'project.zip', 'source_kind': 'project_bundle'},
            RestoreServices(proposal_inputs=provide), inputs, calls)


@pytest.mark.parametrize('status', ['approved', 'rejected', 'stale', 'applied'])
@pytest.mark.parametrize('representation', ['argv', 'mapping'])
def test_public_restore_uses_original_proposals_and_current_typed_inputs(tmp_path, status, representation):
    options, native, inputs, calls = project(tmp_path, status)
    expected = prepare_restore_plan(**options, services=native)
    out = tmp_path / 'output'; out.mkdir()
    invoke = execute if representation == 'argv' else execute_request
    builder = InvocationContextBuilder(recovery_authority=authority(), restore_services=native)
    planned = invoke(invocation(planning(options, out), representation), context_builder=builder).result
    assert planned.exit_code == 0, planned
    assert thaw(planned.result['restore_plan']) == expected.data
    original_count = len(calls)
    applied = invoke(invocation(execution(options, expected, out), representation), context_builder=builder).result
    assert applied.exit_code == 0, applied
    assert len(calls) > original_count
    assert (options['project_root'] / inputs.originals[-1].path).read_bytes() == inputs.originals[-1].source_bytes
    findings = thaw(applied.result['execution']['historical_findings'])
    row = next(item for item in findings if item.get('kind') == 'proposal_original_history')
    assert row['observed_status'] == status and not row['write_authorized']
    assert not row['current_qualification_checked']


def test_completed_proposal_work_replays_originals_without_host_or_roots(recorded, tmp_path):
    options, native, inputs, calls = project(tmp_path, 'rejected')
    plan = prepare_restore_plan(**options, services=native)
    out = tmp_path / 'output'; out.mkdir()
    work = tmp_path / 'work'
    host = InvocationContextBuilder(recovery_authority=authority(),
        recovery_actor={'actor_type': 'human', 'actor_id': 'synthetic-current-owner'}, restore_services=native)
    first = execute_request(invocation({**execution(options, plan, out), '--work-dir': str(work)}, 'mapping'),
                            context_builder=host).result
    assert first.exit_code == 8, first
    request = CommandRequest('work.resume', {}, {'work_dir': str(work)})
    outcome = execute_request(request, context_builder=host).result
    assert outcome.exit_code == 0, outcome
    count = len(calls)
    shutil.rmtree(options['project_root']); shutil.rmtree(options['source_root'])
    before = inventory(work)
    with no_write_attempts():
        repeat = execute_request(request).result
    assert repeat.exit_code == 0, repeat
    assert len(calls) == count and inventory(work) == before
    assert not repeat.result['data']['native_execution_checked']
    assert not repeat.result['data']['checkpoint_changed']
    for key in ('execution', 'history_assessments'):
        if key in outcome.result['data']:
            assert repeat.result['data'][key] == outcome.result['data'][key]


def test_project_data_cannot_supply_a_success_callback_or_stale_approval(tmp_path):
    options, native, inputs, calls = project(tmp_path, 'approved')
    before = inventory(tmp_path)
    from specroad.recovery import RestoreError
    for service in (None, {'proposal_inputs': 'passed'},
            RestoreServices(proposal_inputs=lambda model, record: {'passed': True}),
            RestoreServices(proposal_inputs=lambda model, record: replace(inputs, verifier=verifier(current=False)))):
        with no_write_attempts(), pytest.raises(RestoreError):
            prepare_restore_plan(**options, services=service)
    assert inventory(tmp_path) == before


def test_original_planning_work_requires_fresh_proposal_checks_then_replays_without_them(recorded, tmp_path):
    """A retained four-phase work-v1 request uses the same public native gates.

    This is the existing stored task contract, not a new success record or a
    replacement for the byte-granular public-start cases.
    """
    from specroad.cli.commands import builtin_registry
    from specroad.work._request_binding import _command
    from specroad.work.checkpoints import CheckpointStore
    from specroad.work.manifest import _create_manifest
    from specroad.work.open_existing import protected_paths
    from specroad.work.restore_execution import _build
    from specroad.work.root import WorkDirectory
    options, native, inputs, calls = project(tmp_path, 'rejected')
    expected = prepare_restore_plan(**options, services=native)
    out = tmp_path / 'output'; out.mkdir()
    location = tmp_path / 'planning-work'
    registry = builtin_registry()
    request = CommandRequest.from_mapping(invocation(planning(options, out), 'mapping'))
    phases = ('source_capture', 'inventory_capture', 'qualify_plan', 'deliver_plan')
    initial = _create_manifest(registry, _command(registry, request, recovery=True),
        tool_build=_build(), source_bindings={'project_id': None, 'scope': ['project'],
            'model_root_sha256': None}, inputs=[], units=[{'key': phase, 'phase': phase,
                'range': {'adapter': 'native-restore-planning-work-v1'}} for phase in phases])
    store = CheckpointStore(WorkDirectory(initial, protected_roots=(),
        protected_paths=protected_paths(initial), directory=location), initial)
    store.publish(initial)
    resume = CommandRequest('work.resume', {}, {'work_dir': str(location)})
    host = InvocationContextBuilder(restore_services=native)
    for _ in range(2):
        assert execute_request(resume, context_builder=host).result.exit_code == 8
    saved = inventory(location); project_before = inventory(options['project_root'])
    refused = execute_request(resume).result
    assert refused.exit_code == 3, refused
    assert inventory(location) == saved
    assert inventory(options['project_root']) == project_before
    count = len(calls)
    qualified = execute_request(resume, context_builder=host).result
    assert qualified.exit_code == 8, qualified
    assert len(calls) > count
    count = len(calls)
    complete = execute_request(resume, context_builder=host).result
    assert complete.exit_code == 0, complete
    assert len(calls) > count
    assert thaw(complete.result['data']['restore_plan']) == expected.data
    assert (out / 'plans/original.json').read_bytes() == expected.source_bytes
    saved = inventory(location); count = len(calls)
    shutil.rmtree(options['project_root']); shutil.rmtree(options['source_root'])
    with no_write_attempts():
        replay = execute_request(resume).result
    assert replay.exit_code == 0, replay
    assert not replay.result['data']['checkpoint_changed']
    assert not replay.result['data']['native_execution_checked']
    assert replay.result['data']['restore_plan'] == complete.result['data']['restore_plan']
    assert inventory(location) == saved and len(calls) == count


@pytest.mark.parametrize('status', ['rejected', 'stale', 'applied'])
@pytest.mark.parametrize('source_kind', ['project_bundle', 'baseline'])
def test_terminal_proposals_and_their_original_completion_survive_an_older_source(tmp_path, status, source_kind):
    from specroad.archive.project_snapshot import build_project_baseline_manifest
    from specroad.bundles._payload_model import owned_payload_model
    from specroad.model.canonical import canonical_json_bytes
    from specroad.model.paths import artifact_path
    from support.records import record_value, ref
    from test_restore_plan import decode_files
    options, native, inputs, _ = project(tmp_path, status)
    source_files = dict(inputs.contexts[0].basis.source_files)
    original = inputs.originals[-1]
    older = tmp_path / 'older-source'; older.mkdir()
    for path, raw in source_files.items():
        put(older, path, raw)
    options['source_root'] = older
    if source_kind == 'project_bundle':
        put(options['source_root'], options['source_path'], prepare_project_bundle(options['source_root']).source_bytes)
    else:
        snapshot = build_project_baseline_manifest(owned_payload_model(source_files,
            source_label='synthetic:original-before-proposal'), baseline_id=ref('BASE'))
        baseline = record_value('baseline', **{key: snapshot.data[key] for key in
            ('scope_descriptor', 'manifest', 'model_root_sha256', 'configuration_hash', 'profiles', 'tool_version')})
        path = artifact_path('baseline', baseline['id'], 'SR')
        put(options['source_root'], path, canonical_json_bytes(baseline))
        for item in snapshot.objects:
            put(options['source_root'], item.reference.path, item.content)
        options.update(source_kind='baseline', source_path=path, default_locale='en-GB', generated_path='output')
    before = inventory(tmp_path)
    with no_write_attempts():
        plan = prepare_restore_plan(**options, services=native)
    assert inventory(tmp_path) == before
    assert decode_files(plan)[original.path] == original.source_bytes
    assert plan.data['source_snapshot_root'] != plan.data['expected_target_root']
    assert any(row['path'] == original.path for row in plan.data['preserved'])
    assert any(row.get('observed_status') == status and not row['write_authorized']
               for row in plan.history_assessments)
