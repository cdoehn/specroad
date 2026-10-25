"""Fresh, read-only observations of extracted partials, never ProjectSource.

The original manifest selects bytes, not filesystem authority. Native bundle
verification reconstructs membership before any artifact becomes visible.
Configuration context and boundary proofs never enlarge that membership.
"""
from hashlib import sha256
import os

from ..authoring._bootstrap_io import STAGING
from ..graph.boundary_validation import validate_boundary_references
from ..graph.relations import SourceRelations
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.paths import artifact_path
from ..runtime.preflight import require_project_read_preflight
from ..security import ProjectBoundary, SafetyViolation
from ..security.resource_access import directory_entries, resource_is_directory
from ..storage.archive import ArchiveError, encode_archive
from ..storage.json_syntax import parse_json_object
from ..storage.preflight_metadata import MetadataPhases
from ._extracted_root import _optional
from ._extraction_record import COMPLETED, FORMAT
from ._partial_verification import verify_partial_model
from .container import BundleContainer, _archive_failure
from .errors import BundleError
from .manifest import MANIFEST_NAME, check_entries, check_manifest_bytes, owned_metadata, require

_PROOF = '/'.join((*COMPLETED, 'journal.json'))
_PAYLOAD_ROOTS = ('spec', 'profiles', 'rules', 'mappings', 'attachments', 'archive', 'bundle-context')


def _payload_paths(boundary):
    paths = {'specroad.json'}
    pending = [(p, True) for p in _PAYLOAD_ROOTS]
    while pending:
        path, optional = pending.pop()
        directory = resource_is_directory(boundary, path, missing_ok=optional)
        if directory is None:
            continue
        if directory:
            pending.extend((path + '/' + name, False) for name, _ in directory_entries(boundary, path))
        else:
            paths.add(path)
    return frozenset(paths)


def _marker(boundary):
    boundary._check_root()
    if os.path.lexists(boundary.root / STAGING):
        raise SafetyViolation('Unfinished bootstrap requires recovery')
    raw = _optional(boundary, MANIFEST_NAME)
    proof = _optional(boundary, _PROOF)
    if proof is not None:
        try:
            value = parse_json_object(proof)
            expected = value['entries'][MANIFEST_NAME]
            if (value['format'] != FORMAT or value['state'] != 'prepared' or raw is None
                    or expected['size'] != len(raw) or expected['sha256'] != sha256(raw).hexdigest()):
                raise SafetyViolation('Extracted bundle manifest changed or missing')
        except (KeyError, TypeError, ValueError) as error:
            raise SafetyViolation('Invalid extracted bundle metadata') from error
    return raw, proof


def partial_read_snapshot(root):
    """Return None only for an unmarked or canonical complete-project root."""
    boundary = ProjectBoundary(root)
    marker = _marker(boundary)
    if marker[0] is None:
        return None
    try:
        manifest = parse_json_object(marker[0])
        require('entries' in manifest, 'bundle_entries_missing')
        check_entries(manifest['entries'])
        metadata = owned_metadata({k: v for k, v in manifest.items() if k != 'entries'})
        if metadata['bundle_kind'] == 'project':
            return None
        return PartialReadSnapshot(boundary, marker, manifest, metadata)
    except ArchiveError as error:
        raise _archive_failure(error) from error


class PartialReadSnapshot:
    """Owned original bytes plus a final freshness check; no write capability."""
    def __init__(self, boundary, marker, manifest, metadata):
        self.boundary, self.marker = boundary, marker
        self.configuration_bytes = boundary.read_bytes('specroad.json')
        self.configuration = ProjectConfiguration(parse_json_object(self.configuration_bytes))
        self.preflight()
        paths = _payload_paths(boundary)
        require(paths == {e['path'] for e in manifest['entries']}, 'bundle_partial_root_inventory')
        self.files = {p: boundary.read_bytes(p) for p in sorted(paths)}
        require(self.files['specroad.json'] == self.configuration_bytes, 'bundle_configuration_changed')
        check_manifest_bytes(marker[0], self.files)
        container = BundleContainer(encode_archive(MANIFEST_NAME, metadata, self.files))
        native = verify_partial_model(container)
        from ._payload_model import payload_model
        self.container = container
        self.payload_model = payload_model(container, partial=True)
        self.manifest = container.manifest
        self.records = tuple(SourceRelations(self.files[artifact_path(
            a['artifact_type'], a['id'], self.configuration.id_prefix)],
            path=artifact_path(a['artifact_type'], a['id'], self.configuration.id_prefix))
            for a in native.data['artifacts'])
        self.references = validate_boundary_references(self.records,
            self.manifest['boundary_references'], descriptor=ScopeDescriptor(self.manifest['scope_descriptor']))
        self.observation_sha256 = canonical_json_sha256({
            'scope': 'partial_bundle_artifacts', 'project_root': str(boundary.root),
            'root_identity': [str(p) for p in boundary._root_identity],
            'manifest_sha256': sha256(marker[0]).hexdigest(),
            'files': [{'path': p, 'sha256': sha256(raw).hexdigest()} for p, raw in self.files.items()]})
        self.verify_current()

    def configuration_selection(self, requested=None):
        """Resolve context for the selected scope, without adding query members."""
        from ..configurations import resolve_configuration
        selected = self.manifest['scope_descriptor']['configuration_id']
        if requested is not None and selected is not None and requested != selected:
            raise BundleError('bundle_partial_configuration_conflict', code=None, exit_code=3)
        selected = selected if requested is None else requested
        if selected is None:
            return None
        records = tuple(SourceRelations(d.content, path=d.path) for d in self.payload_model.documents)
        return resolve_configuration(records, selected)

    def require_records(self, records):
        require({r.identity.id: r.source_bytes for r in records} ==
                {r.identity.id: r.source_bytes for r in self.records}
                and len(records) == len(self.records), 'partial_sources_mismatch')

    @property
    def details(self):
        m = self.manifest
        return dict(bundle_kind='partial', read_only=True, project_complete=False,
            scope_descriptor=m['scope_descriptor'], boundary_references=m['boundary_references'],
            bundle_model_root_sha256=m['bundle_model_root_sha256'],
            origin_model_root_sha256=m['origin_model_root_sha256'], origin_root_verified=False)

    def preflight(self):
        require_project_read_preflight(self.boundary, self.configuration_bytes, MetadataPhases())

    def verify_current(self):
        # Marker/root safety is not hidden by a simultaneous operational blocker.
        _marker(self.boundary)
        self.preflight()
        try:
            if (_marker(self.boundary) != self.marker or _payload_paths(self.boundary) != set(self.files)
                    or any(self.boundary.read_bytes(p) != raw for p, raw in self.files.items())
                    or _payload_paths(self.boundary) != set(self.files)
                    or _marker(self.boundary) != self.marker):
                raise BundleError('bundle_partial_read_changed', code=None, exit_code=6)
        except FileNotFoundError as error:
            raise BundleError('bundle_partial_read_changed', code=None, exit_code=6) from error
