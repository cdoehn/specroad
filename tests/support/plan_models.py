"""Synthetic independently authored plan projections and migration inputs."""
import json
from specroad.migration.plan_inputs import migration_inputs
from .artifacts import common_artifact

PLAN = 'SR-IPLAN-' + '0' * 26
ENTRY = 'SR-PENTRY-' + '0' * 25 + '1'
SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'project', 'selector': {},
    'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}


def plan():
    return common_artifact('implementation_plan', 'IPLAN', format='plan-markdown-v1',
        display_id='21', description='Stored description', scope=dict(SCOPE), children=[ENTRY],
        prerequisites=[], coverage_claims=[])


def entry():
    return common_artifact('plan_entry', 'PENTRY', id=ENTRY, display_id='21.a.W',
        description='Implement this behavior', plan_id=PLAN, parent_id=PLAN,
        parent_relation_id='REL-' + '0' * 25 + '2', implemented=False,
        entry_kind='commit', work_kind='implementation', children=[], prerequisites=[], requirement_bindings=[])


def migration(files):
    configuration = json.loads(files['specroad.json'])
    raw = (json.dumps({**configuration, 'schema_version': '0.3.0'}, ensure_ascii=False, indent=2) + '\n').encode()
    fields = dict(inputs=migration_inputs(target_configuration=raw),
        actor={'actor_type': 'tool', 'actor_id': 'synthetic-plan-migration'},
        planned_at='2026-11-22T00:00:00Z', change_plan_id='CP-synthetic-plan-capability',
        request_id='synthetic:plan-capability', target_version='0.3.0')
    return fields, raw
