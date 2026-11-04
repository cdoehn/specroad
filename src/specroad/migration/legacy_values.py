"""Owned immutable original and registry values; projections never replace source bytes."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs
from ..model.identity_values import artifact_identity
from ..storage.json_syntax import parse_json_object as parsed
from .plan_values import require


@dataclass(frozen=True, init=False)
class LegacyArtifact:
    """Original source data and separately labelled, non-serializable-as-current views."""
    source_bytes: bytes
    path: str
    _row: bytes
    manifest_sha256: str
    project_id: str

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
        require(binding.project_id == self.project_id, 'legacy_project_mismatch')
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
        for key, value in dict(source_bytes=raw, path=path, _row=jcs(row), manifest_sha256=self.sha256,
                               project_id=self.data["source"]["project_id"]).items():
            object.__setattr__(result, key, value)
        return result
