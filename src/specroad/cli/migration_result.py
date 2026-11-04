"""Closed public migration response; nested native contracts remain authoritative."""
def document(mode, *, planning=None, execution=None, verification=None, plan_file=None, backup=None):
    return {'format_version': 'migration-command-v1', 'mode': mode, 'planning': planning,
        'execution': execution, 'verification': verification, 'plan_file': plan_file, 'backup': backup}


def schema():
    from .result_schemas import _object, _nullable
    obj = _nullable({'type': 'object'})
    return _object({'format_version': {'const': 'migration-command-v1'},
        'mode': {'enum': ['plan', 'apply', 'verify']},
        'planning': obj, 'execution': obj, 'verification': obj,
        'plan_file': _nullable(_object({'path': {'type': 'string', 'minLength': 1},
            'size': {'type': 'integer', 'minimum': 1},
            'sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}})), 'backup': obj})
