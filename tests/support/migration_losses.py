"""Authored loss candidates and independent JSON/hash oracles; no test execution here."""
import base64
import json
from copy import deepcopy
from .migration_plans import FIELDS, target_inputs, vector_source, planned_files
from .reference01 import encoded, put

REQ = 'spec/requirements/SR-REQ-0001.json'
OPAQUE = {'relation_locator': {'source_id': 'do-not-resolve', 'index': 7},
          'script': 'raise RuntimeError("opaque")', 'text': 'e\u0301/雪',
          'ordered': [None, False, 1, {'x/y~z': 'retained'}]}


def extension_source():
    files = vector_source()
    old = json.loads(files[REQ]); old['extensions']['未知.namespace'] = deepcopy(OPAQUE)
    old['external_identities'] = [{'source_system': 'synthetic', 'source_document': 'source',
        'external_id': '1', 'extensions': {'unknown.identity': deepcopy(OPAQUE)}}]
    old['relations'][0]['extensions']['unknown.relation'] = deepcopy(OPAQUE)
    put(files, old)
    files['notes.bin'] = b'\x00\xffopaque\r\n'
    return files


def with_config_extensions(files, extensions):
    value = json.loads(files['specroad.json']); value['extensions'] = extensions
    files['specroad.json'] = encoded(value)


def target_with_extensions(files, extensions):
    inputs = target_inputs(files)
    config = json.loads(base64.b64decode(inputs['target_configuration']))
    config['extensions'] = extensions
    inputs['target_configuration'] = base64.b64encode(encoded(config)).decode('ascii')
    return inputs


def candidate(files=None, inputs=None):
    from specroad.migration.planning import plan_migration
    files = extension_source() if files is None else files
    inputs = target_inputs(files) if inputs is None else inputs
    result = plan_migration(files, inputs=inputs, **FIELDS)
    assert result.ready, result.data['blockers']
    return files, inputs, planned_files(files, result.change_plan), result


def assess(files, target, inputs):
    from specroad.migration.losses import assess_migration_preservation
    return assess_migration_preservation(files, target, inputs=inputs,
        actor=FIELDS['actor'], planned_at=FIELDS['planned_at'])
