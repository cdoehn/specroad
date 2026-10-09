"""Closed ChangePlan preparation followed by one existing native transaction.

The trusted host supplies its registry, current model, policy and authority.
Work records are passive preparation data, never permission to write. This API
does not install a CLI command or mark normative Work delivery completed.
"""

from dataclasses import dataclass
from pathlib import Path

from ..changes.authoring import bind_plan_authoring, normalize_authoring_actor
from ..changes.committing import publish_prepared_journal
from ..changes.committing_read import read_committing_journal
from ..changes.idempotency import resolve_normative_request
from ..changes.journal import begin_building_journal
from ..changes.locking import project_lock
from ..changes.publication_check import prepare_publication_check
from ..changes.publication_values import PublicationAuthority, PublicationCheckError
from ..changes.receipt_cleanup import cleanup_completed_transaction
from ..changes.receipt_finalization import finalize_committing_journal
from ..changes.receipt_read import read_transaction_completion
from ..changes.request_ids import normalize_request_id
from ..changes.staging import stage_building_journal
from ..changes.target import assess_change_target
from ..changes.target_model import TargetModel
from ..changes.target_values import TargetError, TargetPolicy
from ..changes.transaction_preflight import transaction_preflight
from ..changes.values import ChangePlan
from ..cli.contracts import CommandClass
from ..cli.requests import CommandRequest
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from ._normative_binding import read_plan
from ._resume_restore import check_initial_normative, restore_normative_checkpoint
from .checkpoints import CheckpointStore
from .manifest import (create_normative_work_manifest, partition_work_manifest,
                       read_work_manifest, _bytes)
from .resume import WorkResumeError, _runtime_build, _require, _compatible_read


def _units(plan):
    return [{'key': phase, 'phase': phase, 'range': {
        'adapter': 'native-change-preparation-v1', 'plan_sha256': plan.sha256}}
        for phase in ('target_assessment', 'target_preflight')]


def prepare_normative_work(registry, plan, *, model):
    """Bind two preparation phases without allocating Work or project files.

    Each phase currently handles its full supplied plan/model in memory. This
    is not an incremental large-plan parser or a command registration factory.
    """
    _require(type(plan) is ChangePlan and type(model) is TargetModel,
             'current_normative_plan_and_model_required')
    plan = ChangePlan(plan.source_bytes)
    value = plan.data
    _require(model.manifest(model.artifacts, value['base']['scope_descriptor']).sha256
             == value['base']['model_root_sha256'], 'stale_resume_target')
    actor = value['actor']
    request = CommandRequest('change.apply', options={
        '--actor-type': actor['actor_type'], '--actor-id': actor['actor_id'],
        '--request-id': value['request_id']})
    return create_normative_work_manifest(registry, request, plan=plan,
        tool_build=_runtime_build(), source_bindings={
            'project_id': model.binding.project_id, 'scope': ['project'],
            'model_root_sha256': value['base']['model_root_sha256']},
        inputs=[{'root_id': 'project', 'path': path, 'raw': raw}
                for path, raw in sorted(model.source_files.items())], units=_units(plan))


def _evidence(task, plan, assessment_sha256):
    return canonical_json_bytes({'format_version': 'native-change-preparation-v1',
        'unit_id': task['unit_id'], 'phase': task['phase'], 'plan_sha256': plan.sha256,
        'assessment_sha256': assessment_sha256})


def _checked_work(current, registry, build):
    current = _compatible_read(read_work_manifest, current.raw, current.objects,
                               registry=registry, expected_tool_build=build)
    value = current.as_dict()
    _require(value['command_class'] == 'normative_write' and value['state'] == 'running',
             'normative_preparation_required')
    plan = _compatible_read(read_plan, value, current.objects)
    tasks = current.entries('tasks')
    _require([{key: task[key] for key in ('key', 'phase', 'range')} for task in tasks]
             == _units(plan), 'unsupported_normative_preparation_plan')
    done = current.entries('completed')
    _require([row['unit_id'] for row in done]
             == [task['unit_id'] for task in tasks[:len(done)]],
             'normative_preparation_order_changed')
    assessment = None
    for row, task in zip(done, tasks):
        raw = _bytes(row['evidence'], current.objects)
        record = _compatible_read(parse_json_object, raw)
        digest = record.get('assessment_sha256')
        _require(type(digest) is str and len(digest) == 64
                 and all(c in '0123456789abcdef' for c in digest),
                 'invalid_normative_preparation_evidence')
        _require(raw == _evidence(task, plan, digest),
                 'invalid_normative_preparation_evidence')
        _require(assessment is None or assessment == digest,
                 'normative_preparation_assessment_changed')
        assessment = digest
    return current, plan


def _assessment_sha256(current):
    row = current.entries('completed')[0]
    return parse_json_object(_bytes(row['evidence'], current.objects))['assessment_sha256']


def _arguments(store, registry, model, policy, actor, request_id):
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    _require(type(model) is TargetModel and type(policy) is TargetPolicy,
             'current_resume_model_and_policy_required')
    if not any(boundary.root == Path(model.binding.source_root)
               for boundary in store._location._protected):
        raise WorkResumeError('unprotected_resume_target', exit_code=7)
    build = _runtime_build()
    check_initial_normative(store, registry, build)
    _checked_work(store._initial, registry, build)
    current_actor = normalize_authoring_actor(actor).as_fields()
    identity = normalize_request_id(request_id)
    current_request = None if identity is None else identity.value
    value = store._initial.as_dict()
    _require(current_actor == value['actor'], 'resume_actor_changed')
    _require(current_request == value['request_id'], 'resume_request_changed')
    _require(model.binding.project_id == value['source_bindings']['project_id'],
             'resume_project_changed')
    return build


def _source(model):
    source = ProjectSource(model.binding.source_root,
                           expected_project_id=model.binding.project_id)
    _require(source.boundary._root_identity == model.binding.root_identity,
             'resume_project_root_changed')
    return source


def _transaction_clear(model):
    # Observe only. A Work call never invokes automatic transaction recovery.
    state = transaction_preflight(model.binding.source_root,
                                  command_class=CommandClass.READ_ONLY)
    if not state.data['transaction_preflight_passed']:
        raise WorkResumeError('normative_transaction_requires_recovery',
                              exit_code=state.exit_code)


def _current_target(check, *args, **kwargs):
    try:
        return check(*args, **kwargs)
    except (TargetError, PublicationCheckError) as error:
        if error.reason == 'target_base_root_mismatch':
            raise WorkResumeError('stale_resume_target', exit_code=6) from error
        raise


def advance_normative_preparation(store, *, registry, model, policy, actor,
                                  request_id, gates=(), strict=False, package_files=()):
    """Confirm one whole preparation phase and release the Work lease.

    No native project lock, journal or receipt is created. Completed phases are
    reused; publication independently repeats all mandatory current checks.
    """
    build = _arguments(store, registry, model, policy, actor, request_id)
    current = _compatible_read(store.read)
    _require(current is not None, 'published_work_required')
    _checked_work(current, registry, build)
    _transaction_clear(model)

    def prepare(previous):
        current, plan = _checked_work(previous, registry, build)
        _require(_runtime_build() == build, 'runtime_build_changed')
        _transaction_clear(model)
        remaining = current.entries('remaining')
        if not remaining:
            return previous
        task = remaining[0]
        if task['phase'] == 'target_assessment':
            checked = _current_target(assess_change_target, plan, model,
                                      policy=policy, gates=gates, strict=strict)
            if not checked.target_validated:
                raise PublicationCheckError('publication_target_not_validated', exit_code=3)
            digest = checked.sha256
        else:
            check = _current_target(prepare_publication_check, plan, model,
                policy=policy, gates=gates, strict=strict, package_files=package_files)
            digest = check.request.data['assessment_sha256']
            _require(digest == _assessment_sha256(current),
                     'normative_preparation_assessment_changed')
        _require(_runtime_build() == build, 'runtime_build_changed')
        return partition_work_manifest(current, {task['unit_id']: _evidence(task, plan, digest)})

    result = store._update(prepare)
    _require(_runtime_build() == build, 'runtime_build_changed')
    return result


@dataclass(frozen=True, init=False)
class NormativeWorkPublication:
    """Verified native receipt, separate from final normative Work delivery."""

    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use publish_normative_work')

    def as_dict(self):
        return parse_json_object(self._raw)

    def __bool__(self):
        raise TypeError('Inspect the confirmed transaction result explicitly')


def _publication_result(current, resolution, completion, *, published):
    value = current.as_dict()
    resolved, committed = resolution.data, completion.data
    _require(resolved['action'] == 'replay' and resolved['receipt_verified'],
             'normative_receipt_required')
    result_object = resolved['result_object']
    # The two native readers each verify their own observation. Bind those
    # observations to one receipt before combining them into a Work result.
    _require(committed['commit_completed'] and committed['receipt_verified']
             and committed['state'] == 'committed'
             and committed['transaction_id'] == result_object['transaction_id']
             and committed['request_id'] == resolved['request_id'] == value['request_id']
             and committed['project_id'] == resolved['original_request']['project_id']
                 == value['source_bindings']['project_id']
             and committed['target_model_root_sha256'] == result_object['target_model_root_sha256']
             and committed['receipts']['request'] == resolved['receipt'],
             'normative_receipt_binding_changed')
    result = object.__new__(NormativeWorkPublication)
    object.__setattr__(result, '_raw', canonical_json_bytes({
        'format_version': 'normative-work-publication-v1', 'work_id': value['work_id'],
        'checkpoint_generation': value['checkpoint_generation'],
        'checkpoint_sha256': value['checkpoint_sha256'], 'checkpoint_changed': False,
        'work_completion_recorded': False, 'publication_performed': published,
        'transaction': committed, 'request_resolution': resolved,
        'result_object': result_object}))
    return result


def publish_normative_work(store, *, registry, model, policy, actor, request_id,
                           transaction_id, authority, gates=(), strict=False,
                           package_files=()):
    """Run one unbroken native transaction, or replay its already proven receipt.

    No Work generation is published during this call. Native failures retain
    their journals, receipts and actual file state for existing recovery; this
    function never resumes a transaction, retries, rebases or rolls back.
    """
    build = _arguments(store, registry, model, policy, actor, request_id)
    _require(type(authority) is PublicationAuthority, 'trusted_publication_authority_required')
    with store._location.inspect_checkpoint() as work:
        pointer, current = restore_normative_checkpoint(store, work, registry, build)
        current, plan = _checked_work(current, registry, build)

        def ensure_work():
            _require(_runtime_build() == build, 'runtime_build_changed')
            _require(store._pointer(work) == pointer, 'checkpoint_pointer_changed')
            _require(_compatible_read(store._read_chain, work, pointer[0]).raw == current.raw,
                     'checkpoint_bytes_changed')
            _require(store._pointer(work) == pointer, 'checkpoint_pointer_changed')
            work.check()

        source = _source(model)
        resolution = resolve_normative_request(source, bind_plan_authoring(plan))
        if resolution.data['action'] == 'replay':
            completion = read_transaction_completion(source,
                resolution.data['result_object']['transaction_id'])
            ensure_work()
            return _publication_result(current, resolution, completion, published=False)
        _require(not current.entries('remaining'), 'normative_preparation_incomplete')
        _transaction_clear(model)
        preflight = _current_target(prepare_publication_check, plan, model,
            policy=policy, gates=gates, strict=strict, package_files=package_files)
        _require(preflight.request.data['assessment_sha256'] == _assessment_sha256(current),
                 'normative_preparation_assessment_changed')
        ensure_work()

        def authorize(request):
            ensure_work()
            allowed = authority.check(request)
            ensure_work()
            return allowed

        guarded = PublicationAuthority(authority.authority_id, authority.version, authorize)
        with project_lock(model.binding.source_root, kind='writer', command='change apply',
                project_id=model.binding.project_id, request_id=plan.data['request_id'],
                transaction_id=transaction_id) as held:
            ensure_work()
            building = begin_building_journal(preflight, held_lock=held,
                transaction_id=transaction_id, authority=guarded, gates=gates)
            prepared = stage_building_journal(preflight, building, held_lock=held,
                                              authority=guarded, gates=gates)
            published = publish_prepared_journal(preflight, prepared, held_lock=held,
                                                 authority=guarded, gates=gates)
            journal = read_committing_journal(_source(model), transaction_id,
                expected_sha256=published.data['journal_sha256'], preflight=preflight)
            finalize_committing_journal(preflight, journal, held_lock=held,
                                        authority=guarded, gates=gates)
            completion = cleanup_completed_transaction(preflight, transaction_id,
                                                       held_lock=held, authority=guarded)
            ensure_work()
            resolution = resolve_normative_request(_source(model), bind_plan_authoring(plan))
        ensure_work()
        return _publication_result(current, resolution, completion, published=True)
