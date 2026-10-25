"""Declared field, configuration and duration semantics for supplied-input diff."""
from ..graph.comparison_values import ComparisonInputs, _owned
from ..graph.relations import SourceRelations
from ..graph.field_comparison import field_diff
from ..graph.timing_comparison import compare_duration_bounds
from ..model.canonical import canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.semantic_configuration import semantic_configuration


_TEXT_FIELDS = {
    'goal': ('success_criterion',),
    'capability': ('outcome',),
    'requirement': ('preconditions',),
    'scenario': ('actors', 'preconditions', 'main_flow', 'postconditions'),
    'decision': ('alternatives', 'consequences'),
    'risk': ('acceptance_rationale',),
    'assumption': ('validation_method', 'reevaluation_condition'),
    'component': ('responsibility',),
    'interface': ('contract', 'contract_not_applicable'),
    'release': ('name', 'objective'),
    'milestone': ('objective', 'done_criteria'),
    'task': ('done_criteria',),
    'term': ('term', 'definition', 'synonyms', 'forbidden_synonyms'),
    'source': ('excerpt',),
    'verification': ('preconditions', 'procedure', 'oracle'),
    'test': ('oracle',),
    'issue': ('resolution_criteria', 'permanent_status_reason'),
    'document': ('purpose', 'audience'),
    'relation_review': ('reason', 'comment'),
    'configuration': ('name',),
}


def _contains_text(value):
    """Recognize JSON strings, never interpret their words or numeric claims."""
    pending = [value]
    while pending:
        current = pending.pop()
        if type(current) is str:
            return True
        if type(current) is dict:
            pending.extend(current.values())
        elif type(current) is list:
            pending.extend(current)
    return False


def _field_category(kind, field):
    parts = field['pointer'].split('/')[1:]
    name = parts[0].replace('~1', '/').replace('~0', '~') if parts else ''
    if name == 'applicability':
        return 'applicability_changed'
    if kind == 'configuration' and name in ('dimensions', 'selection', 'parent'):
        return 'configuration_changed'
    if name in ('maturity', 'implementation_status', 'risk_status', 'validation_status',
                'proposal_status', 'issue_status', 'review_state', 'evidence_state', 'baseline_state'):
        return 'status_changed'
    if kind == 'evidence':
        if name in ('subjects', 'run_context', 'configuration_hash', 'configuration_policy'):
            return 'evidence_binding_changed'
        if name == 'result':
            return 'evidence_result_changed'
        if name in ('attachments', 'produced_at', 'producer', 'tool', 'environment', 'origin', 'unbound_reason'):
            return 'evidence_changed'
    opaque_text = name == 'extensions' or name in _TEXT_FIELDS.get(kind, ())
    if kind == 'content_block' and parts[:2] in (['payload', 'markdown'], ['payload', 'title']):
        opaque_text = True
    if (field['category'] == 'field_changed' and opaque_text
            and (_contains_text(field['before']) or _contains_text(field['after']))):
        return 'text_changed'
    return field['category']


def _configuration_comparison(before, after, left, right):
    if before is None and after is None:
        return {'state': 'not_supplied', 'changed': None, 'fields': [],
                'before_sha256': None, 'after_sha256': None}, None
    if type(before) is not ProjectConfiguration or type(after) is not ProjectConfiguration:
        raise ModelError('semantic_diff_configuration_pair_required')
    if (before.project_id != left.project_id or after.project_id != right.project_id
            or before.id_prefix != after.id_prefix
            or any(record.identity.id_prefix != before.id_prefix for record in left.records + right.records)):
        raise ModelError('semantic_diff_configuration_project_mismatch')
    old, new = semantic_configuration(before), semantic_configuration(after)
    delta = field_diff(old, new).data
    for item in delta['changes']:
        item['category'] = 'configuration_changed'
    return {'state': 'compared', 'changed': delta['changed'], 'fields': delta['changes'],
            'before_sha256': canonical_json_sha256(old),
            'after_sha256': canonical_json_sha256(new)}, {
                'before_sha256': canonical_json_sha256(before.data),
                'after_sha256': canonical_json_sha256(after.data)}


def _timing_comparisons(policy, before, after):
    if policy is None:
        policy = {}
    policy = _owned(policy)
    if type(policy) is not dict:
        raise ModelError('semantic_diff_timing_policy_required')
    rows = []
    for identity, bound in sorted(policy.items()):
        if type(bound) is not str or bound not in ('maximum', 'minimum'):
            raise ModelError('explicit_timing_bound_required')
        old, new = before.get(identity), after.get(identity)
        if (old is None or new is None or old['artifact_type'] != 'requirement'
                or new['artifact_type'] != 'requirement' or 'timing' not in old or 'timing' not in new):
            raise ModelError('semantic_diff_timing_subject_required')
        compared = compare_duration_bounds(old['timing'], new['timing'], bound=bound).data
        if compared['value_changed']:
            rows.append({'artifact_id': identity, 'pointer': '/timing', **compared})
    return policy, rows


def _owned_variant_inputs(inputs):
    """Use one original-byte inventory for field and applicability comparison."""
    if type(inputs.records) is not tuple:
        raise ModelError('comparison_records_required')
    if any(type(record) is not SourceRelations for record in inputs.records):
        raise ModelError('source_relations_required')
    return ComparisonInputs(inputs.project_id,
        tuple(SourceRelations(record.source_bytes, path=record.path) for record in inputs.records))


def _variant_scope(before, after, before_id, after_id, *, before_partial=None, after_partial=None):
    if before_id is None and after_id is None:
        return {'state': 'not_evaluated'}
    from ..configurations import evaluate_configuration
    from ..configurations.evaluation import ConfigurationEvaluationError
    if before_id is None or after_id is None:
        raise ConfigurationEvaluationError(ModelError('configuration_comparison_pair_required'))
    left = evaluate_configuration(before.records, before_id, partial=before_partial).data
    right = evaluate_configuration(after.records, after_id, partial=after_partial).data
    old, new = set(left['applicable_artifact_ids']), set(right['applicable_artifact_ids'])
    return {'state': 'evaluated', 'scope': 'supplied_artifact_applicability',
        'before': left, 'after': right, 'added_ids': sorted(new - old),
        'removed_ids': sorted(old - new), 'retained_ids': sorted(old & new),
        'membership_changed': old != new,
        'configuration_changed': left['configuration']['sha256'] != right['configuration']['sha256']}
