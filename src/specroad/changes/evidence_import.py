"""Publish a complete Generic import through the native Evidence/target gates.

The initial writer profile consumes an explicitly supplied existing attachment.
Original bytes and imported attachments are never fetched, rewritten or inferred.
One saved operation sequence binds the complete preparation and all new IDs.
"""
from hashlib import sha256

from ..configurations import resolve_configuration
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.identities import ArtifactIdentity, IdentityAllocation, IdentityInventory
from ..model.paths import classify_path, PathClass, project_path
from ..storage.domain_artifact import DomainArtifact
from ..storage.record_artifact import RecordArtifact
from ..validation import ModelGate
from ..verification import (VerificationContract, VerificationTest,
    prepare_generic_import, prepare_evidence_record)
from ._fold_inputs import _inventory, _relation_inventory, _preflight, _files
from ._metadata_policy import bind_policy
from ._patch_values import _snapshot
from .evidence import _EvidenceCandidates, _record, _run_history, _bound_attachments
from .metadata_values import MetadataArtifact
from .target_values import TargetError
from .target_model import TargetModel
from .values import ChangeOperation


class EvidenceImportDuplicate(TargetError):
    """A candidate matches historical measurements, without request replay."""
    def __init__(self, matches):
        super().__init__('evidence_import_semantic_duplicate')
        self._matches = _snapshot(matches)

    def diagnostic(self):
        return {**super().diagnostic(), 'semantic_duplicates': self._matches.data,
                'write_state': 'not_committed', 'approval_granted': False}


def _measurement_key(value):
    fields = ('configuration_hash', 'configuration_policy', 'producer', 'tool',
              'run_context', 'result', 'produced_at', 'environment')
    return canonical_json_sha256({'format_version': 'evidence-semantic-duplicate-v1',
        **{k: value[k] for k in fields},
        'subjects': sorted(value['subjects'], key=lambda item: item['artifact_id'])})


def _duplicates(model, candidates):
    existing = {}
    for document in model.documents:
        value = SourceRelations(document.content).data
        if value['artifact_type'] == 'evidence':
            record = RecordArtifact(document.content, expected_type='evidence').data
            existing.setdefault(_measurement_key(record), []).append(record['id'])
    matches = []
    # Only historical records are indexed. Repeated occurrences within one new
    # input stay separate; neither successes nor failures are silently dropped.
    for index, candidate in enumerate(candidates):
        key = _measurement_key(candidate)
        if key in existing:
            matches.append({'candidate_index': index, 'source_pointer': candidate['source_pointer'],
                'semantic_sha256': key, 'evidence_ids': sorted(existing[key])})
    return matches


def diagnose_generic_import_duplicates(model, *, source_path, policy):
    """Read-only duplicate observation over explicitly supplied native bytes."""
    if type(model) is not TargetModel:
        raise TargetError('typed_evidence_import_model_required')
    model = model.snapshot()
    _, data, context, _ = _input(model, source_path, policy)
    matches = _duplicates(model, data['candidates'])
    return {'format_version': 'evidence-semantic-duplicate-v1',
        'source_sha256': context['source_sha256'], 'preparation_sha256': context['preparation_sha256'],
        'matches': matches, 'duplicate_count': len(matches), 'write_authorized': False,
        'current_target_verified': False, 'approval_granted': False}


def import_mode(operations):
    selected = any('import_context' in op for op in operations)
    if selected and (not operations or any(op['op'] != 'evidence_record'
            or op.get('import_context') != operations[0].get('import_context')
            or op.get('configuration_id') != operations[0].get('configuration_id')
            for op in operations)):
        raise TargetError('evidence_import_requires_one_bound_set')
    return selected


def _input(model, source_path, policy):
    project_path(source_path)
    descriptors = {a.path: a.data for a in model.attachment_descriptors}
    raw = {d.path: d.content for d in model.resource_files}.get(source_path)
    descriptor = descriptors.get(source_path)
    if (descriptor is None or raw is None
            or classify_path(source_path, model.configuration) is not PathClass.ATTACHMENT
            or len(raw) != descriptor['size'] or sha256(raw).hexdigest() != descriptor['sha256']):
        raise TargetError('evidence_import_original_attachment_required')
    targets = {}
    kinds = {'requirement': DomainArtifact, 'verification': VerificationContract, 'test': VerificationTest}
    for document in model.documents:
        value = SourceRelations(document.content).data
        if value['artifact_type'] in kinds:
            targets[value['id']] = kinds[value['artifact_type']](document.content)
    prepared = prepare_generic_import(raw, targets=list(targets.values()), policy=policy)
    data = prepared.data
    if data['decision'] != 'prepared':
        raise TargetError('evidence_import_aborted')
    if not data['candidates']:
        raise TargetError('evidence_import_nonempty_set_required')
    context = {'format_version': 'evidence-import-context-v1', 'import_format': 'generic',
        'source_path': source_path, 'source_sha256': sha256(raw).hexdigest(),
        'preparation_sha256': prepared.sha256, 'policy': policy}
    return targets, data, context, descriptor


def _operation(model, targets, data, context, original, candidate, *, evidence_id,
               title, configuration_id, actor, planned_at):
    contract_id = candidate['target']['artifact_id']
    contract = targets[contract_id]
    if type(contract) is not VerificationContract:
        raise TargetError('evidence_import_explicit_contract_target_required')
    subject_ids = [s['artifact_id'] for s in candidate['subjects']]
    subjects = [targets[i] for i in subject_ids if type(targets[i]) is DomainArtifact]
    test_id = candidate['run_context']['test_id']
    test = None if test_id is None else targets[test_id]
    expected_ids = {contract_id, *(s.data['id'] for s in subjects)}
    if test_id is not None:
        expected_ids.add(test_id)
    if set(subject_ids) != expected_ids:
        raise TargetError('evidence_import_subject_set_mismatch')
    configuration = (None if configuration_id is None else resolve_configuration(
        tuple(SourceRelations(d.content, path=d.path) for d in model.documents), configuration_id))
    identity = ArtifactIdentity(evidence_id, 'random128-v1', 'evidence', model.configuration.id_prefix)
    allocation = IdentityAllocation(identity, IdentityInventory(
        model.configuration.id_prefix, [a['id'] for a in model.artifacts], (), (identity.id,)))
    record = prepare_evidence_record(subjects, contract, allocation=allocation,
        configuration=configuration, actor=actor, planned_at=planned_at, title=title,
        test=test, **{k: candidate[k] for k in ('result', 'produced_at', 'producer',
            'tool', 'environment', 'origin', 'run_context')}).data
    if any(record[k] != candidate[k] for k in ('configuration_hash', 'configuration_policy')):
        raise TargetError('evidence_import_configuration_mismatch')
    attachments = {a['path']: a for a in candidate['attachments']}
    if original['path'] in attachments and attachments[original['path']] != original:
        raise TargetError('evidence_import_original_attachment_conflict')
    attachments[original['path']] = original
    record['attachments'] = _bound_attachments(model, [attachments[p] for p in sorted(attachments)])
    record['provenance'] = [{'locator': original['path'], 'captured_at': planned_at,
        'content_sha256': original['sha256'], 'extensions': {'specroad.evidence-import': {
            'provenance': data['provenance'], 'preparation_sha256': context['preparation_sha256'],
            'source_pointer': candidate['source_pointer'], 'policy': context['policy']}}}]
    return {'op': 'evidence_record', 'evidence': record, 'configuration_id': configuration_id,
            'import_context': context}


def prepare_generic_operations(model, *, source_path, policy, evidence_ids, title,
                               configuration_id=None, actor, planned_at):
    """Construct the entire explicit set without allocating IDs or writing."""
    model = model.snapshot()
    targets, data, context, original = _input(model, source_path, policy)
    matches = _duplicates(model, data['candidates'])
    if matches:
        raise EvidenceImportDuplicate(matches)
    if (type(evidence_ids) not in (list, tuple) or len(evidence_ids) != len(data['candidates'])
            or any(type(i) is not str for i in evidence_ids) or len(set(evidence_ids)) != len(evidence_ids)):
        raise TargetError('evidence_import_distinct_ids_for_complete_set_required')
    operations = [ChangeOperation(_operation(model, targets, data, context, original, candidate,
        evidence_id=identity, title=title, configuration_id=configuration_id,
        actor=actor, planned_at=planned_at)).data
        for identity, candidate in zip(evidence_ids, data['candidates'])]
    return operations, data


def prepare_import_candidates(model, operations, *, metadata_policy_version,
                              actor, planned_at, preconditions=()):
    """Recompute the full set from owned originals, then retain native guards."""
    owned = [ChangeOperation(value).data for value in operations]
    if not import_mode(owned):
        raise TargetError('evidence_import_operations_required')
    metadata = bind_policy(metadata_policy_version, actor, planned_at)
    state, seen, _ = _inventory(model.artifacts,
        [*model.reserved_artifact_ids, *model.previously_approved_ids])
    _relation_inventory(state, model.reserved_relation_ids)
    _preflight(state, preconditions, _files(model.source_files))
    context = owned[0]['import_context']
    targets, data, expected_context, original = _input(model, context['source_path'], context['policy'])
    if context != expected_context or len(owned) != len(data['candidates']):
        raise TargetError('evidence_import_complete_preparation_mismatch')
    matches = _duplicates(model, data['candidates'])
    if matches:
        raise EvidenceImportDuplicate(matches)
    candidates = []
    for index, (operation, candidate) in enumerate(zip(owned, data['candidates'])):
        value = operation['evidence']
        identity = value['id']
        if identity in seen:
            raise TargetError('evidence_identity_exists', pointer='/evidence/id')
        expected = _operation(model, targets, data, context, original, candidate,
            evidence_id=identity, title=value['title'], configuration_id=operation.get('configuration_id'),
            actor=metadata['actor'], planned_at=planned_at)
        if canonical_json_bytes(expected) != canonical_json_bytes(operation):
            raise TargetError('evidence_import_record_binding_mismatch')
        # The shared single-record guard checks its original fields. Provenance
        # is generated and compared above; callers cannot attach arbitrary data.
        plain = {k: v for k, v in value.items() if k != 'provenance'}
        _record(model, state, {'evidence': plain, 'configuration_id': operation.get('configuration_id')},
                metadata['actor'], planned_at)
        _run_history(state, value)
        state[identity] = value
        seen.add(identity)
        candidates.append(MetadataArtifact(identity, _snapshot(value), None,
            canonical_json_sha256(value), (index,), 'created'))
    history = tuple(sorted(set(model.previously_approved_ids) |
        {a['id'] for a in model.artifacts if a['maturity'] == 'approved'}))
    return _EvidenceCandidates(_snapshot([state[key] for key in sorted(state)]), tuple(candidates), history)


def prepare_import_gates(model, operations, *, actor, planned_at, gates=()):
    """Certify the complete imported target, without approving old Evidence."""
    owned = model.snapshot()
    values = [ChangeOperation(op).data for op in operations]
    if not import_mode(values):
        raise TargetError('evidence_import_operations_required')
    metadata = bind_policy('change-metadata-v1', actor, planned_at)
    identities = {op['evidence']['id'] for op in values}
    context_ids = identities | {s['artifact_id'] for op in values for s in op['evidence']['subjects']}
    bound = canonical_json_sha256({'sources': owned._sources_sha256, 'operations': values,
                                   'metadata': metadata})

    def dependencies(context):
        return context.dependency_result({key: list(context.all_ids) for key in context.subjects})

    def check(context):
        folded = prepare_import_candidates(owned, values, **metadata)
        if canonical_json_sha256({a['id']: a for a in folded.artifacts}) != canonical_json_sha256(
                {key: context.artifact(key) for key in context.all_ids}):
            return context.result([{'reason': 'evidence_import_target_mismatch', 'severity': 'error'}])
        return context.result()

    def limited(allowed):
        def scoped(context):
            if not set(context.subjects) <= allowed:
                return context.result([{'reason': 'evidence_existing_subjects_require_service',
                                        'severity': 'error'}])
            return check(context)
        return scoped

    existing = {g.gate_id for g in gates if type(g) is ModelGate}
    prepared = (ModelGate('extension:evidence-import', 'evidence-import-v1', dependencies, check, bound),)
    for name, allowed in (('lifecycle', identities), ('external_resources', identities),
                          ('evidence_currentness', context_ids)):
        if name not in existing:
            prepared += (ModelGate(name, 'evidence-import-v1', dependencies, limited(allowed), bound),)
    selected_id = values[0].get('configuration_id')
    if selected_id is not None:
        from ..configurations._gate_context import _ConfigurationGateContext
        from ..configurations.gates import _bound_configuration_gate
        selected = _ConfigurationGateContext(tuple(SourceRelations(d.content, path=d.path)
            for d in owned.documents), selected_id)
        prepared += (_bound_configuration_gate(selected),)
    return prepared
