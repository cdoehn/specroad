"""Retain full-project selection through the native snapshot and scope services.

This adapter adds the bundle-specific receipt, root-marker and archive-name
observations to InspectionSnapshot. It does not create another snapshot model,
resolve a second closure, or grant publication/extraction authority.
"""
import os

from ..authoring._inspection_snapshot import InspectionSnapshot, InspectionChanged
from ..changes.target_model import _default_scope
from ..exchange._export_scope import export_scope, resource_identity
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.operational_paths import REQUESTS_ROOT, RECEIPTS_ROOT
from ..model.paths import PathClass
from ..model.record_schemas import validate_record_fields
from ..query.show import _preflight
from ..security.resource_access import opened_resource, directory_entries, resource_is_directory
from ..storage.json_syntax import parse_json_object
from ..storage.project import ProjectSource
from .errors import BundleError
from .manifest import MANIFEST_NAME, owned_metadata, check_entries, require


def _empty_receipts(source):
    # Shallow read preflight deliberately skips passive histories. Absence or
    # emptiness is therefore observed here, through guarded directory handles.
    for path in (REQUESTS_ROOT, RECEIPTS_ROOT):
        with opened_resource(source.boundary, path, directory=True, missing_ok=True) as (fd, _):
            if fd is not None and os.listdir(fd):
                raise BundleError('bundle_portable_receipt_provider_required', code=None, exit_code=5)


def _previous_manifest(source):
    # An extracted partial project may happen to have a closed-looking model.
    # Its marker still prohibits promotion to a writable full bundle.
    with opened_resource(source.boundary, MANIFEST_NAME, missing_ok=True) as (fd, _):
        if fd is None:
            return None
        raw = source.boundary.read_bytes(MANIFEST_NAME)
    value = parse_json_object(raw)
    require('entries' in value, 'bundle_entries_missing')
    check_entries(value['entries'])
    metadata = owned_metadata({key: item for key, item in value.items() if key != 'entries'})
    require(raw == canonical_json_bytes(value), 'noncanonical_bundle_manifest', code='SRV060')
    require(metadata['project_id'] == source.configuration.project_id, 'bundle_configuration_binding')
    if metadata['bundle_kind'] != 'project':
        raise BundleError('bundle_partial_project_source', code='SRV083', exit_code=7)
    return raw


def _archive_paths(source):
    """Observe managed archive names, including deliberately omitted objects."""
    pending = [(p, True) for p in source.configuration.managed_paths if p.split('/')[0] == 'archive']
    seen, paths = set(), set()
    while pending:
        path, optional = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        directory = resource_is_directory(source.boundary, path, missing_ok=optional)
        if directory is None:
            continue
        if directory:
            pending.extend((path + '/' + name, False) for name, _ in directory_entries(source.boundary, path))
        else:
            require(source.classify(path) is PathClass.ARCHIVE_OBJECT, 'bundle_archive_path_invalid')
            paths.add(path)
    return tuple(sorted(paths, key=lambda p: p.encode('utf-8')))


class ProjectBundleSnapshot:
    """Own the selected bytes and the original observation used to recheck them."""

    def __init__(self, root):
        source = ProjectSource(root)
        _preflight(source)
        _empty_receipts(source)
        previous_manifest = _previous_manifest(source)
        snapshot = InspectionSnapshot(root, None, include_archive_objects=True)
        if (snapshot.source.boundary._root_identity != source.boundary._root_identity
                or snapshot.source.configuration_bytes != source.configuration_bytes):
            raise BundleError('bundle_project_changed', code=None, exit_code=6)
        archives = _archive_paths(source)
        descriptor = ScopeDescriptor(_default_scope())
        model = snapshot.model
        for artifact in model.artifacts:
            (validate_domain_fields if artifact['artifact_type'] in DOMAIN_TYPES else
             validate_record_fields)(artifact)
        closure, native, artifacts, _ = export_scope(model, descriptor)
        require(set(closure.artifact_ids) == {a['id'] for a in model.artifacts}
                and set(closure.resource_ids) == {resource_identity(r) for r in model.resources}
                and not closure.boundary_references, 'bundle_project_closure_incomplete')
        require(native.sha256 == model.manifest(artifacts, descriptor.data).sha256,
                'bundle_project_manifest_mismatch', code='SRV060')
        # Snapshot.raw also retains the actual declarative language-package files;
        # TargetModel.source_files alone would lose those required source bytes.
        payloads = dict(snapshot.raw)
        require(set(snapshot.payload_paths).intersection(archives) ==
                {p for p in snapshot.payload_paths if p.startswith('archive/')},
                'bundle_archive_inventory_incomplete')

        self.source = source
        self.model = model
        self.descriptor = descriptor
        self.native = native
        self.payloads = payloads
        self.archives = archives
        self._snapshot = snapshot
        self._previous_manifest = previous_manifest

    def verify_current(self):
        self._snapshot.verify_current()
        if (_archive_paths(self.source) != self.archives
                or _previous_manifest(self.source) != self._previous_manifest):
            raise InspectionChanged('bundle_inventory_changed')
        _empty_receipts(self.source)
        _preflight(self.source)
        self.source.check_current()
