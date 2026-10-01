"""Read-only integrity checks for journal-bound recovery inputs.

Missing building files can be interrupted preparation, not lost before images.
This first slice checks the mandatory, complete prepared images. No status
observation creates a corrupt marker or grants a recovery write capability.
"""
from ._recovery_rollback import _fingerprint
from .execution_values import ChangeExecutionError
from ..security import SafetyViolation


def inspect_critical_inputs(files, journal):
    data = journal.data
    resources, blockers = [], []
    if data['state'] != 'prepared':
        return {'resources': resources, 'blockers': blockers,
                'critical_inputs_verified': False, 'scope': 'not_assessed'}
    for entry in data['files']:
        for role, path_key, size_key, hash_key in (
                ('before_image', 'before_image_path', 'before_size', 'before_sha256'),
                ('staging', 'staging_path', 'after_size', 'after_sha256')):
            path = entry[path_key]
            if path is None:
                continue
            record = {'path': path, 'role': role, 'recovery_critical': True,
                      'required': True, 'expected_size': entry[size_key],
                      'expected_sha256': entry[hash_key], 'observed_size': None,
                      'observed_sha256': None, 'status': 'unavailable'}
            try:
                token = _fingerprint(files, path)
                if token is None:
                    record['status'] = 'missing'
                else:
                    record.update(observed_size=token['size'], observed_sha256=token['sha256'])
                    record['status'] = ('verified' if (token['size'], token['sha256']) ==
                        (entry[size_key], entry[hash_key]) else 'mismatch')
            except (ChangeExecutionError, SafetyViolation, OSError) as error:
                record['reason'] = getattr(error, 'reason', 'recovery_input_unreadable')
            resources.append(record)
            if record['status'] != 'verified':
                blockers.append({'path': path, 'role': role,
                    'reason': 'recovery_' + role + '_' + record['status']})
    return {'resources': resources, 'blockers': blockers,
            'critical_inputs_verified': not blockers, 'scope': 'prepared_images'}
