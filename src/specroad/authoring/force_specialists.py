"""Native original-bound import and Baseline inputs for explicit Force.

No synthetic measurement, guessed import target, replacement configuration,
or success callback is supplied. A complete native conversion must exist.
"""
from hashlib import sha256
from ..changes.write_guard_values import require
from ..changes.force_domain_gates import record_denial
from ..model.errors import ModelError


def compile_specialist(sources, name, data, actor, time, decisions):
    model = sources.model
    require(model is not None, 'force_specialist_concrete_model_required', exit_code=3)
    if name == 'baseline.create':
        from ..changes.baselines import prepare_baseline_operation
        return [prepare_baseline_operation(model, baseline_id=sources.allocate('baseline').id,
            name=data['name'], actor=actor, planned_at=time,
            **{k: data[k] for k in ('configuration_id', 'release_id') if k in data})]
    require(name == 'evidence.import', 'force_specialist_operation_required', exit_code=2)
    from ..changes.evidence_import import _EvidenceSetPlanner
    raw = sources.before.get(data['source_path'])
    require(raw is not None, 'evidence_original_unavailable', exit_code=5)
    decisions.decide(sha256(raw).hexdigest() == data['source_sha256'], gate_id='hash:import_original',
        diagnostic_code='CORE_CONFLICT', subject=data['source_path'], operation=name,
        observed_binding=sha256(raw).hexdigest(), requested_binding=data['source_sha256'],
        effect='import_observed_original_bytes')
    extras = {k: data[k] for k in ('mapping_path','mapping_sha256','measurements_path','measurements_sha256',
        'external_identifiers_path','external_identifiers_sha256','tool','run_context') if k in data}
    planner = _EvidenceSetPlanner(model, data['source_path'], data['policy'],
        format_name=data.get('import_format', 'generic'), extras=extras)
    try:
        planner.require_new_measurements()
    except ModelError as error:
        record_denial(decisions, error, operation=name, subject=data['source_path'], requested=data)
    # Calling each existing original-bound converter retains the full set and
    # exact provenance while bypassing only the observed duplicate prohibition.
    return [planner.operation(index, evidence_id=sources.allocate('evidence').id,
        title=data['title'], configuration_id=data.get('configuration_id'), actor=actor, planned_at=time)
        for index in range(planner.candidate_count)]
