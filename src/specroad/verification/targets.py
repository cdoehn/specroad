"""Resolve an explicit contract or the normative implicit contract of a test.

An implicit contract is a projection of the stored test, never a synthesized
Verification record. Procedure, method and configuration policy are not guessed
from the test type. Evidence evaluation and execution remain separate.
"""

from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from .contracts import (VerificationContractResolution, VerificationTest, _binding,
                        resolve_verification_contract)


def resolve_verification_target(model, subject_id, target_id):
    """Bind all required checks of one actual verified_by target.

Explicit Verification targets retain the existing explicit-contract API result.
A direct Test target uses its own ID as contract_id and test_id and contributes
exactly the overall slot. A lookup never uses titles, paths or external IDs in
place of the relation's actual artifact identity.
"""
    from ..changes.target_model import TargetModel, _default_scope
    from ..model.domain_schemas import DOMAIN_TYPES
    from ..storage.domain_artifact import DomainArtifact
    from ..storage.record_artifact import RecordArtifact
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    for field, value in (('subject_id', subject_id), ('target_id', target_id)):
        if type(value) is not str:
            raise ModelError('artifact_id_required', pointer='/' + field)
    model = model.snapshot()
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    index = {record.identity.id: record for record in records}
    for field, value in (('subject_id', subject_id), ('target_id', target_id)):
        if value not in index:
            raise ModelError('verification_artifact_not_found', pointer='/' + field)
    source, target = index[subject_id], index[target_id]
    if target.identity.artifact_type == 'verification':
        return resolve_verification_contract(model, subject_id, target_id)
    if target.identity.artifact_type != 'test':
        raise ModelError('verification_or_test_target_required', path=target.path, pointer='/target_id')
    test = VerificationTest(target.source_bytes, path=target.path)
    reader = DomainArtifact if source.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
    reader(source.source_bytes, path=source.path)
    RelationReferences(records)
    edges = [(position, relation) for position, relation in enumerate(source.relations)
             if relation.type == 'verified_by' and relation.target == target_id]
    if not edges:
        raise ModelError('verification_relation_required', path=source.path, pointer='/relations')
    descriptor = _default_scope()
    data = {'format_version': 'verification-contract-v1', 'project_id': model.binding.project_id,
            'scope_descriptor': descriptor,
            'model_root_sha256': model.manifest(model.artifacts, descriptor).sha256,
            'input_sha256': model._sources_sha256,
            'validation_scope': 'supplied_model_implicit_test_contract',
            'subject': _binding(source.source_bytes, source.path), 'contract': test.binding,
            'implicit_contract': {'contract_id': target_id, 'test_id': target_id,
                'dimensions': ['overall'],
                'evidence_slots': [{'check_id': 'overall', 'test_id': target_id, 'dimension': 'overall'}]},
            'relations': [{'relation_id': relation.identity.id,
                           'pointer': '/relations/' + str(position),
                           'record': relation.data,
                           'record_sha256': canonical_json_sha256(relation.data)}
                          for position, relation in edges],
            'tests': [test.binding],
            'required_checks': [{'subject_artifact_id': subject_id, 'contract_id': target_id,
                                 'test_id': target_id, 'check_id': 'overall', 'dimension': 'overall'}],
            'project_files_verified': False, 'full_validation_passed': False,
            'project_required_checks_complete': False, 'configuration_applicability_evaluated': False,
            'evidence_evaluated': False, 'test_code_executed': False,
            'write_authorized': False, 'approval_granted': False}
    result = object.__new__(VerificationContractResolution)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
