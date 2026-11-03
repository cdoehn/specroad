"""Inert source plans and declared history; no folding, writes or approvals."""
import base64
from hashlib import sha256

from ...model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ...graph.scope_descriptors import ScopeDescriptor
from ...changes._patch_policy import _patch, _CONTROLLED
from ...model.record_contracts import SPECIAL_STATES
from ...proposals.values import CONTENT_EXCLUSIONS
from .reader import require, path_name, _schema, SourceError

TRANSITIONS = {'draft': {'validated', 'rejected', 'stale'},
    'validated': {'checked', 'rejected', 'stale'}, 'checked': {'in_review', 'rejected', 'stale'},
    'in_review': {'approved', 'rejected', 'stale'}, 'approved': {'applied', 'rejected', 'stale'}}


SPECIFICATION_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'specification',
    'selector': {}, 'configuration_id': None, 'closure_profile': 'core-closure-v1',
    'boundary_policy': 'closed'}


def proposal_basis(snapshot):
    """Project a closed source basis; control dependencies cannot be hidden."""
    controls = {i for i, (_, v) in snapshot['index'].items()
                if v['artifact_type'] in ('proposal', 'baseline')}
    for identity, (_, value) in snapshot['index'].items():
        if identity in controls:
            continue
        targets = [r['target'] for r in value['relations']]
        if value['artifact_type'] == 'verification':
            targets.extend(value['subjects'])
        if value['artifact_type'] == 'evidence':
            targets.extend(r['artifact_id'] for r in value['subjects'])
        if value['artifact_type'] == 'relation_review':
            targets.extend((value['source_id'], value['target_id']))
        if controls.intersection(targets):
            return None
    entries = [r for r in snapshot['entries'] if r['artifact_id'] not in controls]
    return digest({'algorithm': 'reference01-proposal-basis-v1',
        'project_id': snapshot['configuration']['project_id'], 'scope_descriptor': SPECIFICATION_SCOPE,
        'entries': [{k: v for k, v in row.items()
            if row['role'] == 'attachment' or k not in ('size', 'byte_sha256')} for row in entries]})


def _basis_conditions(plan, basis):
    for row in plan['preconditions']:
        if row['kind'] == 'artifact':
            found = basis['index'].get(row['artifact_id'])
            if found is None or found[1]['artifact_type'] in ('proposal', 'baseline'):
                return False
            if 'expected_revision' in row and found[1]['revision'] != row['expected_revision']:
                return False
            if 'expected_sha256' in row and digest(found[1]) != row['expected_sha256']:
                return False
        else:
            # Only source-basis members may satisfy file preconditions.
            names = {r['path'] for r in basis['entries'] if r['artifact_id'] is None
                or basis['index'][r['artifact_id']][1]['artifact_type'] not in ('proposal','baseline')}
            raw = basis['files'].get(row['path']) if row['path'] in names else None
            if row['kind'] == 'file' and (raw is None or sha256(raw).hexdigest() != row['expected_byte_sha256']):
                return False
            if row['kind'] == 'absent' and row['path'] in basis['files']:
                return False
    return True


def binding(value):
    return {'proposal_id': value['id'], 'content_revision': value['content_revision'],
        'content_sha256': value['content_sha256'],
        'base_model_root_sha256': value['base']['model_root_sha256'],
        'change_plan_sha256': value['change_plan']['change_plan_sha256']}


def proposal_fields(value, path, assets):
    require(digest({k: v for k, v in value.items() if k not in CONTENT_EXCLUSIONS}) == value['content_sha256'],
            'source_hash_mismatch', path, 'proposal_content')
    plan = value['change_plan']
    _schema(plan, 'change-plan.json', assets, path)
    ScopeDescriptor(plan['base']['scope_descriptor'])
    require(plan['base']['scope_descriptor'] == SPECIFICATION_SCOPE,
            'source_schema_invalid', path, 'proposal_specification_scope_required')
    require(plan['base'] == value['base'], 'source_hash_mismatch', path, 'proposal_plan_base')
    require(digest({k: v for k, v in plan.items() if k != 'change_plan_sha256'}) == plan['change_plan_sha256'],
            'source_hash_mismatch', path, 'change_plan')
    results, owners, creations = {}, set(), set()
    from .semantics import local_fields, _identity
    for row in plan['result_artifacts']:
        item = row['artifact']; kind = item.get('artifact_type')
        require(kind in assets['artifact_types'] and kind not in ('proposal', 'baseline'),
                'source_schema_invalid', path, 'proposal_result_type')
        _schema(item, 'artifacts/' + kind + '.json', assets, path)
        local_fields(item, path, assets)
        require(item['id'] not in results, 'source_identity_conflict', path)
        require(digest(item) == row['sha256'], 'source_hash_mismatch', path, 'result_artifact')
        results[item['id']] = item
    for op in plan['operations']:
        kind = op['op']
        require(kind not in ('proposal_control', 'baseline_create'), 'source_schema_invalid', path)
        for field in ('source', 'target'):
            if field in op:
                _identity(op[field], assets)
                require(op[field].split('-')[1] not in ('BASE', 'PROP'), 'source_schema_invalid', path)
        target = op.get('source', op.get('target'))
        record_field = {'create': 'artifact', 'evidence_record': 'evidence',
                        'relation_review_record': 'record'}.get(kind)
        if record_field:
            record = op[record_field]; record_kind = record.get('artifact_type')
            require(record_kind in assets['artifact_types'] and record_kind not in ('proposal', 'baseline'),
                    'source_schema_invalid', path)
            _schema(record, 'artifacts/' + record_kind + '.json', assets, path)
            local_fields(record, path, assets)
            require(record['id'] not in creations, 'source_identity_conflict', path)
            creations.add(record['id']); target = record['id']
            if kind == 'create':
                require(record_kind not in SPECIAL_STATES and op['result_id'] == target,
                        'source_schema_invalid', path)
            else:
                require(record_kind == ('evidence' if kind == 'evidence_record' else 'relation_review'),
                        'source_schema_invalid', path)
                require(target in results and jcs(results[target]) == jcs(record),
                        'source_hash_mismatch', path, 'immutable_plan_result')
        if target is not None:
            owners.add(target)
        if kind == 'update':
            _patch(op['patch'], '/change_plan/operations')
        if kind == 'relation_remove':
            require(op['relation_locator']['source_id'] == op['source'],
                    'source_identity_conflict', path)
        if kind == 'transition':
            require(op['from'] != op['to'] and not set(op['metadata']) &
                (_CONTROLLED | {s[0] for s in SPECIAL_STATES.values()}), 'source_state_invalid', path)
        if kind in ('attachment_add', 'attachment_remove'):
            resource = op['attachment']['path'] if kind == 'attachment_add' else op['path']
            path_name(resource)
            require(resource.startswith('attachments/'), 'source_schema_invalid', path)
        if kind == 'representation_normalize':
            path_name(op['path'])
        if kind == 'relation_review_record':
            require(plan['actor']['actor_type'] == 'human', 'source_state_invalid', path)
            for row in op['approval_withdrawals']:
                _identity(row['target'], assets)
                owners.add(row['target'])
    require(set(results) == owners, 'source_closure_incomplete', path, 'plan_result_owners')
    if not plan['operations']:
        require(plan['base']['model_root_sha256'] == plan['expected_result']['model_root_sha256'],
                'source_hash_mismatch', path, 'empty_plan_root')
    conditions = set()
    for row in plan['preconditions']:
        key = ('artifact', row['artifact_id']) if row['kind'] == 'artifact' else ('path', path_name(row['path']))
        require(key not in conditions, 'source_identity_conflict', path)
        conditions.add(key)
    for row in value['control_history']:
        require(row['to'] in TRANSITIONS.get(row['from'], ()), 'source_state_invalid', path)
        try:
            raw = base64.b64decode(row['result_bytes_base64'], validate=True)
        except (ValueError, TypeError) as error:
            raise SourceError('source_schema_invalid', path=path, detail='control_result_encoding') from error
        require(bool(raw) and sha256(raw).hexdigest() == row['result_sha256'],
                'source_hash_mismatch', path, 'control_result_original')


def proposal_history(value, path, snapshots, assets):
    bases = [s for s in snapshots if s['proposal_basis'] == value['base']['model_root_sha256']]
    require(bool(bases), 'source_closure_incomplete', path, 'proposal_original_basis')
    require(any(_basis_conditions(value['change_plan'], s) for s in bases),
            'source_hash_mismatch', path, 'proposal_basis_preconditions')
    revisions = {}
    for snapshot in snapshots:
        entry = snapshot['index'].get(value['id'])
        if entry is None:
            continue
        original = entry[1]; number = original['revision']
        require(number not in revisions or jcs(revisions[number]) == jcs(original),
                'source_identity_conflict', path, 'proposal_revision_conflict')
        revisions[number] = original
    approvals = {}
    for field in ('reviews', 'control_history'):
        for row in value.get(field, ()):
            observed = revisions.get(row['observed_revision'])
            require(observed is not None and row['observed_revision'] < value['revision'],
                    'source_closure_incomplete', path, 'proposal_observed_original')
            require(row['binding'] == binding(observed), 'source_hash_mismatch', path, 'proposal_history_binding')
            if field == 'reviews' and row['binding'] == binding(value):
                actor = row['reviewer']
                require(row['decision'] != 'approved' or observed['proposal_status'] == 'in_review',
                        'source_state_invalid', path)
                if actor['actor_type'] == 'human':
                    approvals[actor['actor_id']] = row['decision'] == 'approved'
    if value['proposal_status'] in ('approved', 'applied'):
        require(any(approvals.values()), 'source_state_invalid', path, 'declared_human_quorum_missing')
    relevant = [row for row in value['control_history'] if row['binding'] == binding(value)]
    state = 'draft'
    for row in relevant:
        require(row['from'] == state, 'source_state_invalid', path, 'control_chain')
        state = row['to']
    require(state == value['proposal_status'], 'source_state_invalid', path, 'control_terminal_state')
    # No result data is promoted into an executed check or actor authentication.
