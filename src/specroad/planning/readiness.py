"""Eight fixed Release gates over native, explicitly bound read observations.

Trusted hosts supply the existing ModelGate services (including lifecycle,
Requirement review and Task Done). Their results are rebound to this complete
readiness input. Project data cannot install a provider or supply a pass flag.
Blocker completion requires an exact, currently authenticated human review;
a terminal label is not proof. This does not open the Release baseline gate.
"""
from dataclasses import dataclass

from ..changes import TargetModel
from ..changes._target_materialization import validation_resources
from ..graph.relations import SourceRelations
from ..graph.review_status import RelationReviewStatuses
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.waiver_fields import waiver_time
from ..storage.json_syntax import parse_json_object
from ..validation import ModelGate, validate_model
from ..verification import prepare_verification_read_input, assess_verification_coverage
from ..verification._read_evaluation import resolve_read_evaluation
from ..verification.read_input import VerificationReadBindingConflict
from .release_scope import resolve_release_scope
from ._readiness_policy import readiness_policy
from .release_blockers import blocker_review_inputs, assess_blocker

GATES = ('scope', 'approval', 'implementation', 'verification', 'coverage',
         'risks', 'issues', 'relations')
IMPLEMENTED = ('capability', 'requirement', 'component', 'interface', 'task')
VERIFIED = ('capability', 'requirement', 'task')


@dataclass(frozen=True, init=False)
class ReleaseReadinessContext:
    """An owned model and evaluation, not an attestation of live disk currency."""
    _encoded: bytes
    _model: TargetModel
    _verification: object

    def __init__(self, model, release_id, *, scope_bindings, evaluated_at,
                 configuration_id=None, evaluation=None, inputs=None, input_roles=None,
                 waiver_reviews=None, waiver_verifier=None):
        if type(model) is not TargetModel:
            raise ModelError('release_readiness_target_model_required')
        model = model.snapshot()
        waiver_time(evaluated_at)
        descriptor = ScopeDescriptor({'scope_version': 'scope-v1', 'scope_kind': 'release',
            'selector': {'release_id': release_id}, 'configuration_id': configuration_id,
            'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'})
        # Native stored-selection precedence also applies to legacy policies.
        evaluation, selection = resolve_read_evaluation(model, evaluation, descriptor,
            conflict_type=VerificationReadBindingConflict)
        release = next(v for v in model.artifacts if v['id'] == release_id)
        policy, policy_reason = readiness_policy(release['readiness_policy'])
        scope = None
        scope_error = None
        try:
            scope = resolve_release_scope(model, release_id, scope_bindings=scope_bindings,
                                          configuration_id=configuration_id).data
        except ModelError as error:
            scope_error = {'reason': error.reason, 'diagnostic': error.diagnostic()}
        verification = None
        if scope is not None:
            verification = prepare_verification_read_input(model, evaluation,
                configuration_id=configuration_id, inputs=inputs, input_roles=input_roles,
                evaluated_at=evaluated_at, scope_descriptor=descriptor, scope_bindings=scope_bindings,
                waiver_reviews=waiver_reviews, waiver_verifier=waiver_verifier)
        binding = {'release_id': release_id, 'model_sources_sha256': model._sources_sha256,
            'model_resources_sha256': model.resources_sha256,
            'scope_descriptor': descriptor.data, 'release_scope': scope,
            # Blocker decisions bind the effective parent manifest, as native
            # Verification does; the Scope hash also includes project config.
            'configuration_sha256': None if verification is None else verification.data['configuration_hash'],
            'policy_sha256': canonical_json_sha256(policy),
            'evaluation_sha256': None if evaluation is None else evaluation.sha256,
            'verification_input_sha256': None if verification is None else verification.sha256,
            'evaluated_at': evaluated_at}
        data = {'binding': binding, 'policy': policy, 'policy_reason': policy_reason,
            'scope_error': scope_error, 'selection': selection,
            'input_sha256': canonical_json_sha256(binding)}
        object.__setattr__(self, '_encoded', canonical_json_bytes(data))
        object.__setattr__(self, '_model', model)
        object.__setattr__(self, '_verification', verification)

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def input_sha256(self):
        return self.data['input_sha256']

    def __bool__(self):
        raise TypeError('A readiness context is not a release decision')


@dataclass(frozen=True, init=False)
class ReleaseReadiness:
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_release_readiness')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    @property
    def exit_code(self):
        return 0 if self.data['ready'] else 3

    def __bool__(self):
        raise TypeError('Readiness is not a lifecycle or publication permit')


def assess_release_readiness(context, *, gates=(), blocker_reviews=(), blocker_verifier=None):
    """Compute all gates, keeping unavailable providers and every blocker.

    ModelGate callbacks are explicitly trusted host code, as in the ordinary
    validator. A version or a callback's presence is not evidence: native gate
    results must cover all subjects and bind the exact current context. The
    host must use the actual lifecycle, Requirement-review and Done services;
    a JSON label, bool or previously bound GateResult cannot stand in for one.
    """
    if type(context) is not ReleaseReadinessContext:
        raise ModelError('typed_release_readiness_context_required')
    if type(gates) not in (tuple, list) or any(type(g) is not ModelGate for g in gates):
        raise ModelError('release_readiness_native_gates_required')
    data = context.data
    model = context._model
    reviews, review_binding = blocker_review_inputs(blocker_reviews, blocker_verifier)
    binding = {**data['binding'], 'providers': sorted([
        {'gate_id': g.gate_id, 'version': g.version, 'resources_sha256': g.resources_sha256}
        for g in gates], key=lambda g: g['gate_id'].encode('utf-8'))}
    binding['blocker_review_inputs'] = review_binding
    input_sha256 = canonical_json_sha256(binding)
    scope = binding['release_scope']
    records = {v['id']: v for v in model.artifacts}
    release_id = binding['release_id']
    complete = scope is not None and scope['scope_applicability_complete']
    ids = [release_id] if scope is None else scope['artifact_ids']
    expected = {'scope': [release_id], 'approval': [i for i in ids
        if records[i]['artifact_type'] != 'configuration'],
        'implementation': [i for i in ids if records[i]['artifact_type'] in IMPLEMENTED],
        'verification': [i for i in ids if records[i]['artifact_type'] in VERIFIED],
        'risks': [i for i in ids if records[i]['artifact_type'] == 'risk'],
        'issues': [i for i in ids if records[i]['artifact_type'] == 'issue']}
    expected['coverage'] = list(expected['verification'])
    expected['relations'] = list(ids)
    rows = {key: {'gate_id': key, 'status': 'passed', 'subject_ids': sorted(expected[key]),
        'evidence_bindings': [], 'findings': []} for key in GATES}

    def finding(gate, subject, reason, *, status='incomplete', evidence_ids=(), relation_ids=()):
        row = rows[gate]
        row['findings'].append({'gate_id': gate, 'subject_id': subject, 'reason': reason,
            'blocking': True, 'evidence_ids': sorted(set(evidence_ids)),
            'relation_ids': sorted(set(relation_ids))})
        if row['status'] != 'failed':
            row['status'] = status

    if data['policy_reason'] is not None:
        finding('scope', None, data['policy_reason'])
    stored_scope = records[release_id].get('scope_descriptor')
    if stored_scope != binding['scope_descriptor']:
        finding('scope', None, 'approved_release_scope_descriptor_missing_or_changed', status='failed')
    if scope is None:
        rows['scope']['evidence_bindings'].append({'scope_resolution_error': data['scope_error']})
        reason = data['scope_error']['reason']
        missing_provider = any(word in reason for word in ('bindings_required', 'observation_missing'))
        finding('scope', None, reason, status='incomplete' if missing_provider else 'failed')
    elif not complete:
        for identifier in scope['unresolved_applicability']:
            finding('scope', identifier, 'scope_applicability_unresolved')
    if not complete:
        for key in GATES[1:]:
            finding(key, None, 'complete_scope_required')

    for identifier in expected['approval']:
        if records[identifier]['maturity'] != 'approved':
            finding('approval', identifier, 'artifact_not_approved', status='failed')
    for identifier in expected['implementation']:
        if records[identifier]['implementation_status'] != 'implemented':
            finding('implementation', identifier, 'artifact_not_implemented', status='failed')

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
        rows[target]['evidence_bindings'].append({'validation_input_sha256': validation.data['input_sha256'],
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
                finding(target, item.get('artifact_id'), reason,
                        status='incomplete' if unavailable else status)
        elif name == 'minimum_relations':
            # An unsatisfied native minimum is still a required relationship
            # when its diagnostic is informational or a warning.
            for item in stage['diagnostics']:
                finding('relations', item.get('artifact_id'), item['reason'], status='failed')
        elif name in ('lifecycle', 'review_currentness', 'task_done', 'evidence_currentness'):
            for item in stage['diagnostics']:
                negative = item['reason'] in ('approval_human_review_rejected',
                    'approval_human_criteria_unconfirmed', 'approval_nonhuman_review',
                    'approval_human_confirmed_compound', 'task_done_criteria_unconfirmed',
                    'task_done_human_review_required')
                finding(target, item.get('artifact_id'), item['reason'],
                        status='failed' if negative else 'incomplete')

    verification = context._verification
    if verification is not None:
        observed = verification.data
        subjects = {v['subject_artifact_id']: v for v in observed['aggregation']['subjects']}
        required = observed['aggregation']['replacement_assessment']['assessment']['selection']['coverage']['required_set']
        coverage = assess_verification_coverage(model, verification)
        rows['coverage']['evidence_bindings'].append({'sha256': coverage.sha256,
            'observation': coverage.data})
        rows['coverage']['evidence_bindings'].append({'required_checks_sha256': required['required_checks_sha256'],
            'required_checks': required['required_checks']})
        for identifier in expected['verification']:
            subject = subjects.get(identifier)
            if subject is None:
                finding('verification', identifier, 'verification_subject_missing')
                finding('coverage', identifier, 'verification_subject_missing')
                continue
            rows['verification']['evidence_bindings'].append({'sha256': verification.sha256,
                'subject_id': identifier, 'observation': subject})
            result = subject['verification_result']
            if result != 'passed':
                finding('verification', identifier, 'verification_' + result,
                        status='failed' if result in ('failed', 'waived') else 'incomplete')
            required_keys = [key for key in required['required_checks'] if key['subject_artifact_id'] == identifier]
            if not required_keys:
                finding('coverage', identifier, 'verification_contract_missing')
            from ..verification._required_keys import _key
            checked_keys = {_key(check) for check in subject['checks']}
            for key in required_keys:
                if _key(key) not in checked_keys:
                    finding('coverage', identifier, 'required_check_unselected')
                if key['test_id'] is not None and key['test_id'] not in ids:
                    finding('coverage', identifier, 'required_test_reference_missing', evidence_ids=[key['test_id']])
            for check in subject['checks']:
                if check['evidence_result'] != 'passed':
                    finding('coverage', identifier, 'required_check_' + check['evidence_result'],
                        status='failed' if check['evidence_result'] == 'failed' else 'incomplete')
                if not check['active_runs']:
                    finding('coverage', identifier, 'required_run_missing')
                for run in check['active_runs']:
                    if not run['evidence']:
                        finding('coverage', identifier, 'evidence_missing')
                    for evidence in run['evidence']:
                        evidence_id = evidence['evidence_id']
                        if evidence_id not in ids:
                            finding('coverage', identifier, 'required_evidence_outside_scope',
                                    evidence_ids=[evidence_id])
                        if evidence['freshness'] != 'current':
                            finding('coverage', identifier, 'evidence_' + evidence['freshness'],
                                    evidence_ids=[evidence_id])
                        if evidence['result'] != 'passed':
                            finding('coverage', identifier, 'evidence_result_' + evidence['result'],
                                status='failed' if (evidence['result'] == 'failed' and
                                    evidence['freshness'] == 'current') else 'incomplete',
                                evidence_ids=[evidence_id])

    decisions = ({} if data['policy_reason'] is not None else
                 {item['subject_id']: item for item in data['policy']['blocker_decisions']})
    for identifier in sorted(decisions):
        if identifier not in expected['risks'] + expected['issues']:
            finding('scope', identifier, 'blocker_decision_subject_outside_scope', status='failed')
    for gate in ('risks', 'issues'):
        for identifier in expected[gate]:
            observation = assess_blocker(binding, records[identifier], decisions.get(identifier),
                                         reviews, blocker_verifier)
            rows[gate]['evidence_bindings'].append(observation)
            for reason in observation['reasons']:
                finding(gate, identifier, reason, status=observation['status'],
                    evidence_ids=(() if observation['review_sha256'] is None else
                                  (observation['review']['review_id'],)))

    sources = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    reviews = RelationReviewStatuses(sources)
    # Closed core closure follows every stored outgoing edge, including weak
    # edges, and their review dependencies. These are used scope relations.
    relations = [r for r in reviews.data['relations'] if r['source_id'] in ids]
    rows['relations']['subject_ids'] = sorted({r['source_id'] for r in relations})
    for row in relations:
        rows['relations']['evidence_bindings'].append(row)
        if row['status'] != 'current':
            finding('relations', row['source_id'], 'relation_' + row['status'], status='failed',
                    relation_ids=[row['relation_id']])
        elif row['selected_review_id'] not in ids:
            finding('relations', row['source_id'], 'required_relation_review_outside_scope',
                    evidence_ids=[row['selected_review_id']], relation_ids=[row['relation_id']])

    for row in rows.values():
        # An unresolved/empty inventory cannot silently waive a required gate.
        if not row['subject_ids'] and complete and not row['findings']:
            row['status'] = 'not_applicable'
        unique = {canonical_json_bytes(f): f for f in row['findings']}
        row['findings'] = sorted(unique.values(), key=lambda f:
            ((f['subject_id'] or '').encode('utf-8'), f['reason'].encode('utf-8'), canonical_json_bytes(f)))
    statuses = {row['status'] for row in rows.values()}
    status = 'blocked' if 'failed' in statuses else 'incomplete' if 'incomplete' in statuses else 'ready'
    report = {'format_version': 'release-readiness-v1', 'release_id': release_id,
        'input_sha256': input_sha256, 'binding': binding, 'status': status,
        'ready': status == 'ready', 'provisional': data['selection']['provisional'],
        'gates': [rows[key] for key in GATES], 'selection': data['selection'],
        'validation_scope': 'supplied_model_native_scope_and_explicit_trusted_services',
        'project_files_verified': False, 'release_baseline_authorized': False,
        'write_authorized': False, 'approval_granted': False}
    value = object.__new__(ReleaseReadiness)
    object.__setattr__(value, '_encoded', canonical_json_bytes(report))
    return value
