"""Closed migration branch of the shared Change Plan, without source execution."""
from hashlib import sha256
from ..changes._schema_fields import obj, arr, text, digest as hash_schema
from ..changes.errors import ChangePlanError
from ..model.canonical import canonical_json_sha256 as digest
from ..model._schema import validate_builtin
from .plan_values import (POLICY, STEP, SOURCE_CONTRACT, safe_path, unb64,
                          MigrationPlanError)
from .reference01.values import SCOPE


def nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}


def inputs_schema():
    requirement = obj({'artifact_id': text(), 'source_sha256': hash_schema(),
        'language': text(), 'normative_force': {'enum': ['must', 'must_not', 'should', 'may']},
        'statement': text()})
    proposal = obj({'artifact_id': text(), 'source_sha256': hash_schema(),
                    'change_plan': {'type': 'object'}})
    return obj({'format_version': {'const': 'migration-inputs-v1'},
        'target_configuration': nullable({'type': 'string'}),
        'target_resources': arr(obj({'path': text(), 'bytes_base64': {'type': 'string'}})),
        'requirement_mappings': arr(requirement), 'proposal_mappings': arr(proposal)})


def migration_operation_schema():
    contract = obj({'schema_version': text(), 'contract_sha256': hash_schema()})
    files = arr(obj({'path': text(), 'size': {'type': 'integer', 'minimum': 0},
                     'sha256': hash_schema()}))
    return obj({'op': {'const': 'schema_migrate'}, 'format_version': {'const': 'schema-migrate-v1'},
        'source_contract': contract, 'target_contract': contract,
        'steps': arr(obj({'step_id': {'const': STEP}, 'source_contract': contract,
            'target_contract': contract, 'direction': {'const': 'forward'}, 'reversible': {'const': False}})),
        'inputs': inputs_schema(), 'inputs_sha256': hash_schema(),
        'source_files': files, 'target_files': files,
        'changes': arr(obj({'path': text(), 'before_sha256': nullable(hash_schema()),
            'after_sha256': nullable(hash_schema()), 'after_bytes_base64': nullable({'type': 'string'})})),
        'result_ids': arr(text()), 'source_model_root_sha256': hash_schema(),
        'target_model_root_sha256': hash_schema(), 'target_manifest': {'type': 'object'},
        'new_required_fields': arr(obj({'path': text(), 'fields': arr(text())})),
        'losses': arr({'type': 'object'}), 'protected_paths': arr(text())})


def _check(ok, reason):
    if not ok:
        raise ChangePlanError(reason, code='SRV146')


def _sorted_rows(rows, field):
    keys = [r[field] for r in rows]
    _check(keys == sorted(set(keys), key=lambda s: s.encode('utf-8')), 'migration_noncanonical_order')


def validate_inputs(value):
    validate_builtin(value, inputs_schema())
    for name, key in [('target_resources', 'path'), ('requirement_mappings', 'artifact_id'),
                      ('proposal_mappings', 'artifact_id')]:
        _sorted_rows(value[name], key)
    # Invalid authored languages are errors even when another input is missing.
    # This is syntax checking, never language detection or registry inference.
    from ..model.language_tags import parse_language_tag
    for row in value['requirement_mappings']:
        parse_language_tag(row['language'])
    if value['target_configuration'] is not None:
        unb64(value['target_configuration'])
    for row in value['target_resources']:
        safe_path(row['path']); unb64(row['bytes_base64'])


def validate_migration_operation(value, pointer=''):
    """Local integrity only. Actual sources and native recomputation are separate."""
    try:
        validate_builtin(value, migration_operation_schema())
        validate_inputs(value['inputs'])
        _check(digest(value['inputs']) == value['inputs_sha256'], 'migration_inputs_hash_mismatch')
        _check(value['source_contract'] == SOURCE_CONTRACT, 'migration_source_contract_mismatch')
        _check(value['target_contract']['schema_version'] == '0.2.0', 'migration_target_version_mismatch')
        expected = {'step_id': STEP, 'source_contract': SOURCE_CONTRACT,
            'target_contract': value['target_contract'], 'direction': 'forward', 'reversible': False}
        _check(value['steps'] == [expected], 'migration_path_mismatch')
        _check(not value['losses'], 'migration_loss_path_unsupported')
        for field in ('source_files', 'target_files', 'changes', 'new_required_fields'):
            _sorted_rows(value[field], 'path')
            for row in value[field]: safe_path(row['path'])
        for field in ('result_ids', 'protected_paths'):
            _check(value[field] == sorted(set(value[field]), key=lambda s: s.encode('utf-8')),
                   'migration_noncanonical_order')
        before = {r['path']: r for r in value['source_files']}
        after = {r['path']: r for r in value['target_files']}
        actual = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
        _check({r['path'] for r in value['changes']} == actual, 'migration_change_set_mismatch')
        for row in value['changes']:
            name = row['path']; old, new = before.get(name), after.get(name)
            _check(row['before_sha256'] == (None if old is None else old['sha256']),
                   'migration_before_hash_mismatch')
            _check(row['after_sha256'] == (None if new is None else new['sha256']),
                   'migration_after_hash_mismatch')
            if new is None:
                _check(row['after_bytes_base64'] is None, 'migration_deleted_bytes')
            else:
                raw = unb64(row['after_bytes_base64'])
                _check(len(raw) == new['size'] and sha256(raw).hexdigest() == new['sha256'],
                       'migration_target_bytes_mismatch')
        for name in value['protected_paths']:
            safe_path(name)
            _check(name in before and before[name] == after.get(name), 'migration_original_changed')
        manifest = value['target_manifest']
        _check(digest(manifest) == value['target_model_root_sha256'], 'migration_target_root_mismatch')
        _check('scope_sha256' in manifest and digest({k: v for k, v in manifest.items()
            if k not in ('model_manifest_version', 'scope_sha256')}) == manifest['scope_sha256'],
            'migration_scope_hash_mismatch')
    except MigrationPlanError as error:
        raise ChangePlanError(error.reason, pointer=pointer) from error


def validate_migration_envelope(value):
    _check(value['metadata_policy_version'] == POLICY and len(value['operations']) == 1
        and value['operations'][0]['op'] == 'schema_migrate', 'migration_operation_required')
    op = value['operations'][0]
    _check(value['base'] == {'scope_descriptor': SCOPE,
        'model_root_sha256': op['source_model_root_sha256']}, 'migration_base_mismatch')
    _check(value['expected_result']['model_root_sha256'] == op['target_model_root_sha256'],
           'migration_expected_root_mismatch')
    expected = [{'kind': 'file', 'path': r['path'], 'expected_byte_sha256': r['sha256']}
                for r in op['source_files']]
    known = {r['path'] for r in op['source_files']}
    expected += [{'kind': 'absent', 'path': r['path']} for r in op['target_files'] if r['path'] not in known]
    _check(value['preconditions'] == expected, 'migration_preconditions_mismatch')
    _check([r['artifact']['id'] for r in value['result_artifacts']] == op['result_ids'],
           'migration_result_ids_mismatch')
    changed = {r['path']: r for r in op['changes']}
    from ..model.paths import artifact_path
    from ..storage.json_syntax import parse_json_object
    for row in value['result_artifacts']:
        v = row['artifact']; path = artifact_path(v['artifact_type'], v['id'], v['id'].split('-')[0])
        _check(path in changed and changed[path]['after_bytes_base64'] is not None,
               'migration_result_bytes_missing')
        _check(parse_json_object(unb64(changed[path]['after_bytes_base64'])) == v,
               'migration_result_bytes_mismatch')
