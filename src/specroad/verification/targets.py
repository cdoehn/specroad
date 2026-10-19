"""Resolve an explicit contract or the normative implicit contract of a test.

An implicit contract is a projection of the stored test, never a synthesized
Verification record. Procedure, method and configuration policy are not guessed
from the test type. Evidence evaluation and execution remain separate.
"""

from ..model.errors import ModelError
from ._projection import required_checks, resolution_data
from ._sources import contract_sources, verified_by_edges
from .contracts import (VerificationTest, _resolved,
                        resolve_verification_contract)


def resolve_verification_target(model, subject_id, target_id):
    """Bind all required checks of one actual verified_by target.

Explicit Verification targets retain the existing explicit-contract API result.
A direct Test target uses its own ID as contract_id and test_id and contributes
exactly the overall slot. A lookup never uses titles, paths or external IDs in
place of the relation's actual artifact identity.
"""
    model, records, _, source, target = contract_sources(
        model, subject_id, target_id, target_field='target_id')
    if target.identity.artifact_type == 'verification':
        return resolve_verification_contract(model, subject_id, target_id)
    if target.identity.artifact_type != 'test':
        raise ModelError('verification_or_test_target_required', path=target.path, pointer='/target_id')
    test = VerificationTest(target.source_bytes, path=target.path)
    edges = verified_by_edges(records, source, target_id)
    implicit = {'contract_id': target_id, 'test_id': target_id, 'dimensions': ['overall'],
                'evidence_slots': [{'check_id': 'overall', 'test_id': target_id, 'dimension': 'overall'}]}
    checks = required_checks(subject_id, target_id, implicit['evidence_slots'])
    return _resolved(resolution_data(model, source, test.binding, edges, [test.binding], checks,
        validation_scope='supplied_model_implicit_test_contract', implicit_contract=implicit))
