"""Check complete project membership against the native effective byte inventory.

No PH layer is reconstructed here. Native model paths, referenced attachments,
archive objects and portable receipt contracts determine the projection.
"""
from ..archive.objects import ObjectReference
from ..bundles._receipts import receipt_path, completed_receipts, verify_imported_receipts
from ..bundles.manifest import check_entries, owned_metadata
from ..model.attachments import AttachmentDescriptor
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.paths import CURRENT_JSON_CLASSES, PathClass, classify_path
from ..model.operational_paths import PASSIVE_ROOTS, passive_journal_directory
from ..storage.json_syntax import parse_json_object
from ._files import require


def _under(path, parent):
    return path == parent or path.startswith(parent + '/')


def _operational(files):
    require(not any(_under(p, '.specroad-bootstrap') for p in files), 'handoff_unfinished_bootstrap', 7)
    for path in files:
        if not path.startswith('.specroad/'):
            continue
        if any(_under(path, root) and path != root for root in PASSIVE_ROOTS):
            continue
        parts = path.split('/')
        require(len(parts) >= 4 and parts[1] in ('transactions', 'recovery')
                and passive_journal_directory(parts[1], parts[2]), 'handoff_active_operational_state', 7)


def verify_projection(snapshot, container):
    prefix = container.manifest['project_path']
    prefix = '' if prefix == '.' else prefix + '/'
    files = {name[len(prefix):]: item.content for name, item in snapshot.effective.files.items()
             if name.startswith(prefix)}
    project = container.project
    require(files.get('specroad.json') == project.files['specroad.json'], 'handoff_project_configuration', 3)
    configuration = ProjectConfiguration(parse_json_object(files['specroad.json']))
    _operational(files)
    normative = {'specroad.json'}
    roots = [p for p in configuration.managed_paths if p.split('/')[0] in ('spec', 'profiles', 'rules', 'mappings')]
    for path in files:
        if not any(_under(path, root) for root in roots):
            continue
        # Match native directory discovery: non-JSON incidental files are not
        # resources; a configured individual input still must be normative.
        if not path.endswith('.json') and path not in roots:
            continue
        require(classify_path(path, configuration) in CURRENT_JSON_CLASSES,
                'handoff_unclassified_normative_resource', 3)
        parents = path.split('/')[:-1]
        require(not any('/'.join(parents[:n]) + '/specroad.json' in files
                        for n in range(1, len(parents) + 1)), 'handoff_foreign_project_root', 7)
        normative.add(path)
    for root in roots:
        if classify_path(root, configuration) in CURRENT_JSON_CLASSES:
            require(root in files or any(p.startswith(root + '/') for p in files),
                    'handoff_required_resource_missing', 3)
    registry = configuration.data.get('language_registry')
    if registry is not None:
        normative.add(registry['path'])
    archives = [p for p in configuration.managed_paths if p.split('/')[0] == 'archive']
    for path in files:
        if any(_under(path, root) for root in archives):
            require(classify_path(path, configuration) is PathClass.ARCHIVE_OBJECT,
                    'handoff_unclassified_archive_resource', 3)
    payloads = set()
    for path in sorted(normative):
        require(path in files, 'handoff_required_resource_missing', 3)
        if classify_path(path, configuration) is not PathClass.ARTIFACT:
            continue
        value = parse_json_object(files[path])
        for item in value.get('attachments', []):
            payloads.add(AttachmentDescriptor.from_data(item).path)
        if value.get('artifact_type') == 'baseline':
            for item in value.get('manifest', []):
                reference = ObjectReference(item.get('sha256'), item.get('size'))
                require(item.get('object_path') == reference.path, 'handoff_archive_reference', 3)
                payloads.add(reference.path)
    receipts = {p: b for p, b in files.items() if receipt_path(p)}
    completed_receipts(receipts, configuration.project_id)
    marker = files.get('bundle-manifest.json')
    proof = files.get('.specroad/recovery/bundle-bootstrap/journal.json')
    if proof is not None:
        record = parse_json_object(proof)
        from hashlib import sha256
        require(record.get('format') == 'specroad-bundle-bootstrap-v1' and marker is not None
            and record.get('state') == 'prepared', 'handoff_extracted_origin_invalid', 7)
        entries = record.get('entries')
        require(type(entries) is dict, 'handoff_extracted_origin_invalid', 7)
        entry = entries.get('bundle-manifest.json')
        require(type(entry) is dict, 'handoff_extracted_origin_invalid', 7)
        require(entry.get('size') == len(marker) and entry.get('sha256') == sha256(marker).hexdigest(),
                'handoff_extracted_origin_changed', 7)
    if marker is not None:
        previous = parse_json_object(marker)
        require(marker == canonical_json_bytes(previous), 'handoff_origin_noncanonical', 3)
        require('entries' in previous, 'handoff_origin_entries_missing', 3)
        check_entries(previous['entries'])
        previous_metadata = owned_metadata({k: v for k, v in previous.items() if k != 'entries'})
        require(previous_metadata['bundle_kind'] == 'project'
                and previous_metadata['project_id'] == configuration.project_id, 'handoff_partial_origin', 7)
    verify_imported_receipts(marker, receipts)
    required = normative | payloads | set(receipts)
    require(required <= files.keys(), 'handoff_required_payload_missing', 3)
    require(project.files == {p: files[p] for p in required}, 'handoff_effective_project_inventory', 3)
