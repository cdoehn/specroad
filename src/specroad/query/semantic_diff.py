"""Deterministic semantic classes over explicitly supplied owned artifacts.

No source provider, applicability evaluator, evidence-currentness service or
natural-language interpretation is implied by this data-only comparison.
"""
from ..graph.artifact_comparison import compare_artifacts
from ..graph.comparison_values import ComparisonInputs, ComparisonResult
from ..model.canonical import canonical_json_sha256
from ..model.domain_schemas import validate_domain_fields
from ..model.errors import ModelError
from ..model.record_contracts import RECORD_TYPES
from ..model.record_schemas import validate_record_fields
from ._semantic_classes import _configuration_comparison, _field_category, _timing_comparisons


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
