"""Acquire a verified historical snapshot for the existing comparison registry.

Only archived bytes supply historical values. Native Baseline IDs select their
canonical record path; explicit record bytes also support archive-only roots.
This adapter contributes no alternative field or resource-diff semantics.
"""
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..security import ProjectBoundary
from ..storage.json_syntax import parse_json_object
from ._baseline_observation import _stored_record, baseline_observation
from ._comparison_capture import SourceCapture


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
    raw = _stored_record(boundary, path) if path is not None else reference
    from ..archive._baseline_view import _record
    from ..archive.materialization import _snapshot
    from ..archive.objects import ObjectReference, read_snapshot_object
    from ..archive.verification import _configuration, verify_baseline_snapshot

    record = _record(boundary, raw)
    if path is not None and record['id'] != reference:
        raise ModelError('comparison_baseline_identity_mismatch', path=path)
    verified = verify_baseline_snapshot(boundary, raw)
    row = next(r for r in record['manifest'] if r['role'] == 'semantic_configuration')
    reference_object = ObjectReference(row['sha256'], row['size'])
    try:
        semantic = read_snapshot_object(boundary, reference_object)
    except FileNotFoundError as error:
        raise ModelError('snapshot_referenced_object_missing', path=reference_object.path) from error
    inert = _configuration(parse_json_object(semantic))
    record, objects, files, _, checked = _snapshot(boundary, raw,
        default_locale=inert.data['default_locale'], generated_path=inert.generated_path)
    if checked != verified:
        raise ModelError('baseline_snapshot_changed')
    configuration = ProjectConfiguration(parse_json_object(files['specroad.json']))
    if expected_project_id is not None and configuration.project_id != expected_project_id:
        raise ModelError('project_identity_mismatch')
    resources = tuple(sorted(files.items()))

    finish = baseline_observation(boundary, path, raw, objects, checked, record)

    return SourceCapture(configuration, resources, str(boundary.root),
                         check=finish, evidence_key='baseline')
