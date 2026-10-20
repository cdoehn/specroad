"""Shared whole-target gate binding and before/after direct impact.

The direct planner and saved-plan adapter both use these same primitives.
Diagnostic text is not interpreted; bound data contracts decide validity.
"""
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..validation import ModelGate
from ..graph.relations import SourceRelations
from ..graph.references import RelationReferences
from ..graph.comparison_values import ComparisonInputs
from ..graph.artifact_comparison import compare_artifacts
from ..graph.direct_impact import direct_impact
from .target_model import _sequence
from .target_values import TargetError

def _gates(gates, policy, plan, model):
    gates = _sequence(gates, 'target_gates_required')
    if any(type(g) is not ModelGate for g in gates) or len({g.gate_id for g in gates}) != len(gates):
        raise TargetError('target_distinct_registered_gates_required')
    # Reusing an old model-only outcome cannot authorize a different plan/command.
    bound = tuple(ModelGate(g.gate_id, g.version, g.dependencies, g.check,
        canonical_json_sha256({'plan':plan.sha256, 'resources':model.resources_sha256,
            'command':policy.data(), 'gate_resources':g.resources_sha256})) for g in gates)
    required = set(policy.required_gate_ids)
    operations = plan.data['operations']
    if any(operation['op'] == 'evidence_record' for operation in operations):
        required.add('extension:evidence-import' if any('import_context' in op for op in operations)
                     else 'extension:evidence-record')
    if (len(operations) == 1 and operations[0]['op'] == 'relation_review_record'
            and operations[0]['record']['decision'] == 'rejected'):
        required.add('extension:review-withdrawal')
    # Raw rule/mapping resources are hash-bound but their full specialized
    # semantics must be confirmed by an explicit trusted whole-target service.
    if any(r.data['kind'] in ('rule','mapping') for r in model.resources):
        required.add('extension:target-resources')
    return bound, sorted(required - {g.gate_id for g in gates})


def _empty_target_gates(report, registered, profile):
    """Command gates also run on an empty target; no vacuous resource approval.

    Reuse the model's bound context/result contracts. Ordinary artifact gates
    remain not-applicable without artifacts; whole-target extension gates do not.
    """
    from ..validation.values import GateContext, GateDependencies, GateResult, ValidationReport
    data = report.data
    if data['source_count']:
        return report
    replacements = {}
    for gate in sorted(registered, key=lambda item: item.gate_id):
        if not gate.gate_id.startswith('extension:'):
            continue
        diagnostics = []
        phase = 'dependencies'
        try:
            context = GateContext._create((), (), profile, (), gate, phase, data['input_sha256'])
            deps = gate.dependencies(context)
            if (type(deps) is not GateDependencies or deps.input_sha256 != context.input_sha256
                    or deps.by_artifact != {}):
                raise ModelError('validation_gate_dependencies_unbound_or_incomplete')
            phase = 'check'
            context = GateContext._create((), (), profile, (), gate, phase, data['input_sha256'])
            outcome = gate.check(context)
            if (type(outcome) is not GateResult or outcome.input_sha256 != context.input_sha256
                    or outcome.checked_ids != ()):
                raise ModelError('validation_gate_result_unbound_or_incomplete')
            diagnostics = list(outcome.diagnostics)
            if any(d.get('artifact_id') is not None for d in diagnostics):
                raise ModelError('validation_gate_diagnostic_outside_subjects')
        except ModelError as error:
            diagnostics = [{**error.diagnostic(), 'severity':'error'}]
        except Exception:
            diagnostics = [{'reason':'validation_gate_discovery_failed' if phase == 'dependencies'
                            else 'validation_gate_check_failed', 'severity':'error'}]
        status = 'failed' if any(d.get('severity','error') == 'error' for d in diagnostics) else 'passed'
        replacements[gate.gate_id] = {'stage':gate.gate_id, 'checked_ids':[],
                                      'status':status, 'diagnostics':diagnostics}
    data['stages'] = [replacements.get(s['stage'], s) for s in data['stages']]
    data['checks_complete'] = all(s['status'] in ('passed','failed','not_applicable') for s in data['stages'])
    data['model_valid'] = (False if any(s['status']=='failed' for s in data['stages']) else
                           True if data['checks_complete'] else None)
    return ValidationReport._create(data)


def _describe(model, artifacts):
    before = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    after = tuple(SourceRelations(canonical_json_bytes(v)) for v in artifacts)
    diff = compare_artifacts(ComparisonInputs(model.binding.project_id, before),
                             ComparisonInputs(model.binding.project_id, after))
    changed = [c['artifact_id'] for c in diff.data['changes']]
    sides = {}
    for name, records in (('before',before), ('after',after)):
        try:
            refs = RelationReferences(records)
            ids = {r.identity.id for r in records}
            sides[name] = {'complete': True, 'items': [direct_impact(i,refs).data for i in changed if i in ids]}
        except ModelError as error:
            sides[name] = {'complete':False, 'reason':error.reason, 'items':[]}
    return diff.data, {'depth':1, 'transitive':False, **sides}
