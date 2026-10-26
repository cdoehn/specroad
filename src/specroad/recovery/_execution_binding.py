"""Original request reconstruction and independently checked persisted layouts."""
from types import SimpleNamespace

from ..changes.authoring import normalize_authoring_actor, normalize_request_id
from ..changes._journal_codec import _text
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.operational_paths import passive_journal_directory
from ..storage.json_syntax import parse_json_object
from ._execution_layout import execution_layout
from ._journal_selection import journal_selection
from .values import require, persisted_contract


def active_paths(entries):
    found = []
    for row in entries:
        parts = row['path'].split('/')
        if (len(parts) == 3 and parts[0] == '.specroad' and parts[1] in ('transactions', 'recovery')
                and not (row['kind'] == 'directory' and passive_journal_directory(parts[1], parts[2]))
                and row['kind'] != 'missing'):
            found.append(row['path'])
    return tuple(sorted(found))


def original_active(plan):
    return active_paths(plan.data['inventory']['entries'])


def restore_request(plan, project, actor, request_id, selection):
    data = plan.data
    return {'action': 'restore', 'project_id': data['project_id'],
        'project_root': data['project_root'], 'root_identity': list(project._root_identity),
        'restore_plan_sha256': data['restore_plan_sha256'], 'plan_bytes_sha256': plan.sha256,
        'source_sha256': data['source']['sha256'], 'inventory_sha256': data['inventory']['sha256'],
        'expected_target_root': data['expected_target_root'], 'target_sha256': data['target']['sha256'],
        'backup_sha256': data['backup']['sha256'], 'affected_journals': selection,
        'selection_sha256': canonical_json_sha256(selection), 'actor': actor.as_fields(), 'request_id': request_id}


@persisted_contract
def checked_layout(raw, plan, project):
    value = parse_json_object(raw)
    require(canonical_json_bytes(value) == raw, 'restore_execution_bytes_invalid')
    request = value.get('request')
    require(type(request) is dict and 'actor' in request and 'request_id' in request,
            'restore_execution_request_missing')
    actor = normalize_authoring_actor(request['actor'])
    identity = normalize_request_id(request['request_id'])
    identity = None if identity is None else identity.value
    require(actor.actor_type not in ('ai', 'ci') or identity is not None,
            'restore_execution_request_missing')
    selection = journal_selection(plan, canonical_json_bytes(request.get('affected_journals')),
                                  original_active(plan))
    require(request == restore_request(plan, project, actor, identity, selection),
            'restore_original_request_conflict', exit_code=6)
    require(_text(value.get('authority_id')) and _text(value.get('authority_version')),
            'restore_execution_attribution_missing')
    # Attribution is inert data. No saved authority is made callable.
    attribution = SimpleNamespace(authority_id=value['authority_id'], version=value['authority_version'])
    layout = execution_layout(plan, request, attribution)
    require(layout['own'][layout['active'] + '/intent.json'] == raw,
            'restore_execution_binding_conflict', exit_code=6)
    return layout
