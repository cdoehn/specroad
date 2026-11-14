"""Qualify complete archived Baseline originals without reconstructing a project."""
from hashlib import sha256
from ..archive.objects import ObjectReference, SnapshotObject
from ..archive.verification import verify_baseline_objects
from ..model.record_schemas import validate_record_fields
from ..storage.json_syntax import parse_json_object
from .formats import declared_resource
from .errors import require


def baseline_objects(raw, read, *, active=frozenset()):
    """Verify every archived Baseline recursively, including original objects."""
    token = sha256(raw).hexdigest()
    require(token not in active, 'restore_baseline_cycle')
    declared_resource(raw, 'source:baseline', normative=True)
    record = parse_json_object(raw)
    validate_record_fields(record, expected_type='baseline')
    objects = {}
    for row in record['manifest']:
        require({'object_path', 'sha256', 'size'} <= row.keys(), 'restore_baseline_object_binding_missing')
        ref = ObjectReference(row['sha256'], row['size'])
        require(row['object_path'] == ref.path, 'restore_baseline_object_path_mismatch')
        content = read(ref.path)
        require(type(content) is bytes and len(content) == ref.size and sha256(content).hexdigest() == ref.sha256,
                'restore_baseline_object_bytes_mismatch', path=ref.path)
        declared_resource(content, ref.path, normative=row['role'] in
            ('artifact', 'profile', 'rule', 'mapping', 'semantic_configuration'))
        objects[ref.path] = content
    verify_baseline_objects(raw, tuple(SnapshotObject(b) for b in objects.values()))
    for row in record['manifest']:
        if row['role'] == 'artifact':
            content = objects[row['object_path']]
            if parse_json_object(content)['artifact_type'] == 'baseline':
                nested = baseline_objects(content, read, active=active | {token})
                for path, data in nested.items():
                    require(path not in objects or objects[path] == data, 'restore_baseline_object_conflict')
                    objects[path] = data
    return objects
