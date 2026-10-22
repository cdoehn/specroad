"""Domain adapters check supplied values, never execute operations or writes."""
from ..model.record_contracts import SPECIAL_STATES
from ..model.attachments import AttachmentDescriptor
from ..model.paths import project_path
from ..graph.relations import Relation
from .errors import ChangePlanError
from ._common import (_at, _text, _reference, _artifact, _generic, _patch,
                      _normalization_path, _CONTROLLED)

def validate_create(value, pointer):
    identity = _artifact(value['artifact'], pointer + '/artifact')
    _generic(identity, pointer + '/artifact')
    if identity.id_scheme != 'random128-v1':
        raise ChangePlanError('new_identity_requires_random128', pointer=pointer + '/artifact/id_scheme')
    if value['result_id'] != identity.id:
        raise ChangePlanError('creation_identity_mismatch', pointer=pointer + '/result_id', code='SRV146')

def validate_update(value, pointer):
    _patch(value['patch'], pointer + '/patch')

def validate_relation_add(value, pointer):
    _at(pointer + '/relation', Relation, _reference(value['source'], pointer + '/source'), value['relation'])
    if value['relation'].get('id_scheme') != 'random128-v1':
        raise ChangePlanError('new_relation_requires_random128', pointer=pointer + '/relation/id_scheme')

def validate_relation_remove(value, pointer):
    token = value['relation_id']
    if not token.startswith('REL-'):
        raise ChangePlanError('invalid_relation_reference', pointer=pointer + '/relation_id')
    from ..model.identity_tokens import decode128
    _at(pointer + '/relation_id', decode128, token[4:])

def validate_transition(value, pointer):
    if value['from'] == value['to']:
        raise ChangePlanError('transition_requires_distinct_states', pointer=pointer + '/to')
    metadata = value['metadata']
    if set(metadata) & (_CONTROLLED | {v[0] for v in SPECIAL_STATES.values()}):
        raise ChangePlanError('controlled_transition_metadata', pointer=pointer + '/metadata')

def validate_retire(value, pointer):
    return None

def validate_evidence_record(value, pointer):
    _artifact(value['evidence'], pointer + '/evidence', 'evidence')
    if 'import_context' in value:
        _at(pointer + '/import_context/source_path', project_path,
            value['import_context']['source_path'])
    if value.get('configuration_id') is not None:
        identity = _reference(value['configuration_id'], pointer + '/configuration_id')
        if identity.artifact_type != 'configuration':
            raise ChangePlanError('configuration_reference_required', pointer=pointer + '/configuration_id')


def validate_baseline_create(value, pointer):
    identity = _artifact(value['record'], pointer + '/record', 'baseline')
    if identity.id_scheme != 'random128-v1':
        raise ChangePlanError('new_identity_requires_random128', pointer=pointer + '/record/id_scheme')
    if value['record']['baseline_kind'] == 'release' and 'verification_evaluation' not in value['record']:
        raise ChangePlanError('release_baseline_readiness_required', pointer=pointer + '/record/baseline_kind')
    from .baselines import object_documents
    documents = _at(pointer, object_documents, value)
    if value['record']['baseline_kind'] == 'release':
        from ..archive._release_snapshot import release_selection
        _at(pointer, release_selection, value['record'], {d.path: d.content for d in documents})

def validate_attachment_add(value, pointer):
    _at(pointer + '/attachment', AttachmentDescriptor.from_data, value['attachment'])
    if not value['attachment']['path'].startswith('attachments/'):
        raise ChangePlanError('attachment_path_required', pointer=pointer + '/attachment/path')

def validate_attachment_remove(value, pointer):
    _at(pointer + '/path', project_path, value['path'])
    if not value['path'].startswith('attachments/'):
        raise ChangePlanError('attachment_path_required', pointer=pointer + '/path')

def validate_representation_normalize(value, pointer):
    _at(pointer + '/path', project_path, value['path'])
    _normalization_path(value['path'], pointer + '/path')

def validate_relation_review_record(value, pointer):
    _artifact(value['record'], pointer + '/record', 'relation_review')
    if value['record']['reviewer']['actor_type'] != 'human':
        raise ChangePlanError('human_review_required', pointer=pointer + '/record/reviewer')
    for index, entry in enumerate(value['approval_withdrawals']):
        _reference(entry['target'], pointer + '/approval_withdrawals/' + str(index) + '/target')
    seen = set()
    if value['source'] == value['target']:
        raise ChangePlanError('relation_self_reference', pointer=pointer + '/target')
    for index, withdrawal in enumerate(value['approval_withdrawals']):
        at = pointer + '/approval_withdrawals/' + str(index)
        identity = _reference(withdrawal['target'], at + '/target')
        if identity.artifact_type != 'requirement' or identity.id in seen:
            raise ChangePlanError('invalid_approval_withdrawal_target', pointer=at + '/target')
        seen.add(identity.id)
        _text(withdrawal['reason'], at + '/reason')

def validate_proposal_control(value, pointer):
    if _reference(value['target'], pointer + '/target').artifact_type != 'proposal':
        raise ChangePlanError('proposal_target_required', pointer=pointer + '/target')
    transitions = {'draft': {'validated', 'rejected', 'stale'}, 'validated': {'checked', 'rejected', 'stale'}, 'checked': {'in_review', 'rejected', 'stale'}, 'in_review': {'approved', 'rejected', 'stale'}, 'approved': {'applied', 'rejected', 'stale'}}
    previous = None
    for index, event in enumerate(value['events']):
        at = pointer + '/events/' + str(index)
        _text(event['reason'], at + '/reason')
        if event['to'] not in transitions.get(event['from'], ()) or (previous is not None and previous != event['from']):
            raise ChangePlanError('invalid_proposal_control_sequence', pointer=at)
        previous = event['to']

