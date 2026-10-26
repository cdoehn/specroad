"""Native historical Evidence assessments, not verification or readiness gates."""
from ..changes.evidence import _run_history
from ..storage.domain_artifact import DomainArtifact
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from ..verification import VerificationContext, assess_verification_context
from ..verification.contracts import VerificationContract, VerificationTest
from .values import require


def evidence_assessments(model):
    """Check stored subjects with native readers and retain negative/stale data.

    No run is selected, no procedure executed and no approval inferred. W uses
    explicit bound configuration policy at the unconfigured project scope;
    independent-policy reuse still requires its specialist provider.
    """
    documents = {parse_json_object(d.content)['id']: d for d in model.documents}
    state = {a['id']: a for a in model.artifacts}
    subjects = {}
    for identity, value in state.items():
        kind = value['artifact_type']
        if kind in ('verification', 'test'):
            document = documents[identity]
            reader = VerificationContract if kind == 'verification' else VerificationTest
            subjects[identity] = reader(document.content, path=document.path)
    reports = []
    for identity, value in sorted(state.items()):
        if value['artifact_type'] != 'evidence':
            continue
        document = documents[identity]
        record = RecordArtifact(document.content, expected_type='evidence', path=document.path)
        require(value.get('configuration_policy') == 'bound' and 'configuration_hash' in value,
                'restore_evidence_configuration_provider_required', path=document.path)
        _run_history(state, value)
        for entry in value['subjects']:
            subject_id = entry['artifact_id']
            require(subject_id in documents, 'restore_evidence_subject_missing', path=document.path)
            if subject_id not in subjects:
                subject = documents[subject_id]
                subjects[subject_id] = DomainArtifact(subject.content, path=subject.path)
            context = VerificationContext(subjects[subject_id], configuration=None)
            reports.append(assess_verification_context(context, record).data)
    return tuple(reports)
