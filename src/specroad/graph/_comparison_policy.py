"""Conservative structural field categories. Never interpret prose or units."""

def _category(parts, before, after):
    # Only declared structural field locations; never infer from words.
    if not parts:
        return 'field_changed'
    name = parts[0]
    if name in ('statement', 'description', 'rationale', 'title', 'response',
                'actor', 'trigger', 'object', 'context', 'decision'):
        return 'text_changed' if type(before) is str or type(after) is str else 'field_changed'
    if name == 'timing':
        return ('text_changed' if len(parts) == 1 and (type(before) is str or type(after) is str)
                else 'timing_changed')
    if name in ('revision', 'created_at', 'updated_at', 'created_by', 'updated_by'):
        return 'audit_changed'
    if name in ('maturity', 'implementation_status', 'risk_status', 'proposal_status', 'baseline_status'):
        return 'status_changed'
    if name in ('scope', 'scope_descriptor', 'applicability'):
        return 'scope_changed'
    if name in ('exceptions', 'deviation_conditions', 'deviation_authority'):
        return 'exception_changed'
    if name == 'thresholds':
        return 'threshold_changed'
    if name == 'relations':
        return 'relation_changed'
    if name in ('verification_plan_status', 'verification_waiver', 'evidence_slots', 'verification_context_sha256'):
        return 'verification_changed'
    if name in ('code_references', 'code_ref', 'file_path', 'line_range', 'symbol', 'source_component', 'target_component'):
        return 'code_reference_changed' if name in ('code_references', 'code_ref') else 'field_changed'
    return 'field_changed'


