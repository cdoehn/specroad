"""Closed stored conflict contract; schema validation never proves source truth."""
FORMAT = 'merge-conflicts-v1'
ROLES = ('base', 'ours', 'theirs')
PENDING = ['audited_resolution', 'merge_metadata', 'target_validation', 'publication']
FIELD_CLASSES = ('scalar_change', 'type_change', 'remove_edit', 'ordered_sequence_change',
    'collection_semantics_required', 'set_element_conflict', 'schema_invalid_combination')
BINARY_CLASSES = ('attachment_binary_change', 'resource_binary_change')
GUARD_CLASSES = ('identity_collision', 'identity_history_unresolved', 'relation_owner_change',
    'relation_absence_unproven', 'relation_origin_metadata_change', 'relation_remove_edit',
    'relation_immutable_change', 'relation_invalid_combination', 'immutable_original_change',
    'artifact_absence_unproven', 'lifecycle_transition_conflict', 'supersession_target_conflict',
    'retirement_content_conflict', 'lifecycle_reactivation', 'supersession_target_missing',
    'attachment_absence_unproven', 'attachment_remove_edit', 'resource_absence_unproven',
    'resource_location_conflict')


def object_schema(properties):
    return {'type': 'object', 'properties': properties, 'required': sorted(properties),
            'additionalProperties': False}


def schema():
    text = {'type': 'string'}
    nonempty = {'type': 'string', 'minLength': 1}
    sha = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    count = {'type': 'integer', 'minimum': 0}
    nullable = lambda item: {'anyOf': [{'type': 'null'}, item]}
    array = lambda item: {'type': 'array', 'items': item}
    identity = object_schema({'kind': {'enum': ['configuration','artifact','relation','profile',
        'rule','mapping','language_registry','language_package','attachment','archive']},
        'id': nonempty, 'version': nullable(nonempty)})
    binding = {'path': nonempty, 'pointer': text, 'size': count, 'byte_sha256': sha,
        'value_sha256': sha, 'value_domain': {'enum':['json-v1','bytes-v1','relation-navigation-v1']},
        'owner_id': nullable(nonempty), 'id_scheme': nullable(nonempty),
        'storage_class': {'enum':['current','legacy_immutable']}}
    observation = {'anyOf': [object_schema({'state': {'const':'absent'},
        **{name: {'type':'null'} for name in binding}}),
        object_schema({'state':{'const':'present'}, **binding})]}
    value = {'anyOf': [object_schema({'state': {'const':'absent'}}),
        object_schema({'state':{'const':'present'}, 'domain':{'const':'json-v1'}, 'value':{}}),
        object_schema({'state':{'const':'present'}, 'domain':{'const':'bytes-v1'}, 'size':count, 'sha256':sha})]}
    row = object_schema({'conflict_id': {'type':'string','pattern':r'^MC-[0-9a-f]{64}(?![\s\S])'},
        'identity':identity, 'artifact_ids':array(nonempty),
        'pointer': {'type':'string','pattern':r'^(?:/(?:[^~]|~[01])*)*(?![\s\S])'},
        'conflict_class':{'enum':list(FIELD_CLASSES+BINARY_CLASSES+GUARD_CLASSES)},
        'values':object_schema({role:value for role in ROLES}),
        'observations':object_schema({role:observation for role in ROLES}),
        'element_keys':array({}),
        'impact':object_schema({'scope':{'const':'direct_source_relations'}, 'depth':{'type':'integer','const':1},
            'transitive':{'const':False}, 'by_role':object_schema({role:array(object_schema({
                'relation_id':nonempty,'source_id':nonempty,'target_id':nonempty,'relation_type':nonempty}))
                for role in ROLES})}),
        'allowed_resolutions':array({'enum':['take_ours','take_theirs','take_base','value']})})
    return object_schema({'conflict_format_version':{'const':FORMAT}, 'plan_id':nonempty,
        'source_bindings':object_schema({role:{'type':'object'} for role in ROLES}),
        'source_bindings_sha256':sha, 'history_input_sha256':sha,
        'conflicts':array(row), 'conflicts_sha256':sha, 'pending_gates':{'const':PENDING},
        'ready':{'const':False}, 'write_authorized':{'const':False}, 'approval_granted':{'const':False}})
