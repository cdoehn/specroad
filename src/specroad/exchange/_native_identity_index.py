"""Passive native-owner lookup, separate from import-history construction."""
from dataclasses import dataclass
from types import MappingProxyType

from ..graph._relation_validation import EXTERNAL_KEY, _external_identities
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.paths import project_path
from ..storage.json_syntax import parse_json_object
from ._identity_errors import ImportIdentityError, _error
from ._import_identity import ExternalIdentity


def _source_path(value):
    if value is None:
        return None
    if type(value) is not str:
        raise ImportIdentityError("identity_source_path_required")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise ImportIdentityError("identity_source_path_required") from error
    try:
        return project_path(value)
    except ModelError as error:
        raise _error(error) from error


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
            path = _source_path(supplied.path)
            if type(supplied.source_bytes) is not bytes:
                raise ImportIdentityError("bytes_required", path=path)
            # Reconstruct from actual bytes instead of trusting cached projections.
            try:
                source = SourceRelations(supplied.source_bytes, path=path)
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
            try:
                identity = ExternalIdentity(value)
            except ModelError as error:
                raise _error(error, path=path, prefix=prefix + "/external_identities/" + str(i)) from error
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
