"""Fold owned immutable history; never use current mutable files as source."""
from hashlib import sha256

from ..model.attachments import AttachmentDescriptor
from ..model.errors import ModelError
from ..model.paths import PathClass, artifact_path, classify_path
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from ._sources import baseline_objects
from .values import require


def preserve_history(files, additions, current, configuration):
    """Return explicit additions from actual current bytes and native archives.

    The W provider supports sealed Baselines and recorded Evidence. Other
    protected kinds still encounter the existing fail-closed history checks.
    Dependencies may reuse identical source bytes, never guessed mutable data.
    """
    additions = {p: (raw, list(reasons)) for p, (raw, reasons) in additions.items()}
    target = {**files, **{p: raw for p, (raw, _) in additions.items()}}
    visited = set()
    archived_payloads = {}

    def add(path, raw, reason):
        require(path not in target or target[path] == raw,
                'restore_protected_history_conflict', path=path, exit_code=6)
        target[path] = raw
        if path not in files:
            reasons = additions.get(path, (raw, []))[1]
            additions[path] = (raw, sorted(set([*reasons, reason])))

    def read(path):
        if path in current or path in target:
            return current[path] if path in current else target[path]
        candidates = archived_payloads.get(path, ())
        require(candidates, 'restore_protected_dependency_missing', path=path)
        require(all(raw == candidates[0] for raw in candidates),
                'restore_protected_history_conflict', path=path, exit_code=6)
        return candidates[0]

    def retain(raw, path):
        record = RecordArtifact(raw, path=path)
        value = record.data
        require(value['id_scheme'] == 'random128-v1', 'restore_legacy_provider_required', path=path)
        require(artifact_path(record.artifact_type, record.id, configuration.id_prefix) == path,
                'restore_current_identity_conflict', path=path, exit_code=6)
        add(path, raw, 'protected_history')
        if path in visited:
            return
        visited.add(path)
        if record.artifact_type == 'baseline':
            originals = baseline_objects(raw, read)
            for object_path, content in originals.items():
                add(object_path, content, 'protected_dependency')
            for row in value['manifest']:
                if row['role'] == 'attachment':
                    archived_payloads.setdefault(row['source_path'], []).append(originals[row['object_path']])
            for row in value['manifest']:
                if row['role'] != 'artifact':
                    continue
                content = originals[row['object_path']]
                archived = parse_json_object(content)
                if archived['artifact_type'] in ('baseline', 'evidence'):
                    retain(content, artifact_path(archived['artifact_type'], archived['id'], configuration.id_prefix))
        else:
            for entry in value.get('attachments', []):
                descriptor = AttachmentDescriptor.from_data(entry)
                require(classify_path(descriptor.path, configuration) is PathClass.ATTACHMENT,
                        'restore_protected_attachment_path_invalid', path=descriptor.path)
                content = read(descriptor.path)
                require(len(content) == descriptor.size and sha256(content).hexdigest() == descriptor.sha256,
                        'restore_protected_attachment_bytes_mismatch', path=descriptor.path)
                add(descriptor.path, content, 'protected_dependency')

    for path, raw in sorted(current.items()):
        if classify_path(path, configuration) is not PathClass.ARTIFACT:
            continue
        try:
            record = RecordArtifact(raw, path=path)
        except ModelError:
            continue  # Damaged bytes are still inventoried and backed up.
        if record.artifact_type in ('baseline', 'evidence'):
            retain(raw, path)
    return additions
