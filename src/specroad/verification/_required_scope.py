"""Revalidate independent scope inputs against the supplied model's bytes.

Resource-use and current-review observations remain explicit provider inputs;
no empty provider, query page or closure is invented from an evaluation.
"""
from collections import Counter

from ..graph.closure_inputs import ClosureBindings
from ..graph.relations import SourceRelations
from ..graph.scope_closure import resolve_scope_closure
from ..graph.scope_descriptors import ScopeDescriptor
from ..graph.scope_inputs import ScopeResource, ScopeSeedInputs
from ..graph.scope_query_page import QuerySeedPage
from ..graph.scope_seeds import resolve_scope_seeds
from ..model.attachments import AttachmentDescriptor
from ..model.errors import ModelError


def resolve_required_scope(model, records, descriptor, bindings, configuration_id):
    """Recompute seeds and closure without receiving any evaluation descriptor."""
    if type(descriptor) is not ScopeDescriptor:
        raise ModelError('verification_scope_descriptor_required')
    descriptor = ScopeDescriptor(descriptor.data)
    if descriptor.data['configuration_id'] != configuration_id:
        raise ModelError('verification_scope_configuration_mismatch')
    if type(bindings) is not ClosureBindings or type(bindings.inventory) is not ScopeSeedInputs:
        raise ModelError('verification_scope_bindings_required')
    inventory = bindings.inventory
    source_files = {}
    for source in inventory.records:
        if type(source) is not SourceRelations:
            raise ModelError('verification_scope_source_required')
        fresh = SourceRelations(source.source_bytes, path=source.path)
        if fresh != source or source.path in source_files:
            raise ModelError('verification_scope_source_binding_mismatch')
        source_files[source.path] = source.source_bytes
    if source_files != {record.path: record.source_bytes for record in records}:
        raise ModelError('verification_scope_inventory_mismatch')
    resources = []
    for resource in inventory.resources:
        if type(resource) is not ScopeResource:
            raise ModelError('verification_scope_resource_required')
        resources.append(ScopeResource(**resource.data))
    # Opaque provider resource IDs need not equal paths or semantic IDs, but
    # every resource must correspond to the actual complete model inventory.
    declared = Counter((r.kind, r.version, r.sha256) for r in resources)
    actual = Counter((r.data['kind'], r.data.get('version') if r.data['kind'] in
                      ('profile', 'rule', 'mapping') else None, r.data['sha256'])
                     for r in model.resources)
    if declared != actual:
        raise ModelError('verification_scope_resource_binding_mismatch')
    owned = ScopeSeedInputs(model.configuration, records, resources,
                            archive_bindings=dict(inventory.archive_bindings))
    if owned.fingerprint != inventory.fingerprint:
        raise ModelError('verification_scope_inventory_binding_mismatch')
    attachments = {}
    actual_attachments = {item.path: item for item in model.attachment_descriptors}
    for name, item in bindings.attachments.items():
        if type(item) is not AttachmentDescriptor:
            raise ModelError('verification_scope_attachment_required')
        fresh = AttachmentDescriptor.from_data(item.data)
        if actual_attachments.get(fresh.path) != fresh:
            raise ModelError('verification_scope_attachment_binding_mismatch')
        attachments[name] = fresh
    dependencies = ClosureBindings(owned, uses=dict(bindings.uses),
        current_reviews=dict(bindings.current_reviews), attachments=attachments)
    if dependencies.fingerprint != bindings.fingerprint:
        raise ModelError('verification_scope_dependency_binding_mismatch')
    value = descriptor.data
    base = value['selector']['base_scope_descriptor'] if value['scope_kind'] == 'configuration' else value
    page = None
    if base['scope_kind'] == 'query':
        from ..query.selection import NormalizedQuery
        from ..query.paging import query_records
        query = base['selector']['query']
        if query['evaluation'] is not None:
            raise ModelError('verification_scope_evaluation_not_independent',
                             pointer='/selector/query/evaluation')
        # Re-evaluate the actual query, never accept an asserted page of IDs.
        result = query_records(records, NormalizedQuery.from_data(query),
                               project=model.configuration.data, configuration_id=configuration_id)
        page = QuerySeedPage(descriptor, owned, [item['id'] for item in result.data['items']],
                             total=result.data['total'])
    seeds = resolve_scope_seeds(descriptor, owned, query_page=page)
    return resolve_scope_closure(seeds, dependencies, query_page=page)
