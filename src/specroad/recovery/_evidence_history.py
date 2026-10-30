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

    No run is selected, no procedure executed and no approval inferred.
    Independent policy is assessed against the actual recorded native contract;
    a negative historical assessment never becomes a current approval.
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
        require(value.get('configuration_policy') in ('bound', 'independent') and 'configuration_hash' in value,
                'restore_evidence_configuration_provider_required', path=document.path)
        _run_history(state, value)
        for entry in value['subjects']:
            subject_id = entry['artifact_id']
            require(subject_id in documents, 'restore_evidence_subject_missing', path=document.path)
            if subject_id not in subjects:
                subject = documents[subject_id]
                subjects[subject_id] = DomainArtifact(subject.content, path=subject.path)
            context = VerificationContext(subjects[subject_id], configuration=None)
            if value['configuration_policy'] == 'bound':
                reports.append(assess_verification_context(context, record).data)
                continue
            run = value['run_context']
            recorded = {row['artifact_id'] for row in value['subjects']}
            contracts = [candidate for key, candidate in subjects.items()
                if type(candidate) is VerificationContract and key in recorded
                and run is not None and any(slot['check_id'] == run['check_id'] and
                    slot['test_id'] == run['test_id'] for slot in candidate.data['evidence_slots'])
                and (subject_id == key or subject_id in candidate.data['subjects'] or
                    any(slot['test_id'] == subject_id for slot in candidate.data['evidence_slots']))]
            require(contracts, 'restore_evidence_contract_required', path=document.path)
            # All actually recorded matching contracts are assessed; none is
            # selected as an authoritative run or a substitute human review.
            reports.extend(assess_verification_context(context, record, contract=contract).data
                           for contract in contracts)
    return tuple(reports)
