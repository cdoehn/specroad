"""Owned explicit contracts and the required checks for one subject/contract pair.

Only supplied bytes are inspected. Resolving a contract neither executes its
procedure nor evaluates Evidence, configuration applicability or verification
success. Project-wide required-check aggregation is a separate operation.
"""

from dataclasses import dataclass
from hashlib import sha256

from ..graph.references import RelationReferences
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact


def _binding(raw, path):
    value = parse_json_object(raw, path=path)
    return {'artifact_id': value['id'], 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': path,
            'source_sha256': sha256(raw).hexdigest(),
            'record_sha256': canonical_json_sha256(value), 'record': value}


@dataclass(frozen=True, init=False)
class VerificationContract:
    """A locally complete stored contract, with no inferred default slots."""
    source_bytes: bytes
    path: str | None

    def __init__(self, raw, *, path=None):
        record = RecordArtifact(raw, expected_type='verification', path=path)
        SourceRelations(raw, expected_type='verification', path=path)
        value = record.data
        covered = {slot['dimension'] for slot in value['evidence_slots']}
        for position, dimension in enumerate(value['dimensions']):
            if dimension not in covered:
                raise ModelError('missing_verification_dimension_slot', path=path,
                                 pointer='/dimensions/' + str(position))
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, 'path', path)

    @property
    def data(self):
        return parse_json_object(self.source_bytes, path=self.path)

    @property
    def binding(self):
        return _binding(self.source_bytes, self.path)

    def __bool__(self):
        raise TypeError('A contract is not verification success or approval')


@dataclass(frozen=True, init=False)
class VerificationTest:
    """A passive test identity, type and oracle; the referenced path is not read."""
    source_bytes: bytes
    path: str | None

    def __init__(self, raw, *, path=None):
        RecordArtifact(raw, expected_type='test', path=path)
        SourceRelations(raw, expected_type='test', path=path)
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, 'path', path)

    @property
    def data(self):
        return parse_json_object(self.source_bytes, path=self.path)

    @property
    def binding(self):
        return _binding(self.source_bytes, self.path)

    def __bool__(self):
        raise TypeError('A test reference is not an executed test or approval')


def prepare_verification_contract(value, *, path=None):
    """Prepare a new draft candidate, without writing or changing lifecycle data.

Only absent slots may receive the overall default, and only when no additional
dimensions are declared. Stored records use VerificationContract directly, which
never repairs missing fields. Applying this candidate needs the normal writer.
"""
    candidate = parse_json_object(canonical_json_bytes(value), path=path)
    if candidate.get('maturity') != 'draft' or candidate.get('revision') != 1:
        raise ModelError('new_verification_draft_required', path=path)
    if 'evidence_slots' not in candidate:
        if 'dimensions' not in candidate:
            candidate['dimensions'] = ['overall']
        if candidate['dimensions'] != ['overall']:
            raise ModelError('explicit_verification_slots_required', path=path,
                             pointer='/evidence_slots')
        candidate['evidence_slots'] = [
            {'check_id': 'overall', 'test_id': None, 'dimension': 'overall'}]
    return VerificationContract(canonical_json_bytes(candidate), path=path)


@dataclass(frozen=True, init=False)
class VerificationContractResolution:
    """Bound required checks for one explicit pair, never a project-wide result."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_verification_contract with actual model bytes')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    def __bool__(self):
        raise TypeError('Resolved required checks are not verification success or approval')


def resolve_verification_contract(model, subject_id, contract_id):
    """Resolve every declared slot for an actual verified_by edge.

This first explicit-contract API rejects direct test targets. It does not infer
an implicit contract, choose a subset of slots or execute referenced code. The
supplied model is snapshotted and native relation identity/type checks apply.
"""
    from ..changes.target_model import TargetModel, _default_scope
    from ..model.domain_schemas import DOMAIN_TYPES
    from ..storage.domain_artifact import DomainArtifact
    if type(model) is not TargetModel:
        raise ModelError('verification_target_model_required')
    for field, value in (('subject_id', subject_id), ('contract_id', contract_id)):
        if type(value) is not str:
            raise ModelError('artifact_id_required', pointer='/' + field)
    model = model.snapshot()
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    index = {record.identity.id: record for record in records}
    for field, value in (('subject_id', subject_id), ('contract_id', contract_id)):
        if value not in index:
            raise ModelError('verification_artifact_not_found', pointer='/' + field)
    source, target = index[subject_id], index[contract_id]
    contract = VerificationContract(target.source_bytes, path=target.path)
    reader = DomainArtifact if source.identity.artifact_type in DOMAIN_TYPES else RecordArtifact
    reader(source.source_bytes, path=source.path)
    RelationReferences(records)
    edges = [(position, relation) for position, relation in enumerate(source.relations)
             if relation.type == 'verified_by' and relation.target == contract_id]
    if not edges:
        raise ModelError('verification_relation_required', path=source.path, pointer='/relations')
    value = contract.data
    if subject_id not in value['subjects']:
        raise ModelError('verification_subject_not_declared', path=target.path, pointer='/subjects')
    for position, declared in enumerate(value['subjects']):
        if declared not in index:
            raise ModelError('verification_subject_not_found', path=target.path,
                             pointer='/subjects/' + str(position))
    tests = {}
    for position, slot in enumerate(value['evidence_slots']):
        test_id = slot['test_id']
        if test_id is None or test_id in tests:
            continue
        if test_id not in index:
            raise ModelError('verification_test_not_found', path=target.path,
                             pointer='/evidence_slots/' + str(position) + '/test_id')
        test = index[test_id]
        tests[test_id] = VerificationTest(test.source_bytes, path=test.path).binding
    checks = [{'subject_artifact_id': subject_id, 'contract_id': contract_id,
               'test_id': slot['test_id'], 'check_id': slot['check_id'],
               'dimension': slot['dimension']} for slot in value['evidence_slots']]
    checks.sort(key=lambda item: ((item['test_id'] or '').encode('utf-8'),
                                  item['check_id'].encode('utf-8')))
    descriptor = _default_scope()
    data = {'format_version': 'verification-contract-v1', 'project_id': model.binding.project_id,
            'scope_descriptor': descriptor,
            'model_root_sha256': model.manifest(model.artifacts, descriptor).sha256,
            'input_sha256': model._sources_sha256,
            'validation_scope': 'supplied_model_explicit_subject_contract',
            'subject': _binding(source.source_bytes, source.path), 'contract': contract.binding,
            'relations': [{'relation_id': relation.identity.id,
                           'pointer': '/relations/' + str(position),
                           'record': relation.data,
                           'record_sha256': canonical_json_sha256(relation.data)}
                          for position, relation in edges],
            'tests': [tests[key] for key in sorted(tests)], 'required_checks': checks,
            'project_files_verified': False, 'full_validation_passed': False,
            'project_required_checks_complete': False, 'configuration_applicability_evaluated': False,
            'evidence_evaluated': False, 'test_code_executed': False,
            'write_authorized': False, 'approval_granted': False}
    result = object.__new__(VerificationContractResolution)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result
