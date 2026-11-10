"""Owned historical values; no acquisition, writer or authorization."""
from dataclasses import dataclass
from ..model.canonical import canonical_json_sha256 as digest
from ..storage.json_syntax import parse_json_object as parsed
from ..snapshots.inventory import source_resource_rows


def _immutable_key(binding, files):
    return not (type(binding) is not bytes or type(files) is not tuple
                or any(type(row) is not tuple or len(row) != 2
                       or type(row[0]) is not str or type(row[1]) is not bytes
                       for row in files))


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
        binding, files = self._binding, self._files
        # Only exact owned byte tuples qualify. Preserve the existing checks
        # and their errors for unusual or tampered value representations.
        if not _immutable_key(binding, files):
            source_resource_rows(self)
            return
        from ..recovery._owned_checks import checked_bytes

        def check():
            source_resource_rows(RecordedSource(binding, files))
            # Cache only a successful pure proof, never its mutable outputs.

        checked_bytes('merge-recorded-source-v1', (binding, files), check)


@dataclass(frozen=True)
class RecordedMergeSources:
    base: RecordedSource
    ours: RecordedSource
    theirs: RecordedSource
    @property
    def binding(self): return {r: getattr(self, r).binding for r in ('base', 'ours', 'theirs')}
    @property
    def sha256(self): return digest(self.binding)
