"""Owned synthetic review/semantic services; never real human acceptance.

Use real coupled review and lifecycle writers, original files and receipts.
Only external host identity/semantic observations are explicitly supplied.
"""
from specroad.authoring.lifecycle import transition_artifact, normalize_transition_input
from specroad.authoring.requirement_approval import approve_requirement
from specroad.changes import PublicationAuthority
from specroad.changes.requirement_approval import (bind_requirement_approval,
    requirement_approval_gates, ApprovalPrerequisiteProvider)
from specroad.validation import ApprovalContext, HumanRequirementReview, ModelGate
from support.approval import review_data, verifier, prerequisites
from test_negative_relation_review import negative_project, call, options, ACTOR
from test_negative_relation_review_right import current, coupled

TIME = '2026-10-11T02:32:00Z'


def lifecycle_options(request):
    return dict(actor=ACTOR, planned_at=TIME, change_plan_id='CP-' + request,
        transaction_id='txn-' + request, request_id=request,
        authority=PublicationAuthority('owned-approval-host', '1', lambda request: True))


def ready_project(root):
    model, source, history, gates = negative_project(root)
    first = call(model, source, options(model, gates))
    proposed_model = current(root, model)
    proposed = next(a for a in proposed_model.artifacts if a['id'] == source['id'])
    confirmation = coupled(proposed_model, proposed, gates, decision='confirmed', request='reconfirm')
    confirmed = current(root, model)
    # An explicitly registered host authenticates the unchanged stored history.
    # Its exact target oracle includes only the requested native transition.
    expected = {a['id']: a for a in confirmed.artifacts}
    expected[source['id']] = {**proposed, 'maturity': 'in_review', 'revision': 6,
                             'updated_at': TIME, 'updated_by': ACTOR}
    def check(target):
        assert {key: target.artifact(key) for key in target.all_ids} == expected
        return target.result()
    def dependencies(target):
        return target.dependency_result({key: list(target.all_ids) for key in target.subjects})
    native = transition_artifact(confirmed,
        normalize_transition_input(proposed, to='in_review', reason='Fresh human review requested.'),
        gates=(*gates, *(ModelGate(name, 'owned-exact-history-v1', dependencies, check)
                        for name in ('lifecycle', 'review_currentness'))),
        **lifecycle_options('start-review'))
    live = current(root, model)
    context = ApprovalContext(source['id'], live.documents, profile=live.profile,
                              configuration=live.configuration.data)
    review = HumanRequirementReview(review_data(context, reviewed_at=TIME))
    observed = []
    def evaluate(actual):
        assert actual.input_sha256 == context.input_sha256
        observed.append(actual.input_sha256)
        return prerequisites(actual)
    provider = ApprovalPrerequisiteProvider('owned-seven-services', '1', evaluate)
    before = next(a for a in live.artifacts if a['id'] == source['id'])
    operation = bind_requirement_approval(normalize_transition_input(before, to='approved',
        reason='Explicit new human approval after reconfirmation.'), context, review)
    fields = dict(context=context, review=review, verifier=verifier(),
                  prerequisite_provider=provider, gates=gates, **lifecycle_options('approve'))
    fields['planned_at'] = '2026-10-11T02:33:00Z'
    return live, operation, fields, {'source': source, 'proposed': proposed, 'before': before,
        'negative': first, 'confirmation': confirmation, 'in_review': native,
        'initial_reviews': history, 'service_calls': observed}


def registered(model, operation, fields):
    return requirement_approval_gates(model, operation,
        **{k: fields[k] for k in ('actor', 'planned_at', 'context', 'review',
                                  'verifier', 'prerequisite_provider', 'gates')})
