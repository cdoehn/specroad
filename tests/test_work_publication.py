"""Real temporary native transactions after separately persisted preparations.

Registry and human authority are explicit test-host registrations. The actual
project lock, journal, staging, replacements, receipts and readers run normally.
Recorded build identity is a labelled in-process fixture, not a CLI claim.
"""

from dataclasses import FrozenInstanceError
import errno
import json
import os
from pathlib import Path

import pytest

from specroad import _build
from specroad.changes import (CommitPublicationError, PublicationAuthority,
    PublicationCheckError, read_transaction_completion, transaction_preflight)
from specroad.changes.authoring import bind_plan_authoring
from specroad.changes.idempotency import resolve_normative_request
from specroad.changes.target import assess_change_target
from specroad.changes.target_values import TargetPolicy
from specroad.cli.contracts import CommandClass
from specroad.model.canonical import canonical_json_bytes
from specroad.security import ProjectBoundary
from specroad.storage.project import ProjectSource
from specroad.work import publication
from specroad.work.checkpoints import CheckpointStore
from specroad.work.manifest import partition_work_manifest
from specroad.work.publication import (NormativeWorkPublication,
    prepare_normative_work, advance_normative_preparation, publish_normative_work)
from specroad.work.resume import WorkResumeError
from specroad.work.root import WorkDirectory
from support.automatic_recovery import current_model
from support.folds import goal, edit, create
from support.publication import prepared, ALLOW, files
from support.read_only import inventory, no_write_attempts
from support.targets import ACTOR, TIME, POLICY, SCOPE
from test_work_resume import recorded
from test_work_resume_right import registry, prepare_work


def setup(tmp_path, *, multi=False, publish=True):
    values = [goal(1), goal(2)]
    operations = [edit(values[0], 'First complete target')]
    if multi:
        operations += [edit(values[1], 'Second complete target'), create(goal(0,
            revision=1, created_at=TIME, updated_at=TIME, created_by=ACTOR, updated_by=ACTOR))]
    model, plan, preflight = prepared(tmp_path / 'project',
        artifacts=values, operations=operations)
    reg = registry()
    before = inventory(tmp_path)
    with no_write_attempts():
        initial = prepare_normative_work(reg, plan, model=model)
    assert inventory(tmp_path) == before
    location = WorkDirectory(initial, protected_roots=(ProjectBoundary(model.binding.source_root),),
                             directory=tmp_path / 'work')
    store = CheckpointStore(location, initial)
    if publish:
        store.publish(initial)
    return model, plan, preflight, reg, initial, location, store


def arguments(reg, model, plan):
    return {'registry': reg, 'model': model, 'policy': POLICY,
            'actor': plan.data['actor'], 'request_id': plan.data['request_id']}


def prepare(store, reg, model, plan):
    return advance_normative_preparation(store, **arguments(reg, model, plan))


def ready(store, reg, model, plan):
    prepare(store, reg, model, plan)
    return prepare(store, reg, model, plan)


def publish(store, reg, model, plan, **changes):
    options = {**arguments(reg, model, plan),
               'transaction_id': 'txn-work-native', 'authority': ALLOW}
    options.update(changes)
    return publish_normative_work(store, **options)


@pytest.mark.parametrize('multi', [False, True])
def test_preparations_are_separate_durable_generations_without_project_changes(recorded, tmp_path, multi):
    model, plan, _, reg, initial, location, store = setup(tmp_path, multi=multi)
    project = Path(model.binding.source_root); before = inventory(project)
    previous = initial
    for count in (1, 2):
        # New controller instances reuse only persisted bytes and the original
        # independently bound initial plan; no prior live preparation handle.
        fresh = CheckpointStore(WorkDirectory(initial,
            protected_roots=(ProjectBoundary(project),), directory=location.path), initial)
        following = prepare(fresh, registry(), model.snapshot(), plan)
        assert following.as_dict()['checkpoint_generation'] == count
        assert len(following.entries('completed')) == count
        assert len(following.entries('remaining')) == 2 - count
        assert all(following.objects[k] == v for k, v in previous.objects.items())
        for key in ('work_id', 'actor', 'request_id', 'operations_sha256', 'plan_binding'):
            assert following.as_dict()[key] == initial.as_dict()[key]
        assert store.read().raw == following.raw and inventory(project) == before
        assert transaction_preflight(project, command_class=CommandClass.READ_ONLY).exit_code == 0
        assert not (location.path / 'work-lock.json').exists()
        previous = following
    assert following.as_dict()['state'] == 'running'
    assert not following.as_dict()['result_parts']
    replay = prepare(store, reg, model, plan)
    assert replay.raw == following.raw and inventory(project) == before


@pytest.mark.parametrize('multi', [False, True])
def test_all_original_operations_publish_in_one_native_transaction_and_replay(recorded, tmp_path, monkeypatch, multi):
    model, plan, preflight, reg, initial, location, store = setup(tmp_path, multi=multi)
    checkpoint = ready(store, reg, model, plan)
    expected = {**model.source_files, **{d.path: d.content for d in preflight.request.documents}}
    native = publication.publish_prepared_journal; calls = []; authorizations = []

    def observe(*args, **kwargs):
        calls.append(args[0].request.plan.source_bytes)
        assert store._pointer_value((location.path / 'work.json').read_bytes())['checkpoint_generation'] == 2
        return native(*args, **kwargs)

    def allow(request):
        authorizations.append(request.plan.source_bytes)
        assert request.plan.data['operations'] == plan.data['operations']
        assert request.plan.data['request_id'] == plan.data['request_id']
        return True

    monkeypatch.setattr(publication, 'publish_prepared_journal', observe)
    authority = PublicationAuthority('explicit-test-human', '1', allow)
    result = publish(store, reg, model, plan, authority=authority)
    value = result.as_dict(); project = Path(model.binding.source_root)
    assert calls == [plan.source_bytes] and authorizations
    assert all(raw == plan.source_bytes for raw in authorizations)
    assert files(project) == expected
    assert current_model(project).manifest(current_model(project).artifacts, SCOPE).sha256 == plan.data['expected_result']['model_root_sha256']
    assert value['publication_performed'] is True
    assert value['transaction']['commit_completed'] and value['transaction']['cleanup_completed']
    assert value['result_object']['write_state'] == 'committed'
    assert value['result_object']['published_paths'] == sorted(d.path for d in preflight.request.documents)
    assert len(list((project / '.specroad/requests').glob('*.json'))) == 1
    assert len(list((project / '.specroad/transactions/receipts').glob('*/transaction.json'))) == 1
    assert store.read().raw == checkpoint.raw
    assert not value['checkpoint_changed'] and not value['work_completion_recorded']
    direct = resolve_normative_request(ProjectSource(project), bind_plan_authoring(plan)).data
    assert direct['result_object'] == value['result_object']
    assert direct['original_request']['actor'] == initial.as_dict()['actor']
    assert direct['original_request']['operations_sha256'] == initial.as_dict()['operations_sha256']
    before = inventory(tmp_path)
    denied = PublicationAuthority('denied-live-write', '1', lambda request: False)
    with no_write_attempts():
        replay = publish(store, registry(), model, plan,
                         transaction_id='must-not-create-second-transaction', authority=denied)
    assert replay.as_dict()['result_object'] == value['result_object']
    assert replay.as_dict()['publication_performed'] is False
    assert calls == [plan.source_bytes] and inventory(tmp_path) == before
    assert replay.as_dict()['transaction']['current_target_verified'] is False
    with pytest.raises(TypeError):
        bool(result)
    with pytest.raises(TypeError):
        NormativeWorkPublication()
    with pytest.raises(FrozenInstanceError):
        result._raw = b'{}'
    value['result_object']['exit_code'] = 9
    assert result.as_dict()['result_object']['exit_code'] == 0


@pytest.mark.parametrize('count', [0, 1])
def test_incomplete_preparation_cannot_open_a_project_writer(recorded, tmp_path, count):
    model, plan, _, reg, _, _, store = setup(tmp_path)
    for _ in range(count):
        prepare(store, reg, model, plan)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        publish(store, reg, model, plan)
    assert caught.value.reason == 'normative_preparation_incomplete'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('operation', ['prepare', 'publish'])
def test_absent_work_is_never_created_to_claim_preparation(recorded, tmp_path, operation):
    model, plan, _, reg, _, _, store = setup(tmp_path, publish=False)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(FileNotFoundError) as caught:
        (prepare if operation == 'prepare' else publish)(store, reg, model, plan)
    assert caught.value.errno == errno.ENOENT
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['actor', 'request', 'runtime'])
def test_original_identity_and_build_cannot_be_relabelled_at_publication(recorded, tmp_path, monkeypatch, change):
    model, plan, _, reg, _, _, store = setup(tmp_path)
    ready(store, reg, model, plan); options = {}
    if change == 'actor':
        options['actor'] = {'actor_type': 'human', 'actor_id': 'different'}
    elif change == 'request':
        options['request_id'] = 'another-request'
    else:
        monkeypatch.setattr(_build, 'BUILD_METADATA', {**_build.BUILD_METADATA, 'build_sha256': '8' * 64})
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        publish(store, reg, model, plan, **options)
    assert caught.value.exit_code == 6 and inventory(tmp_path) == before


def test_actual_changed_target_is_rechecked_before_writer_creation(recorded, tmp_path):
    model, plan, _, reg, _, _, store = setup(tmp_path)
    checkpoint = ready(store, reg, model, plan)
    path = Path(model.binding.source_root) / model.documents[0].path
    path.write_bytes(path.read_bytes() + b' ')
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(PublicationCheckError) as caught:
        publish(store, reg, model, plan)
    assert caught.value.exit_code == 6
    assert inventory(tmp_path) == before and store.read().raw == checkpoint.raw


@pytest.mark.parametrize('prepared_count', [0, 1, 2])
def test_changed_fresh_model_is_a_conflict_in_every_phase(recorded, tmp_path, prepared_count):
    model, plan, _, reg, initial, _, store = setup(tmp_path)
    checkpoint = initial
    for _ in range(prepared_count):
        checkpoint = prepare(store, reg, model, plan)
    project = Path(model.binding.source_root)
    path = project / model.documents[0].path
    value = json.loads(path.read_bytes()); value['statement'] = 'Changed external model'
    path.write_bytes(canonical_json_bytes(value))
    fresh = current_model(project); before = inventory(tmp_path)
    with pytest.raises(WorkResumeError) as caught:
        (publish if prepared_count == 2 else prepare)(store, reg, fresh, plan)
    assert caught.value.as_dict() == {'reason': 'stale_resume_target', 'exit_code': 6}
    assert store.read().raw == checkpoint.raw and inventory(tmp_path) == before


@pytest.mark.parametrize('operation', ['prepare', 'publish'])
def test_generic_planner_data_is_not_the_closed_native_preparation_plan(recorded, tmp_path, operation):
    model, plan, _, reg, _, _, _ = setup(tmp_path)
    generic = prepare_work(reg, model, plan)
    location = WorkDirectory(generic, protected_roots=(ProjectBoundary(model.binding.source_root),),
                             directory=tmp_path / 'generic-work')
    store = CheckpointStore(location, generic); store.publish(generic)
    before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError) as caught:
        (prepare if operation == 'prepare' else publish)(store, reg, model, plan)
    assert caught.value.reason == 'unsupported_normative_preparation_plan'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['wrong_phase', 'wrong_plan', 'extra_field', 'out_of_order'])
def test_rehashed_invalid_preparation_evidence_never_opens_the_writer(recorded, tmp_path, change):
    model, plan, _, reg, initial, _, store = setup(tmp_path)
    task = initial.entries('tasks')[1 if change == 'out_of_order' else 0]
    # Deliberately forged passive planner data, not actual execution evidence.
    row = {'format_version': 'native-change-preparation-v1', 'unit_id': task['unit_id'],
           'phase': task['phase'], 'plan_sha256': plan.sha256,
           'assessment_sha256': assess_change_target(plan, model, policy=POLICY).sha256}
    if change == 'wrong_phase': row['phase'] = 'publish'
    elif change == 'wrong_plan': row['plan_sha256'] = '0' * 64
    elif change == 'extra_field': row['approved'] = True
    forged = partition_work_manifest(initial, {task['unit_id']: canonical_json_bytes(row)})
    store.publish(forged); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(WorkResumeError):
        publish(store, reg, model, plan)
    assert inventory(tmp_path) == before and store.read().raw == forged.raw


def test_live_authority_denial_preserves_preparation_and_all_normative_bytes(recorded, tmp_path):
    model, plan, _, reg, _, _, store = setup(tmp_path)
    checkpoint = ready(store, reg, model, plan)
    project = Path(model.binding.source_root); before = files(project)
    with pytest.raises(PublicationCheckError) as caught:
        publish(store, reg, model, plan,
                authority=PublicationAuthority('test-denied', '1', lambda request: False))
    assert caught.value.exit_code == 7
    assert files(project) == before and store.read().raw == checkpoint.raw
    assert not (project / '.specroad/transactions/txn-work-native').exists()
    assert not (project / '.specroad/requests').exists()


def test_missing_global_gate_cannot_be_confirmed_by_the_first_preparation(recorded, tmp_path):
    model, plan, _, reg, initial, _, store = setup(tmp_path)
    project = Path(model.binding.source_root); before = inventory(project)
    options = arguments(reg, model, plan)
    options['policy'] = TargetPolicy('requires-global-gate', '1', ('extension:missing',))
    with pytest.raises(PublicationCheckError) as caught:
        advance_normative_preparation(store, **options)
    assert caught.value.exit_code == 3
    assert store.read().raw == initial.raw and inventory(project) == before


@pytest.mark.parametrize('late', [False, True])
def test_preparation_publication_failure_keeps_actual_work_without_project_writes(recorded, tmp_path, monkeypatch, late):
    model, plan, _, reg, initial, _, store = setup(tmp_path)
    project_before = inventory(Path(model.binding.source_root))
    native_replace = os.replace
    import specroad.work.checkpoints as checkpoints
    with monkeypatch.context() as patch:
        if late:
            def fail_after(src, dst, **kwargs):
                result = native_replace(src, dst, **kwargs)
                if dst == 'work.json':
                    raise OSError(errno.EIO, 'Owned late checkpoint failure')
                return result
            patch.setattr(os, 'replace', fail_after)
        else:
            def fail_before(*args, **kwargs):
                raise OSError(errno.ENOSPC, 'Owned checkpoint storage failure')
            patch.setattr(checkpoints, '_write_new', fail_before)
        with pytest.raises(OSError):
            prepare(store, reg, model, plan)
    actual = store.read()
    assert actual.as_dict()['checkpoint_generation'] == (1 if late else 0)
    assert inventory(Path(model.binding.source_root)) == project_before
    following = prepare(store, reg, model, plan)
    assert following.as_dict()['checkpoint_generation'] == (2 if late else 1)
    assert inventory(Path(model.binding.source_root)) == project_before


def test_lost_output_after_native_commit_replays_receipt_without_second_write(recorded, tmp_path, monkeypatch):
    model, plan, _, reg, _, _, store = setup(tmp_path, multi=True)
    checkpoint = ready(store, reg, model, plan)
    native = publication.cleanup_completed_transaction
    with monkeypatch.context() as patch:
        def lose_output(*args, **kwargs):
            result = native(*args, **kwargs)
            assert result.data['commit_completed'] and result.data['cleanup_completed']
            raise OSError(errno.EIO, 'Owned output loss after actual commit')
        patch.setattr(publication, 'cleanup_completed_transaction', lose_output)
        with pytest.raises(OSError):
            publish(store, reg, model, plan)
    proof = read_transaction_completion(ProjectSource(model.binding.source_root), 'txn-work-native')
    assert proof.data['commit_completed'] and store.read().raw == checkpoint.raw
    before = inventory(tmp_path)
    with no_write_attempts():
        replay = publish(store, reg, model, plan)
    assert not replay.as_dict()['publication_performed'] and inventory(tmp_path) == before
    assert replay.as_dict()['result_object']['transaction_id'] == 'txn-work-native'


def test_interrupted_native_publication_requires_recovery_not_work_resume(recorded, tmp_path, monkeypatch):
    model, plan, _, reg, _, _, store = setup(tmp_path, multi=True)
    checkpoint = ready(store, reg, model, plan)
    project = Path(model.binding.source_root); native = os.replace; moved = []
    with monkeypatch.context() as patch:
        def interrupt_after_target(src, dst, **kwargs):
            result = native(src, dst, **kwargs)
            if dst != 'journal.json':
                moved.append(dst)
                raise OSError(errno.EIO, 'Owned error after first actual target replacement')
            return result
        patch.setattr(os, 'replace', interrupt_after_target)
        with pytest.raises(CommitPublicationError) as caught:
            publish(store, reg, model, plan)
    assert len(moved) == 1 and caught.value.publication_possible
    assert store.read().raw == checkpoint.raw
    journal = json.loads((project / '.specroad/transactions/txn-work-native/journal.json').read_bytes())
    assert journal['state'] == 'committing'
    assert transaction_preflight(project, command_class=CommandClass.READ_ONLY).data['recovery_required']
    before = inventory(tmp_path)
    for action in (prepare, publish):
        with no_write_attempts(), pytest.raises(WorkResumeError) as blocked:
            action(store, reg, model, plan)
        assert blocked.value.reason == 'normative_transaction_requires_recovery'
        assert blocked.value.exit_code == 5 and inventory(tmp_path) == before
