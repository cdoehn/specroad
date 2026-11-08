"""17.l.R: retained portable bytes, every global boundary and refused handoffs."""
from support.merge_matrix import originals, recorded, phase_boundaries
from base64 import b64decode
from hashlib import sha256
import json
import shutil

import pytest

from specroad import _build
from specroad.merge.preparation import prepare_merge
from specroad.merge import resolve_merge_conflict
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.work.merge import resume_merge_work
from specroad.work.manifest import partition_work_manifest
from specroad.work.packages import export_work_package
from specroad.storage.archive import encode_archive, decode_archive
from support.merge_application import templates, case, work, complete
from support.merge_preparation import store_for, finish
from support.merge_resolution import PLAN_ID, ACTOR, WHEN
from support.merge_target import small_seed, inputs, replace
from support.migration_cli import invoke, success
from support.read_only import inventory


@phase_boundaries
def test_public_package_resume_at_each_boundary_needs_no_old_sources(recorded, tmp_path, originals, phase):
    data = case(tmp_path/'input', originals)
    _, sources, history, options, _ = data
    expected = prepare_merge(sources, plan_id=PLAN_ID, history=history)
    store = store_for(tmp_path/'old-work', sources, history)
    tasks = store.read().entries('tasks')
    if phase == 'completed':
        finish(store, 100000)
    else:
        prefix = next(i for i, task in enumerate(tasks) if task['phase'] == phase)
        if prefix: resume_merge_work(store, max_units=prefix)
    retained = tmp_path/'transport'; retained.mkdir()
    package = retained/'retained.zip'
    success(work('export', tmp_path/'old-work', {'--output': str(package)}))
    # Explicit test destruction: only the retained package survives on the receiving side.
    shutil.rmtree(tmp_path/'old-work'); shutil.rmtree(tmp_path/'input')
    destination = tmp_path/'new-work'
    success(invoke('work.restore', {'--output': str(destination)}, authorize=False,
                   arguments={'file': str(package)}))
    actual = success(complete(destination))['data']
    assert actual == expected
    before = inventory(destination)
    assert success(work('resume', destination))['data'] == expected
    assert inventory(destination) == before
    assert not (tmp_path/'input').exists()
    assert not actual['write_authorized'] and not actual['project_writes_performed']


@pytest.mark.parametrize('phase', ['inventory', 'comparison', 'metadata', 'target_validation'])
def test_rehashed_phase_forgery_cannot_survive_public_resume(recorded, tmp_path, originals, phase):
    data = case(tmp_path/'input', originals)
    store = store_for(tmp_path/'work', data[1], data[2])
    tasks = store.read().entries('tasks')
    prefix = next(i for i, task in enumerate(tasks) if task['phase'] == phase)
    if prefix: resume_merge_work(store, max_units=prefix)
    current = store.read(); task = current.entries('remaining')[0]
    store.publish(partition_work_manifest(current, {task['unit_id']: jcs({
        'adapter': 'merge-work-v1', 'phase': phase, 'result': {'forged': True}})}))
    before = inventory(tmp_path/'input')
    total = len(tasks)
    for _ in range(total+2):
        result = work('resume', tmp_path/'work')
        if result.exit_code != 8: break
    assert result.exit_code in (3, 6), (result.exit_code, result.diagnostics)
    assert inventory(tmp_path/'input') == before
    assert store.read().as_dict()['state'] == 'running'


@pytest.mark.parametrize('failure', ['incomplete', 'runtime', 'object', 'history', 'plan_id', 'live_source', 'mixed_mode'])
def test_invalid_work_never_becomes_a_publication_plan(recorded, tmp_path, originals, monkeypatch, failure):
    data = case(tmp_path/'input', originals)
    store = store_for(tmp_path/'work', data[1], data[2])
    if failure != 'incomplete': finish(store, 100000)
    options = {**data[3], **data[4], '--work-dir': str(tmp_path/'work')}
    if failure == 'runtime': monkeypatch.setattr(_build, 'BUILD_METADATA', {'format_version': 1,
        'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': '5'*64})
    elif failure == 'object': next((tmp_path/'work'/'objects').iterdir()).write_bytes(b'corrupt original')
    elif failure == 'history':
        history = json.loads((tmp_path/'input'/'history.json').read_bytes())
        history['not_native_history'] = True
        (tmp_path/'input'/'history.json').write_bytes(jcs(history))
    elif failure == 'plan_id': options['--plan-id'] = 'MP-'+'1'*26
    elif failure == 'live_source':
        path = data[0]/'specroad.json'; path.write_bytes(path.read_bytes()+b'\n')
    elif failure == 'mixed_mode': options['--resolutions'] = str(tmp_path/'no-such-plan')
    before = inventory(tmp_path)
    result = invoke('merge.plan', options, authorize=False)
    assert result.exit_code in (2, 3, 5, 6, 7), (result.exit_code, result.diagnostics)
    assert inventory(tmp_path) == before


def test_unresolved_conflict_does_not_produce_a_change_plan(recorded, tmp_path):
    files = small_seed(tmp_path/'seed')
    sources, history, _, _ = inputs(tmp_path/'input', [files,
        replace(files, 'goal', title='left'), replace(files, 'goal', title='right')])
    history_path = tmp_path/'history.json'; history_path.write_bytes(jcs(history))
    options = {'--for-apply': True, '--project': sources.ours.source_root,
        '--history': str(history_path), '--plan-id': PLAN_ID, '--change-plan-id': 'synthetic-conflict',
        '--actor-type': ACTOR['actor_type'], '--actor-id': ACTOR['actor_id'], '--planned-at': WHEN}
    options.update({'--'+role: getattr(sources, role).source_root for role in ('base', 'ours', 'theirs')})
    before = inventory(tmp_path)
    result = invoke('merge.plan', options, authorize=False)
    assert result.exit_code == 3 and inventory(tmp_path) == before


def test_noncanonical_audited_resolution_survives_portable_handoff(recorded, tmp_path):
    files = small_seed(tmp_path/'seed')
    sources, history, plan, _ = inputs(tmp_path/'input', [files,
        replace(files, 'goal', title='left'), replace(files, 'goal', title='right')])
    conflict = next(row for row in plan.data['conflicts'] if row['pointer'] == '/title')
    decision = resolve_merge_conflict(plan.canonical_bytes, sources, history=history,
        expected_plan_sha256=plan.sha256, conflict_id=conflict['conflict_id'], actor=ACTOR, resolved_at=WHEN, take='theirs')
    raw = json.dumps(decision.data, indent=2).encode()+b'\n'
    store = store_for(tmp_path/'work', sources, history, plan_raw=raw, expected_plan_sha256=sha256(raw).hexdigest(), fail_on_change=True)
    expected, code = finish(store, 2)
    assert code == 1 and expected['target']['target_validated']
    transport = tmp_path/'transport'; transport.mkdir(); package = transport/'work.zip'
    success(work('export', tmp_path/'work', {'--output': str(package)}))
    success(invoke('work.restore', {'--output': str(tmp_path/'restored')}, arguments={'file': str(package)}, authorize=False))
    history_path = tmp_path/'history.json'; history_path.write_bytes(jcs(history))
    options = {'--for-apply': True, '--work-dir': str(tmp_path/'restored'), '--project': sources.ours.source_root,
        '--history': str(history_path), '--plan-id': PLAN_ID, '--change-plan-id': 'synthetic-audited-merge',
        '--actor-type': ACTOR['actor_type'], '--actor-id': ACTOR['actor_id'], '--planned-at': WHEN}
    options.update({'--'+role: getattr(sources, role).source_root for role in ('base', 'ours', 'theirs')})
    before = inventory(tmp_path)
    result = success(invoke('merge.plan', options, authorize=False))
    bound = result['change_plan']['operations'][0]['inputs']
    assert b64decode(bound['plan_bytes_base64']) == raw
    assert bound['plan_sha256'] == sha256(raw).hexdigest()
    assert json.loads(b64decode(bound['plan_bytes_base64']))['resolutions'] == decision.data['resolutions']
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('failure', ['object', 'missing_checkpoint', 'runtime', 'pointer'])
def test_invalid_portable_merge_is_refused_before_destination_allocation(recorded, tmp_path, originals, failure):
    data = case(tmp_path/'input', originals)
    store = store_for(tmp_path/'work', data[1], data[2])
    resume_merge_work(store)
    original = export_work_package(store)
    metadata, payloads = decode_archive(original, manifest_name='work-package.json',
                                        expected_sha256=sha256(original).hexdigest())
    if failure == 'object':
        payloads[next(name for name in payloads if name.startswith('objects/'))] = b'corrupted'
    elif failure == 'missing_checkpoint':
        del payloads[next(name for name in payloads if name.startswith('checkpoints/'))]
    elif failure == 'runtime': metadata['tool_build']['build_sha256'] = '0'*64
    else:
        pointer = json.loads(payloads['work.json']); pointer['checkpoint_generation'] = True
        payloads['work.json'] = jcs(pointer)
    raw = encode_archive('work-package.json', metadata, payloads)
    transport = tmp_path/'transport'; transport.mkdir(); package = transport/'work.zip'; package.write_bytes(raw)
    before = inventory(tmp_path)
    result = invoke('work.restore', {'--output': str(tmp_path/'rejected')}, authorize=False,
                    arguments={'file': str(package)})
    assert result.exit_code in (3, 5, 6, 7), (result.exit_code, result.diagnostics)
    assert inventory(tmp_path) == before and not (tmp_path/'rejected').exists()
