"""Owned explicit contracts and the required checks for one subject/contract pair.

Only supplied bytes are inspected. Resolving a contract neither executes its
procedure nor evaluates Evidence, configuration applicability or verification
success. Project-wide required-check aggregation is a separate operation.
"""

from dataclasses import dataclass

from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from ._projection import record_binding as _binding, required_checks, resolution_data
from ._sources import contract_sources, verified_by_edges


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
    """Bound required checks for one pair, never a project-wide result."""
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


def _resolved(data):
    result = object.__new__(VerificationContractResolution)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    return result


def resolve_verification_contract(model, subject_id, contract_id):
    """Resolve every declared slot for an actual verified_by edge.

This first explicit-contract API rejects direct test targets. It does not infer
an implicit contract, choose a subset of slots or execute referenced code. The
supplied model is snapshotted and native relation identity/type checks apply.
"""
    model, records, index, source, target = contract_sources(
        model, subject_id, contract_id, target_field='contract_id')
    contract = VerificationContract(target.source_bytes, path=target.path)
    edges = verified_by_edges(records, source, contract_id)
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
    checks = required_checks(subject_id, contract_id, value['evidence_slots'])
    return _resolved(resolution_data(model, source, contract.binding, edges,
        [tests[key] for key in sorted(tests)], checks,
        validation_scope='supplied_model_explicit_subject_contract'))
