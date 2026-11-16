"""Synthetic native requirement reviews; never a release or human approval."""
from hashlib import sha256
from specroad.changes.review_record import review_context, prepare_review_record
from specroad.model.identity_values import artifact_identity
from specroad.qualification import QualificationServices as RestoreServices, RequirementReviewInputs
from specroad.validation import ApprovalContext, HumanRequirementReview
from support.approval import values, review_data, verifier, prerequisites, QUALITY_FIELDS
from support.records import record_value, ref
from support.restore import restore_case

def approved_project(tmp_path, kind='functional', source_kind='project_bundle'):
    records = values(kind, maturity='approved')
    requirement, source, verification = records
    source['content_sha256'] = sha256(b'original source').hexdigest()
    verification['subjects'] = [requirement['id']]
    if kind == 'quality':
        requirement['thresholds'] = [{'property': 'latency', 'method': 'timestamp difference',
            'comparison': 'lte', 'target': {'value': 5, 'unit': 'ms'}}]
    if kind == 'interface':
        from support.domain import domain_value
        component = domain_value('component')
        requirement['scope'] = {'boundary': component['id']}
        records.append(component)
    for index, edge in enumerate(requirement['relations']):
        context = review_context(records, requirement['id'], edge['relation_id'])
        identity = artifact_identity(record_value('relation_review', id=ref('RREV', str(index))))
        records.append(prepare_review_record(context, identity,
            actor={'actor_type': 'human', 'actor_id': 'synthetic-reviewer'},
            planned_at='2026-10-01T00:00:00Z', decision='confirmed', reason='Synthetic fixture'))
    records.append(record_value('document'))
    return restore_case(tmp_path, source_kind, values=records)[0]

def services(*, fault=None, calls=None, kind='functional'):
    def inputs(model, identity):
        if calls is not None:
            calls.append(identity)
        context = ApprovalContext(identity, model.documents, profile=model.profile,
            configuration=model.configuration.data, mode='stored',
            quality_fields=QUALITY_FIELDS if kind == 'quality' else (),
            interface_fields=('/scope/boundary',) if kind == 'interface' else ())
        data = review_data(context)
        if fault == 'rejected':
            data['decision'] = 'rejected'
        elif fault == 'nonhuman':
            data['reviewer']['actor_type'] = 'ai'
        elif fault == 'foreign':
            data['input_sha256'] = '0' * 64
        elif fault == 'criteria':
            data['criteria'] = {}
        return RequirementReviewInputs(context, HumanRequirementReview(data),
            verifier(authenticated=fault != 'unauthenticated', current=fault != 'stale'),
            () if fault == 'prerequisite' else prerequisites(context))
    return RestoreServices(requirement_review=inputs,
                           source_content=lambda model, record: b'original source')
