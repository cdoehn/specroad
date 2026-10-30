"""Fold owned immutable history; never use current mutable files as source."""
from hashlib import sha256

from ..model.attachments import AttachmentDescriptor
from ..model.errors import ModelError
from ..model.paths import PathClass, artifact_path, classify_path
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from ._codec import file_row
from ._sources import baseline_objects
from ._schema_boundary import declared_files
from .values import require


def protected_record(value):
    return (value['artifact_type'] in ('baseline', 'evidence', 'relation_review') or
            value['artifact_type'] == 'proposal' and
            value['proposal_status'] in ('rejected', 'applied', 'stale'))


def history_target(files, additions, current, configuration):
    """Fold actual protected history into an explicit target and preservation rows.

    Sealed Baselines, Evidence, RelationReviews and terminal Proposals retain
    their original bytes and complete dependencies. Their current native
    qualification is separate. No mutable source data is guessed here.
    """
    fold = _HistoryFold(files, additions, current, configuration)
    fold.retain_current()
    declared_files(current, include_payloads=False)
    fold.close_baselines()
    fold.retain_archives()
    fold.retain_attachments(fold.attachment_bindings())
    declared_files(fold.target)
    return fold.target, fold.preservation_rows()


class _HistoryFold:
    """Own one in-memory target while resolving its immutable original bytes."""

    def __init__(self, files, additions, current, configuration):
        self.files = files
        self.additions = {p: (raw, list(reasons)) for p, (raw, reasons) in additions.items()}
        self.target = {**files, **{p: raw for p, (raw, _) in self.additions.items()}}
        self.current = current
        self.configuration = configuration
        self.records = {}
        self.pending = []
        self.archived_payloads = {}

    def _add(self, path, raw, reason):
        require(path not in self.target or self.target[path] == raw,
                'restore_protected_history_conflict', path=path, exit_code=6)
        self.target[path] = raw
        if path not in self.files:
            reasons = self.additions.get(path, (raw, []))[1]
            self.additions[path] = (raw, sorted(set([*reasons, reason])))

    def _read(self, path):
        if path in self.current or path in self.target:
            return self.current[path] if path in self.current else self.target[path]
        require(False, 'restore_protected_dependency_missing', path=path)

    def _retain(self, raw, path):
        record = RecordArtifact(raw, path=path)
        value = record.data
        require(artifact_path(record.artifact_type, record.id, self.configuration.id_prefix) == path,
                'restore_current_identity_conflict', path=path, exit_code=6)
        self._add(path, raw, 'protected_history')
        if path in self.records:
            return
        self.records[path] = record
        self.pending.append((path, raw))

    def retain_current(self):
        # Register identities first: missing dependencies cannot hide a known
        # immutable identity conflict or make it depend on filename traversal.
        for path, raw in sorted(self.current.items()):
            if classify_path(path, self.configuration) is not PathClass.ARTIFACT:
                continue
            try:
                record = RecordArtifact(raw, path=path)
            except ModelError:
                continue  # Damaged bytes are still inventoried and backed up.
            if protected_record(record.data):
                self._retain(raw, path)

    def close_baselines(self):
        # Retaining nested Baselines extends pending while it is traversed.
        # Keep all original attachment versions until exact bindings select
        # the Evidence dependencies after the complete graph is closed.
        for path, raw in self.pending:
            record = self.records[path]
            value = record.data
            if record.artifact_type == 'baseline':
                originals = baseline_objects(raw, self._read)
                for object_path, content in originals.items():
                    self._add(object_path, content, 'protected_dependency')
                for row in value['manifest']:
                    if row['role'] == 'attachment':
                        self.archived_payloads.setdefault(row['source_path'], []).append(originals[row['object_path']])
                for row in value['manifest']:
                    if row['role'] != 'artifact':
                        continue
                    content = originals[row['object_path']]
                    archived = parse_json_object(content)
                    if protected_record(archived):
                        self._retain(content, artifact_path(archived['artifact_type'], archived['id'], self.configuration.id_prefix))

    def retain_archives(self):
        # An unreferenced original is still protected history, not expendable
        # scratch. Verify its native content address before preserving it.
        from ..archive.objects import SnapshotObject
        for path, raw in sorted(self.current.items()):
            if classify_path(path, self.configuration) is PathClass.ARCHIVE_OBJECT:
                require(SnapshotObject(raw).reference.path == path,
                        'restore_archive_object_mismatch', path=path)
                self._add(path, raw, 'protected_dependency')

    def attachment_bindings(self):
        # Source Evidence participates too. Incompatible protected bindings
        # conflict even when neither payload exists in the damaged tree.
        required = {}
        for path, raw in sorted(self.target.items()):
            if classify_path(path, self.configuration) is not PathClass.ARTIFACT:
                continue
            try:
                record = RecordArtifact(raw, path=path)
            except ModelError:
                continue
            if not protected_record(record.data):
                continue
            for entry in record.data.get('attachments', []):
                descriptor = AttachmentDescriptor.from_data(entry)
                require(classify_path(descriptor.path, self.configuration) is PathClass.ATTACHMENT,
                        'restore_protected_attachment_path_invalid', path=descriptor.path)
                binding = (descriptor.size, descriptor.sha256)
                require(descriptor.path not in required or required[descriptor.path] == binding,
                        'restore_protected_dependency_conflict', path=descriptor.path, exit_code=6)
                required[descriptor.path] = binding
        return required

    def retain_attachments(self, required):
        for path, (size, digest) in sorted(required.items()):
            if path in self.target:
                require((len(self.target[path]), sha256(self.target[path]).hexdigest()) == (size, digest),
                        'restore_protected_dependency_conflict', path=path, exit_code=6)
            if path in self.current or path in self.target:
                content = self._read(path)
            else:
                candidates = [raw for raw in self.archived_payloads.get(path, ())
                              if (len(raw), sha256(raw).hexdigest()) == (size, digest)]
                require(candidates, 'restore_protected_dependency_missing', path=path)
                require(all(raw == candidates[0] for raw in candidates),
                        'restore_protected_history_conflict', path=path, exit_code=6)
                content = candidates[0]
            require((len(content), sha256(content).hexdigest()) == (size, digest),
                    'restore_protected_attachment_bytes_mismatch', path=path)
            self._add(path, content, 'protected_dependency')

    def preservation_rows(self):
        return [{**file_row(p, raw), 'reasons': reasons}
                for p, (raw, reasons) in sorted(self.additions.items(), key=lambda item: item[0].encode('utf-8'))]
