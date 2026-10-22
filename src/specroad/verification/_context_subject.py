"""Own and natively validate capability, requirement, task, contract and test subject values."""
from ..model.errors import ModelError
from ..storage.domain_artifact import DomainArtifact
from .contracts import VerificationContract, VerificationTest


def owned_subject(subject):
    if type(subject) is DomainArtifact:
        owned = DomainArtifact(subject.source_bytes, path=subject.path)
        if owned.data['artifact_type'] not in ('capability', 'requirement', 'task'):
            raise ModelError('typed_verification_subject_required')
        return owned
    if type(subject) is VerificationContract:
        return VerificationContract(subject.source_bytes, path=subject.path)
    if type(subject) is VerificationTest:
        return VerificationTest(subject.source_bytes, path=subject.path)
    raise ModelError('typed_verification_subject_required')
