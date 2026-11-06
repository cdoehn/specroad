"""Private owned historical inputs: byte proof, never live source acquisition."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..migration.plan_values import b64, unb64, file_bindings
from ..model.errors import ModelError
from ..snapshots import SourceSnapshot
from ..snapshots.inventory import source_resource_rows


def require(ok, reason):
    if not ok:
        raise ModelError(reason)


@dataclass(frozen=True)
class RecordedSource:
    _binding: bytes
    _files: tuple

    @property
    def binding(self): return parsed(self._binding)
    @property
    def files(self): return dict(self._files)
    @property
    def kind(self): return self.binding['kind']
    @property
    def source_root(self): return self.binding['source_root']
    @property
    def commit_id(self): return self.binding['commit_id']
    @property
    def project_id(self): return self.binding['project_id']
    @property
    def schema_version(self): return self.binding['schema_version']
    def verify_owned(self):
        source_resource_rows(self)


@dataclass(frozen=True)
class RecordedMergeSources:
    base: RecordedSource
    ours: RecordedSource
    theirs: RecordedSource
    @property
    def binding(self): return {r: getattr(self, r).binding for r in ('base', 'ours', 'theirs')}
    @property
    def sha256(self): return digest(self.binding)


def verify_observation(source):
    if type(source) is SourceSnapshot:
        source.verify_current()
    elif type(source) is RecordedSource:
        source.verify_owned()
    else:
        raise ModelError('merge_source_snapshot_required')


def sources_type(value):
    from .sources import MergeSources
    return type(value) in (MergeSources, RecordedMergeSources)


def recorded_sources(values):
    require(type(values) is dict and set(values) == {'base', 'ours', 'theirs'}, 'merge_recorded_sources_required')
    result = []
    for role in ('base', 'ours', 'theirs'):
        row = values[role]
        require(type(row) is dict and set(row) == {'binding', 'files'}, 'merge_recorded_source_schema')
        binding, rows = row['binding'], row['files']
        require(type(binding) is dict and type(rows) is list, 'merge_recorded_source_schema')
        fields = {'kind', 'source_root', 'commit_id', 'project_id', 'schema_version', 'scope_descriptor',
            'model_root_sha256', 'resources', 'atomic_snapshot', 'full_semantic_validation', 'approval_granted', 'write_authorized'}
        kind = binding.get('kind')
        require(kind in ('local', 'git', 'baseline', 'bundle') and set(binding) ==
            fields | ({kind} if kind in ('baseline', 'bundle') else set()), 'merge_recorded_binding_schema')
        require(all(binding.get(k) is False for k in ('atomic_snapshot', 'full_semantic_validation',
            'approval_granted', 'write_authorized')), 'merge_recorded_authority_claim')
        require(all(type(r) is dict and set(r) == {'path', 'bytes_base64'} for r in rows), 'merge_recorded_file_schema')
        names = [r['path'] for r in rows]
        require(all(type(n) is str for n in names) and names == sorted(set(names)), 'merge_recorded_file_order')
        from ..storage.archive import validate_portable_archive_paths
        validate_portable_archive_paths(names)
        files = tuple((r['path'], unb64(r['bytes_base64'])) for r in rows)
        require(file_bindings(dict(files)) == binding['resources'], 'merge_recorded_file_binding')
        source = RecordedSource(jcs(binding), files)
        source.verify_owned(); result.append(source)
    require(len({r.project_id for r in result}) == 1 and len({r.schema_version for r in result}) == 1,
            'merge_recorded_project_binding')
    return RecordedMergeSources(*result)


def capture_sources(sources):
    from .sources import MergeSources
    require(type(sources) is MergeSources, 'merge_live_sources_required')
    return {role: {'binding': getattr(sources, role).binding,
        'files': [{'path': p, 'bytes_base64': b64(raw)} for p, raw in sorted(getattr(sources, role).files.items())]}
        for role in ('base', 'ours', 'theirs')}
