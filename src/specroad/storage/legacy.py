"""Descriptor-bound legacy manifest reads and exact original-byte freshness."""
from hashlib import sha256
from ..migration.legacy_manifest import manifest_paths, validate_legacy_manifest
from ..migration.plan_values import MANIFEST_PATH, require
from .json_syntax import parse_json_object


def capture_legacy_manifest(source):
    try:
        raw = source.boundary.read_bytes(MANIFEST_PATH)
    except FileNotFoundError:
        return None
    files = {MANIFEST_PATH: raw}
    for path in manifest_paths(raw):
        files[path] = source.boundary.read_bytes(path)
    result = validate_legacy_manifest(files, project_id=source.configuration.project_id)
    check_legacy_current(source, result)
    return result


def check_legacy_current(source, manifest):
    if manifest is None:
        try:
            source.boundary.read_bytes(MANIFEST_PATH)
        except FileNotFoundError:
            return
        require(False, 'legacy_manifest_changed', path=MANIFEST_PATH, exit_code=6)
    for path, size, expected in manifest.byte_bindings:
        raw = source.boundary.read_bytes(path)
        require(len(raw) == size and sha256(raw).hexdigest() == expected,
                'legacy_manifest_changed', path=path, exit_code=6)


def legacy_artifact(source, path, raw, *, expected_type=None):
    manifest = source._legacy_manifest
    registered = manifest is not None and path in manifest.protected_paths
    if not registered and parse_json_object(raw, path=path).get('schema_version') != '0.1.0':
        return None
    require(manifest is not None, 'legacy_manifest_required', path=path)
    return manifest.artifact(path, raw, expected_type=expected_type)
