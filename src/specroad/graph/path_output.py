"""Complete external delivery of already computed paths; no graph search or CLI.

The trusted producer chooses the complete path set and its semantic order.
These values preserve identities and directions, not a claim of shortestness,
scope completeness, lifecycle validity or a current project snapshot.
"""
from dataclasses import dataclass

from ..diagnostics.spooling import DiagnosticSort, DiagnosticSpool
from ..model.identity_values import ArtifactIdentity
from ..model.relation_values import RelationIdentity
from ..result_contract import ResultContractError
from .relation_views import RelationView


@dataclass(frozen=True)
class PathRecord:
    artifacts: tuple
    relations: tuple
    inverse: tuple

    def __post_init__(self):
        if (type(self.artifacts) is not tuple or not self.artifacts
                or type(self.relations) is not tuple or type(self.inverse) is not tuple
                or len(self.artifacts) != len(self.relations) + 1
                or len(self.inverse) != len(self.relations)
                or any(type(value) is not ArtifactIdentity for value in self.artifacts)
                or any(type(value) is not RelationIdentity for value in self.relations)
                or any(type(value) is not bool for value in self.inverse)):
            raise ResultContractError("An owned path with exact identities and directions is required")
        if len({value.id_prefix for value in self.artifacts}) != 1:
            raise ResultContractError("Path identities must belong to one project prefix")

    @classmethod
    def from_views(cls, start, views):
        if type(start) is not ArtifactIdentity or type(views) is not tuple:
            raise ResultContractError("An owned start and relation views are required")
        artifacts, relations, inverse = [start], [], []
        for view in views:
            if type(view) is not RelationView or view.source != artifacts[-1]:
                raise ResultContractError("Path views must form a connected directed walk")
            artifacts.append(view.target)
            relations.append(view.stored.relation.identity)
            inverse.append(view.inverse)
        return cls(tuple(artifacts), tuple(relations), tuple(inverse))

    def as_dict(self):
        return dict(artifacts=[dict(id=value.id, id_scheme=value.id_scheme,
                                  artifact_type=value.artifact_type, id_prefix=value.id_prefix)
                               for value in self.artifacts],
                    relations=[value.as_fields() for value in self.relations], inverse=list(self.inverse))

    @classmethod
    def from_dict(cls, value):
        if (type(value) is not dict or set(value) != {"artifacts", "relations", "inverse"}
                or any(type(value[key]) is not list for key in value)):
            raise ResultContractError("Exact path fields are required")
        for artifact in value["artifacts"]:
            if type(artifact) is not dict or set(artifact) != {"id", "id_scheme", "artifact_type", "id_prefix"}:
                raise ResultContractError("Exact artifact identity fields are required")
        for relation in value["relations"]:
            if type(relation) is not dict or set(relation) != {"relation_id", "id_scheme"}:
                raise ResultContractError("Exact relation identity fields are required")
        return cls(tuple(ArtifactIdentity(**item) for item in value["artifacts"]),
                   tuple(RelationIdentity(**item) for item in value["relations"]), tuple(value["inverse"]))


def _path_key(value):
    if type(value) is not PathRecord:
        raise ResultContractError("Expected a typed path record")
    return ()  # Preserve the complete producer-defined order using input sequence.


class PathSpool(DiagnosticSpool):
    _record_field = "path"
    _format = "path-spool-v1"
    _ordering = "supplied-path-order-v1"
    _cursor_format = "path-cursor-v1"
    _sort_key = staticmethod(_path_key)
    _decode = staticmethod(PathRecord.from_dict)


class PathSort(DiagnosticSort):
    """The same bounded-run driver, preserving every supplied ordered path."""
    def __init__(self, root, paths, *, protected_roots, batch_bytes=65536):
        super().__init__(root, paths, protected_roots=protected_roots,
                         batch_bytes=batch_bytes, _spool_type=PathSpool)


def create_path_spool(root, paths, *, protected_roots, batch_bytes=65536):
    task = PathSort(root, paths, protected_roots=protected_roots, batch_bytes=batch_bytes)
    while not task.advance(256)["complete"]:
        pass
    return task.result
