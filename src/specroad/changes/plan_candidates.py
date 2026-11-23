"""Native Markdown fold for the common target and saved-Proposal pipelines."""
from dataclasses import dataclass
from ..model.canonical import canonical_json_sha256
from ..srx._json_values import JsonSnapshot
from .metadata_values import MetadataArtifact
from .target_values import TargetError
from .target_model import TargetModel
from .plan_source_operation import recompile, sources


def mode(operations):
    return any(op['op'] == 'plan_edit' for op in operations)


@dataclass(frozen=True)
class PlanCandidates:
    target_model: TargetModel
    candidates: tuple
    decisions: tuple = ()
    previously_approved_ids: tuple = ()
    metadata_applied: bool = True

    @property
    def artifacts(self):
        return self.target_model.artifacts


def rebuild(model, plan_sources, *, documents=None, resource_files=None):
    return TargetModel(model.configuration_bytes, model.binding,
        model.documents if documents is None else documents,
        profile=model.profile, resource_files=model.resource_files if resource_files is None else resource_files,
        attachments=model.attachment_descriptors, language_packages=model.language_packages,
        plan_sources=plan_sources, **model.reservations)


def prepare(model, operations, *, metadata_policy_version, actor, planned_at, preconditions):
    if metadata_policy_version != 'change-metadata-v1' or len(operations) != 1 or operations[0]['op'] != 'plan_edit':
        raise TargetError('plan_source_specialist_sequence_required')
    op = operations[0]
    before = {s.path: s.source_bytes for s in sources(op, 'before')}
    if before != {s.path: s.source_bytes for s in model.plan_sources}:
        raise TargetError('plan_source_inventory_changed')
    target_sources, values = recompile(op, actor=actor, planned_at=planned_at,
                                      id_prefix=model.configuration.id_prefix)
    old = {v['id']: v for v in model.artifacts}
    new = {p.data['id']: p.data for s in target_sources for p in s.projections}
    for value in values:
        prior = old.get(value['id'])
        if prior is None and (value['id'] in old or value['id'] in model.reserved_artifact_ids):
            raise TargetError('plan_identity_reserved')
    removed = set(v['id'] for s in model.plan_sources for v in (p.data for p in s.projections)) - set(new)
    for identity in removed:
        if old[identity]['maturity'] != 'draft' or identity in model.previously_approved_ids:
            raise TargetError('plan_historical_identity_removal_forbidden')
    from ..migration.model_inputs import records
    from ..graph.plan_sources import records as plan_records
    old_relations = {e.identity.id for r in records(model) for e in r.relations}
    new_relations = [e.identity.id for r in plan_records(target_sources) for e in r.relations]
    if (len(new_relations) != len(set(new_relations)) or
            (set(new_relations) - old_relations) & set(model.reserved_relation_ids)):
        raise TargetError('plan_relation_identity_reserved')
    incoming = []
    remaining_records = tuple(r for r in records(model)
        if r.data['artifact_type'] not in ('implementation_plan','plan_entry')) + plan_records(target_sources)
    for record in remaining_records:
        for edge in record.relations:
            if edge.target in removed:
                incoming.append({'source_id':record.identity.id,'target_id':edge.target,'relation_id':edge.identity.id})
        for claim in record.data.get('coverage_claims', []):
            for ref in claim['contributors']:
                if ref['entry_id'] in removed or ref['plan_id'] in removed:
                    incoming.append({'source_id':record.identity.id,'target_id':ref['entry_id'],'claim_id':claim['claim_id']})
    if incoming:
        error = TargetError('plan_remove_open_impact')
        from ..model.canonical import canonical_json_bytes
        error.impact = sorted(incoming, key=canonical_json_bytes)
        raise error
    target = rebuild(model, target_sources)
    candidates = tuple(MetadataArtifact(v['id'], JsonSnapshot(v, rule_id='plan-authoring'),
        None if v['id'] not in old else canonical_json_sha256(old[v['id']]),
        canonical_json_sha256(v), (0,), 'created' if v['id'] not in old else 'changed') for v in values)
    return PlanCandidates(target, candidates)
