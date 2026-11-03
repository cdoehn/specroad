"""Explicit synthetic author decisions; never a real mapping authorization."""
import base64
import json
from .migration_plans import target_inputs
from .reference01 import digest

REQUIREMENT_PATH = 'spec/requirements/SR-REQ-0001.json'


def decision(files, *, identity='SR-REQ-0001', language='en', force='must',
             statement='Preserve original bytes.'):
    source = json.loads(files['spec/requirements/' + identity + '.json'])
    return {'artifact_id': identity, 'source_sha256': digest(source),
            'language': language, 'normative_force': force, 'statement': statement}


def supplied(files, rows, *, default_language=None, configuration=None):
    """Use known target resources; only the caller supplies semantic decisions."""
    from specroad.migration.planning import migration_inputs
    target = target_inputs(files)
    return migration_inputs(
        target_configuration=(base64.b64decode(target['target_configuration'])
                              if configuration is None else configuration),
        target_resources={row['path']: base64.b64decode(row['bytes_base64'])
                          for row in target['target_resources']},
        requirement_mappings=rows, requirement_default_language=default_language)
