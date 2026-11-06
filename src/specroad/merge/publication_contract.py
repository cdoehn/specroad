"""Closed specialized Change Plan operation; parsing never grants a write."""
from hashlib import sha256
from ..changes._schema_fields import obj, arr, text, digest as hash_schema
from ..changes.errors import ChangePlanError
from ..model._schema import validate_builtin
from ..model.canonical import canonical_json_sha256 as digest
from ..migration.plan_values import b64, unb64, file_bindings, changes
from ..storage.json_syntax import parse_json_object as parsed

POLICY = 'merge-metadata-v1'
OPERATION = 'merge_publish'


def require(ok, reason):
    if not ok: raise ChangePlanError(reason, code='SRV146')


def publication_operation_schema():
    nullable = lambda value: {'anyOf': [value, {'type': 'null'}]}
    files = arr(obj({'path': text(), 'size': {'type': 'integer', 'minimum': 0}, 'sha256': hash_schema()}))
    inputs = obj({**{k: text() for k in ('plan_bytes_base64','metadata_bytes_base64','target_bytes_base64', 'target_configuration')},
        **{k: hash_schema() for k in ('plan_sha256','metadata_sha256','target_sha256')},
        'sources': {'type': 'object'}, 'history': {'type': 'object'}})
    return obj({'op': {'const': OPERATION}, 'format_version': {'const': 'merge-publication-v1'},
        'inputs': inputs, 'inputs_sha256': hash_schema(), 'source_files': files, 'target_files': files,
        'changes': arr(obj({'path': text(), 'before_sha256': nullable(hash_schema()),
            'after_sha256': nullable(hash_schema()), 'after_bytes_base64': nullable(text())})),
        'result_ids': arr(text()), 'source_model_root_sha256': hash_schema(), 'target_model_root_sha256': hash_schema()})


def validate_publication_operation(value, pointer=''):
    validate_builtin(value, publication_operation_schema())
    inputs = value['inputs']
    require(digest(inputs) == value['inputs_sha256'], 'merge_publication_inputs_hash')
    for name in ('plan', 'metadata', 'target'):
        require(sha256(unb64(inputs[name+'_bytes_base64'])).hexdigest() == inputs[name+'_sha256'],
                'merge_publication_input_hash')
    for key in ('source_files','target_files','changes'):
        rows = value[key]; names = [r['path'] for r in rows]
        require(names == sorted(set(names), key=lambda p:p.encode('utf-8')), 'merge_publication_file_order')
        from ..storage.archive import validate_portable_archive_paths
        validate_portable_archive_paths(names)
    before = {r['path']: r for r in value['source_files']}; after = {r['path']: r for r in value['target_files']}
    require({r['path'] for r in value['changes']} == {p for p in set(before)|set(after) if before.get(p)!=after.get(p)},
            'merge_publication_change_set')
    for row in value['changes']:
        path=row['path']; old=before.get(path); new=after.get(path)
        require(row['before_sha256'] == (None if old is None else old['sha256']) and
                row['after_sha256'] == (None if new is None else new['sha256']), 'merge_publication_change_hash')
        require(not path.startswith('.specroad/'), 'merge_publication_operational_write')
        if new is None: require(row['after_bytes_base64'] is None, 'merge_publication_deleted_bytes')
        else:
            raw = unb64(row['after_bytes_base64'])
            require(len(raw)==new['size'] and sha256(raw).hexdigest()==new['sha256'], 'merge_publication_target_bytes')
    require(value['result_ids']==sorted(set(value['result_ids'])), 'merge_publication_result_order')


def validate_publication_envelope(value):
    require(value['metadata_policy_version']==POLICY and len(value['operations'])==1
            and value['operations'][0]['op']==OPERATION, 'merge_publication_operation_required')
    op=value['operations'][0]
    sources=op['inputs']['sources']
    require(type(sources) is dict and type(sources.get('ours')) is dict and
        type(sources['ours'].get('binding')) is dict, 'merge_publication_ours_required')
    binding=sources['ours']['binding']
    require(value['base']=={'scope_descriptor':binding.get('scope_descriptor'),
        'model_root_sha256':op['source_model_root_sha256']} and
        op['source_model_root_sha256']==binding.get('model_root_sha256'), 'merge_publication_base_binding')
    require(value['expected_result']['model_root_sha256']==op['target_model_root_sha256'], 'merge_publication_result_binding')
    before={r['path'] for r in op['source_files']}
    conditions=[{'kind':'file','path':r['path'],'expected_byte_sha256':r['sha256']} for r in op['source_files']]
    conditions += [{'kind':'absent','path':r['path']} for r in op['target_files'] if r['path'] not in before]
    require(value['preconditions']==conditions, 'merge_publication_preconditions')
    rows={r['path']:r for r in op['changes']}
    require([r['artifact']['id'] for r in value['result_artifacts']]==op['result_ids'], 'merge_publication_result_ids')
    from ..model.paths import artifact_path
    for item in value['result_artifacts']:
        v=item['artifact'];p=artifact_path(v['artifact_type'],v['id'],v['id'].split('-')[0])
        require(p in rows and rows[p]['after_bytes_base64'] is not None and
                parsed(unb64(rows[p]['after_bytes_base64']))==v, 'merge_publication_result_bytes')
