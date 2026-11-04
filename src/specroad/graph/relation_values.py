"""Immutable, source-bound relation values. No writer or adjacency indices."""

from dataclasses import dataclass
import json
from ..model.errors import ModelError
from ..model.identity_values import ArtifactIdentity, artifact_identity
from ..model.relation_identity import relation_identity
from ..storage.artifact_common import CommonArtifact
from ..storage.json_reader import parse_json_object
from ._relation_validation import KEY_FIELDS, _validate_fields

@dataclass(frozen=True, init=False)
class Relation:
    source: ArtifactIdentity
    _encoded: bytes

    def __init__(self, source, value):
        if type(source) is not ArtifactIdentity:
            raise ModelError("artifact_identity_required")
        _validate_fields(value)
        # Validate before encoding: do not run conversion hooks of foreign objects.
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "_encoded", encoded)

    @property
    def data(self):
        return json.loads(self._encoded)

    @property
    def identity(self):
        return relation_identity(self.data)

    @property
    def type(self):
        return self.data["type"]

    @property
    def target(self):
        return self.data["target"]

    @property
    def key(self):
        data = self.data
        return (self.source.id,) + tuple(data[name] for name in KEY_FIELDS)


@dataclass(frozen=True, init=False)
class SourceRelations:
    """Original artifact bytes and validated edges stored only at that source.

    The common envelope and relation fields are checked. Target existence,
    permitted type pairs, graph cycles and lifecycle authority are separate.
    """
    source_bytes: bytes
    identity: ArtifactIdentity
    relations: tuple
    path: str | None
    validation_scope: str

    def __init__(self, raw, *, expected_type=None, path=None):
        common = CommonArtifact(raw, expected_type=expected_type, path=path)
        value = parse_json_object(common.source_bytes, path=path)
        identity = artifact_identity(value)
        relations = []
        seen = set()
        for index, data in enumerate(value["relations"]):
            try:
                relation = Relation(identity, data)
                if relation.identity.id in seen:
                    raise ModelError("duplicate_relation_id", pointer="/relation_id")
            except ModelError as error:
                error.path = path
                error.pointer = "/relations/" + str(index) + error.pointer
                raise
            seen.add(relation.identity.id)
            relations.append(relation)
        object.__setattr__(self, "source_bytes", common.source_bytes)
        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "relations", tuple(relations))
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "validation_scope", "relation_fields_only")

    @classmethod
    def from_legacy(cls, original):
        from ..migration.legacy_manifest import LegacyArtifact
        if type(original) is not LegacyArtifact:
            raise ModelError('legacy_original_required')
        result = object.__new__(cls)
        values = dict(source_bytes=original.source_bytes, identity=original.identity,
            relations=tuple(Relation(original.identity, row) for row in original.navigation['relations']),
            path=original.path, validation_scope=original.validation_scope)
        for name, value in values.items():
            object.__setattr__(result, name, value)
        return result

    @property
    def storage_class(self):
        return ('legacy_immutable' if self.validation_scope == 'qualified_reference01_original_and_manifest'
                else 'current')

    @property
    def data(self):
        return parse_json_object(self.source_bytes, path=self.path)


