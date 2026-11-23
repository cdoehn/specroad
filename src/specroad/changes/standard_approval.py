"""Isolated standard approval, guarded by the complete native target validator.

Requirement approval keeps its dedicated authenticated review contract. Special
records retain their specialist workflows. This passive reduction is never a
publication permission: the native target gate and host authority run afresh.
"""
from dataclasses import dataclass, replace
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.errors import ModelError
from ..validation import ModelGate
from .values import ChangeOperation
from .lifecycle_values import LifecycleError, LifecycleResult
from ._metadata_policy import bind_policy
from ._metadata_materialize import apply_policy
from ._fold_inputs import _inventory, _preflight, _files
from ._fold_results import _finish
from ._patch_values import _snapshot
from .lifecycle import _history, lifecycle_content_sha256
from .target_model import _default_scope

GATE='extension:standard-approval'
VERSION='standard-approval-v1'
EXCLUDED={'requirement','proposal','evidence','baseline','relation_review','implementation_plan','plan_entry'}


def mode(operations):
    return any(op['op']=='transition' and 'standard_approval' in op['metadata'] for op in operations)


def bind(model, operation):
    op=ChangeOperation(operation).data
    op['metadata']['standard_approval']={'version':VERSION,'model_root_sha256':model.manifest(model.artifacts,_default_scope()).sha256}
    return ChangeOperation(op).data


def prepare(model, operations, *, metadata_policy_version, actor, planned_at, preconditions=()):
    metadata=bind_policy(metadata_policy_version,actor,planned_at)
    if len(operations)!=1:raise LifecycleError('approval_isolated_standard_transition_required')
    op=ChangeOperation(operations[0]).data
    before=next((v for v in model.artifacts if v['id']==op.get('target')),None)
    if (op['op']!='transition' or op['from']!='in_review' or op['to']!='approved'
            or before is None or before['maturity']!='in_review' or before['artifact_type'] in EXCLUDED
            or op['metadata'].get('standard_approval')!={'version':VERSION,'model_root_sha256':model.manifest(model.artifacts,_default_scope()).sha256}):
        raise LifecycleError('approval_standard_binding_mismatch')
    if metadata['actor']['actor_type']!='human':raise LifecycleError('approval_human_actor_required')
    history=_history(model.previously_approved_ids)
    base,_,_=_inventory(model.artifacts,[*model.reserved_artifact_ids,*history])
    checked=_preflight(base,preconditions,_files(model.source_files))
    identity=before['id'];state={**base,identity:{**before,'maturity':'approved'}}
    folded=apply_policy(base,_finish(state,base,{identity:[0]},1,checked,hasher=digest),metadata)
    content=lifecycle_content_sha256(before)
    decisions=[{'artifact_id':identity,'base_maturity':'in_review','final_maturity':'approved',
        'base_content_sha256':content,'final_content_sha256':content,'content_changed':False,
        'approval_withdrawn':False,'withdrawal_reason':None,'operation_indices':[0]}]
    events=[{'operation_index':0,'target':identity,'from':'in_review','to':'approved',
        'actor':metadata['actor'],'planned_at':metadata['planned_at'],'metadata':op['metadata']}]
    return LifecycleResult(folded,_snapshot(decisions),_snapshot(events),
        _history=_snapshot(sorted(set(history)|{a['id'] for a in base.values() if a['maturity']=='approved'})))


@dataclass(frozen=True)
class _Check:
    model: object
    operation_bytes: bytes
    metadata_bytes: bytes
    services: object
    packages: tuple

    def __call__(self, context):
        from ..storage.json_syntax import parse_json_object
        from ..model.paths import artifact_path
        from ..validation import ModelDocument
        from ._target_materialization import materialize_target
        from ..qualification.project import validate_project
        folded=prepare(self.model,[parse_json_object(self.operation_bytes)],**parse_json_object(self.metadata_bytes))
        candidates=tuple(ModelDocument(artifact_path(c.data['artifact_type'],c.id,self.model.configuration.id_prefix),jcs(c.data))
                         for c in folded.candidates)
        target=materialize_target(self.model,candidates)
        if ({v['id']:v for v in target.artifacts}!={i:context.artifact(i) for i in context.all_ids}
            or {d.path:d.content for d in target.documents}!={d.path:d.content for d in context.documents}):
            raise ModelError('approval_target_binding_mismatch')
        validate_project({**target.source_files, **dict(self.packages)},services=self.services)
        return context.result()


def gate(model, operation, *, actor, planned_at, services, packages=()):
    def dependencies(context):
        return context.dependency_result({i:list(context.all_ids) for i in context.subjects})
    return ModelGate(GATE,VERSION,dependencies,_Check(model.snapshot(),jcs(operation),
        jcs(dict(metadata_policy_version='change-metadata-v1',actor=actor,planned_at=planned_at)),services,tuple(packages)),model._sources_sha256)


def require_gate(gates, operations, model, *, actor, planned_at):
    if not mode(operations):return
    selected=[g for g in gates if type(g) is ModelGate and g.gate_id==GATE]
    if (len(selected)!=1 or type(selected[0].check) is not _Check or len(operations)!=1
            or selected[0].check.operation_bytes!=jcs(operations[0])
            or selected[0].check.model._sources_sha256!=model._sources_sha256
            or selected[0].check.metadata_bytes!=jcs(dict(metadata_policy_version='change-metadata-v1',actor=actor,planned_at=planned_at))):
        raise LifecycleError('approval_gate_binding_mismatch')
