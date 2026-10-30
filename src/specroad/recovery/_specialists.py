"""Existing native specialist checks over the exact owned Restore model."""
from ..graph.relations import SourceRelations
from ..graph.review_status import RelationReviewStatuses
from ..graph.relation_obligations import RelationObligations
from ..validation.approval import assess_requirement_approval
from ..validation.approval_values import ApprovalContext
from .services import RequirementReviewInputs
from .values import require


def approval_checks(model, services):
    """Rebind every current human review to the complete original stored model."""
    results = {}
    for artifact in model.artifacts:
        if artifact['artifact_type'] != 'requirement' or artifact['maturity'] != 'approved':
            continue
        identity = artifact['id']
        require(services.requirement_review is not None,
                'restore_requirement_review_provider_required', path=identity)
        inputs = services.requirement_review(model.snapshot(), identity)
        require(type(inputs) is RequirementReviewInputs,
                'restore_native_approval_inputs_required', path=identity)
        supplied = inputs.context.data
        context = ApprovalContext(identity, model.documents, profile=model.profile,
            configuration=model.configuration.data, mode='stored',
            quality_fields=supplied['quality_fields'], interface_fields=supplied['interface_fields'])
        require(inputs.context.input_sha256 == context.input_sha256,
                'restore_approval_context_changed', path=identity, exit_code=6)
        assessment = assess_requirement_approval(context, review=inputs.review,
            verifier=inputs.verifier, prerequisites=inputs.prerequisites)
        if not assessment.data['requirements_satisfied']:
            findings = assessment.data['findings']
            require(False, findings[0]['reason'] if findings else 'restore_requirement_review_invalid',
                    path=identity)
        results[identity] = (context, assessment)
    return results


def review_checks(model):
    """Keep historic negative/stale records; never turn them into approval."""
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    statuses = RelationReviewStatuses(records)
    by_relation = {s.relation_id: s for s in statuses.statuses}
    approved = {a['id'] for a in model.artifacts if a['maturity'] == 'approved'}
    obligations = RelationObligations(records, profile_rules=model.profile.minimum_relation_rules())
    for check in obligations.checks:
        if check.artifact_id in approved and check.minimum > 0 and check.severity == 'error':
            require(check.satisfied and all(by_relation[key].status == 'current'
                    for key in check.relation_ids), 'restore_retained_approval_review_invalid',
                    path=check.artifact_id)
    return statuses


def proposal_checks(model, services):
    from ..proposals import ProposalOriginal, ProposalInputs, assess_proposal
    from ..storage.json_syntax import parse_json_object
    results = {}
    for document in model.documents:
        if parse_json_object(document.content)['artifact_type'] != 'proposal':
            continue
        original = ProposalOriginal(document.content, path=document.path)
        require(services.proposal_inputs is not None,
                'restore_proposal_original_contexts_required', path=document.path)
        inputs = services.proposal_inputs(model.snapshot(), original)
        require(type(inputs) is ProposalInputs, 'restore_native_proposal_inputs_required', path=document.path)
        results[original.binding.proposal_id] = assess_proposal(original, inputs, model, services=services)
    return results


def configuration_checks(model):
    from ..configurations.evaluation import evaluate_configuration
    from ..configurations.applicability import evaluate_applicability
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    configurations = [a['id'] for a in model.artifacts if a['artifact_type'] == 'configuration']
    for identity in configurations:
        value = evaluate_configuration(records, identity).data
        require(not value['inconsistent_dependencies'], 'configuration_dependency_excluded', path=identity)
    # Applicability contracts are checked by evaluate_configuration, including
    # inheritance and native expressions. The unconfigured project is retained.
    for record in records:
        evaluate_applicability(record)


def task_gate(model, services):
    from ..planning.task_implementation import task_done_read_gate
    if not any(a['artifact_type'] == 'task' and a['implementation_status'] == 'implemented'
               for a in model.artifacts):
        return ()
    require(services.task_done is not None, 'restore_task_done_provider_required')
    return (task_done_read_gate(model, services.task_done(model.snapshot())),)


def external_checks(model, services, subjects):
    from ..storage.record_artifact import RecordArtifact
    from ..verification.code_reference_state import assess_code_reference
    documents = {SourceRelations(d.content).identity.id: d for d in model.documents}
    for identity in subjects:
        document = documents[identity]
        kind = SourceRelations(document.content).identity.artifact_type
        if kind == 'source':
            from hashlib import sha256
            record = RecordArtifact(document.content, expected_type='source', path=document.path)
            value = record.data
            if 'content_sha256' not in value and 'excerpt' not in value:
                # The source contract permits unapproved locator metadata.
                # A restore must not invent a byte binding or require fetching
                # an external document merely to retain that valid metadata.
                require(value['maturity'] != 'approved',
                        'restore_source_content_binding_required', path=identity)
                continue
            require(services.source_content is not None,
                    'restore_source_content_provider_required', path=identity)
            raw = services.source_content(model.snapshot(), record)
            require(type(raw) is bytes, 'restore_source_content_bytes_required', path=identity)
            if 'content_sha256' in value:
                require(sha256(raw).hexdigest() == value['content_sha256'],
                        'restore_source_content_changed', path=identity, exit_code=6)
            else:
                require('excerpt' in value and raw == value['excerpt'].encode('utf-8'),
                        'restore_source_content_binding_required', path=identity)
            continue
        if kind != 'code_ref':
            # Source metadata and bound attachments are checked by the native
            # record/model readers. A URI is data and never triggers a fetch.
            continue
        record = RecordArtifact(document.content, expected_type='code_ref', path=document.path)
        require(services.code_source is not None, 'restore_code_source_provider_required', path=identity)
        source = services.code_source(model.snapshot(), record)
        observation = assess_code_reference(source, record)
        require(observation.data['state'] == 'current', 'restore_code_reference_not_current', path=identity)
