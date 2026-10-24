"""Resolve an export from actual native resources, before format projection."""
from ..graph.closure_inputs import ClosureBindings, artifact_node, resource_node
from ..graph.relations import SourceRelations
from ..graph.review_status import RelationReviewStatuses
from ..graph.scope_closure import resolve_scope_closure
from ..graph.scope_inputs import ScopeResource, ScopeSeedInputs
from ..graph.scope_query_page import QuerySeedPage
from ..graph.scope_seeds import resolve_scope_seeds
from ..model.canonical import canonical_json_sha256
from ..model.errors import ModelError
from ..model.model_manifest import ManifestResource, ModelManifest
from ..model.manifest_projection import project_manifest_value


def resource_identity(record):
    value = record.data
    return value['path'] if 'path' in value else value['id'] + '@' + value['version']


def export_scope(model, descriptor):
    """Bind native selection and closure; never accept asserted inventories/hashes."""
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    by_resource = {resource_identity(r): r for r in model.resources}
    if len(by_resource) != len(model.resources):
        raise ModelError('export_resource_identity_conflict')
    resources = [ScopeResource(name, r.data['kind'], r.data['sha256'],
        r.data.get('version') if r.data['kind'] in ('profile', 'rule', 'mapping') else None,
        r.data['kind'] == 'profile' and name in model.profile.profile_chain)
        for name, r in by_resource.items()]
    archives = {}
    for record in records:
        if record.identity.artifact_type == 'baseline':
            from ..archive.verification import verify_baseline_objects
            from ..archive.objects import SnapshotObject
            verify_baseline_objects(record.source_bytes,
                tuple(SnapshotObject(d.content) for d in model.resource_files
                      if d.path.startswith('archive/objects/')))
            archives[record.identity.id] = tuple(sorted({r['object_path'] for r in record.data['manifest']}))
    inventory = ScopeSeedInputs(model.configuration, records, resources, archive_bindings=archives)
    active = {r.resource_id for r in resources if r.active}
    uses = {resource_node(name): set() for name in by_resource}
    from ..storage.json_syntax import parse_json_object
    from ..mappings import ExternalIdentityRegistry
    from ..model.paths import PathClass, classify_path
    registries = []
    for document in model.resource_files:
        if classify_path(document.path, model.configuration) is not PathClass.MAPPING:
            continue
        value = parse_json_object(document.content)
        if value.get('mapping_format_version') in ('external-identity-registry-v1', 'csv-profile-v1'):
            key = value['mapping_id'] + '@' + value['mapping_version']
            bound = value['mapping']
            target = bound['mapping_id'] + '@' + bound['mapping_version']
            if target not in by_resource or by_resource[target].data['sha256'] != bound['sha256']:
                raise ModelError('export_mapping_dependency_missing')
            uses[resource_node(key)].add(resource_node(target))
            if value['mapping_format_version'] == 'external-identity-registry-v1':
                registries.append(ExternalIdentityRegistry(document.content))
    # The composed profile actually applies to every native artifact. Its
    # complete bytes bind built-in rules as well as configured declarations.
    for resource in model.profile_resources:
        if resource.key not in by_resource:
            continue
        for name, entry in by_resource.items():
            if entry.data['kind'] == 'language_registry':
                uses[resource_node(resource.key)].add(resource_node(name))
        for rule in resource.data.get('lint_rules', []):
            key = rule.get('rule_id', '') + '@' + rule.get('version', '')
            if key in by_resource:
                uses[resource_node(resource.key)].add(resource_node(key))
    attachments = {d.path: d for d in model.attachment_descriptors}
    for record in records:
        data = record.data
        targets = {resource_node(key) for key in active}
        for attachment in data.get('attachments', []):
            path = attachment['path']
            if path not in attachments:
                raise ModelError('export_attachment_binding_missing')
            targets.add(resource_node(path))
        if data['artifact_type'] == 'content_block' and data['block_kind'] in ('prose', 'admonition'):
            from ..documents.blocks import ContentBlock
            from ..documents.prose import parse_prose
            pending = [parse_prose(ContentBlock(record.source_bytes)).data['content']]
            while pending:
                node = pending.pop()
                path = node.get('attachment_path')
                if path is not None:
                    if path not in attachments:
                        raise ModelError('export_attachment_binding_missing', path=record.path)
                    targets.add(resource_node(path))
                pending.extend(node.get('children', []))
        identities = list(data.get('external_identities', []))
        for relation in data['relations']:
            for identity in relation['external_identities']:
                identities.append(identity)
                kind = 'hierarchy' if relation['type'] == 'contains' else 'relation'
                for registry in registries:
                    if any(row['object_class'] == kind and all(row[k] == identity[k]
                            for k in ('source_system', 'source_document', 'external_id'))
                           for row in registry.data['entries']):
                        targets.add(resource_node(registry.key))
        for identity in identities:
            key = identity.get('mapping_id')
            if key is not None:
                if key not in by_resource or by_resource[key].data['kind'] != 'mapping':
                    raise ModelError('export_mapping_dependency_missing')
                targets.add(resource_node(key))
        uses[artifact_node(record.identity.id)] = targets
    reviews = RelationReviewStatuses(records)
    dependencies = ClosureBindings(inventory,
        uses={key: tuple(value) for key, value in uses.items()},
        current_reviews={r.relation_id: r.matching_review_ids for r in reviews.statuses},
        attachments=attachments)
    page = None
    value = descriptor.data
    if value['scope_kind'] == 'query':
        from ..query.selection import NormalizedQuery
        from ..query.paging import query_records
        query = NormalizedQuery.from_data(value['selector']['query'])
        result = query_records(records, query, project=model.configuration.data,
                               configuration_id=value['configuration_id'])
        page = QuerySeedPage(descriptor, inventory, [r['id'] for r in result.data['items']],
                             total=result.data['total'])
    seeds = resolve_scope_seeds(descriptor, inventory, query_page=page)
    closure = resolve_scope_closure(seeds, dependencies, query_page=page)
    selected = {r.identity.id: r for r in records if r.identity.id in closure.artifact_ids}
    manifest_resources = [by_resource[key] for key in closure.resource_ids]
    manifest_resources.extend(ManifestResource(model.binding, {'kind': 'artifact', 'id': key,
        'artifact_type': r.identity.artifact_type, 'revision': r.data['revision'],
        'sha256': canonical_json_sha256(r.data)}) for key, r in selected.items())
    rows = [r.data for r in manifest_resources]
    native = ModelManifest(project_manifest_value(model.configuration.project_id, descriptor.data,
        [r for r in rows if r['kind'] == 'artifact'],
        [r for r in rows if r['kind'] not in ('artifact', 'attachment', 'archive')],
        [r for r in rows if r['kind'] == 'attachment'],
        [r.data for r in closure.boundary_references],
        seeds.configuration_sha256 if value['configuration_id'] is not None else inventory.configuration_sha256,
        model.profile.sha256, archive_objects=[r for r in rows if r['kind'] == 'archive']))
    return closure, native, tuple(selected[key].data for key in closure.artifact_ids), by_resource
