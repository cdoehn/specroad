"""Owned local/Git comparison observations; no full model or approval claim."""
from dataclasses import dataclass
from hashlib import sha256

from ..graph.comparison_values import ComparisonInputs
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.domain_schemas import validate_domain_fields
from ..model.errors import ModelError
from ..model.paths import CURRENT_JSON_CLASSES, PathClass, artifact_path, classify_path
from ..model.record_contracts import RECORD_TYPES
from ..model.record_schemas import validate_record_fields
from ..runtime.preflight import require_project_read_preflight
from ..security import SafetyViolation
from ..storage.json_reader import JsonResource, configuration_schema
from ..storage.preflight_metadata import MetadataPhases
from ..storage.project import ProjectSource
from ..storage.resource_discovery import current_json_paths
from .git_source import GitObjectSource
from .semantic_diff import compare_semantic


def _git_json_paths(source, configuration):
    """Mirror configured JSON discovery against the pinned physical Git tree."""
    entries = source._entries
    children = {}
    for path in entries:
        parent, _, name = path.rpartition('/')
        children.setdefault(parent, []).append((name, path))

    def inspect(path):
        parts = path.split('/')
        for index in range(1, len(parts) + 1):
            current = '/'.join(parts[:index])
            entry = entries.get(current)
            if entry is None:
                return None
            mode, kind, _ = entry
            directory = (mode, kind) == (b'040000', b'tree')
            if (not directory and (mode, kind) not in
                    {(b'100644', b'blob'), (b'100755', b'blob')}) or (index < len(parts) and not directory):
                raise SafetyViolation('Comparison source path is not safely traversable')
            if directory and current + '/specroad.json' in entries:
                raise SafetyViolation('Nested project roots cannot be combined')
        return directory

    pending = [path for path in configuration.managed_paths
               if path.split('/')[0] in {'spec', 'profiles', 'rules', 'mappings'}]
    seen, paths = set(), {'specroad.json'}
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        directory = inspect(path)
        category = classify_path(path, configuration)
        if directory is None:
            if category in CURRENT_JSON_CLASSES:
                raise ModelError('git_path_missing', path=path)
            continue
        if not directory:
            if category not in CURRENT_JSON_CLASSES:
                raise ModelError('unclassified_normative_resource', path=path)
            paths.add(path)
            continue
        rows = children.get(path, ())
        if len({name.casefold() for name, _ in rows}) != len(rows):
            raise SafetyViolation('Portable directory names collide')
        for _, child in rows:
            if inspect(child):
                pending.append(child)
            elif child.endswith('.json'):
                if classify_path(child, configuration) not in CURRENT_JSON_CLASSES:
                    raise ModelError('unclassified_normative_json', path=child)
                paths.add(child)
    if len({path.casefold() for path in paths}) != len(paths):
        raise ModelError('resource_path_collision')
    return tuple(sorted(paths))


@dataclass(frozen=True, init=False)
class ComparisonSourceSnapshot:
    """Owned bytes observed once; neither a live reader nor an atomic snapshot.

    Local projects must pass read preflight and observed-byte rechecks. Git
    sources use only the selected commit, never current working-tree resources.
    Other normative JSON is bound but its semantics belong to later adapters.
    """
    kind: str
    source_root: str
    commit_id: str | None
    configuration: ProjectConfiguration
    inputs: ComparisonInputs
    resources: tuple

    def __init__(self, root, *, kind='local', reference=None, expected_project_id=None):
        if type(kind) is not str or kind not in ('local', 'git', 'baseline', 'bundle'):
            raise ModelError('comparison_source_kind_invalid')
        if kind in ('baseline', 'bundle'):
            raise ModelError('comparison_source_unavailable')
        if expected_project_id is not None and (type(expected_project_id) is not str
                or not expected_project_id.strip() or '\0' in expected_project_id):
            raise ModelError('comparison_project_required')
        if expected_project_id is not None:
            canonical_json_bytes(expected_project_id)
        if kind == 'local':
            if reference is not None:
                raise ModelError('comparison_reference_not_allowed')
            source = ProjectSource(root, expected_project_id=expected_project_id)
            require_project_read_preflight(source.boundary, source.configuration_bytes, MetadataPhases())
            configuration = source.configuration
            names = current_json_paths(source)
            resources = tuple((path, source.read_normative(path)) for path in names)
            source_root, commit_id = str(source.boundary.root), None
        else:
            source = GitObjectSource(root, reference)
            raw = source.read_bytes('specroad.json')
            configuration = ProjectConfiguration(JsonResource(raw, configuration_schema(), path='specroad.json').data)
            if expected_project_id is not None and configuration.project_id != expected_project_id:
                raise ModelError('project_identity_mismatch')
            names = _git_json_paths(source, configuration)
            resources = tuple((path, raw if path == 'specroad.json' else source.read_bytes(path)) for path in names)
            source_root, commit_id = str(source.root), source.commit_id
        records = []
        for path, raw in resources:
            if classify_path(path, configuration) is not PathClass.ARTIFACT:
                continue
            record = SourceRelations(raw, path=path)
            value = record.data
            if artifact_path(value['artifact_type'], value['id'], configuration.id_prefix) != path:
                raise ModelError('artifact_path_identity_mismatch', path=path)
            validate = validate_record_fields if value['artifact_type'] in RECORD_TYPES else validate_domain_fields
            try:
                validate(value)
            except ModelError as error:
                error.path = path
                raise
            records.append(record)
        inputs = ComparisonInputs(configuration.project_id, records)
        if kind == 'local':
            require_project_read_preflight(source.boundary, source.configuration_bytes, MetadataPhases())
            if current_json_paths(source) != names:
                raise ModelError('comparison_source_membership_changed')
            for path, raw in resources:
                if source.read_normative(path) != raw:
                    raise ModelError('comparison_source_changed', path=path)
            if current_json_paths(source) != names:
                raise ModelError('comparison_source_membership_changed')
            source.check_current()
            # A transaction can appear during the final byte/membership reads.
            # Observe operational state again before publishing owned inputs.
            # This remains an observation, never an atomic lock or write permit.
            require_project_read_preflight(source.boundary, source.configuration_bytes, MetadataPhases())
        for key, value in (('kind', kind), ('source_root', source_root), ('commit_id', commit_id),
                           ('configuration', configuration), ('inputs', inputs), ('resources', resources)):
            object.__setattr__(self, key, value)

    @property
    def uncompared_resources(self):
        return tuple((path, raw) for path, raw in self.resources
                     if classify_path(path, self.configuration) not in (PathClass.CONFIGURATION, PathClass.ARTIFACT))

    @property
    def binding(self):
        """Local provenance and raw bytes, explicitly not a SpecRoad model root."""
        return {'binding_version': 'comparison-source-v1', 'kind': self.kind,
                'source_root': self.source_root, 'commit_id': self.commit_id,
                'project_id': self.configuration.project_id,
                'resources': [{'path': path, 'sha256': sha256(raw).hexdigest()} for path, raw in self.resources],
                'comparison_scope': 'project_configuration_and_artifacts',
                'uncompared_resources': [path for path, _ in self.uncompared_resources],
                'atomic_snapshot': False, 'full_semantic_validation': False,
                'approval_granted': False, 'write_authorized': False}

    @property
    def sha256(self):
        return canonical_json_sha256(self.binding)


def compare_sources(before, after, *, timing_bounds=None):
    """Compare captured data with exactly the existing semantic-diff contract."""
    if type(before) is not ComparisonSourceSnapshot or type(after) is not ComparisonSourceSnapshot:
        raise ModelError('comparison_source_snapshot_required')
    if (before.configuration.project_id != after.configuration.project_id
            or before.configuration.id_prefix != after.configuration.id_prefix):
        raise ModelError('comparison_project_mismatch')
    # Opaque resources cannot silently turn a real profile/rule delta into an
    # unchanged project. Their interpretation remains outside this increment.
    if before.uncompared_resources != after.uncompared_resources:
        raise ModelError('comparison_resource_semantics_unavailable')
    return compare_semantic(before.inputs, after.inputs,
        before_configuration=before.configuration, after_configuration=after.configuration,
        timing_bounds=timing_bounds)
