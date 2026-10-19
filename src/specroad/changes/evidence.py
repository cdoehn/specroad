"""Isolated Evidence creation with byte-derived bindings and native write gates.

Prepared identities and measurements are explicit inputs. Existing records are
immutable observations, not approvals or a selected successful verification run.
Attachment bytes already belong to the supplied project; this service never
imports files or creates an alternate publication path.
"""
from dataclasses import dataclass

from ..configurations import resolve_configuration
from ..graph.relations import SourceRelations
from ..model.attachments import AttachmentDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.identities import IdentityAllocation, IdentityInventory
from ..model.identity_values import artifact_identity
from ..model.paths import classify_path, PathClass
from ..storage.domain_artifact import DomainArtifact
from ..validation import ModelGate
from ..verification import VerificationContract, VerificationTest, prepare_evidence_record
from ._fold_inputs import _inventory, _relation_inventory, _preflight, _files
from ._metadata_policy import bind_policy
from ._patch_values import _snapshot
from .metadata_values import MetadataArtifact
from .target_values import TargetError
from .values import ChangeOperation


def evidence_mode(operations):
    selected = any(op['op'] == 'evidence_record' for op in operations)
    if selected and len(operations) != 1:
        raise TargetError('evidence_requires_one_isolated_operation', pointer='/operations')
    return selected


def _record(model, state, operation, actor, planned_at):
    value = operation['evidence']
    subjects, contracts, tests = [], [], []
    documents = {SourceRelations(d.content).identity.id: d for d in model.documents}
    for binding in value['subjects']:
        identity = binding['artifact_id']
        if identity not in state:
            raise TargetError('evidence_subject_missing', pointer='/evidence/subjects')
        document = documents[identity]
        kind = state[identity]['artifact_type']
        if kind == 'requirement':
            subjects.append(DomainArtifact(document.content, expected_type=kind, path=document.path))
        elif kind == 'verification':
            contracts.append(VerificationContract(document.content, path=document.path))
        elif kind == 'test':
            tests.append(VerificationTest(document.content, path=document.path))
        else:
            raise TargetError('evidence_subject_kind_not_supported', pointer='/evidence/subjects')
    if len(contracts) != 1 or len(tests) > 1:
        raise TargetError('evidence_explicit_contract_and_test_required', pointer='/evidence/subjects')
    selected_id = operation.get('configuration_id')
    configuration = (None if selected_id is None else resolve_configuration(
        tuple(SourceRelations(d.content, path=d.path) for d in model.documents), selected_id))
    identity = artifact_identity(value)
    allocation = IdentityAllocation(identity, IdentityInventory(
        model.configuration.id_prefix, list(state), (), (identity.id,)))
    expected = prepare_evidence_record(subjects, contracts[0], allocation=allocation,
        configuration=configuration, actor=actor, planned_at=planned_at,
        test=None if not tests else tests[0], unbound_reason=value.get('unbound_reason'),
        **{key: value[key] for key in ('title', 'result', 'produced_at', 'producer',
            'tool', 'environment', 'origin', 'run_context')}).data
    if 'attachments' in value:
        declared = [AttachmentDescriptor.from_data(item) for item in value['attachments']]
        available = {item.path: item.data for item in model.attachment_descriptors}
        if len({item.path.casefold() for item in declared}) != len(declared):
            raise TargetError('evidence_attachment_path_collision', pointer='/evidence/attachments')
        for item in declared:
            if (classify_path(item.path, model.configuration) is not PathClass.ATTACHMENT
                    or available.get(item.path) != item.data):
                raise TargetError('evidence_attachment_binding_mismatch', pointer='/evidence/attachments')
        expected['attachments'] = [item.data for item in declared]
    if canonical_json_bytes(expected) != canonical_json_bytes(value):
        raise TargetError('evidence_record_binding_mismatch', pointer='/evidence')
    return expected


def _run_history(state, record):
    run = record['run_context']
    if run is None:
        return
    for previous in state.values():
        if previous['artifact_type'] != 'evidence' or previous['run_context'] is None:
            continue
        old = previous['run_context']
        if (old['run_id'] == run['run_id'] and any(old[key] != run[key]
                for key in ('subject_id', 'subject_state_sha256'))):
            raise TargetError('evidence_run_identity_conflict', pointer='/evidence/run_context')


@dataclass(frozen=True)
class _EvidenceCandidates:
    _model: object
    candidates: tuple
    _history: tuple

    @property
    def artifacts(self): return self._model.data
    @property
    def metadata_applied(self): return True
    @property
    def decisions(self): return []
    @property
    def previously_approved_ids(self): return list(self._history)


def prepare_evidence_candidates(model, operations, *, metadata_policy_version,
        actor, planned_at, preconditions=()):
    """Rebuild one new record from actual inputs; reject mutation and rebinding."""
    owned = [ChangeOperation(value).data for value in operations]
    if not evidence_mode(owned):
        raise TargetError('evidence_operation_required')
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    state, seen, _ = _inventory(model.artifacts,
        [*model.reserved_artifact_ids, *model.previously_approved_ids])
    _relation_inventory(state, model.reserved_relation_ids)
    _preflight(state, preconditions, _files(model.source_files))
    value = owned[0]['evidence']
    identity = artifact_identity(value)
    if identity.id in seen:
        raise TargetError('evidence_identity_exists', pointer='/evidence/id')
    if identity.id_prefix != model.configuration.id_prefix:
        raise TargetError('mixed_project_prefix', pointer='/evidence/id')
    if identity.id_scheme != 'random128-v1':
        raise TargetError('new_identity_requires_random128', pointer='/evidence/id_scheme')
    expected = _record(model, state, owned[0], metadata['actor'], planned_at)
    _run_history(state, expected)
    state[identity.id] = expected
    candidate = MetadataArtifact(identity.id, _snapshot(expected), None,
        canonical_json_sha256(expected), (0,), 'created')
    history = tuple(sorted(set(model.previously_approved_ids) |
        {a['id'] for a in model.artifacts if a['maturity'] == 'approved'}))
    return _EvidenceCandidates(_snapshot([state[key] for key in sorted(state)]),
                               (candidate,), history)


def prepare_evidence_gates(model, operation, *, actor, planned_at, gates=()):
    """Validate the new recording only; unrelated semantic services stay required.

    Old Evidence may be stale without being rewritten or promoted to current.
    The host must provide gates for other lifecycle/currentness subjects. This
    command gate always rechecks the exact record, whole target and run history.
    """
    owned = model.snapshot()
    value = ChangeOperation(operation.data).data
    identity = value['evidence']['id']
    metadata = bind_policy('change-metadata-v1', actor, planned_at)
    bound = canonical_json_sha256({'sources': owned._sources_sha256,
        'operation': value, 'metadata': metadata})
    context_ids = {identity, *(item['artifact_id'] for item in value['evidence']['subjects'])}

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    def check(context):
        folded = prepare_evidence_candidates(owned, [value], **metadata)
        expected = {a['id']: a for a in folded.artifacts}
        actual = {key: context.artifact(key) for key in context.all_ids}
        if canonical_json_sha256(expected) != canonical_json_sha256(actual):
            return context.result([{'reason': 'evidence_target_mismatch', 'severity': 'error'}])
        return context.result()

    def limited(allowed):
        def scoped(context):
            if not set(context.subjects) <= allowed:
                return context.result([{'reason': 'evidence_existing_subjects_require_service',
                                        'severity': 'error'}])
            return check(context)
        return scoped

    existing = {g.gate_id for g in gates if type(g) is ModelGate}
    prepared = (ModelGate('extension:evidence-record', 'evidence-record-v1',
                          dependencies, check, bound),)
    for name, allowed in (('lifecycle', {identity}), ('external_resources', {identity}),
                          ('evidence_currentness', context_ids)):
        if name not in existing:
            prepared += (ModelGate(name, 'evidence-record-v1', dependencies, limited(allowed), bound),)
    if value.get('configuration_id') is not None:
        from ..configurations._gate_context import _ConfigurationGateContext
        from ..configurations.gates import _bound_configuration_gate
        selected = _ConfigurationGateContext(tuple(SourceRelations(d.content, path=d.path)
            for d in owned.documents), value['configuration_id'])
        prepared += (_bound_configuration_gate(selected),)
    return prepared
