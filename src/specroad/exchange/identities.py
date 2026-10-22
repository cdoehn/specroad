"""Owned native identities and import history over explicitly supplied sources.

The caller supplies the actual mapping projections, payload and timestamp. This
layer does not select fields, accept losses, resolve conflicts or authorize an
import. History values can be placed in an artifact or relation candidate; the
normal change-plan and publication gates still apply.
"""
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType

from ..graph._relation_validation import EXTERNAL_KEY, _external_identities
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object


class ImportIdentityError(ModelError):
    exit_code = 3

    @property
    def code(self):
        return "SRV147" if self.reason.startswith("duplicate_") else "SRV090"

    def diagnostic(self):
        return {**super().diagnostic(), "code": self.code, "exit_code": self.exit_code}


def _error(error, *, path=None, prefix="", strip=""):
    pointer = error.pointer
    if strip and pointer.startswith(strip):
        pointer = pointer[len(strip):]
    return ImportIdentityError(error.reason, path=path if path is not None else error.path,
                               pointer=prefix + pointer)


@dataclass(frozen=True, init=False)
class ExternalIdentity:
    """The existing native relation identity contract, also usable on artifacts.

    Legacy identities without history remain unbound. Stored hashes and mapping
    names are retained as data; loading them does not verify their provenance.
    """
    _encoded: bytes

    def __init__(self, value):
        try:
            encoded = canonical_json_bytes(value)
            data = parse_json_object(encoded)
            _external_identities([data])
        except ModelError as error:
            raise _error(error, strip="/external_identities/0") from error
        object.__setattr__(self, "_encoded", encoded)

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def key(self):
        data = self.data
        return tuple(data[name] for name in EXTERNAL_KEY)

    @property
    def import_bound(self):
        return "mapping_id" in self.data

    def with_import_history(self, *, mapping_id, imported_projection,
                            source_projection, source_payload, imported_at):
        """Return a candidate with hashes of the explicitly supplied values.

        Projection hashes use JCS; the payload hash uses the exact original
        bytes. No projection is inferred from a complete artifact or from this
        identity. Existing revision and extension values remain unchanged.
        """
        if type(source_payload) is not bytes:
            raise ImportIdentityError("source_payload_bytes_required", pointer="/source_payload")
        hashes = {}
        for name, projection in (("imported_projection", imported_projection),
                                 ("source_projection", source_projection)):
            if type(projection) is not dict:
                raise ImportIdentityError("import_projection_object_required", pointer="/" + name)
            try:
                hashes[name] = sha256(canonical_json_bytes(projection)).hexdigest()
            except ModelError as error:
                raise _error(error, prefix="/" + name) from error
        data = self.data
        data.update(mapping_id=mapping_id, imported_at=imported_at,
                    last_imported_projection_sha256=hashes["imported_projection"],
                    last_source_projection_sha256=hashes["source_projection"],
                    last_source_payload_sha256=sha256(source_payload).hexdigest())
        return ExternalIdentity(data)


@dataclass(frozen=True, init=False)
class NativeIdentityIndex:
    """Find native owners by class/system/document/id, never by revision.

    The index covers only the supplied artifact bytes. It is not a completeness,
    graph-validation or currentness attestation. Non-artifact mapping registries
    have their own API. Returned observations cannot mutate this index.
    """
    _entries: object

    def __init__(self, sources):
        if type(sources) not in (list, tuple):
            raise ImportIdentityError("identity_sources_required")
        entries, artifacts, relations = {}, set(), set()
        prefix = None
        for supplied in sources:
            if type(supplied) is not SourceRelations:
                raise ImportIdentityError("identity_source_required")
            # Reconstruct from actual bytes instead of trusting cached projections.
            try:
                source = SourceRelations(supplied.source_bytes, path=supplied.path)
            except ModelError as error:
                raise _error(error) from error
            native = source.identity
            path = source.path if source.path is not None else native.path
            if path != native.path:
                raise ImportIdentityError("artifact_path_identity_mismatch", path=path)
            if prefix is not None and native.id_prefix != prefix:
                raise ImportIdentityError("mixed_project_prefix", path=path)
            prefix = native.id_prefix
            if native.id in artifacts:
                raise ImportIdentityError("duplicate_artifact_id", path=path, pointer="/id")
            artifacts.add(native.id)
            self._add(entries, "artifact", native.id, None, path,
                      source.data.get("external_identities", []), "")
            for i, relation in enumerate(source.relations):
                at = "/relations/" + str(i)
                relation_id = relation.identity.id
                if relation_id in relations:
                    raise ImportIdentityError("duplicate_relation_id", path=path, pointer=at + "/relation_id")
                relations.add(relation_id)
                self._add(entries, "relation", native.id, relation_id, path,
                          relation.data["external_identities"], at)
        object.__setattr__(self, "_entries", MappingProxyType(entries))

    @staticmethod
    def _add(entries, kind, artifact_id, relation_id, path, values, prefix):
        try:
            _external_identities(values)
        except ModelError as error:
            raise _error(error, path=path, prefix=prefix) from error
        for i, value in enumerate(values):
            identity = ExternalIdentity(value)
            key = (kind,) + identity.key
            if key in entries:
                raise ImportIdentityError("duplicate_external_" + kind + "_identity", path=path,
                    pointer=prefix + "/external_identities/" + str(i))
            entries[key] = canonical_json_bytes({"object_class": kind, "artifact_id": artifact_id,
                "relation_id": relation_id, "path": path, "identity": identity.data})

    def lookup(self, object_class, source_system, source_document, external_id):
        if type(object_class) is not str or object_class not in ("artifact", "relation"):
            raise ImportIdentityError("native_object_class_required", pointer="/object_class")
        identity = ExternalIdentity(dict(zip(EXTERNAL_KEY, (source_system, source_document, external_id))))
        encoded = self._entries.get((object_class,) + identity.key)
        return None if encoded is None else parse_json_object(encoded)
