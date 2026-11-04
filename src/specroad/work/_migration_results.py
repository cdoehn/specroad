"""Closed passive Work results shared by completion and native rechecks."""
from ..migration.plan_values import require
from ._data_contract import _object

def _outcome(current, records):
    return {'format_version': 'migration-work-result-v1', 'command_id': current.as_dict()['command_id'],
        'target_observation': 'planned_target' if current.as_dict()['command_id'] == 'migrate.plan' else 'provided_target_bytes',
        'planning': records[1]['result']['report'], 'verification': records[2]['result'],
        'project_writes_performed': False, 'write_authorized': False, 'approval_granted': False}


def check_outcome(value, document, exit_code):
    """Closed inert result validation; semantic execution is rechecked by adapters."""
    _object(document, ('format_version', 'command_id', 'target_observation', 'planning',
                       'verification', 'project_writes_performed', 'write_authorized', 'approval_granted'))
    planning = value['command_id'] == 'migrate.plan'
    require(document['format_version'] == 'migration-work-result-v1'
        and document['command_id'] == value['command_id']
        and value['command_class'] == ('plan_output' if planning else 'read_only')
        and document['target_observation'] == ('planned_target' if planning else 'provided_target_bytes')
        and type(exit_code) is int and exit_code == 0
        and all(document[k] is False for k in ('project_writes_performed', 'write_authorized', 'approval_granted'))
        and type(document['planning']) is dict and type(document['verification']) is dict,
        'migration_work_result_invalid', exit_code=6)
