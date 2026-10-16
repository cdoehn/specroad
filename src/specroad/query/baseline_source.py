"""Acquire a verified historical snapshot for the existing comparison registry.

Only archived bytes supply historical values. Native Baseline IDs select their
canonical record path; explicit record bytes also support archive-only roots.
This adapter contributes no alternative field or resource-diff semantics.
"""
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..security import ProjectBoundary
from ..storage.json_syntax import parse_json_object


def baseline_source(root, reference, expected_project_id):
    # Reject selectors for another source kind before touching a fallback root.
    path = None
    if type(reference) is str:
        try:
            path = artifact_path('baseline', reference, reference.split('-', 1)[0])
        except ModelError as error:
            raise ModelError('comparison_source_unavailable') from error
    elif type(reference) is not bytes:
        raise ModelError('comparison_baseline_reference_required')
    boundary = ProjectBoundary(root)
    raw = boundary.read_bytes(path) if path is not None else reference
    from ..archive._baseline_view import _record
    from ..archive.materialization import _snapshot, _check_objects
    from ..archive.objects import ObjectReference, read_snapshot_object
    from ..archive.verification import _configuration, verify_baseline_snapshot

    record = _record(boundary, raw)
    if path is not None and record['id'] != reference:
        raise ModelError('comparison_baseline_identity_mismatch', path=path)
    verified = verify_baseline_snapshot(boundary, raw)
    row = next(r for r in record['manifest'] if r['role'] == 'semantic_configuration')
    semantic = read_snapshot_object(boundary, ObjectReference(row['sha256'], row['size']))
    inert = _configuration(parse_json_object(semantic))
    record, objects, files, _, checked = _snapshot(boundary, raw,
        default_locale=inert.data['default_locale'], generated_path=inert.generated_path)
    if checked != verified:
        raise ModelError('baseline_snapshot_changed')
    configuration = ProjectConfiguration(parse_json_object(files['specroad.json']))
    if expected_project_id is not None and configuration.project_id != expected_project_id:
        raise ModelError('project_identity_mismatch')
    resources = tuple(sorted(files.items()))

    def finish():
        if path is not None and boundary.read_bytes(path) != raw:
            raise ModelError('comparison_source_changed', path=path)
        _check_objects(boundary, objects)
        if verify_baseline_snapshot(boundary, raw) != checked:
            raise ModelError('baseline_snapshot_changed')
        if path is not None and boundary.read_bytes(path) != raw:
            raise ModelError('comparison_source_changed', path=path)
        return canonical_json_bytes({'baseline_id': record['id'], 'record_path': path,
            'record_sha256': checked['record_sha256'], 'model_root_sha256': checked['model_root_sha256'],
            'snapshot_integrity_verified': True,
            'objects': [item.reference.data for _, item in sorted(objects.items())],
            'historical_full_validation_verified': False, 'release_authorized': False})

    return configuration, resources, str(boundary.root), None, finish
