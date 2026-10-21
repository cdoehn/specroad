"""Explicit human Done review and native Task implementation publication.

This path binds a human decision to the complete original Task, supplied
model and unconfigured project scope. It does not invent a Task verification
context hash: Appendix L currently defines that projection for other types.
Review labels are passive input; only the explicitly supplied trusted host
verifier can confirm human origin and current validity. No JSON imports code.
Core requires the reserved Done service on every implemented Task; the native
review service certifies only its own subject, not other labelled Tasks.
"""
from dataclasses import dataclass
import re

from ..changes import ChangeOperation, TargetModel, prepare_change_lifecycle
from ..changes._metadata_policy import bind_policy
from ..changes.update_inputs import normalize_artifact_update_input
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.audit import actor as read_actor
from ..model.audit_values import UtcTimestamp
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from ..validation import ModelGate, ReviewVerifier, ReviewVerification

_GATE = 'task_done'
_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


@dataclass(frozen=True, init=False)
class TaskDoneContext:
    """An exact status-change intention, not a new content-hash projection."""
    _encoded: bytes

    def __init__(self, model, task_id, *, scope_descriptor):
        if type(model) is not TargetModel or type(scope_descriptor) is not ScopeDescriptor:
            raise ModelError('typed_task_done_context_required')
        if type(task_id) is not str:
            raise ModelError('task_implementation_identity_required')
        model = model.snapshot()
        if scope_descriptor.data != _SCOPE:
            raise ModelError('task_done_unconfigured_project_scope_required')
        document = next((d for d in model.documents
                         if parse_json_object(d.content)['id'] == task_id), None)
        if document is None:
            raise ModelError('task_implementation_subject_missing')
        task = DomainArtifact(document.content, expected_type='task').data
        operation = normalize_artifact_update_input(task,
            patch=[{'op': 'replace', 'path': '/implementation_status', 'value': 'implemented'}],
            expected_revision=task['revision'], expected_sha256=canonical_json_sha256(task))
        data = {'format_version': 'task-done-context-v1', 'task_id': task_id,
            'project_id': model.binding.project_id, 'model_sources_sha256': model._sources_sha256,
            'task': task, 'task_sha256': canonical_json_sha256(task),
            'done_criteria_sha256': canonical_json_sha256(task['done_criteria']),
            'scope_descriptor': scope_descriptor.data, 'operation': operation.data}
        object.__setattr__(self, '_encoded', canonical_json_bytes(data))

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def input_sha256(self):
        return canonical_json_sha256(self.data)

    def __bool__(self):
        raise TypeError('A Task context is not a Done proof')


@dataclass(frozen=True, init=False)
class HumanTaskDoneReview:
    """Passive exact-context review; criteria correspond to stored array order."""
    _encoded: bytes

    def __init__(self, data):
        fields = {'review_id', 'input_sha256', 'task_id', 'task_sha256',
            'done_criteria_sha256', 'reviewer', 'reviewed_at', 'decision', 'criteria'}
        if type(data) is not dict or set(data) != fields:
            raise ModelError('task_done_review_fields_invalid')
        raw = canonical_json_bytes(data)
        value = parse_json_object(raw)
        for name in ('review_id', 'task_id'):
            if type(value[name]) is not str or not value[name].strip():
                raise ModelError('task_done_review_identity_required')
        for name in ('input_sha256', 'task_sha256', 'done_criteria_sha256'):
            if type(value[name]) is not str or re.fullmatch('[0-9a-f]{64}', value[name]) is None:
                raise ModelError('task_done_review_hash_required')
        read_actor(value['reviewer']); UtcTimestamp(value['reviewed_at'])
        if type(value['decision']) is not str or value['decision'] not in ('confirmed', 'rejected'):
            raise ModelError('task_done_review_decision_invalid')
        if type(value['criteria']) is not list or any(type(v) is not bool for v in value['criteria']):
            raise ModelError('task_done_review_criteria_invalid')
        object.__setattr__(self, '_encoded', raw)

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)


def _confirmed(context, review, verifier):
    if type(context) is not TaskDoneContext or type(review) is not HumanTaskDoneReview:
        raise ModelError('typed_task_done_review_required')
    value, observed = context.data, review.data
    if (observed['input_sha256'] != context.input_sha256 or
            any(observed[key] != value[key] for key in ('task_id', 'task_sha256', 'done_criteria_sha256'))):
        raise ModelError('task_done_review_binding_mismatch')
    if observed['reviewer']['actor_type'] != 'human':
        raise ModelError('task_done_human_review_required')
    if (observed['decision'] != 'confirmed' or
            len(observed['criteria']) != len(value['task']['done_criteria']) or
            not all(observed['criteria'])):
        raise ModelError('task_done_criteria_unconfirmed')
    if type(verifier) is not ReviewVerifier:
        raise ModelError('task_done_review_verifier_required')
    try:
        result = verifier.check(context, review)
    except Exception as error:
        raise ModelError('task_done_review_verification_failed') from error
    if (type(result) is not ReviewVerification or result.input_sha256 != context.input_sha256
            or result.review_sha256 != review.sha256):
        raise ModelError('task_done_review_verifier_unbound')
    if not result.authenticated_human or not result.current:
        raise ModelError('task_done_review_not_authenticated_or_current')


@dataclass(frozen=True, init=False)
class TaskImplementation:
    """Owned intention and checked review binding, never publication authority."""
    _encoded: bytes
    _context: TaskDoneContext
    _review: HumanTaskDoneReview
    _verifier: ReviewVerifier

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_task_implementation')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    @property
    def operation(self):
        return ChangeOperation(self.data['operation'])

    def __bool__(self):
        raise TypeError('Done review is not publication authority or approval')


def prepare_task_implementation(context, *, review, verifier):
    """Require an exact, current human confirmation of every Done criterion."""
    _confirmed(context, review, verifier)
    value = context.data
    data = {'format_version': 'task-implementation-v1',
        **{key: value[key] for key in ('task_id', 'project_id', 'model_sources_sha256',
            'task_sha256', 'done_criteria_sha256', 'scope_descriptor', 'operation')},
        'input_sha256': context.input_sha256, 'review_id': review.data['review_id'],
        'review_sha256': review.sha256,
        'verifier': {'id': verifier.verifier_id, 'version': verifier.version},
        'validation_scope': 'explicit_task_done_review_update',
        'done_criteria_satisfied': True, 'authenticated_by_supplied_verifier': True,
        'project_files_verified': False, 'release_readiness_evaluated': False,
        'test_code_executed': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(TaskImplementation)
    for name, item in (('_encoded', canonical_json_bytes(data)), ('_context', context),
                       ('_review', review), ('_verifier', verifier)):
        object.__setattr__(result, name, item)
    return result


def implement_task(model, prepared, *, actor, planned_at, change_plan_id,
        transaction_id, authority, request_id=None, gates=(), strict=False, package_files=()):
    """Publish exactly the prepared status update using the ordinary writer.

    The host still supplies other required services and live write authority.
    The native writer checks the complete on-disk base, lock and transaction.
    The human review is rechecked at every target gate, not used as a ticket.
    Retain the original preparation/model for a durable historical retry.
    """
    from ..authoring.update import update_artifact
    if type(model) is not TargetModel or type(prepared) is not TaskImplementation:
        raise ModelError('typed_task_implementation_required')
    if type(gates) not in (tuple, list) or any(type(gate) is not ModelGate for gate in gates):
        raise ModelError('task_implementation_gates_required')
    if any(gate.gate_id in (_GATE, 'extension:task-done') for gate in gates):
        raise ModelError('task_done_gate_override')
    model = model.snapshot()
    context = TaskDoneContext(model, prepared.data['task_id'],
        scope_descriptor=ScopeDescriptor(prepared.data['scope_descriptor']))
    current = prepare_task_implementation(context, review=prepared._review, verifier=prepared._verifier)
    if current.data != prepared.data:
        raise ModelError('task_implementation_preparation_changed')
    operation = current.operation
    metadata = bind_policy('change-metadata-v1', actor, planned_at)
    resources = canonical_json_sha256({'preparation_sha256': current.sha256, 'metadata': metadata})

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    def check(target):
        # One review certifies only its own Task, never an unreviewed neighbour
        # already labelled implemented in the supplied project. The reserved
        # hook is required by Core on every implemented Task, including drafts.
        missing = [key for key in target.subjects if key != context.data['task_id']]
        if missing:
            return target.result([{'reason': 'task_done_review_missing',
                'artifact_id': key, 'severity': 'error'} for key in missing])
        if target.configuration_data is not None:
            return target.result([{'reason': 'task_done_unconfigured_project_scope_required',
                                   'severity': 'error'}])
        _confirmed(context, prepared._review, prepared._verifier)
        folded = prepare_change_lifecycle(model.artifacts, [operation.data],
            **metadata, source_files=model.source_files, **model.reservations)
        expected = {row['id']: row for row in folded.artifacts}
        actual = {key: target.artifact(key) for key in target.all_ids}
        if canonical_json_sha256(expected) != canonical_json_sha256(actual):
            return target.result([{'reason': 'task_done_target_changed', 'severity': 'error'}])
        return target.result()

    gate = ModelGate(_GATE, 'bound-task-done-v2', dependencies, check, resources)
    return update_artifact(model, operation, actor=actor, planned_at=planned_at,
        change_plan_id=change_plan_id, transaction_id=transaction_id, authority=authority,
        request_id=request_id, gates=(*gates, gate), strict=strict, package_files=package_files)
