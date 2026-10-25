"""E.3.2 endpoint observations, separate from the native member inventory."""
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_sha256
from ..model.domain_schemas import DOMAIN_TYPES, validate_domain_fields
from ..model.record_schemas import validate_record_fields
from ..model.paths import artifact_path
from .manifest import require

PREFIX = 'bundle-context/'


def proof_path(identity):
    # Callers supply native-validated identities, never arbitrary path inputs.
    return PREFIX + 'boundary-targets/' + identity + '.json'


def required_targets(boundaries, artifacts):
    reviewed = {a['relation_id'] for a in artifacts if a['artifact_type'] == 'relation_review'}
    selected = {b['target_id'] for b in boundaries if b['relation_id'] in reviewed}
    result = {}
    for boundary in boundaries:
        key = boundary['target_id']
        if key not in selected:
            continue
        previous = result.get(key)
        require(previous is None or all(previous[k] == boundary[k]
                for k in ('target_type', 'origin_target_sha256')), 'bundle_boundary_target_conflict', code='SRV060')
        result[key] = boundary
    return result


def read_boundary_context(container, model):
    files, manifest = container.files, container.manifest
    artifacts = [SourceRelations(d.content, path=d.path).data for d in model.documents]
    targets = required_targets(manifest['boundary_references'], artifacts)
    require({p for p in files if p == PREFIX[:-1] or p.startswith(PREFIX)}
            == {proof_path(key) for key in targets}, 'bundle_boundary_context_inventory')
    excluded = {row['path'] for row in manifest['excluded_contents']}
    records = {}
    for identity, boundary in targets.items():
        raw = files[proof_path(identity)]
        record = SourceRelations(raw)
        value = record.data
        (validate_domain_fields if value['artifact_type'] in DOMAIN_TYPES else validate_record_fields)(value)
        require(record.identity.id == identity and record.identity.artifact_type == boundary['target_type'],
                'bundle_boundary_context_identity')
        native_path = artifact_path(record.identity.artifact_type, identity, model.configuration.id_prefix)
        require(native_path not in excluded, 'bundle_boundary_context_excluded')
        require(native_path not in files or files[native_path] == raw, 'bundle_boundary_context_roles')
        require(canonical_json_sha256(value) == boundary['origin_target_sha256'],
                'bundle_boundary_context_hash', code='SRV060')
        records[identity] = record
    return records
