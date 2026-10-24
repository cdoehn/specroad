"""14.o.R: genuine durable candidate continuations and native import parity."""
from copy import deepcopy
import errno
import json
import os
from pathlib import Path

import pytest

from specroad import _build
from specroad.changes import PublicationAuthority
from specroad.model.errors import ModelError
from specroad.changes.target_values import TargetPolicy
from specroad.exchange import apply_import_plan, prepare_import_plan, ImportIdentityError
from specroad.exchange import import_work
from specroad.exchange.import_work import finalize_import_work
from specroad.graph.relations import SourceRelations
from specroad.graph.review_status import RelationReviewStatuses
from specroad.model.canonical import canonical_json_bytes
from specroad.model.paths import artifact_path
from specroad.work.checkpoints import CheckpointStorageError
from specroad.work.manifest import partition_work_manifest
from specroad.work.resume import WorkResumeError
from support.import_execution import ALLOW
from support.import_work import FORMATS, setup, advance, registry, reopen
from support.read_only import inventory, no_write_attempts
from support.targets import SCOPE
from test_work_progress import ticking
from test_work_resume import recorded


@pytest.mark.parametrize('fmt', FORMATS)
@pytest.mark.parametrize('size', [1, 2, 100])
@pytest.mark.parametrize('profile', ['constrained', 'standard'])
def test_every_candidate_plan_and_native_target_equal_direct_execution(recorded, tmp_path, fmt, size, profile):
    direct_dir = tmp_path / 'direct'; direct_dir.mkdir()
    stepped_dir = tmp_path / 'stepped'; stepped_dir.mkdir()
    direct, values, options, _, _ = setup(direct_dir, fmt)
    native, candidates, args, initial, store = setup(stepped_dir, fmt)
    expected = prepare_import_plan(direct, values, **options)
    assert expected.plan_valid, expected.data['diagnostics']
    before = inventory(Path(native.binding.source_root)); executed = []
    while store.read().entries('remaining'):
        store = reopen(initial, store._location.path, native.binding.source_root)
        result, _ = advance(store, args, size=size, profile=profile)
        assert result.executed_unit_ids and not set(result.executed_unit_ids).intersection(executed)
        assert list(result.reused_unit_ids) == executed
        executed.extend(result.executed_unit_ids)
        assert inventory(Path(native.binding.source_root)) == before
    final = finalize_import_work(store, registry=registry())
    outcome = json.loads(final.outcome_bytes); report = outcome['result']['import_plan']
    assert canonical_json_bytes(report) == expected.canonical_bytes
    assert len(executed) == len(candidates) + 1 == len(initial.entries('tasks'))
    assert report['objects'][-1]['candidate_index'] == 3 and len(report['objects']) == 4
    assert report['input_parsed'] is False and report['candidate_origin'] == 'explicit_parsed_artifacts'
    assert outcome['result']['import_completed'] is False and outcome['result']['write_authorized'] is False
    assert final.command_exit_code == 0 and outcome['summary']['complete'] is True
    replay_before = inventory(stepped_dir)
    assert finalize_import_work(store, registry=registry()).outcome_bytes == final.outcome_bytes
    assert advance(store, args, size=100)[0].executed_unit_ids == ()
    assert inventory(stepped_dir) == replay_before
    one = apply_import_plan(direct, values, **options, transaction_id='txn-parity', authority=ALLOW)
    two = apply_import_plan(native, candidates, **args, plan_bytes=canonical_json_bytes(report),
                            transaction_id='txn-parity', authority=ALLOW)
    assert one['execution']['write_state'] == two['execution']['write_state'] == 'committed'
    assert one['execution']['target_model_root_sha256'] == two['execution']['target_model_root_sha256']
    assert one['execution']['audit']['operations'] == two['execution']['audit']['operations'] == report['operations']
    # Compare actual normative file bytes and independent literal business values.
    all_paths = set(native.source_files) | {artifact_path(v['artifact']['artifact_type'], v['artifact']['id'], 'SR')
                                           for v in report['change_plan']['result_artifacts']}
    assert {p: (Path(native.binding.source_root)/p).read_bytes() for p in all_paths} == {
        p: (Path(direct.binding.source_root)/p).read_bytes() for p in all_paths}
    artifacts = [SourceRelations(p.read_bytes(), path=p.relative_to(native.binding.source_root).as_posix())
                 for p in Path(native.binding.source_root).glob('spec/**/*.json')]
    statements = {a.data['statement'] for a in artifacts if a.data['artifact_type'] == 'goal'}
    assert {'Updated supplier goal.', 'Unicode é e\u0301 日本語', 'Third, "quoted" value', 'Final object'} <= statements
    source = native.artifacts[0] if native.artifacts[0]['relations'] else next(a for a in native.artifacts if a['relations'])
    statuses = RelationReviewStatuses(artifacts)
    assert statuses.for_relation(source['id'], source['relations'][0]['relation_id']).status == 'suspect'
    assert statuses.approval_granted is False


@pytest.mark.parametrize('done', [0, 1, 4])
def test_no_partial_work_can_be_completed_or_write_project(recorded, tmp_path, done):
    native, _, args, _, store = setup(tmp_path)
    if done: advance(store, args, size=done)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        finalize_import_work(store, registry=registry())
    assert caught.value.reason == 'unfinished_import_work_cannot_complete'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('fmt', FORMATS)
def test_original_sources_can_disappear_and_completed_mapping_is_never_repeated(recorded, tmp_path, monkeypatch, fmt):
    native, candidates, args, initial, store = setup(tmp_path, fmt)
    expected = prepare_import_plan(native, candidates, **args).canonical_bytes
    first, _ = advance(store, args, size=2)
    for p in native.source_files: (Path(native.binding.source_root)/p).unlink()
    project_before = inventory(Path(native.binding.source_root))
    moved = tmp_path / 'relocated-work'; store._location.path.rename(moved)
    store = reopen(initial, moved, native.binding.source_root)
    original = import_work._prepare_candidate_changes; seen = []
    def observe(*a, **kw):
        assert kw['start_index'] not in (0, 1)
        seen.append(kw['start_index']); return original(*a, **kw)
    monkeypatch.setattr(import_work, '_prepare_candidate_changes', observe)
    while store.read().entries('remaining'): advance(store, args)
    final = finalize_import_work(store, registry=registry())
    assert canonical_json_bytes(json.loads(final.outcome_bytes)['result']['import_plan']) == expected
    assert seen == [2, 3] and len(first.executed_unit_ids) == 2
    assert inventory(Path(native.binding.source_root)) == project_before


@pytest.mark.parametrize('defect', ['external', 'native', 'field'])
def test_late_native_failure_keeps_exact_prefix_and_original_error(recorded, tmp_path, defect):
    def mutate(native, candidates, options):
        if defect == 'external': candidates[2] = deepcopy(candidates[0])
        elif defect == 'native': candidates[2]['new_artifact']['id'] = candidates[1]['new_artifact']['id']
        else: del candidates[2]['fields']['Text']
    native, candidates, args, _, store = setup(tmp_path, mutate=mutate)
    with pytest.raises(ModelError) as direct: prepare_import_plan(native, candidates, **args)
    advance(store, args, size=2); previous = store.read(); before = inventory(tmp_path)
    with pytest.raises(type(direct.value)) as stepped: advance(store, args)
    assert stepped.value.diagnostic() == direct.value.diagnostic()
    assert store.read().raw == previous.raw and inventory(tmp_path) == before


@pytest.mark.parametrize('defect', ['loss', 'missing_gate'])
@pytest.mark.parametrize('size', [1, 100])
def test_complete_invalid_plan_retains_all_findings_and_no_write_authority(recorded, tmp_path, defect, size):
    def mutate(native, candidates, options):
        if defect == 'loss': candidates[3]['fields']['Unmapped'] = {'kept': [None, False, 'tail']}
        else: options['gates'] = []
    native, candidates, args, _, store = setup(tmp_path, mutate=mutate)
    expected = prepare_import_plan(native, candidates, **args); before = inventory(Path(native.binding.source_root))
    assert not expected.plan_valid
    while store.read().entries('remaining'): advance(store, args, size=size)
    final = finalize_import_work(store, registry=registry())
    result = json.loads(final.outcome_bytes)
    assert canonical_json_bytes(result['result']['import_plan']) == expected.canonical_bytes
    assert final.command_exit_code == expected.data['exit_code'] and result['status'] == 'failed'
    assert result['summary']['complete'] is True and result['result']['import_completed'] is False
    with pytest.raises(ImportIdentityError):
        apply_import_plan(native, candidates, **args, plan_bytes=expected.canonical_bytes,
                          transaction_id='txn-invalid', authority=ALLOW)
    assert inventory(Path(native.binding.source_root)) == before


@pytest.mark.parametrize('flag', ['--step-cpu-ms', '--step-wall-ms'])
def test_soft_budget_always_completes_one_real_candidate(recorded, tmp_path, flag):
    _, _, args, initial, store = setup(tmp_path)
    step, measure = advance(store, args, size=100, sampler=ticking(), limits={flag: 1})
    assert len(step.executed_unit_ids) == 1 and measure['soft_budget_exceeded']
    assert len(step.manifest.entries('remaining')) == len(initial.entries('tasks')) - 1


@pytest.mark.parametrize('change', ['policy', 'build', 'missing_input', 'absent_work'])
def test_missing_or_incompatible_work_never_falls_back_or_allocates(recorded, tmp_path, monkeypatch, change):
    _, _, args, initial, store = setup(tmp_path, publish=change != 'absent_work')
    if change == 'policy': args['policy'] = TargetPolicy('other-command', '1', ())
    elif change == 'build': monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': 'd'*64})
    elif change == 'missing_input':
        item = next(i for i in initial.entries('inputs') if i['root_id'] == 'candidates')
        matches = list(store._location.path.rglob(item['sha256']))
        assert len(matches) == 1; matches[0].unlink()
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises((WorkResumeError, CheckpointStorageError, FileNotFoundError)):
        advance(store, args)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['identity', 'index', 'phase', 'input', 'extra'])
def test_rehashed_inconsistent_candidate_evidence_is_rejected(recorded, tmp_path, change):
    _, _, args, initial, store = setup(tmp_path)
    step, _ = advance(store, args); first = step.manifest.entries('completed')[0]
    row = json.loads(step.manifest.objects[first['evidence']['sha256']])
    if change == 'identity': row['observation']['objects'][0]['identity']['external_id'] = 'other'
    elif change == 'index': row['observation']['objects'][0]['candidate_index'] = True
    elif change == 'phase': row['phase'] = 'import_target'
    elif change == 'input': row['input_manifest_sha256'] = '0'*64
    else: row['approved'] = True
    forged = partition_work_manifest(initial, {first['unit_id']: canonical_json_bytes(row)})
    foreign = reopen(initial, tmp_path/'forged-work', tmp_path/'project')
    foreign.publish(initial); foreign.publish(forged); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError): advance(foreign, args)
    assert inventory(tmp_path) == before and foreign.read().raw == forged.raw


@pytest.mark.parametrize('late', [False, True])
def test_failed_checkpoint_retains_actual_durable_generation(recorded, tmp_path, monkeypatch, late):
    import specroad.work.checkpoints as checkpoints
    native, _, args, initial, store = setup(tmp_path); before = inventory(Path(native.binding.source_root))
    original = os.replace
    with monkeypatch.context() as patch:
        if late:
            def fail(src, dst, **kwargs):
                observed = original(src, dst, **kwargs)
                if dst == 'work.json': raise OSError(errno.EIO, 'Owned late checkpoint failure')
                return observed
            patch.setattr(os, 'replace', fail)
        else:
            def fail(*a, **k): raise OSError(errno.ENOSPC, 'Owned storage failure')
            patch.setattr(checkpoints, '_write_new', fail)
        with pytest.raises(OSError): advance(store, args)
    assert store.read().as_dict()['checkpoint_generation'] == (1 if late else 0)
    assert inventory(Path(native.binding.source_root)) == before
    next_step, _ = advance(store, args)
    assert next_step.manifest.as_dict()['checkpoint_generation'] == (2 if late else 1)


@pytest.mark.parametrize('change', ['strategy', 'created_ids', 'diagnostics', 'target_hash',
    'nested_authority', 'policy', 'invalid_result', 'extra'])
def test_rehashed_inconsistent_final_report_is_rejected(recorded, tmp_path, change):
    _, _, args, initial, store = setup(tmp_path)
    advance(store, args, size=100); current = store.read()
    additions = {r['unit_id']: current.objects[r['evidence']['sha256']] for r in current.entries('completed')}
    last = current.entries('completed')[-1]['unit_id']
    row = json.loads(additions[last]); report = row['observation']
    if change == 'strategy': report['strategy'] = 'create_only'
    elif change == 'created_ids': report['created_ids'].pop()
    elif change == 'diagnostics': report['diagnostics'].append({'exit_code': 3})
    elif change == 'target_hash': report['target_model_root_sha256'] = '0'*64
    elif change == 'nested_authority': report['target_assessment']['write_authorized'] = True
    elif change == 'policy':
        report['target_assessment']['binding']['command']['version'] = 'other'
        report['binding']['target_binding']['command']['version'] = 'other'
    elif change == 'invalid_result': report.update(plan_valid=False, exit_code=3)
    else: report['approved'] = True
    additions[last] = canonical_json_bytes(row)
    forged = partition_work_manifest(initial, additions)
    foreign = reopen(initial, tmp_path/'forged-work', tmp_path/'project')
    foreign.publish(initial); foreign.publish(forged); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError):
        finalize_import_work(foreign, registry=registry())
    assert inventory(tmp_path) == before and foreign.read().raw == forged.raw


@pytest.mark.parametrize('changed', ['source', 'candidate', 'actor', 'request', 'authority'])
def test_finished_work_plan_cannot_replace_current_inputs_or_live_authority(recorded, tmp_path, changed):
    native, candidates, args, _, store = setup(tmp_path)
    advance(store, args, size=100)
    report = json.loads(finalize_import_work(store, registry=registry()).outcome_bytes)['result']['import_plan']
    options = dict(args); supplied = deepcopy(candidates); authority = ALLOW
    if changed == 'source': options['input_bytes'] += b'\n'
    elif changed == 'candidate': supplied[-1]['fields']['Text'] = 'Different import'
    elif changed == 'actor': options['actor'] = {'actor_type': 'human', 'actor_id': 'another-person'}
    elif changed == 'request': options['request_id'] = 'different-request'
    else: authority = PublicationAuthority('explicit-denial', '1', lambda request: False)
    before = {p: (Path(native.binding.source_root)/p).read_bytes() for p in native.source_files}
    with pytest.raises(ModelError):
        apply_import_plan(native, supplied, **options, plan_bytes=canonical_json_bytes(report),
                          transaction_id='txn-refused', authority=authority)
    assert {p: (Path(native.binding.source_root)/p).read_bytes() for p in native.source_files} == before
    assert not (Path(native.binding.source_root)/'.specroad/requests').exists()


def test_empty_candidate_inventory_still_requires_one_complete_target_unit(recorded, tmp_path):
    native, candidates, args, initial, store = setup(tmp_path, mutate=lambda m, c, o: c.clear())
    assert len(initial.entries('tasks')) == 1
    step, _ = advance(store, args)
    assert len(step.executed_unit_ids) == 1 and not step.manifest.entries('remaining')
    report = json.loads(finalize_import_work(store, registry=registry()).outcome_bytes)['result']['import_plan']
    assert canonical_json_bytes(report) == prepare_import_plan(native, candidates, **args).canonical_bytes
    assert report['objects'] == report['operations'] == []
