"""Own and natively validate requirement, contract and test subject values."""
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from .contracts import VerificationContract, VerificationTest


def owned_subject(subject):
    if type(subject) is DomainArtifact:
        return DomainArtifact(subject.source_bytes, expected_type='requirement', path=subject.path)
    if type(subject) is VerificationContract:
        return VerificationContract(subject.source_bytes, path=subject.path)
    if type(subject) is VerificationTest:
        return VerificationTest(subject.source_bytes, path=subject.path)
    raise ModelError('typed_verification_subject_required')
