"""Real qualified synthetic inputs for audited merge decisions and CLI examples."""
from specroad.merge import build_merge_conflicts
from specroad.model.canonical import canonical_json_bytes as jcs
from .merge_lifecycle import artifact, bound_records, changed

ACTOR = {'actor_type': 'human', 'actor_id': 'synthetic-resolution-operator'}
WHEN = '2026-01-02T03:04:05Z'
ROLES = ('base', 'ours', 'theirs')
PLAN_ID = 'MP-' + '0' * 26


def case(root, original):
    root.mkdir(parents=True, exist_ok=True)
    path, value = artifact(original)
    sources, history = bound_records(root, original, path,
        [changed(value, title=role, extensions={'vendor.resolve': {'item': index}})
         for index, role in enumerate(ROLES)])
    return sources, history, build_merge_conflicts(sources, plan_id=PLAN_ID, history=history)


def request_files(root, sources, history, plan):
    root.mkdir(parents=True, exist_ok=True)
    plan_file, inputs_file = root / 'plan.json', root / 'inputs.json'
    plan_file.write_bytes(plan.canonical_bytes)
    inputs_file.write_bytes(jcs({'format_version': 'merge-resolution-inputs-v1',
        'sources': {role: {'kind': 'local', 'root': getattr(sources, role).source_root,
                           'reference': None} for role in ROLES}, 'history': history}))
    catalogue = plan.data.get('catalogue', plan.data)
    row = next(row for row in catalogue['conflicts'] if row['pointer'] == '/title')
    return {'command_id': 'merge.resolve', 'arguments': {'merge_plan': str(plan_file)},
        'options': {'--format': 'json', '--inputs': str(inputs_file),
            '--expected-plan-sha256': plan.sha256, '--conflict': row['conflict_id'], '--take': 'ours',
            '--actor-type': ACTOR['actor_type'], '--actor-id': ACTOR['actor_id'], '--resolved-at': WHEN}}


def argv(request):
    result = ['merge', 'resolve', request['arguments']['merge_plan']]
    for key, value in request['options'].items():
        result.append(key)
        if value is not True:
            result.append(value)
    return result


def example_inputs(root, command):
    from test_project_bundle import project
    root.mkdir(parents=True, exist_ok=True)
    sources, history, plan = case(root / 'sources', project(root / 'seed').raw)
    return request_files(root / 'plans', sources, history, plan)
