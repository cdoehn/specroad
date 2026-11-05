"""Owned complete source observations; no merge plan, checkout or write grant."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType

from .._metadata import MODEL_SCHEMA_VERSION
from ..bundles._payload_model import owned_payload_model
from ..changes.target_model import _default_scope
from ..exchange._export_scope import export_scope, resource_identity
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.paths import PathClass, classify_path
from ..query._comparison_capture import SourceCapture
from ..query.baseline_source import baseline_source
from ..query.comparison_sources import _git_json_paths
from ..query.git_source import GitObjectSource
from ..security import ProjectBoundary, SafetyViolation
from ..storage.json_syntax import parse_json_object


@dataclass(frozen=True)
class SourceRequest:
    root: str | Path
    kind: str = 'local'
    reference: str | None = None

    def __post_init__(self):
        if type(self.kind) is not str or self.kind not in _READERS:
            raise ModelError('merge_source_request_required')
        if not isinstance(self.root, (str, Path)) or not str(self.root).strip() or '\0' in str(self.root):
            raise ModelError('comparison_reference_required')
        canonical_json_bytes(str(self.root))
        if self.kind in ('local', 'bundle'):
            if self.reference is not None:
                raise ModelError('comparison_reference_not_allowed')
        elif type(self.reference) is not str or not self.reference.strip() or '\0' in self.reference:
            raise ModelError('comparison_reference_required')
        else:
            canonical_json_bytes(self.reference)


def _complete_marker(raw, project_id=None):
    if raw is None:
        return
    from ..bundles.manifest import check_entries, owned_metadata
    value = parse_json_object(raw)
    check_entries(value.get('entries'))
    metadata = owned_metadata({k: v for k, v in value.items() if k != 'entries'})
    if metadata['bundle_kind'] != 'project' or metadata['read_only']:
        raise ModelError('merge_complete_project_required')
    if raw != canonical_json_bytes(value):
        raise ModelError('noncanonical_bundle_manifest')
    if project_id is not None and metadata['project_id'] != project_id:
        raise ModelError('bundle_configuration_binding')


def _local(root, reference):
    if reference is not None:
        raise ModelError('comparison_reference_not_allowed')
    from ..bundles._project_snapshot import ProjectBundleSnapshot
    snapshot = ProjectBundleSnapshot(root)
    return SourceCapture(snapshot.model.configuration, tuple(sorted(snapshot.payloads.items())),
                         str(snapshot.source.boundary.root), check=snapshot.verify_current)


def _git(root, reference):
    from ..authoring._bootstrap_io import STAGING
    from ..bundles._extraction_record import COMPLETED
    from ..bundles._extracted_root import require_complete_markers
    source = GitObjectSource(root, reference)
    if STAGING in source._entries:
        raise SafetyViolation('Unfinished bootstrap requires recovery')
    proof_path = '/'.join((*COMPLETED, 'journal.json'))
    marker = source.read_optional_bytes('bundle-manifest.json')
    proof = source.read_optional_bytes(proof_path)
    require_complete_markers(marker, proof)
    configuration = ProjectConfiguration(parse_json_object(source.read_bytes('specroad.json')))
    _complete_marker(marker, configuration.project_id)
    files = {p: source.read_bytes(p) for p in _git_json_paths(source, configuration)}
    registry = configuration.data.get('language_registry')
    if registry is not None:
        files[registry['path']] = source.read_bytes(registry['path'])
    from ..migration.legacy_manifest import manifest_paths
    from ..migration.plan_values import MANIFEST_PATH
    protected = set(manifest_paths(files[MANIFEST_PATH])) if MANIFEST_PATH in files else set()
    payloads = set(protected)
    from ..archive.objects import ObjectReference
    from ..model.attachments import AttachmentDescriptor
    for path, raw in tuple(files.items()):
        if classify_path(path, configuration) is not PathClass.ARTIFACT:
            continue
        record = parse_json_object(raw, path=path)
        payloads.update(AttachmentDescriptor.from_data(item).path for item in record.get('attachments', []))
        if record.get('artifact_type') == 'baseline' and path not in protected:
            for row in record.get('manifest', []):
                item = ObjectReference(row.get('sha256'), row.get('size'))
                if item.path != row.get('object_path'):
                    raise ModelError('baseline_snapshot_object_path_mismatch')
                payloads.add(item.path)
    for path in sorted(payloads):
        files[path] = source.read_bytes(path)

    def check():
        # Reobserve pinned objects, never resolve the mutable ref again. Missing
        # commits/trees/blobs are failures even if an earlier read succeeded.
        for path, raw in (*files.items(), ('bundle-manifest.json', marker), (proof_path, proof)):
            if source.read_optional_bytes(path) != raw:
                raise ModelError('comparison_source_changed', path=path)

    return SourceCapture(configuration, tuple(sorted(files.items())), str(source.root),
                         commit_id=source.commit_id, check=check)


def _baseline(root, reference):
    if type(reference) is not str:
        raise ModelError('comparison_baseline_reference_required')
    from ..bundles._extracted_root import require_complete_root
    boundary = ProjectBoundary(root)
    markers = require_complete_root(boundary)
    capture = baseline_source(root, reference, None)
    # The native baseline reader supports selected configurations too. Such a
    # selection must not silently stand in for the complete merge input.
    evidence = parse_json_object(capture.finish())
    if 'configuration_binding' in evidence:
        raise ModelError('merge_complete_project_required')
    record_raw = boundary.read_bytes(evidence['record_path'])
    if sha256(record_raw).hexdigest() != evidence['record_sha256']:
        raise ModelError('comparison_source_changed')
    record = parse_json_object(record_raw)
    keys = [row['profile_id'] + '@' + row['version'] for row in record['profiles']]

    def check():
        if require_complete_root(boundary) != markers:
            raise ModelError('comparison_source_changed')
        checked = parse_json_object(capture.finish())
        return canonical_json_bytes({**checked, 'profile_keys': keys})

    return SourceCapture(capture.configuration, capture.resources, capture.source_root,
                         check=check, evidence_key=capture.evidence_key)


def _bundle(root, reference):
    if reference is not None:
        raise ModelError('comparison_reference_not_allowed')
    from ..bundles.container import BundleContainer
    from ..bundles.verification import verify_bundle
    from ..bundles._receipts import verify_payload_receipts
    path = Path(root)
    boundary = ProjectBoundary(path.parent)
    raw = boundary.read_bytes(path.name)
    verified = verify_bundle(raw)
    _complete_marker(canonical_json_bytes(verified['manifest']))
    container = BundleContainer(raw)
    receipts = verify_payload_receipts(container)
    files = {p: b for p, b in container.files.items() if p not in receipts}
    configuration = ProjectConfiguration(parse_json_object(files['specroad.json']))

    def check():
        try:
            current = boundary.read_bytes(path.name)
        except FileNotFoundError as error:
            raise ModelError('comparison_source_changed') from error
        if current != raw:
            raise ModelError('comparison_source_changed')
        return canonical_json_bytes(verified)

    return SourceCapture(configuration, tuple(sorted(files.items())), str(boundary.root / path.name),
                         check=check, evidence_key='bundle')


_READERS = MappingProxyType({'local': _local, 'git': _git, 'baseline': _baseline, 'bundle': _bundle})


@dataclass(frozen=True, init=False)
class SourceSnapshot:
    """Native scope/root plus immutable raw bytes and original provenance.

    Capturing bytes is neither an atomic filesystem snapshot nor an assertion
    that the entire model passed semantic validation or received approval.
    """
    kind: str
    source_root: str
    commit_id: str | None
    project_id: str
    schema_version: str
    _files: tuple
    _binding: bytes
    _observation: object

    def __init__(self, request):
        if type(request) is not SourceRequest or type(request.kind) is not str or request.kind not in _READERS:
            raise ModelError('merge_source_request_required')
        capture = _READERS[request.kind](request.root, request.reference)
        configuration = capture.configuration
        if configuration.data['schema_version'] != MODEL_SCHEMA_VERSION:
            raise ModelError('merge_schema_migration_required')
        files = tuple(sorted(capture.resources))
        evidence = capture.finish()
        details = None if evidence is None else parse_json_object(evidence)
        keys = tuple(details['profile_keys']) if request.kind == 'baseline' else None
        model = owned_payload_model(dict(files), source_label='merge:' + capture.source_root,
                                    profile_keys=keys)
        descriptor = ScopeDescriptor(_default_scope())
        closure, native, artifacts, _ = export_scope(model, descriptor)
        if (set(closure.artifact_ids) != {a['id'] for a in model.artifacts}
                or set(closure.resource_ids) != {resource_identity(r) for r in model.resources}
                or closure.boundary_references
                or native.sha256 != model.manifest(artifacts, descriptor.data).sha256):
            raise ModelError('merge_source_closure_incomplete')
        if capture.finish() != evidence:
            raise ModelError('comparison_source_changed')
        if details is not None:
            expected = (details['model_root_sha256'] if request.kind == 'baseline' else
                        details['manifest']['bundle_model_root_sha256'])
            if native.sha256 != expected:
                raise ModelError('merge_source_root_mismatch')
        binding = {'kind': request.kind, 'source_root': capture.source_root,
            'commit_id': capture.commit_id, 'project_id': configuration.project_id,
            'schema_version': configuration.data['schema_version'],
            'scope_descriptor': descriptor.data, 'model_root_sha256': native.sha256,
            'resources': [{'path': p, 'size': len(raw), 'sha256': sha256(raw).hexdigest()} for p, raw in files],
            'atomic_snapshot': False, 'full_semantic_validation': False,
            'approval_granted': False, 'write_authorized': False,
            **({capture.evidence_key: details} if capture.evidence_key is not None else {})}
        for name, value in (('kind', request.kind), ('source_root', capture.source_root),
                ('commit_id', capture.commit_id), ('project_id', configuration.project_id),
                ('schema_version', configuration.data['schema_version']), ('_files', files),
                ('_binding', canonical_json_bytes(binding)), ('_observation', capture.finish)):
            object.__setattr__(self, name, value)

    def verify_current(self):
        """Recheck the original acquisition; retained bytes never refresh silently."""
        self._observation()

    @property
    def files(self):
        return dict(self._files)

    @property
    def binding(self):
        return parse_json_object(self._binding)

    @property
    def sha256(self):
        return sha256(self._binding).hexdigest()


@dataclass(frozen=True)
class MergeSources:
    base: SourceSnapshot
    ours: SourceSnapshot
    theirs: SourceSnapshot

    def __post_init__(self):
        rows = (self.base, self.ours, self.theirs)
        if any(type(row) is not SourceSnapshot for row in rows):
            raise ModelError('merge_source_snapshot_required')
        if len({row.project_id for row in rows}) != 1:
            raise ModelError('merge_project_mismatch')
        if len({row.schema_version for row in rows}) != 1:
            raise ModelError('merge_schema_migration_required')

    @property
    def binding(self):
        return {name: getattr(self, name).binding for name in ('base', 'ours', 'theirs')}

    @property
    def sha256(self):
        return canonical_json_sha256(self.binding)


def load_merge_sources(base, ours, theirs):
    """Load three complete native sources without planning or publishing a merge."""
    result = MergeSources(*(SourceSnapshot(request) for request in (base, ours, theirs)))
    for source in (result.base, result.ours, result.theirs):
        source.verify_current()
    return result
