"""Pure per-check candidate selection over a privately frozen JSON snapshot.

The public adapter owns native validation, scope and contract resolution. This
function neither resolves a model nor reads files, clocks or external results.
"""
from ..storage.json_syntax import parse_json_object
from ._subject_binding import subject_context_sha256


def candidate_check(snapshot):
    """Return the complete observed/expected union without changing its inputs."""
    inputs = parse_json_object(snapshot)
    key = inputs['key']
    expected = inputs['expected_run_ids']
    contract = inputs['contract']
    selected = inputs['evaluation_binding']
    runs = {run_id: [] for run_id in expected}
    used = set()
    for item in inputs['evidence']:
        value, binding = item['record'], item['binding']
        run = value['run_context']
        if run is None or run['subject_id'] != selected['evaluated_subject']['subject_id']:
            continue
        if run['subject_state_sha256'] != selected['evaluated_subject']['state_sha256']:
            continue
        if run['check_id'] != key['check_id'] or run['test_id'] != key['test_id']:
            continue
        subjects = {item['artifact_id']: item for item in value['subjects']}
        ids = {key['subject_artifact_id'], key['contract_id']}
        if key['test_id'] is not None:
            ids.add(key['test_id'])
        if not ids <= subjects.keys() or 'configuration_hash' not in value:
            continue
        policy = value.get('configuration_policy')
        same_configuration = value['configuration_hash'] == selected['configuration_hash']
        if policy == 'bound':
            if not same_configuration:
                continue
        elif policy == 'independent' and contract.get('configuration_policy') == 'independent':
            # Cross-configuration reuse requires the actual current
            # declaration, never an Evidence label or an old policy.
            if (not same_configuration and subjects[key['contract_id']]['verification_context_sha256']
                    != subject_context_sha256(contract)):
                continue
        else:
            continue
        observation = {**binding, 'result': value['result'], 'subjects': value['subjects'],
            'run_context': run, 'configuration_hash': value['configuration_hash'],
            'configuration_policy': policy}
        runs.setdefault(run['run_id'], []).append(observation)
        used.add(value['id'])
    check = {**key, 'expected_run_ids': expected,
        'runs': [{'run_id': run_id, 'expected': run_id in expected, 'evidence': runs[run_id]}
                 for run_id in sorted(runs, key=lambda item: item.encode('utf-8'))]}
    return check, used
