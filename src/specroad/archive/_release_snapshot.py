"""Bind stored Release selection to the existing whole-project snapshot.

Snapshot construction is inert. Native M13 admission and the normal writer
remain mandatory; a valid selection or archive hash is never a release permit.
The snapshot keeps its project scope, with the approved Release scope bound
separately in the selection object. No new scope resolver or hash is invented.
"""
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ..verification.evaluation import VerificationEvaluation
from ._release_selection import bind_stored_release_selection
from .baseline import BaselineManifest
from .objects import SnapshotObject
from .project_snapshot import build_project_baseline_manifest


def release_snapshot(model, *, baseline_id, release_id, configuration_id=None):
    selection = bind_stored_release_selection(model, release_id=release_id, evaluation=None)
    stored = selection['stored_evaluation']
    if stored is None:
        raise ModelError('stored_release_evaluation_required')
    evaluation = VerificationEvaluation(canonical_json_bytes(stored))
    scope = ScopeDescriptor({'scope_version': 'scope-v1', 'scope_kind': 'release',
        'selector': {'release_id': release_id}, 'configuration_id': configuration_id,
        'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'})
    snapshot = build_project_baseline_manifest(model, baseline_id=baseline_id,
                                              configuration_id=configuration_id)
    data = snapshot.data
    if release_id not in {r['id'] for r in data['model_manifest']['artifacts']}:
        raise ModelError('baseline_release_excluded')
    item = SnapshotObject(canonical_json_bytes({'format_version': 'release-baseline-selection-v1',
        'release_id': release_id, 'scope_descriptor': scope.data,
        'verification_evaluation': stored, 'evaluation_sha256': evaluation.sha256,
        'stored_evaluation_sha256': selection['stored_evaluation_sha256']}))
    row = {'role': 'release_selection', 'object_path': item.reference.path,
           'sha256': item.reference.sha256, 'size': item.reference.size,
           'media_type': 'application/json'}
    rows = [*data['manifest'], row]
    rows.sort(key=lambda r: (r['role'].encode('utf-8'),
        r.get('id', r.get('source_path', '')).encode('utf-8'), r.get('version', '').encode('utf-8')))
    objects = {o.reference.path: o for o in (*snapshot.objects, item)}
    result = object.__new__(BaselineManifest)
    object.__setattr__(result, '_encoded', canonical_json_bytes({**data,
        'baseline_kind': 'release', 'verification_evaluation': stored, 'manifest': rows}))
    object.__setattr__(result, 'objects', tuple(objects[p] for p in sorted(objects)))
    return result


def release_selection(record, objects):
    """Read one complete hash-bound selection, never a readiness success label."""
    rows = [r for r in record['manifest'] if r.get('role') == 'release_selection']
    if len(rows) != 1 or 'verification_evaluation' not in record:
        raise ModelError('release_baseline_readiness_required')
    row = rows[0]
    raw = objects.get(row.get('object_path'))
    if type(raw) is not bytes:
        raise ModelError('release_baseline_selection_object_required')
    item = SnapshotObject(raw)
    if row != {'role': 'release_selection', 'object_path': item.reference.path,
               'sha256': item.reference.sha256, 'size': item.reference.size,
               'media_type': 'application/json'}:
        raise ModelError('release_baseline_selection_binding_mismatch')
    value = parse_json_object(raw)
    if set(value) != {'format_version', 'release_id', 'scope_descriptor',
                     'verification_evaluation', 'evaluation_sha256', 'stored_evaluation_sha256'}:
        raise ModelError('release_baseline_selection_invalid')
    scope = ScopeDescriptor(value['scope_descriptor']).data
    evaluation = VerificationEvaluation(canonical_json_bytes(value['verification_evaluation']))
    if (value['format_version'] != 'release-baseline-selection-v1'
            or scope['scope_kind'] != 'release'
            or scope['selector']['release_id'] != value['release_id']
            or scope['boundary_policy'] != 'closed'
            or scope['configuration_id'] != record['scope_descriptor'].get('configuration_id')
            or value['verification_evaluation'] != record['verification_evaluation']
            or value['evaluation_sha256'] != evaluation.sha256
            or value['stored_evaluation_sha256'] != canonical_json_sha256(record['verification_evaluation'])
            or canonical_json_bytes(value) != raw):
        raise ModelError('release_baseline_selection_binding_mismatch')
    return value
