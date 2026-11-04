"""Owned historical integrity reports, distinct from current-context assessment."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed


@dataclass(frozen=True, init=False)
class HistoricalVerification:
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use verify_source_history or verify_migrated_history')

    @property
    def data(self):
        return parsed(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    def __bool__(self):
        raise TypeError('Historical integrity is not current verification or approval')



def _records(inventory):
    records = {}
    for original in inventory.originals:
        if original.role != 'artifact':
            continue
        value = original.data
        kind = value['artifact_type']
        if kind not in ('baseline', 'evidence'):
            continue
        key = (value['id'], value['revision'])
        row = records.setdefault(key, {'artifact_id': value['id'], 'artifact_type': kind,
            'revision': value['revision'], 'logical_path': original.path,
            'original_byte_sha256': original.byte_sha256,
            'original_canonical_sha256': original.canonical_sha256,
            'snapshot_roots': [], 'historical_integrity_verified': True})
        row['snapshot_roots'].append(original.snapshot_root)
        if kind == 'baseline':
            row.update(model_root_sha256=value['model_root_sha256'],
                model_root_algorithm=value['model_root_algorithm'],
                scope_descriptor=value['scope_descriptor'], baseline_kind=value['baseline_kind'],
                manifest=value['manifest'])
        else:
            row.update(context_hash_algorithm=value['context_hash_algorithm'],
                subjects=value['subjects'], result=value['result'], run_context=value.get('run_context'),
                configuration_binding={k: value[k] for k in
                    ('configuration_hash', 'configuration_policy') if k in value})
    for row in records.values():
        row['snapshot_roots'] = sorted(set(row['snapshot_roots']))
    return [records[key] for key in sorted(records)]



def _report(inventory, manifest=None):
    source = inventory.data
    historical = {key: source[key] for key in ('contract_id', 'contract_version',
        'contract_manifest_sha256', 'legacy_reader_id', 'project_id', 'model_root_sha256',
        'scope_descriptor', 'snapshot_roots')}
    historical['records'] = _records(inventory)
    value = {'format_version': 'migration-history-verification-v1', 'historical': historical,
        'legacy_manifest_sha256': None if manifest is None else manifest.sha256,
        'historical_integrity_verified': True,
        'validation_scope': 'qualified_reference01_originals_and_complete_snapshot_closure',
        'historical_compatibility_claimed': False, 'external_run_verified': False,
        'human_authority_verified': False, 'current_context_verified': False,
        'current_readiness_verified': False, 'approval_granted': False,
        'write_authorized': False, 'test_code_executed': False}
    result = object.__new__(HistoricalVerification)
    object.__setattr__(result, '_encoded', jcs(value))
    return result
