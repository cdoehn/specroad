"""Validate the small machine contract across the native Core subprocess boundary."""
from datetime import datetime
from pathlib import Path
from .config import digest, identity, text

BINDING = {"repo_id", "base_commit", "state_fingerprint", "fingerprint_algorithm"}


def binding(value):
    if not isinstance(value, dict) or set(value) != BINDING:
        raise ValueError
    identity(value['repo_id'])
    base = value['base_commit']
    if not isinstance(base,str) or len(base) not in (40,64) or any(c not in '0123456789abcdef' for c in base):
        raise ValueError
    if value['fingerprint_algorithm'] != 'patchharbor-state-v1':
        raise ValueError
    fp = value['state_fingerprint']
    if not isinstance(fp,str) or not fp or any(c not in '0123456789abcdef' for c in fp):
        raise ValueError


def timestamp(value):
    if value is None:
        return None
    stamp = datetime.fromisoformat(text(value).replace('Z','+00:00'))
    if stamp.tzinfo is None:
        raise ValueError
    return stamp


def facts(value, operation):
    if not isinstance(value,dict):
        raise ValueError
    digest(value['sha256']); binding(value['binding'])
    expected = 'result' if operation == 'result' else 'patch'
    if value['kind'] != expected:
        raise ValueError
    if operation == 'result':
        identity(value['run_id'])
        if value['operation'] not in ('bundle','apply') or not Path(text(value['repository_path'])).is_absolute():
            raise ValueError
        for key in ('dry_run','success','entrypoint_started','dirty'):
            if type(value[key]) is not bool:
                raise ValueError
        if value.get('patch_sha256') is not None:
            digest(value['patch_sha256'])
        if value.get('expected') is not None:
            binding(value['expected'])
        timestamp(value.get('captured_at'))
        if value.get('development_contract') is not None:
            from .mixed_contract import capability
            capability(value['development_contract'])
    elif operation == 'validate':
        digest(value['reference_sha256'])
        if type(value['binding_matches']) is not bool:
            raise ValueError
    return value
