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

    The provider supports sealed Baselines and recorded Evidence. Other
    protected kinds still encounter the existing fail-closed history checks.
    Dependencies may reuse identical source bytes, never guessed mutable data.
    """
    additions = {p: (raw, list(reasons)) for p, (raw, reasons) in additions.items()}
    target = {**files, **{p: raw for p, (raw, _) in additions.items()}}
    records = {}
    pending = []
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
        require(False, 'restore_protected_dependency_missing', path=path)

    def retain(raw, path):
        record = RecordArtifact(raw, path=path)
        value = record.data
        require(value['id_scheme'] == 'random128-v1', 'restore_legacy_provider_required', path=path)
        require(artifact_path(record.artifact_type, record.id, configuration.id_prefix) == path,
                'restore_current_identity_conflict', path=path, exit_code=6)
        add(path, raw, 'protected_history')
        if path in records:
            return
        records[path] = record
        pending.append((path, raw))

    # Register every readable immutable identity before looking for dependency
    # bytes. A known identity conflict must not depend on filename traversal or
    # be hidden by a missing attachment of the first record encountered.
    for path, raw in sorted(current.items()):
        if classify_path(path, configuration) is not PathClass.ARTIFACT:
            continue
        try:
            record = RecordArtifact(raw, path=path)
        except ModelError:
            continue  # Damaged bytes are still inventoried and backed up.
        if record.artifact_type in ('baseline', 'evidence'):
            retain(raw, path)

    # Close the Baseline graph before resolving Evidence dependencies. Original
    # attachments from unrelated snapshots may share a path while representing
    # different bytes; only an exact declared binding can select one of them.
    for path, raw in pending:
        record = records[path]
        value = record.data
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

    # Include source Evidence as well as the retained records. Two protected
    # records cannot demand different contents at one target path, even when
    # neither of those contents happens to be available in the damaged tree.
    required = {}
    for path, raw in sorted(target.items()):
        if classify_path(path, configuration) is not PathClass.ARTIFACT:
            continue
        try:
            record = RecordArtifact(raw, path=path)
        except ModelError:
            continue
        if record.artifact_type != 'evidence':
            continue
        for entry in record.data.get('attachments', []):
            descriptor = AttachmentDescriptor.from_data(entry)
            require(classify_path(descriptor.path, configuration) is PathClass.ATTACHMENT,
                    'restore_protected_attachment_path_invalid', path=descriptor.path)
            binding = (descriptor.size, descriptor.sha256)
            require(descriptor.path not in required or required[descriptor.path] == binding,
                    'restore_protected_dependency_conflict', path=descriptor.path, exit_code=6)
            required[descriptor.path] = binding
    for path, (size, digest) in sorted(required.items()):
        if path in target:
            require((len(target[path]), sha256(target[path]).hexdigest()) == (size, digest),
                    'restore_protected_dependency_conflict', path=path, exit_code=6)
        if path in current or path in target:
            content = read(path)
        else:
            candidates = [raw for raw in archived_payloads.get(path, ())
                          if (len(raw), sha256(raw).hexdigest()) == (size, digest)]
            require(candidates, 'restore_protected_dependency_missing', path=path)
            require(all(raw == candidates[0] for raw in candidates),
                    'restore_protected_history_conflict', path=path, exit_code=6)
            content = candidates[0]
        require((len(content), sha256(content).hexdigest()) == (size, digest),
                'restore_protected_attachment_bytes_mismatch', path=path)
        add(path, content, 'protected_dependency')
    return additions
