"""Private read-only input boundary, separate from future transaction publishing.

Only source observation, exact byte capture and freshness checks belong here.
No target authorization, output handle, repair or cache-write path is exposed.
"""
from hashlib import sha256
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.paths import PathClass, artifact_path
from ..security import ProjectBoundary
from ..validation import ModelDocument
from .json_syntax import parse_json_object
from .project import ProjectSource
from .resource_discovery import current_json_paths
from .operational_preflight import observe_operational_preflight

def _operational_metadata(boundary, *, complete_inventory=False):
    return observe_operational_preflight(boundary, complete_inventory=complete_inventory)


def _artifact_names(source):
    return tuple(path for path in current_json_paths(source)
                 if source.classify(path) is PathClass.ARTIFACT)


def _capture_documents(source):
    names = _artifact_names(source)
    documents = tuple(ModelDocument(name, source.read_normative(name)) for name in names)
    # Invalid JSON/schema values are diagnosed by validate_model, not repaired.
    for document in documents:
        try:
            value = parse_json_object(document.content, path=document.path)
        except ModelError:
            continue
        if type(value.get("id")) is str and type(value.get("artifact_type")) is str:
            expected = artifact_path(value["artifact_type"], value["id"], source.configuration.id_prefix)
            if expected != document.path:
                raise ModelError("artifact_path_identity_mismatch", path=document.path)
    return documents


def _fresh(source, operational, documents):
    source.check_current()
    if _operational_metadata(source.boundary) != operational:
        raise ModelError("operational_metadata_changed")
    if _artifact_names(source) != tuple(document.path for document in documents):
        raise ModelError("read_only_membership_changed")
    for document in documents:
        if source.read_normative(document.path) != document.content:
            raise ModelError("read_only_source_changed", path=document.path)
    source.check_current()
    if _artifact_names(source) != tuple(document.path for document in documents):
        raise ModelError("read_only_membership_changed")
    if _operational_metadata(source.boundary) != operational:
        raise ModelError("operational_metadata_changed")


def _source(root, data, expected_project_id):
    data["phase"] = "operational"
    boundary = ProjectBoundary(root)
    observation = _operational_metadata(boundary)
    data["operational"] = observation
    if observation["consistency_state"] != "consistent":
        return None, observation
    data["phase"] = "configuration"
    source = ProjectSource(boundary.root, expected_project_id=expected_project_id)
    # ProjectSource creates its own capability. Reject replacement in between.
    boundary._check_root()
    if boundary._root_identity != source.boundary._root_identity:
        raise ModelError("read_only_project_replaced")
    data["project_id"] = source.configuration.project_id
    data["configuration_sha256"] = sha256(source.configuration_bytes).hexdigest()
    return source, observation


def _ready(source, observation, data):
    """Recheck immediately before the model read, after caller-supplied composition."""
    source.check_current()
    current = _operational_metadata(source.boundary)
    if current != observation:
        data["operational"] = current
        if current["consistency_state"] != "consistent":
            return False
        raise ModelError("operational_metadata_changed")
    return True


def _record_freshness(source, observation, documents, data):
    _fresh(source, observation, documents)
    data["source_observation_sha256"] = canonical_json_sha256({
        "project_id": data["project_id"], "configuration_sha256": data["configuration_sha256"],
        "sources": data["source_bindings"], "resources": data["resource_bindings"],
        "operational": observation})
    data["freshness_verified"] = True
