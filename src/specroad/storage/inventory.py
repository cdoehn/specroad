"""Complete current-resource inventory, not a scope closure or sealed snapshot.

JSON files in managed normative trees and explicitly referenced attachment bytes
are inputs. Generated, operational, unreferenced and archive data are excluded.
No cache, workspace file, ID reservation or transaction is created by a read.
"""

from hashlib import sha256

from ..model.artifact_schemas import validate_common_fields
from ..model.attachments import AttachmentDescriptor
from ..model.errors import ModelError
from ..model.hashes import canonical_json_sha256
from ..model.paths import PathClass, artifact_path
from ..model.versions import SCHEMA_VERSION
from .attachments import fingerprint_file, verify_attachments
from .json_syntax import parse_json_object
from .project import ProjectSource
from ..model.resource_inventory import ResourceEntry, ResourceInventory
from .resource_discovery import current_json_paths as _scan_json_paths


def _read_json_entry(source, path):
    raw = source.read_normative(path)
    value = parse_json_object(raw, path=path)
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ModelError("unsupported_schema_version", path=path, pointer="/schema_version",
                         highest_supported=SCHEMA_VERSION)
    kind = source.classify(path)
    if kind is PathClass.ARTIFACT:
        validate_common_fields(value)
        if artifact_path(value["artifact_type"], value["id"], source.configuration.id_prefix) != path:
            raise ModelError("artifact_path_identity_mismatch", path=path)
    return ResourceEntry(path, kind.value, len(raw), sha256(raw).hexdigest(),
                         canonical_json_sha256(value), "application/json"), value


def _attachment_declarations(value, path):
    if value.get("artifact_type") != "evidence":
        return ()
    declarations = value.get("attachments", [])
    if type(declarations) is not list:
        raise ModelError("attachment_sequence_required", path=path, pointer="/attachments")
    result = tuple(AttachmentDescriptor.from_data(item) for item in declarations)
    if len({item.path for item in result}) != len(result):
        raise ModelError("duplicate_attachment", path=path, pointer="/attachments")
    return result


def inventory_project(source, *, attachments=()):
    """Observe every current resource or fail. Never return a partial inventory.

    Additional declarations must be explicit. Only the defined evidence field is
    traversed automatically; strings/paths in extensions remain passive values.
    Full artifact/profile/graph validation belongs to the later validation layer.
    """
    if not isinstance(source, ProjectSource):
        raise TypeError("A bound ProjectSource is required")
    if isinstance(attachments, (str, bytes, dict)):
        raise ModelError("attachment_sequence_required")
    try:
        explicit = tuple(attachments)
    except TypeError as error:
        raise ModelError("attachment_sequence_required") from error
    if any(not isinstance(value, AttachmentDescriptor) for value in explicit):
        raise ModelError("invalid_attachment_descriptor")
    if len({value.path for value in explicit}) != len(explicit):
        raise ModelError("duplicate_attachment")
    source.check_current()
    names = _scan_json_paths(source)
    entries = []
    declared = {}
    def include(descriptor):
        previous = declared.get(descriptor.path)
        if previous is not None and previous != descriptor:
            raise ModelError("conflicting_attachment_declarations", path=descriptor.path)
        declared[descriptor.path] = descriptor
    for descriptor in explicit:
        include(descriptor)
    for path in names:
        entry, value = _read_json_entry(source, path)
        entries.append(entry)
        if entry.kind == PathClass.ARTIFACT.value:
            for descriptor in _attachment_declarations(value, path):
                include(descriptor)
    registry = source.configuration.data.get("language_registry")
    if registry is not None:
        path = registry["path"]
        if path in names:
            raise ModelError("conflicting_resource_roles", path=path)
        observed = fingerprint_file(source.boundary, path)
        if observed.sha256 != registry["sha256"]:
            raise ModelError("registry_hash_mismatch", path=path)
        entries.append(ResourceEntry(path, "language_registry", observed.size, observed.sha256))
    for item in verify_attachments(source, tuple(declared.values())):
        entries.append(ResourceEntry(item.path, "attachment", item.size, item.sha256,
                                     media_type=item.media_type))
    if len({entry.path.casefold() for entry in entries}) != len(entries):
        raise ModelError("resource_path_collision")
    # Full byte recheck plus second membership scan. This detects observed races,
    # but cannot replace locking and target validation in a future transaction.
    for entry in entries:
        current = fingerprint_file(source.boundary, entry.path)
        if current.size != entry.size or current.sha256 != entry.sha256:
            raise ModelError("inventory_resource_changed", path=entry.path)
    if _scan_json_paths(source) != names:
        raise ModelError("inventory_membership_changed")
    source.check_current()
    return ResourceInventory(source.configuration.project_id,
                             tuple(sorted(entries, key=lambda item: item.path)),
                             str(source.boundary.root), source.boundary._root_identity,
                             tuple(sorted(explicit, key=lambda item: item.path)))


def check_inventory_current(source, inventory):
    """Rebuild and compare a read binding. Still not a locked write permission."""
    if not isinstance(source, ProjectSource) or not isinstance(inventory, ResourceInventory):
        raise TypeError("A ProjectSource and ResourceInventory are required")
    source.check_current()
    if (inventory.source_root != str(source.boundary.root)
            or inventory.root_identity != source.boundary._root_identity
            or inventory.project_id != source.configuration.project_id):
        raise ModelError("inventory_project_mismatch")
    current = inventory_project(source, attachments=inventory.explicit_attachments)
    if current.data != inventory.data:
        raise ModelError("inventory_changed")
