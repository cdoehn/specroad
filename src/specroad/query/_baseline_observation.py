"""Final byte observation and owned evidence for archived comparison sources."""
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError


def _stored_record(boundary, path):
    try:
        return boundary.read_bytes(path)
    except FileNotFoundError as error:
        raise ModelError('comparison_baseline_record_missing', path=path) from error



def baseline_observation(boundary, path, raw, objects, checked, record):
    from ..archive.materialization import _check_objects
    from ..archive.verification import verify_baseline_snapshot

    def finish():
        if path is not None and _stored_record(boundary, path) != raw:
            raise ModelError('comparison_source_changed', path=path)
        _check_objects(boundary, objects)
        if verify_baseline_snapshot(boundary, raw) != checked:
            raise ModelError('baseline_snapshot_changed')
        if path is not None and _stored_record(boundary, path) != raw:
            raise ModelError('comparison_source_changed', path=path)
        return canonical_json_bytes({'baseline_id': record['id'], 'record_path': path,
            'record_sha256': checked['record_sha256'], 'model_root_sha256': checked['model_root_sha256'],
            **({'configuration_binding': checked['configuration_binding']}
               if 'configuration_binding' in checked else {}),
            'snapshot_integrity_verified': True,
            'objects': [item.reference.data for _, item in sorted(objects.items())],
            'historical_full_validation_verified': False, 'release_authorized': False})

    return finish
