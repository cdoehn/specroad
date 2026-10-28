"""Passive Restore result bindings; never current project authorization.

The installed live adapter proves the native completion before publishing these
bytes. Readers prove retention and consistency with that original Work order,
not a new observation of the current project or a human product approval.
"""
from hashlib import sha256
from types import SimpleNamespace

from ..changes.authoring import normalize_authoring_actor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..recovery._execution_binding import restore_request
from ..recovery.values import guarded, persisted_contract, require
from ..storage.json_syntax import parse_json_object
from ._data_contract import _hash, _object, _text


COMPLETION_FIELDS = frozenset(('format_version', 'request_sha256', 'request', 'result',
    'expected_target_root', 'backup_manifest_sha256', 'authority_id', 'authority_version',
    'historical_findings'))


@guarded
@persisted_contract
def transaction(value, objects, *, initial=None):
    from .manifest import _bytes, _entries
    from .restore_execution import _units
    raw = _bytes(value['plan_binding']['plan_source'], objects)
    tasks = _entries('tasks', value['manifests']['tasks'], objects)
    done = _entries('completed', value['manifests']['completed'], objects)
    require([{k: t[k] for k in ('key', 'phase', 'range')} for t in tasks] == _units(raw)
            and done and done[0]['unit_id'] == tasks[0]['unit_id'],
            'restore_work_execution_plan_required', exit_code=6)
    evidence_raw = _bytes(done[0]['evidence'], objects)
    evidence = parse_json_object(evidence_raw)
    _object(evidence, ('format_version', 'work_id', 'unit_id',
                      'initial_checkpoint_sha256', 'tool_build', 'completion'))
    _hash(evidence['initial_checkpoint_sha256'])
    require(evidence['format_version'] == 'restore-work-transaction-v1'
            and evidence['work_id'] == value['work_id']
            and evidence['unit_id'] == tasks[0]['unit_id']
            and evidence['tool_build'] == value['tool_build']
            and canonical_json_bytes(evidence) == evidence_raw,
            'restore_work_evidence_binding_conflict', exit_code=6)
    if initial is not None:
        require(evidence['initial_checkpoint_sha256'] == initial.as_dict()['checkpoint_sha256'],
                'restore_work_evidence_binding_conflict', exit_code=6)
    completion = evidence['completion']
    _object(completion, COMPLETION_FIELDS)
    require(completion['format_version'] == 'restore-completion-v1'
            and completion['result'] == 'restored', 'restore_work_completion_invalid')
    _text(completion['authority_id']); _text(completion['authority_version'])
    require(type(completion['historical_findings']) is list, 'restore_work_completion_invalid')
    request = completion['request']
    identity = request['root_identity']
    require(type(identity) is list and len(identity) == 2
            and all(type(n) is int and n >= 0 for n in identity), 'restore_work_completion_invalid')
    # Root identity is historical attribution here, never a live root handle.
    data = parse_json_object(raw)
    plan = SimpleNamespace(data=data, sha256=sha256(raw).hexdigest())
    selection = parse_json_object(_bytes(value['plan_binding']['journal_selection'], objects))
    expected = restore_request(plan, SimpleNamespace(_root_identity=identity),
        normalize_authoring_actor(value['actor']), value['request_id'], selection)
    token = canonical_json_sha256(expected)
    backup = {'format_version': 'restore-backup-v1', 'request_sha256': token,
              'inventory': data['inventory'], 'backup': data['backup']}
    require(request == expected and completion['request_sha256'] == token
            and completion['expected_target_root'] == data['expected_target_root']
            and completion['backup_manifest_sha256'] == canonical_json_sha256(backup),
            'restore_work_completion_binding_conflict', exit_code=6)
    return completion


@guarded
@persisted_contract
def outcome(value, objects, document):
    """Validate a complete original native payload without pruning findings."""
    completion = transaction(value, objects)
    fresh = 'normative_paths' in document
    _object(document, COMPLETION_FIELDS | {'recovery_required', 'audit_path'}
            | ({'normative_paths'} if fresh else {'replayed', 'source_observation'}))
    require({key: document[key] for key in COMPLETION_FIELDS} == completion,
            'restore_work_result_differs_from_native_completion', exit_code=6)
    require(document['recovery_required'] is False,
            'restore_work_result_incomplete')
    if fresh:
        from .manifest import _bytes
        from ..recovery._operational_history import operational_path
        plan = parse_json_object(_bytes(value['plan_binding']['plan_source'], objects))
        before = {r['path']: r for r in plan['inventory']['entries'] if r['kind'] == 'file'}
        target = {r['path']: r for r in plan['target']['entries']}
        changed = sorted({p for p in before if not operational_path(p) and p not in target}
            | {p for p, row in target.items() if before.get(p) != {**row, 'kind': 'file'}},
            key=lambda p: p.encode('utf-8'))
        require(document['normative_paths'] == changed, 'restore_work_result_paths_changed', exit_code=6)
    else:
        require(type(document['replayed']) is bool, 'restore_work_result_incomplete')
        observation = document['source_observation']
        _object(observation, ('status', 'reason'))
        require(observation['status'] in ('unchanged', 'unavailable_or_changed'),
                'restore_work_source_observation_invalid')
        if observation['status'] == 'unchanged':
            require(observation['reason'] is None, 'restore_work_source_observation_invalid')
        else:
            _text(observation['reason'])
    require(document['audit_path'] == '.specroad/recovery/archive/'
            + completion['request_sha256'] + '/completed.json',
            'restore_work_audit_binding_conflict', exit_code=6)
    return document


def projection(value, objects, document):
    """Paths are relative to the independently checked external Work root."""
    from .manifest import _entries
    document = outcome(value, objects, document)
    raw = canonical_json_bytes(document)
    digest = sha256(raw).hexdigest()
    name = 'result-' + digest + '.json'
    execution = _entries('completed', value['manifests']['completed'], objects)[0]['evidence']
    manifest = canonical_json_bytes({'format_version': 'restore-work-result-files-v1',
        'work_id': value['work_id'], 'command_id': value['command_id'],
        'transaction_evidence': execution, 'files': [{'path': 'results/' + name,
            'size': len(raw), 'sha256': digest, 'media_type': 'application/json',
            'role': 'restore_result'}]})
    return ((name, raw), ('manifest-' + sha256(manifest).hexdigest() + '.json', manifest))


def delivery_evidence(value, objects, document):
    from .manifest import _entries
    tasks = _entries('tasks', value['manifests']['tasks'], objects)
    files = projection(value, objects, document)
    return canonical_json_bytes({'format_version': 'restore-work-delivery-v1',
        'work_id': value['work_id'], 'unit_id': tasks[1]['unit_id'],
        'outcome': document, 'files': [{'path': 'results/' + name,
            'size': len(raw), 'sha256': sha256(raw).hexdigest()} for name, raw in files]})


@guarded
@persisted_contract
def saved_delivery(value, objects):
    from .manifest import _bytes, _entries
    done = _entries('completed', value['manifests']['completed'], objects)
    tasks = _entries('tasks', value['manifests']['tasks'], objects)
    require(len(done) == 2 and [d['unit_id'] for d in done] == [t['unit_id'] for t in tasks],
            'restore_work_delivery_required', exit_code=6)
    raw = _bytes(done[1]['evidence'], objects)
    document = parse_json_object(raw)['outcome']
    require(raw == delivery_evidence(value, objects, document),
            'restore_work_delivery_binding_conflict', exit_code=6)
    return document


def final_outcome(value, objects, document, exit_code):
    require(value['command_id'] == 'recover.restore' and value['command_class'] == 'recovery_write'
            and type(exit_code) is int and exit_code == 0,
            'restore_work_result_incomplete')
    require(canonical_json_bytes(document) == canonical_json_bytes(saved_delivery(value, objects)),
            'restore_work_final_result_changed', exit_code=6)

