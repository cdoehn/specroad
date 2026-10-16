"""Bounded input capture followed by the existing saved-plan Work protocol.

Capture resumes within its live invocation. Once sealed, the ordinary Work
codec/store owns durable continuation. Whole-model planning is still in memory;
this adapter makes no streaming-parser or constant-memory claim.
"""
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


class BaselineSnapshotConflict(ModelError):
    exit_code = 6


class BaselineSnapshotTask:
    """Capture exactly the supplied model's inputs without changing the project.

    The native capture guard coordinates with cooperative writers. Publication
    later rechecks the full current inventory under the existing writer lock.
    """

    def __init__(self, model, *, block_bytes=65536):
        from ..changes.target_model import TargetModel
        from ..security import ProjectBoundary
        from ..work.snapshot import InputSnapshotTask
        if type(model) is not TargetModel:
            raise ModelError('baseline_target_model_required')
        model = model.snapshot()
        boundary = ProjectBoundary(model.binding.source_root)
        if boundary._root_identity != model.binding.root_identity:
            raise BaselineSnapshotConflict('baseline_snapshot_root_changed')
        self._model = model
        self._capture = InputSnapshotTask({'project': boundary},
            [{'root_id': 'project', 'path': path} for path in sorted(model.source_files)],
            block_bytes=block_bytes)
        self._verified = False
        self._failure = None

    def advance(self, max_units):
        if self._failure is not None:
            raise BaselineSnapshotConflict(**self._failure)
        state = self._capture.advance(max_units)
        if state['complete'] and not self._verified:
            for path, expected in sorted(self._model.source_files.items()):
                if self._capture.read_input('project', path) != expected:
                    self._failure = {'reason': 'baseline_snapshot_source_changed', 'path': path}
                    self._capture.close()
                    raise BaselineSnapshotConflict(**self._failure)
            self._verified = True
        return self.state

    @property
    def state(self):
        return parse_json_object(canonical_json_bytes({
            'format_version': 'baseline-input-capture-v1', 'capture': self._capture.state,
            'project_id': self._model.binding.project_id,
            'source_binding_verified': self._verified, 'binding_error': self._failure,
            'validation_scope': 'supplied_target_model_inputs',
            'baseline_created': False, 'write_authorized': False, 'durable_checkpoint': False}))

    def prepare_working_plan(self, **options):
        """Return the unchanged native preview only after all inputs are bound."""
        from .creation import prepare_working_baseline
        if self._failure is not None:
            raise BaselineSnapshotConflict(**self._failure)
        if not self._verified:
            raise ModelError('baseline_snapshot_incomplete')
        return prepare_working_baseline(self._model, **options)

    def prepare_work(self, registry, **options):
        """Return inert Work data; the caller explicitly publishes its checkpoint."""
        from ..changes import ChangePlan
        from ..work.publication import prepare_normative_work
        preview = self.prepare_working_plan(**options)
        if not preview['target_validated']:
            raise ModelError('baseline_snapshot_target_validation_required')
        return prepare_normative_work(registry,
            ChangePlan(canonical_json_bytes(preview['plan'])), model=self._model)

    def close(self):
        self._capture.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __reduce__(self):
        raise TypeError('Live Baseline capture tasks cannot be serialized')

    def __copy__(self):
        raise TypeError('Live Baseline capture tasks cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('Live Baseline capture tasks cannot be copied')


def _baseline_work_inputs(store, model, gates):
    from ..authoring.plans import _execution_inputs
    from ..work._normative_binding import read_plan
    from ..work.checkpoints import CheckpointStore
    if type(store) is not CheckpointStore:
        raise ModelError('baseline_work_store_required')
    plan = read_plan(store._initial.as_dict(), store._initial.objects)
    value = plan.data
    operations = value['operations']
    if len(operations) != 1 or operations[0]['op'] != 'baseline_create':
        raise ModelError('baseline_work_plan_required')
    _, policy, gates = _execution_inputs(model, 'baseline.create', operations,
        value['actor'], value['planned_at'], gates)
    return policy, gates


def advance_baseline_work(store, *, registry, model, actor, request_id,
                          gates=(), strict=False, package_files=()):
    """Confirm one existing Work preparation phase with native Baseline gates."""
    from ..work.publication import advance_normative_preparation
    policy, gates = _baseline_work_inputs(store, model, gates)
    return advance_normative_preparation(store, registry=registry, model=model,
        policy=policy, actor=actor, request_id=request_id, gates=gates,
        strict=strict, package_files=package_files)


def publish_baseline_work(store, *, registry, model, actor, request_id,
                          transaction_id, authority, gates=(), strict=False, package_files=()):
    """Publish the exact saved Baseline once through the native Work transaction."""
    from ..work.publication import publish_normative_work
    policy, gates = _baseline_work_inputs(store, model, gates)
    return publish_normative_work(store, registry=registry, model=model,
        policy=policy, actor=actor, request_id=request_id, gates=gates, strict=strict,
        package_files=package_files, transaction_id=transaction_id, authority=authority)
