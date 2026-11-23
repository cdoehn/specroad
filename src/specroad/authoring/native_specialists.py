"""Raw public intentions for the existing document/record authoring specialists.

Only native allocators create identities. Original Evidence is explicit input;
review decisions are explicit human input, never inferred from an actor label.
"""
from copy import deepcopy
from hashlib import sha256
from ..changes import AuthoringError, ChangeOperation
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.identity_values import artifact_identity
from ..model.identities import allocate_artifact_identity
from ..model.relation_identity import allocate_relation_identity, relation_identity
from .creation import _draft
from .inputs import normalize_artifact_create_input

from ..model.authoring_command_ids import SPECIAL_COMMANDS as COMMANDS

KINDS = {'view.create':'view','document.create':'document','section.add':'section','block.add':'content_block'}
FIELDS = {
    'view.create': {'fields'}, 'document.create': {'fields'}, 'section.add': {'fields','parent_id','position'},
    'block.add': {'fields','parent_id','position'},
    'section.move': {'target','parent_id','position','expected_relation_sha256','reason'},
    'section.remove': {'target','expected_revision','expected_sha256','reason','cascade','move_children_to','position'},
    'block.update': {'target','patch','options','expected_revision','expected_sha256'},
    'block.remove': {'target','expected_revision','expected_sha256','reason'},
    'baseline.create': {'name','configuration_id','release_id'},
    'relation.review': {'source','relation_id','decision','reason','comment','expected_revision','expected_sha256'},
    'evidence.record': {'verification_id','record','configuration_id'},
    'evidence.import': {'source_path','source_sha256','policy','title','configuration_id',
        'import_format','mapping_path','mapping_sha256','measurements_path','measurements_sha256',
        'external_identifiers_path','external_identifiers_sha256','tool','run_context'},
}


def compile_specialist(intent, sources, actor, time, *, recorded=None):
    name = intent['command_id']
    if set(intent) - FIELDS[name] - {'command_id'}:
        raise AuthoringError('unexpected_authoring_field')
    data = {k:v for k,v in intent.items() if k!='command_id'}
    old = None if recorded is None else [ChangeOperation(op).data for op in recorded]
    try:
        result = _compile(name, data, sources, actor, time, old)
        from .plans import _operations
        result = _operations(name, result)
    except KeyError as error:
        raise AuthoringError('missing_authoring_input') from error
    if old is not None and jcs(result) != jcs(old):
        raise AuthoringError('request_operations_conflict', exit_code=6)
    return result


def _compile(name, data, sources, actor, time, old):
    def allocate(kind):
        return allocate_artifact_identity(kind, sources.identities).identity
    def relation():
        return allocate_relation_identity(sources.relations).identity
    def guards():
        return {k:data[k] for k in ('expected_revision','expected_sha256') if k in data}
    if name in KINDS:
        kind = KINDS[name]
        identity = artifact_identity(old[0]['artifact']) if old is not None else allocate(kind)
        prepared = normalize_artifact_create_input(kind, data['fields'])
        value = _draft(prepared, identity, actor, time, sources.source.configuration)
        result = [{'op':'create','artifact':value,'result_id':identity.id}]
        if name not in ('document.create','view.create'):
            from ._document_operations import _contains
            edge = relation_identity(old[1]['relation']) if old is not None else relation()
            result.append(_contains(data['parent_id'], identity.id, edge, data['position'], actor, time))
        return result
    if name in ('block.update','block.remove'):
        from .native_intents import compile_intent, _artifact
        if old is None and _artifact(sources,data['target'])['artifact_type'] != 'content_block':
            raise AuthoringError('document_content_block_required',exit_code=3)
        mapped = {**data, 'command_id':'artifact.update' if name=='block.update' else 'lifecycle.transition'}
        if name=='block.remove':mapped['to']='retired'
        return compile_intent(mapped,sources,actor,time,recorded=old)
    if name=='section.move':
        from ._document_operations import _move, _reparent
        kwargs=dict(parent_id=data['parent_id'],position=data['position'],
            expected_relation_sha256=data['expected_relation_sha256'],reason=data['reason'],actor=actor,planned_at=time)
        if old is not None:
            return _reparent(old[0]['source'],old[0]['relation_id'],data['target'],
                relation_identity=relation_identity(old[1]['relation']),**kwargs)
        return _move(sources.model,data['target'],relation_identity=relation(),**kwargs)[1]
    if name=='section.remove':
        return _remove_section(data,sources,actor,time,old)
    if name=='baseline.create':
        from ..changes.baselines import prepare_baseline_operation, object_documents
        if old is None:
            return [prepare_baseline_operation(sources.model,baseline_id=allocate('baseline').id,
                name=data['name'],actor=actor,planned_at=time,
                **{k:data[k] for k in ('configuration_id','release_id') if k in data})]
        op=deepcopy(old[0]);record=op['record'];record['title']=data['name']
        if record['scope_descriptor'].get('configuration_id') != data.get('configuration_id'):
            raise AuthoringError('request_operations_conflict',exit_code=6)
        release=None
        if record['baseline_kind']=='release':
            from ..archive._release_snapshot import release_selection
            release=release_selection(record,{d.path:d.content for d in object_documents(op)})['release_id']
        if release!=data.get('release_id'):raise AuthoringError('request_operations_conflict',exit_code=6)
        return [op]
    if name=='relation.review':
        from .negative_reviews import _intent, _operation, _preflight_context
        from ..changes.reviews import prepare_review_record, review_time
        from ..changes.negative_reviews import prepare_negative_review_record, required_review_withdrawals
        intent=_intent(data['source'],data['relation_id'],data['decision'],data['reason'],data.get('comment'),guards())
        if old is not None:
            return [_operation(intent,old[0]['record'],old[0]['approval_withdrawals']).data]
        context=_preflight_context(sources.model,intent)
        identity=allocate('relation_review')
        if review_time(sources.model.artifacts,context,time)!=time:
            raise AuthoringError('review_timestamp_not_newest',exit_code=6)
        options=dict(actor=actor,planned_at=time,reason=data['reason'],comment=data.get('comment'))
        negative=data['decision']=='rejected'
        record=(prepare_negative_review_record(context,identity,**options) if negative else
            prepare_review_record(context,identity,decision='confirmed',**options))
        withdrawals=required_review_withdrawals(sources.model.artifacts,data['source'],data['relation_id'],
            profile=sources.model.profile) if negative else []
        return [_operation(intent,record,withdrawals).data]
    if name=='evidence.record':
        from .evidence import prepare_evidence_operation
        from ..storage.record_artifact import RecordArtifact
        record=RecordArtifact(jcs(data['record']),expected_type='evidence')
        return [prepare_evidence_operation(data['verification_id'],record,
            configuration_id=data.get('configuration_id')).data]
    from ..changes.evidence_import import _EvidenceSetPlanner
    extras = {k:data[k] for k in ('mapping_path','mapping_sha256','measurements_path','measurements_sha256',
        'external_identifiers_path','external_identifiers_sha256','tool','run_context') if k in data}
    format_name = data.get('import_format','generic')
    if old is not None:
        expected={'source_path':data['source_path'],'source_sha256':data['source_sha256'],
            'policy':data['policy'],'import_format':format_name}
        if any(op['op']!='evidence_record' or any(op.get('import_context',{}).get(k)!=v for k,v in expected.items())
            or {k:v for k,v in op['import_context'].items() if k in FIELDS['evidence.import'] - set(expected)} != extras
            or op['evidence']['title']!=data['title'] or op.get('configuration_id')!=data.get('configuration_id') for op in old):
            raise AuthoringError('request_operations_conflict',exit_code=6)
        return old
    raw=sources.model.source_files.get(data['source_path'])
    if raw is None or sha256(raw).hexdigest()!=data['source_sha256']:
        raise AuthoringError('evidence_original_binding_changed',exit_code=6)
    planner=_EvidenceSetPlanner(sources.model,data['source_path'],data['policy'],format_name=format_name,extras=extras)
    ids=[];inventory=sources.identities
    for _ in range(planner.candidate_count):
        allocation=allocate_artifact_identity('evidence',inventory)
        ids.append(allocation.identity.id);inventory=allocation.inventory
    return planner.new_operations(ids,title=data['title'],configuration_id=data.get('configuration_id'),actor=actor,planned_at=time)

from ._native_section_removal import _remove_section
