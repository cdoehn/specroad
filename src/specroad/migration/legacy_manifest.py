"""Qualified original-byte registry and detached legacy navigation, never a writer."""
from dataclasses import dataclass
from hashlib import sha256
import re

from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..model.identity_values import artifact_identity
from ..storage.json_syntax import parse_json_object as parsed
from .plan_values import MANIFEST_PATH, require, owned_files, safe_path
from .plan_inputs import target_contract
from .plan_originals import _original_archive
from .relation_derivation import _SourceRelations
from .reference01 import inventory_bytes


def manifest_paths(raw):
    """Check read destinations before any manifest-directed filesystem access."""
    value = parsed(raw, path=MANIFEST_PATH)
    rows = value.get('entries')
    require(type(rows) is list and bool(rows), 'legacy_manifest_entries_required')
    names = set()
    for row in rows:
        require(type(row) is dict, 'legacy_manifest_entry_invalid')
        path = safe_path(row.get('path'))
        logical = safe_path(row.get('logical_path'))
        role = row.get('role')
        require(role in ('artifact', 'configuration', 'profile', 'attachment'), 'legacy_manifest_role_invalid')
        address = re.fullmatch(r'archive/objects/([0-9a-f]{2})/([0-9a-f]{64})', path)
        if address:
            require(address[1] == address[2][:2], 'legacy_manifest_address_invalid')
        else:
            require(path == logical and (role == 'artifact' and path.startswith('spec/')
                or role == 'attachment' and path != 'specroad.json'
                and not path.startswith(('spec/', 'profiles/', 'rules/', 'mappings/', 'archive/'))),
                'legacy_manifest_destination_invalid', path=path)
        names.add(path)
    # Validate portable paths and prefix conflicts independently of row ordering.
    owned_files({p: b'' for p in names})
    return tuple(sorted(names))


@dataclass(frozen=True, init=False)
class LegacyArtifact:
    """Original source data and separately labelled, non-serializable-as-current views."""
    source_bytes: bytes
    path: str
    _row: bytes
    manifest_sha256: str

    @property
    def data(self):
        return parsed(self.source_bytes, path=self.path)

    @property
    def artifact_type(self):
        return self.data['artifact_type']

    @property
    def id(self):
        return self.data['id']

    @property
    def schema_version(self):
        return self.data['schema_version']

    @property
    def storage_class(self):
        return 'legacy_immutable'

    @property
    def validation_scope(self):
        return 'qualified_reference01_original_and_manifest'

    @property
    def navigation(self):
        value = self.data
        row = parsed(self._row)
        value.update(row['identity_projection'])
        value['relations'] = [{**r['original'], 'relation_id': r['relation_id'],
                               'id_scheme': r['id_scheme']} for r in row['relation_projections']]
        return value  # schema_version stays 0.1.0; this is NOT a current original.

    @property
    def identity(self):
        return artifact_identity(self.navigation)

    @property
    def common_fields(self):
        from ..model.artifact_schemas import artifact_common_schema
        names = artifact_common_schema(self.artifact_type)['properties']
        return {k: v for k, v in self.data.items() if k in names}

    @property
    def audit(self):
        from ..model.audit import artifact_audit
        return artifact_audit(self.data)

    def manifest_resource(self, binding):
        from ..model.model_manifest import ManifestResource
        value = self.data
        return ManifestResource(binding, {'kind': 'artifact', 'id': value['id'],
            'artifact_type': value['artifact_type'], 'revision': int(value['revision']),
            'sha256': sha256(self.source_bytes).hexdigest(),
            'hash_domain': 'legacy-original-bytes-v1', 'legacy_manifest_sha256': self.manifest_sha256})


@dataclass(frozen=True, init=False)
class LegacyManifest:
    _encoded: bytes
    _files: tuple
    _originals: tuple

    @property
    def data(self):
        return parsed(self._encoded)

    @property
    def sha256(self):
        return sha256(self._encoded).hexdigest()

    @property
    def byte_bindings(self):
        return tuple((p, len(raw), sha256(raw).hexdigest()) for p, raw in self._files)

    @property
    def protected_paths(self):
        return tuple(p for p, _ in self._files)

    def artifact(self, path, raw, *, expected_type=None):
        candidates = [(row, original) for row, original in self._originals
                      if row['path'] == path and row['role'] == 'artifact']
        require(bool(candidates), 'legacy_original_unregistered', path=path)
        row, original = candidates[0]
        require(raw == original.source_bytes, 'legacy_original_bytes_changed', path=path, exit_code=6)
        require(expected_type is None or original.data['artifact_type'] == expected_type,
                'artifact_type_mismatch', path=path)
        result = object.__new__(LegacyArtifact)
        for key, value in dict(source_bytes=raw, path=path, _row=jcs(row), manifest_sha256=self.sha256).items():
            object.__setattr__(result, key, value)
        return result


def validate_legacy_manifest(files, *, project_id):
    """Reconstruct and qualify the original source, then compare its entire registry.

    Files are owned input bytes. No project-selected schema, import, writer,
    historical approval or current readiness is trusted or manufactured here.
    """
    files = owned_files(files)
    require(MANIFEST_PATH in files, 'legacy_manifest_required')
    raw = files[MANIFEST_PATH]
    names = manifest_paths(raw)
    require(all(p in files for p in names), 'legacy_original_missing')
    value = parsed(raw)
    # The full closed shape is compared with the native source projection below.
    rows = value['entries']
    by_snapshot = {}
    referenced_roots = set()
    for row in rows:
        root = row.get('source_model_root_sha256')
        require(type(root) is str and re.fullmatch('[0-9a-f]{64}', root) is not None,
                'legacy_source_root_invalid')
        physical = files[row['path']]
        require(type(row.get('original_size')) in (int, float) and len(physical) == row['original_size']
                and sha256(physical).hexdigest() == row.get('original_byte_sha256'),
                'legacy_original_bytes_changed', path=row['path'], exit_code=6)
        logical = row['logical_path']
        snapshot = by_snapshot.setdefault(root, {})
        require(logical not in snapshot or snapshot[logical] == physical,
                'legacy_original_conflict', path=logical, exit_code=6)
        snapshot[logical] = physical
        if row['role'] == 'artifact':
            data = parsed(physical, path=logical)
            if data.get('artifact_type') == 'baseline':
                parent = data.get('model_root_sha256')
                require(type(parent) is str, 'legacy_source_root_invalid')
                referenced_roots.add(parent)
    roots = set(by_snapshot) - referenced_roots
    require(len(roots) == 1, 'legacy_source_root_ambiguous')
    source = dict(by_snapshot[next(iter(roots))])
    source.update({p: files[p] for p in names if p.startswith('archive/objects/')})
    inventory = inventory_bytes(source)
    require(inventory.data['project_id'] == project_id, 'legacy_project_mismatch')
    relations = _SourceRelations(inventory)
    archives, expected, _ = _original_archive(inventory, source, target_contract(), relations)
    current = [o for o in inventory.originals if o.snapshot_root == inventory.model_root_sha256]
    expected['proposal_transitions'] = sorted([{
        'artifact_id': o.data['id'], 'source_revision': o.data['revision'],
        'source_sha256': o.canonical_sha256, 'target_revision': o.data['revision'] + 1,
        'target_content_revision': o.data['content_revision'] + 1}
        for o in current if o.role == 'artifact' and o.classification == 'mutable'
        and o.data['artifact_type'] == 'proposal'], key=lambda r: r['artifact_id'])
    require(jcs(value) == jcs(expected), 'legacy_manifest_projection_mismatch')
    originals = {(o.snapshot_root, o.path): o for o in inventory.originals}
    registered = tuple((r, originals[(r['source_model_root_sha256'], r['logical_path'])]) for r in rows)
    result = object.__new__(LegacyManifest)
    object.__setattr__(result, '_encoded', jcs(expected))
    object.__setattr__(result, '_files', tuple(sorted({MANIFEST_PATH: raw, **{p: files[p] for p in names}}.items())))
    object.__setattr__(result, '_originals', registered)
    return result
