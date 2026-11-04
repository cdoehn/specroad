"""Original bytes and manifest entries; no identity-allocation algorithm."""
from .reference01.values import CONTRACT_ID, CONTRACT_VERSION, READER_ID
from .plan_values import require, SOURCE_CONTRACT
# Preserve the internal helper import seam used by bound migration callers.
from .relation_derivation import _relation, _SourceRelations


def _original_archive(inventory, source, target_contract_value, source_relations):
    """Keep source originals separate from every derived navigation value."""
    originals = inventory.originals; current_root = inventory.model_root_sha256
    by_snapshot = {(o.snapshot_root, o.path): o for o in originals}
    archive = dict(inventory.payloads); entries, identities = [], {}
    for original in originals:
        raw = original.source_bytes; address = 'archive/objects/' + original.byte_sha256[:2] + '/' + original.byte_sha256
        require(address not in source or source[address] == raw, 'migration_archive_collision', path=address)
        require(address not in archive or archive[address] == raw, 'migration_archive_collision', path=address)
        archive[address] = raw
        value = original.data if original.role != 'attachment' else {}
        artifact = original.role == 'artifact'
        if artifact:
            key = (value['id'], value['revision'])
            require(key not in identities or identities[key] == raw, 'migration_original_revision_conflict')
            identities[key] = raw
        relation_rows = source_relations.projections(original) if artifact else []
        payloads = {}
        if value.get('artifact_type') == 'baseline':
            for row in value['manifest']:
                path = 'archive/objects/' + row['byte_sha256'][:2] + '/' + row['byte_sha256']
                payloads[path] = {'path': path, 'size': row['size'], 'sha256': row['byte_sha256']}
        for row in value.get('attachments', []):
            payloads[row['path']] = {k: row[k] for k in ('path', 'size', 'sha256')}
        if value.get('artifact_type') == 'code_ref':
            item = by_snapshot.get((original.snapshot_root, value['path']))
            require(item is not None, 'migration_original_payload_missing')
            payloads[value['path']] = {'path': value['path'], 'size': len(item.source_bytes), 'sha256': item.byte_sha256}
        if artifact:
            from .reference01.semantics import prose_payloads
            for path in prose_payloads(value, original.path):
                item = by_snapshot.get((original.snapshot_root, path))
                require(item is not None, 'migration_original_payload_missing')
                payloads[path] = {'path': path, 'size': len(item.source_bytes), 'sha256': item.byte_sha256}
        physical = [address]
        if (original.snapshot_root == current_root and original.classification != 'mutable'
                and source.get(original.path) == raw):
            physical.append(original.path)
        for path in sorted(set(physical)):
            entries.append({'path': path, 'logical_path': original.path, 'role': original.role,
                'artifact_id': value.get('id') if artifact else None,
                'artifact_type': value.get('artifact_type') if artifact else None,
                'source_schema_version': '0.1.0', 'original_size': len(raw),
                'original_byte_sha256': original.byte_sha256,
                'original_canonical_sha256': original.canonical_sha256,
                'source_model_root_sha256': original.snapshot_root,
                'original_revision': value.get('revision') if artifact else None,
                'legacy_reader_id': READER_ID,
                'identity_projection': {'id_scheme': 'legacy-sequential-v1'} if artifact else None,
                'relation_projections': relation_rows, 'referenced_payloads': [payloads[p] for p in sorted(payloads)],
                'migration_provenance': {'contract_id': CONTRACT_ID, 'contract_version': CONTRACT_VERSION,
                    'contract_sha256': SOURCE_CONTRACT['contract_sha256'], 'source_snapshot_root': original.snapshot_root}})
    unique = {}
    for row in entries:
        key = (row['path'], row['source_model_root_sha256'], row['logical_path'])
        require(key not in unique or unique[key] == row, 'migration_manifest_conflict')
        unique[key] = row
    manifest = {'schema_version': '0.2.0', 'mapping_id': 'legacy-preservation', 'mapping_version': '1.0.0',
        'legacy_manifest_version': '1.0.0',
        'source': {'project_id': inventory.data['project_id'], **SOURCE_CONTRACT,
                   'contract_id': CONTRACT_ID, 'contract_version': CONTRACT_VERSION},
        'target': {'project_id': inventory.data['project_id'], **target_contract_value},
        'entries': [unique[k] for k in sorted(unique)], 'proposal_transitions': []}
    return archive, manifest, source_relations
