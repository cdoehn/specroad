"""Force provenance cannot stand in for positive currentness or approval."""
from ..validation import ModelGate
from ..model.canonical import canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object


def evidence(model):
    rows = list(getattr(model, 'force_provenance', ()))
    return dict(force_provenance=rows, force_approval_granted=False)


def affected(model):
    by_path = {d.path: {parse_json_object(d.content)['id']} for d in model.documents}
    by_path.update({source.path: {p.data['id'] for p in source.projections} for source in model.plan_sources})
    by_path['specroad.json'] = {v['id'] for v in model.artifacts}
    return {identity for row in getattr(model, 'force_provenance', ()) for identity in by_path.get(row['path'], ())}


def provenance_gate(model, *, independently_approved=()):
    rows = tuple(getattr(model, 'force_provenance', ()))
    if not rows:
        return ()
    ids = affected(model)
    def dependencies(context):
        return context.dependency_result({i: list(context.all_ids) for i in context.subjects})
    def check(context):
        diagnostics = []
        for identity in sorted(ids):
            value = context.artifact(identity)
            positive = (identity not in independently_approved and (value.get('maturity') in ('approved', 'applied') or
                value.get('artifact_type') in ('relation_review', 'evidence', 'baseline') or
                value.get('proposal_status') in ('approved', 'applied')))
            diagnostics.append(dict(reason='force_original_requires_independent_evidence' if positive else 'force_provenance_retained',
                severity='error' if positive else 'info', artifact_id=identity))
        return context.result(diagnostics)
    return (ModelGate('extension:force-provenance', 'force-provenance-v1', dependencies, check, digest(list(rows))),)
