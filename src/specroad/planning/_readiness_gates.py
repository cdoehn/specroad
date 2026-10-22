"""Readiness gate adapters; native services retain every domain decision.

Scope, verification aggregation and relationship currentness are never rebuilt
here. Each adapter adds its observations to the same bound gate contributions.
"""
from ..changes._target_materialization import validation_resources
from ..graph.relations import SourceRelations
from ..graph.review_status import RelationReviewStatuses
from ..model.canonical import canonical_json_sha256
from ..validation import ModelGate, validate_model
from ..verification import assess_verification_coverage
from ..verification._required_keys import _key
from ._readiness_decisions import GATES, BlockerDecision, GateDecision, ReadinessBinding
from .release_blockers import assess_blocker

IMPLEMENTED = ('capability', 'requirement', 'component', 'interface', 'task')
VERIFIED = ('capability', 'requirement', 'task')
GateDecisions = dict[str, GateDecision]


def expected_subjects(records, release_id, ids) -> dict[str, list[str]]:
    expected = {'scope': [release_id], 'approval': [i for i in ids
        if records[i]['artifact_type'] != 'configuration'],
        'implementation': [i for i in ids if records[i]['artifact_type'] in IMPLEMENTED],
        'verification': [i for i in ids if records[i]['artifact_type'] in VERIFIED],
        'risks': [i for i in ids if records[i]['artifact_type'] == 'risk'],
        'issues': [i for i in ids if records[i]['artifact_type'] == 'issue']}
    expected['coverage'] = list(expected['verification'])
    expected['relations'] = list(ids)
    return expected


def assess_scope(data, binding, records, rows: GateDecisions, *, complete):
    scope = binding['release_scope']
    release_id = binding['release_id']
    if data['policy_reason'] is not None:
        rows['scope'].finding(None, data['policy_reason'])
    stored_scope = records[release_id].get('scope_descriptor')
    if stored_scope != binding['scope_descriptor']:
        rows['scope'].finding(None, 'approved_release_scope_descriptor_missing_or_changed', status='failed')
    if scope is None:
        rows['scope'].evidence_bindings.append({'scope_resolution_error': data['scope_error']})
        reason = data['scope_error']['reason']
        missing_provider = any(word in reason for word in ('bindings_required', 'observation_missing'))
        rows['scope'].finding(None, reason, status='incomplete' if missing_provider else 'failed')
    elif not complete:
        for identifier in scope['unresolved_applicability']:
            rows['scope'].finding(identifier, 'scope_applicability_unresolved')
    if not complete:
        for key in GATES[1:]:
            rows[key].finding(None, 'complete_scope_required')


def assess_artifacts(records, expected, rows: GateDecisions):
    for identifier in expected['approval']:
        if records[identifier]['maturity'] != 'approved':
            rows['approval'].finding(identifier, 'artifact_not_approved', status='failed')
    for identifier in expected['implementation']:
        if records[identifier]['implementation_status'] != 'implemented':
            rows['implementation'].finding(identifier, 'artifact_not_implemented', status='failed')


def assess_validation(model, bound: ReadinessBinding, gates, ids, rows: GateDecisions):
    binding = bound.data
    input_sha256 = bound.sha256
    # The native validator owns schemas, type-specific gates and mandatory
    # providers. Including readiness in its resource binding prevents replay of
    # a provider result under changed scope, evaluation, time or policy bytes.
    bound_gates = [ModelGate(g.gate_id, g.version, g.dependencies, g.check,
        canonical_json_sha256({'readiness_input_sha256': input_sha256,
            'provider_resources_sha256': g.resources_sha256})) for g in gates]
    validation = validate_model(model.documents, profile=model.profile, selected_ids=ids,
        resources=validation_resources(model), configuration_id=binding['scope_descriptor']['configuration_id'],
        gates=bound_gates)
    for stage in validation.data['stages']:
        name = stage['stage']
        target = ('implementation' if name == 'task_done' else
                  'relations' if name == 'minimum_relations' else 'approval')
        rows[target].evidence_bindings.append({'validation_input_sha256': validation.data['input_sha256'],
            'stage': name, 'status': stage['status'], 'checked_ids': stage['checked_ids'],
            'observation': stage})
        if stage['status'] not in ('passed', 'not_applicable'):
            status = 'incomplete' if stage['status'] in ('unavailable', 'blocked') else 'failed'
            issues = stage['diagnostics'] or [{'reason': 'validation_' + stage['status']}]
            for item in issues:
                reason = item['reason']
                unavailable = (reason in ('validation_gate_result_unbound_or_incomplete',
                    'validation_gate_check_failed', 'task_done_review_missing',
                    'task_done_review_verification_failed', 'task_done_target_changed',
                    'task_done_unconfigured_project_scope_required',
                    'task_done_review_binding_mismatch', 'task_done_review_verifier_required',
                    'task_done_review_verifier_unbound', 'task_done_review_not_authenticated_or_current',
                    'evidence_context_not_current', 'approval_human_review_missing') or
                    reason.startswith('approval_review_') or reason.endswith('_unavailable'))
                rows[target].finding(item.get('artifact_id'), reason,
                        status='incomplete' if unavailable else status)
        elif name == 'minimum_relations':
            # An unsatisfied native minimum is still a required relationship
            # when its diagnostic is informational or a warning.
            for item in stage['diagnostics']:
                rows['relations'].finding(item.get('artifact_id'), item['reason'], status='failed')
        elif name in ('lifecycle', 'review_currentness', 'task_done', 'evidence_currentness'):
            for item in stage['diagnostics']:
                negative = item['reason'] in ('approval_human_review_rejected',
                    'approval_human_criteria_unconfirmed', 'approval_nonhuman_review',
                    'approval_human_confirmed_compound', 'task_done_criteria_unconfirmed',
                    'task_done_human_review_required')
                rows[target].finding(item.get('artifact_id'), item['reason'],
                        status='failed' if negative else 'incomplete')


def assess_verification(model, verification, expected, ids, rows: GateDecisions):
    if verification is not None:
        observed = verification.data
        subjects = {v['subject_artifact_id']: v for v in observed['aggregation']['subjects']}
        required = observed['aggregation']['replacement_assessment']['assessment']['selection']['coverage']['required_set']
        coverage = assess_verification_coverage(model, verification)
        rows['coverage'].evidence_bindings.append({'sha256': coverage.sha256,
            'observation': coverage.data})
        rows['coverage'].evidence_bindings.append({'required_checks_sha256': required['required_checks_sha256'],
            'required_checks': required['required_checks']})
        for identifier in expected['verification']:
            subject = subjects.get(identifier)
            if subject is None:
                rows['verification'].finding(identifier, 'verification_subject_missing')
                rows['coverage'].finding(identifier, 'verification_subject_missing')
                continue
            rows['verification'].evidence_bindings.append({'sha256': verification.sha256,
                'subject_id': identifier, 'observation': subject})
            result = subject['verification_result']
            if result != 'passed':
                rows['verification'].finding(identifier, 'verification_' + result,
                        status='failed' if result in ('failed', 'waived') else 'incomplete')
            required_keys = [key for key in required['required_checks'] if key['subject_artifact_id'] == identifier]
            if not required_keys:
                rows['coverage'].finding(identifier, 'verification_contract_missing')
            checked_keys = {_key(check) for check in subject['checks']}
            for key in required_keys:
                if _key(key) not in checked_keys:
                    rows['coverage'].finding(identifier, 'required_check_unselected')
                if key['test_id'] is not None and key['test_id'] not in ids:
                    rows['coverage'].finding(identifier, 'required_test_reference_missing', evidence_ids=[key['test_id']])
            for check in subject['checks']:
                if check['evidence_result'] != 'passed':
                    rows['coverage'].finding(identifier, 'required_check_' + check['evidence_result'],
                        status='failed' if check['evidence_result'] == 'failed' else 'incomplete')
                if not check['active_runs']:
                    rows['coverage'].finding(identifier, 'required_run_missing')
                for run in check['active_runs']:
                    if not run['evidence']:
                        rows['coverage'].finding(identifier, 'evidence_missing')
                    for evidence in run['evidence']:
                        evidence_id = evidence['evidence_id']
                        if evidence_id not in ids:
                            rows['coverage'].finding(identifier, 'required_evidence_outside_scope',
                                    evidence_ids=[evidence_id])
                        if evidence['freshness'] != 'current':
                            rows['coverage'].finding(identifier, 'evidence_' + evidence['freshness'],
                                    evidence_ids=[evidence_id])
                        if evidence['result'] != 'passed':
                            rows['coverage'].finding(identifier, 'evidence_result_' + evidence['result'],
                                status='failed' if (evidence['result'] == 'failed' and
                                    evidence['freshness'] == 'current') else 'incomplete',
                                evidence_ids=[evidence_id])


def assess_blockers(data, binding: ReadinessBinding, records, expected, reviews, verifier, rows: GateDecisions):
    decisions = ({} if data['policy_reason'] is not None else
                 {item['subject_id']: item for item in data['policy']['blocker_decisions']})
    for identifier in sorted(decisions):
        if identifier not in expected['risks'] + expected['issues']:
            rows['scope'].finding(identifier, 'blocker_decision_subject_outside_scope', status='failed')
    for gate in ('risks', 'issues'):
        for identifier in expected[gate]:
            observation = assess_blocker(binding.data, records[identifier], decisions.get(identifier),
                                         reviews, verifier)
            rows[gate].include_blocker(BlockerDecision.from_observation(binding, observation))


def assess_relations(model, ids, rows: GateDecisions):
    sources = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    reviews = RelationReviewStatuses(sources)
    # Closed core closure follows every stored outgoing edge, including weak
    # edges, and their review dependencies. These are used scope relations.
    relations = [r for r in reviews.data['relations'] if r['source_id'] in ids]
    rows['relations'].subject_ids = sorted({r['source_id'] for r in relations})
    for row in relations:
        rows['relations'].evidence_bindings.append(row)
        if row['status'] != 'current':
            rows['relations'].finding(row['source_id'], 'relation_' + row['status'], status='failed',
                    relation_ids=[row['relation_id']])
        elif row['selected_review_id'] not in ids:
            rows['relations'].finding(row['source_id'], 'required_relation_review_outside_scope',
                    evidence_ids=[row['selected_review_id']], relation_ids=[row['relation_id']])
