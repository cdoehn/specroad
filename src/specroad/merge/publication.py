"""Merge plan producer and adapter to the shared native snapshot writer."""
from dataclasses import dataclass
from pathlib import Path
from ..model.canonical import canonical_json_sha256 as digest
from ..changes.core import prepare_change_plan
from ..changes.values import ChangePlan
from ..changes.locking import project_lock
from ..changes._lock_files import LockFiles
from ..changes.publication_values import PublicationAuthority
from ..changes._journal_codec import _transaction
from ..changes.schema_transition_values import authoring, SchemaTransitionError
from ..changes.schema_transition import publish_schema_transition
from ..changes.schema_transition_recovery import historical_request
from ..migration.plan_values import b64, file_bindings, changes
from ..migration._backup_source import _observe
from ..storage.operational_preflight import observe_operational_preflight
from ..recovery._owned_checks import owned_checks
from .sources import MergeSources
from ._recorded import capture_sources
from .target import verify_merge_target
from .publication_target import reconstructed, result_artifacts
from .publication_contract import require


@owned_checks
def plan_merge_publication(root, target_raw, metadata_raw, plan_raw, sources, *, history,
        expected_target_sha256, expected_metadata_sha256, expected_plan_sha256,
        change_plan_id, actor, planned_at, request_id=None, services=None):
    require(type(sources) is MergeSources,'merge_live_sources_required')
    checked=verify_merge_target(target_raw,metadata_raw,plan_raw,sources,history=history,
        expected_target_sha256=expected_target_sha256,expected_metadata_sha256=expected_metadata_sha256,
        expected_plan_sha256=expected_plan_sha256,services=services)
    require(checked.data['target_validated'] is True,'merge_publication_target_invalid')
    from ..snapshots import SourceRequest,SourceSnapshot
    ours=SourceSnapshot(SourceRequest(root))
    require(ours.files==sources.ours.files and ours.binding['model_root_sha256']==sources.ours.binding['model_root_sha256'],
            'merge_publication_current_ours_changed')
    files,_,current=_observe(root)
    inputs={'plan_bytes_base64':b64(plan_raw),'metadata_bytes_base64':b64(metadata_raw),
        'target_bytes_base64':b64(target_raw),'plan_sha256':expected_plan_sha256,'metadata_sha256':expected_metadata_sha256,
        'target_sha256':expected_target_sha256,'history':history,'sources':capture_sources(sources),
        'target_configuration':b64(checked.files['specroad.json'])}
    _,candidate,target=reconstructed(inputs,files)
    results=result_artifacts(sources.ours.files,candidate.files)
    operation={'op':'merge_publish','format_version':'merge-publication-v1','inputs':inputs,'inputs_sha256':digest(inputs),
        'source_files':file_bindings(files),'target_files':file_bindings(target),'changes':changes(files,target),
        'result_ids':[r['artifact']['id'] for r in results],
        'source_model_root_sha256':sources.ours.binding['model_root_sha256'],
        'target_model_root_sha256':checked.data['expected_target_model_root_sha256']}
    conditions=[{'kind':'file','path':r['path'],'expected_byte_sha256':r['sha256']} for r in operation['source_files']]
    conditions += [{'kind':'absent','path':r['path']} for r in operation['target_files'] if r['path'] not in files]
    result=prepare_change_plan({'format_version':'1.2.0','metadata_policy_version':'merge-metadata-v1',
        'change_plan_id':change_plan_id,'request_id':request_id,'planned_at':planned_at,'actor':actor,
        'base':{'scope_descriptor':sources.ours.binding['scope_descriptor'],'model_root_sha256':operation['source_model_root_sha256']},
        'operations':[operation],'preconditions':conditions,'result_artifacts':results,
        'expected_result':{'model_root_sha256':operation['target_model_root_sha256']}})
    current();ours.verify_current()
    for role in ('base','ours','theirs'):getattr(sources,role).verify_current()
    return result


@dataclass(frozen=True)
class MergePublicationContext:
    sources: MergeSources
    root: Path
    services: object
    def check(self):
        # A same-root local source is intentionally changed by this writer.
        # The common guard proves its full before/after prefix on every effect.
        for role in ('base','ours','theirs'):
            source=getattr(self.sources,role)
            if source.kind=='local' and Path(source.source_root)==self.root: continue
            source.verify_current()


@owned_checks
def apply_merge_publication(root, raw, *, expected_plan_sha256, sources, transaction_id,
        backup_descriptor, authority, services=None):
    """One explicit attempt; preserve failed state for native recovery."""
    require(type(raw) is bytes and type(authority) is PublicationAuthority,'merge_publication_explicit_authority_required')
    plan=ChangePlan(raw)
    require(plan.data['metadata_policy_version']=='merge-metadata-v1' and plan.sha256==expected_plan_sha256,
            'merge_publication_plan_binding')
    authoring(plan);_transaction(transaction_id)
    op=plan.data['operations'][0];project_id=op['inputs']['sources']['ours']['binding']['project_id']
    with LockFiles(root) as files:
        require(observe_operational_preflight(files.boundary)['consistency_state']=='consistent','merge_publication_recovery_required')
        historical=historical_request(files,plan,project_id)
        if historical is not None:return historical
        original_root=files.boundary._root_identity
        canonical_root=files.boundary.root
    require(type(sources) is MergeSources and capture_sources(sources)==op['inputs']['sources'],'merge_publication_sources_changed')
    for role in ('base','ours','theirs'):getattr(sources,role).verify_current()
    context=MergePublicationContext(sources,canonical_root,services)
    with project_lock(root,kind='writer',command='merge apply',project_id=project_id,
            request_id=plan.data['request_id'],transaction_id=transaction_id) as held:
        require(held._files.boundary._root_identity==original_root,'merge_publication_root_changed')
        historical=historical_request(held._files,plan,project_id)
        if historical is not None:return historical
        try:
            context.check()
            return publish_schema_transition(plan,held_lock=held,backup_descriptor=backup_descriptor,
                authority=authority,merge_context=context)
        except Exception as error:
            if isinstance(error,SchemaTransitionError):raise
            raise SchemaTransitionError(getattr(error,'reason','merge_publication_interrupted'),
                exit_code=getattr(error,'exit_code',6),write_state='unknown') from error
