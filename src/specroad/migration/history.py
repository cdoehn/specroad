"""Source-algorithm verification of historical originals, never current approval.

Every public call qualifies actual bytes and the complete historical closure.
Neither a saved report, a navigation projection nor an old version label is
proof. No procedure, code payload, writer or current validation is executed.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes as jcs
from ..storage.json_syntax import parse_json_object as parsed
from .legacy_manifest import validate_legacy_manifest
from .plan_values import owned_files, require
from .reference01 import inventory_bytes, inventory_project


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


def verify_source_history(files):
    """Verify a complete reference-0.1 source using its fixed native contract."""
    files = owned_files(files, passive=True)
    inventory = inventory_bytes({p: raw for p, raw in files.items() if not p.startswith('.specroad/')})
    return _report(inventory)


def _registered_inventory(manifest):
    # validate_legacy_manifest already proved every registration and original.
    # Reconstruct the unique top source from its complete native original set;
    # never feed transformed target files to the historical reader.
    roots = {o.snapshot_root for _, o in manifest._originals}
    parents = {o.data['model_root_sha256'] for _, o in manifest._originals
               if o.role == 'artifact' and o.data['artifact_type'] == 'baseline'}
    require(len(roots - parents) == 1, 'legacy_source_root_ambiguous')
    root = next(iter(roots - parents))
    files = {o.path: o.source_bytes for _, o in manifest._originals if o.snapshot_root == root}
    files.update({p: raw for p, raw in manifest._files if p.startswith('archive/objects/')})
    return inventory_bytes(files)


def verify_migrated_history(files, *, project_id):
    """Verify the real registry and all of its originals, including old snapshots."""
    manifest = validate_legacy_manifest(files, project_id=project_id)
    return _report(_registered_inventory(manifest), manifest)


def _baseline_report(inventory, raw, manifest=None):
    require(type(raw) is bytes, 'baseline_record_bytes_required')
    originals = [o for o in inventory.originals if o.role == 'artifact'
                 and o.data['artifact_type'] == 'baseline' and o.source_bytes == raw]
    require(bool(originals), 'legacy_original_unregistered')
    record = originals[0].data
    history = _report(inventory, manifest)
    return {'format_version': 'historical-baseline-verification-v1',
        'baseline_id': record['id'], 'baseline_kind': record['baseline_kind'],
        'record_sha256': sha256(raw).hexdigest(), 'scope_descriptor': record['scope_descriptor'],
        'model_root_sha256': record['model_root_sha256'],
        'model_root_algorithm': record['model_root_algorithm'],
        'history_binding_sha256': history.sha256, 'historical': history.data['historical'],
        'legacy_manifest_sha256': None if manifest is None else manifest.sha256,
        'snapshot_integrity_verified': True,
        'validation_scope': 'qualified_reference01_originals_and_complete_snapshot_closure',
        'project_completeness_verified': False, 'full_validation_passed': False,
        'current_context_verified': False, 'external_run_verified': False,
        'human_authority_verified': False, 'release_readiness_evaluated': False,
        'atomic_snapshot': False, 'write_authorized': False, 'approval_granted': False,
        'release_authorized': False}


def verify_historical_baseline(boundary, raw):
    """Read-only native baseline dispatch before and after a qualified migration."""
    from ..security import ProjectBoundary
    from ..storage.operational_preflight import observe_operational_preflight
    from ..storage.project import ProjectSource
    require(type(boundary) is ProjectBoundary, 'snapshot_object_boundary_required')
    boundary._check_root()
    configuration = boundary.read_bytes('specroad.json')
    require(observe_operational_preflight(boundary)['consistency_state'] == 'consistent',
            'historical_source_state_invalid')
    if parsed(configuration).get('schema_version') == '0.1.0':
        inventory = inventory_project(boundary.root)
        result = _baseline_report(inventory, raw)
    else:
        source = ProjectSource(boundary.root)
        require(source.boundary._root_identity == boundary._root_identity, 'historical_source_changed')
        source.check_current()
        manifest = source._legacy_manifest
        require(manifest is not None, 'legacy_manifest_required')
        result = _baseline_report(_registered_inventory(manifest), raw, manifest)
        source.check_current()
    require(boundary.read_bytes('specroad.json') == configuration, 'historical_source_changed')
    require(observe_operational_preflight(boundary)['consistency_state'] == 'consistent',
            'historical_source_state_invalid')
    boundary._check_root()
    return result
