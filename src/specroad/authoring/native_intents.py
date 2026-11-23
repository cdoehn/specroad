"""Passive raw authoring intentions compiled by existing native adapters."""
from ..changes.request_ids import AuthoringError
from ..changes import ChangeOperation
from ..model.canonical import canonical_json_bytes as jcs
from ..model.identities import allocate_artifact_identity
from ..model.relation_identity import allocate_relation_identity, relation_identity
from ..model.identity_values import artifact_identity
from .creation import _draft
from .inputs import normalize_artifact_create_input

from ..model.authoring_command_ids import COMMANDS, BASIC_COMMANDS, SPECIAL_COMMANDS


def compile_intent(intent, sources, actor, time, *, recorded=None):
    command = intent['command_id']
    if command in SPECIAL_COMMANDS:
        from .native_specialists import compile_specialist
        return compile_specialist(intent, sources, actor, time, recorded=recorded)
    common = {'command_id'}
    allowed = {'artifact.create': {'artifact_type', 'fields'},
        'artifact.update': {'target', 'patch', 'options', 'expected_revision', 'expected_sha256'},
        'lifecycle.transition': {'target', 'to', 'reason', 'expected_revision', 'expected_sha256'},
        'relation.add': {'source', 'type', 'target', 'rationale', 'position'},
        'relation.remove': {'source', 'relation_id', 'expected_sha256', 'reason'}}
    if command not in allowed or set(intent) - common - allowed[command]:
        raise AuthoringError('invalid_authoring_intent')
    required = {'artifact.create': {'artifact_type','fields'}, 'artifact.update': {'target'},
        'lifecycle.transition': {'target','to','reason'}, 'relation.add': {'source','type','target'},
        'relation.remove': {'source','relation_id','expected_sha256','reason'}}[command]
    if not required <= set(intent):
        raise AuthoringError('missing_authoring_input')
    if recorded is not None:
        if len(recorded) != 1:
            raise AuthoringError('request_operations_conflict', exit_code=6)
        recorded = ChangeOperation(recorded[0]).data
    if command == 'artifact.create':
        prepared = normalize_artifact_create_input(intent['artifact_type'], intent['fields'])
        identity = (artifact_identity(recorded['artifact']) if recorded is not None else
                    allocate_artifact_identity(intent['artifact_type'], sources.identities).identity)
        value = _draft(prepared, identity, actor, time, sources.source.configuration)
        result = {'op': 'create', 'artifact': value, 'result_id': value['id']}
    elif command == 'artifact.update':
        guards = {k: intent[k] for k in ('expected_revision', 'expected_sha256') if k in intent}
        if recorded is not None:
            if ('patch' in intent) == ('options' in intent):
                raise AuthoringError('exactly_one_update_input_required')
            patch = intent.get('patch')
            if 'options' in intent:
                patch = _recorded_options(intent['options'], recorded['patch'])
            result = {'op': 'update', 'target': intent['target'], 'patch': patch, **guards}
        else:
            from ..changes.update_inputs import normalize_artifact_update_input
            value = _artifact(sources, intent['target'])
            result = normalize_artifact_update_input(value, **guards,
                **{k: intent[k] for k in ('patch', 'options') if k in intent}).data
    elif command == 'lifecycle.transition':
        if recorded is not None:
            if intent['to'] == 'retired':
                result = {'op': 'retire', 'target': intent['target'], 'reason': intent['reason'],
                          **{k: intent[k] for k in ('expected_revision', 'expected_sha256') if k in intent}}
            else:
                if set(intent) & {'expected_revision', 'expected_sha256'}:
                    raise AuthoringError('unexpected_transition_guard')
                result = {'op': 'transition', 'target': intent['target'], 'from': recorded['from'],
                          'to': intent['to'], 'metadata': {'reason': intent['reason']}}
                for key in ('requirement_approval', 'standard_approval'):
                    if key in recorded.get('metadata', {}):
                        result['metadata'][key] = recorded['metadata'][key]
        else:
            from ..changes.lifecycle_inputs import normalize_retire_input, normalize_transition_input
            value = _artifact(sources, intent['target'])
            if intent['to'] == 'retired':
                result = normalize_retire_input(value, reason=intent['reason'],
                    **{k: intent[k] for k in ('expected_revision', 'expected_sha256') if k in intent}).data
            else:
                if set(intent) & {'expected_revision', 'expected_sha256'}:
                    raise AuthoringError('unexpected_transition_guard')
                result = normalize_transition_input(value, to=intent['to'], reason=intent['reason']).data
    elif command == 'relation.add':
        if recorded is None:
            _artifact(sources, intent['source'])
        from ..changes.relation_inputs import normalize_relation_add_input, _addition
        prepared = normalize_relation_add_input(intent['source'], intent['type'], intent['target'],
            **{k: intent[k] for k in ('rationale', 'position') if k in intent})
        identity = (relation_identity(recorded['relation']) if recorded is not None else
                    allocate_relation_identity(sources.relations).identity)
        result = _addition(prepared, identity, actor, time).data
    else:
        if recorded is None:
            _artifact(sources, intent['source'])
        result = {'op': 'relation_remove', **{k: intent[k] for k in
            ('source', 'relation_id', 'expected_sha256', 'reason')}}
    result = ChangeOperation(result).data
    if recorded is not None and jcs(result) != jcs(recorded):
        raise AuthoringError('request_operations_conflict', exit_code=6)
    return [result]


def _artifact(sources, identity):
    result = next((v for v in sources.model.artifacts if v['id'] == identity), None)
    if result is None:
        raise AuthoringError('authoring_target_missing', exit_code=3)
    if result['artifact_type'] in ('implementation_plan', 'plan_entry'):
        raise AuthoringError('plan_native_command_required', exit_code=2)
    return result


def _recorded_options(options, patch):
    # The old operation is a verified historical witness of add versus replace.
    # Do not compile set/unset against an already modified live document.
    from ..changes._patch_values import _strict_value
    if type(options) not in (list, tuple) or len(options) != len(patch):
        raise AuthoringError('request_operations_conflict', exit_code=6)
    for pair, operation in zip(options, patch):
        if type(pair) not in (list, tuple) or len(pair) != 2:
            raise AuthoringError('ordered_options_required')
        flag, value = pair
        if flag == '--set':
            pointer, sep, raw = value.partition('=')
            match = bool(sep) and operation['op'] in ('add', 'replace') and operation['path'] == pointer
            match = match and jcs(_strict_value(raw, '/options')) == jcs(operation['value'])
        else:
            match = flag == '--unset' and operation == {'op': 'remove', 'path': value}
        if not match:
            raise AuthoringError('request_operations_conflict', exit_code=6)
    return patch
