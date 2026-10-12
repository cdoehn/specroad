"""Deterministic semantic classes over explicitly supplied owned artifacts.

No source provider, applicability evaluator, evidence-currentness service or
natural-language interpretation is implied by this data-only comparison.
"""
from ..graph.artifact_comparison import compare_artifacts
from ..graph.comparison_values import ComparisonInputs, ComparisonResult, _owned
from ..graph.field_comparison import field_diff
from ..graph.timing_comparison import compare_duration_bounds
from ..model.canonical import canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.domain_schemas import validate_domain_fields
from ..model.errors import ModelError
from ..model.record_contracts import RECORD_TYPES
from ..model.record_schemas import validate_record_fields
from ..model.semantic_configuration import semantic_configuration


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


def compare_semantic(before, after, *, before_configuration=None,
                     after_configuration=None, timing_bounds=None):
    """Classify supplied sets; explicit policies never grant approval or writes.

    Configuration comparison requires both typed declarations. Timing bounds
    map existing requirement IDs to an explicit maximum/minimum interpretation.
    Their validity is checked even when the artifacts have no field changes.
    """
    if type(before) is not ComparisonInputs or type(after) is not ComparisonInputs:
        raise ModelError('comparison_inputs_required')
    # Validate the entire supplied field inventory before classifying changes.
    # No stored approval state authenticates the records or resolves references.
    for inputs in (before, after):
        for record in inputs.records:
            value = record.data
            validate = validate_record_fields if value['artifact_type'] in RECORD_TYPES else validate_domain_fields
            validate(value)
    base = compare_artifacts(before, after).data
    left = {record.identity.id: record.data for record in before.records}
    right = {record.identity.id: record.data for record in after.records}
    configuration, configuration_inputs = _configuration_comparison(
        before_configuration, after_configuration, before, after)
    policy, timing = _timing_comparisons(timing_bounds, left, right)
    timing_by_id = {row['artifact_id']: row for row in timing}
    changes = base['changes']
    for item in changes:
        identity = item['artifact_id']
        value = right.get(identity, left.get(identity))
        # Preserve whole-artifact classes such as retirement and document edits;
        # replace only the field-level categories with their declared semantics.
        categories = set(item['categories']) - {field['category'] for field in item['fields']}
        for field in item['fields']:
            field['category'] = _field_category(value['artifact_type'], field)
            if field['pointer'] == '/timing' or field['pointer'].startswith('/timing/'):
                if identity in timing_by_id:
                    field['category'] = timing_by_id[identity]['category']
            categories.add(field['category'])
        item['categories'] = sorted(categories)
    categories = {category for item in changes for category in item['categories']}
    if configuration['changed']:
        categories.add('configuration_changed')
    inputs = {'before_artifacts_sha256': before.fingerprint, 'after_artifacts_sha256': after.fingerprint,
              'configuration_inputs': configuration_inputs, 'timing_bounds': policy}
    return ComparisonResult({'comparison_version': 'semantic-diff-v1',
        'project_id': before.project_id, 'input_sha256': canonical_json_sha256(inputs),
        **inputs, 'changed': base['changed'] or bool(configuration['changed']),
        'categories': sorted(categories), 'changes': changes,
        'project_configuration': configuration, 'timing': timing,
        'inventory_delta': {'scope': 'supplied_artifact_sets',
            'added_ids': sorted(right.keys() - left.keys()), 'removed_ids': sorted(left.keys() - right.keys())},
        'configuration_scope': {'state': 'not_evaluated'},
        'evidence_currency': {'state': 'not_evaluated'},
        'validation_scope': 'supplied_artifact_fields_and_declared_semantics_only',
        'full_semantic_validation': False, 'approval_granted': False, 'write_authorized': False})
