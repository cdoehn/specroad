"""Synthetic byte fixtures; literal source/target vectors remain independent."""
import base64
import copy
import json
from hashlib import sha256
from pathlib import Path
from .model import configuration_value
from .reference01 import (CONTRACT, minimal, full_project, encoded, digest, put)

ACTOR = {'actor_type': 'tool', 'actor_id': 'synthetic-migrator'}
STAMP = '2026-11-03T01:00:00Z'
FIELDS = {'actor': ACTOR, 'planned_at': STAMP, 'change_plan_id': 'CP-synthetic-migration',
          'request_id': 'synthetic:migration', 'target_version': '0.2.0'}


def target_inputs(files, *, proposals=()):
    config = configuration_value(project_id='synthetic-reference-project')
    core = (Path(__file__).resolve().parents[2] / 'src/specroad/profile_data/core.json').read_bytes()
    requirements = []
    for path, raw in files.items():
        if path.startswith('spec/requirements/'):
            value = json.loads(raw)
            requirements.append({'artifact_id': value['id'], 'source_sha256': digest(value),
                'language': 'en', 'normative_force': 'must', 'statement': value['statement']})
    # The helper encodes explicitly authored data; it never transforms a source.
    from specroad.migration.planning import migration_inputs
    return migration_inputs(target_configuration=encoded(config), target_resources={'profiles/core.json': core},
        requirement_mappings=requirements, proposal_mappings=proposals)


def empty_proposal_plan(root):
    scope = {'scope_version': 'scope-v1', 'scope_kind': 'specification', 'selector': {},
        'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}
    value = {'format_version': '1.2.0', 'metadata_policy_version': 'change-metadata-v1',
        'change_plan_id': 'CP-synthetic-proposal', 'request_id': 'synthetic:replacement',
        'actor': ACTOR, 'planned_at': STAMP,
        'base': {'scope_descriptor': scope, 'model_root_sha256': root},
        'operations': [], 'preconditions': [], 'result_artifacts': [],
        'expected_result': {'model_root_sha256': root}}
    return {**value, 'change_plan_sha256': digest(value)}


def mapped_inputs(files):
    from specroad.migration.planning import plan_migration
    inputs = target_inputs(files)
    first = plan_migration(files, inputs=inputs, **FIELDS)
    if first.ready:
        return inputs
    assert {b['reason'] for b in first.data['blockers']} == {'proposal_mapping_required'}
    mappings = []
    for path, raw in files.items():
        if path.startswith('spec/proposals/'):
            value = json.loads(raw)
            if value['proposal_status'] not in ('applied', 'rejected', 'stale'):
                mappings.append({'artifact_id': value['id'], 'source_sha256': digest(value),
                    'change_plan': empty_proposal_plan(first.data['expected_proposal_basis_sha256'])})
    return target_inputs(files, proposals=mappings)


def planned_files(files, plan):
    result = dict(files)
    for row in plan.data['operations'][0]['changes']:
        if row['after_bytes_base64'] is None:
            del result[row['path']]
        else:
            result[row['path']] = base64.b64decode(row['after_bytes_base64'], validate=True)
    return result


def vector_source():
    files = minimal()
    files['spec/requirements/SR-REQ-0001.json'] = (CONTRACT/'vectors/requirement-before.json').read_bytes()
    return files


def unsigned(plan):
    value = copy.deepcopy(plan.data)
    value.pop('change_plan_sha256')
    return value
