"""Partial native reconstruction using the same seed, review and closure rules.

Only the supplied bytes are observed. Outside proof records are endpoints,
never members, seeds, review history or transitive resource providers.
"""
from ..exchange._export_scope import (_scope_resources, _archive_bindings, _resource_uses,
    _artifact_uses, _native_manifest)
from ..graph.relations import SourceRelations
from ..graph._review_status_selection import _status
from ..graph.closure_inputs import ClosureBindings
from ..graph.scope_inputs import ScopeSeedInputs
from ..graph.scope_descriptors import ScopeDescriptor
from ..graph.scope_seeds import resolve_scope_seeds
from ..graph.scope_closure import verify_partial_scope_closure
from ..model.errors import ModelError
from ._payload_model import payload_model
from .boundary_context import PREFIX, read_boundary_context, required_targets
from .partial import _configuration_context, _selected_payloads
from .manifest import require


def _review_bindings(records, proof, boundaries):
    index = {r.identity.id: r for r in records}
    history = {}
    for record in records:
        if record.identity.artifact_type == 'relation_review':
            history.setdefault(record.data['relation_id'], []).append(record.data)
    boundary_ids = {b['relation_id'] for b in boundaries}
    result = {}
    for record in records:
        for relation in record.relations:
            endpoints = index
            if relation.identity.id in boundary_ids and relation.target in proof:
                endpoints = {**index, relation.target: proof[relation.target]}
            observation = _status(record, relation, endpoints, history.get(relation.identity.id, ()))
            result[relation.identity.id] = observation.matching_review_ids
    return result


def _closure_inputs(model, descriptor, records, proof, boundaries, context_paths):
    """Bind observed resources and reviews without expanding proof endpoints."""
    by_resource, resources = _scope_resources(model)
    inventory = ScopeSeedInputs(model.configuration, records, resources,
        archive_bindings=_archive_bindings(model, records), partial_descriptor=descriptor)
    uses, registries = _resource_uses(model, by_resource)
    active = {r.resource_id for r in resources if r.active}
    attachments = {a.path: a for a in model.attachment_descriptors}
    for record in records:
        try:
            uses.update(_artifact_uses((record,), active, attachments, registries, by_resource))
        except ModelError:
            if record.path not in context_paths:
                raise
            # An unresolved resource of context-only configuration is outside
            # this scope. If reached, the walker rejects its missing provider.
    bindings = ClosureBindings(inventory, uses={key: tuple(value) for key, value in uses.items()},
        current_reviews=_review_bindings(records, proof, boundaries),
        attachments=attachments)
    return inventory, bindings, by_resource


def _check_payload_inventory(container, model, closure, native, artifacts, proof, context_paths):
    """Require precisely the native members and their separate context roles."""
    require(set(proof) == set(required_targets(native.data['boundary_references'], artifacts)),
            'bundle_boundary_context_membership')
    files = {p: raw for p, raw in container.files.items() if not p.startswith(PREFIX)}
    expected = _selected_payloads(model, files, closure, artifacts, context_paths)
    require(set(files) == set(expected), 'bundle_partial_payload_inventory')


def verify_partial_model(container):
    model = payload_model(container, partial=True)
    manifest = container.manifest
    descriptor = ScopeDescriptor(manifest['scope_descriptor'])
    context_paths, configuration_hash = _configuration_context(model, descriptor.data)
    records = tuple(SourceRelations(d.content, path=d.path) for d in model.documents)
    proof = read_boundary_context(container, model)
    inventory, bindings, by_resource = _closure_inputs(
        model, descriptor, records, proof, manifest['boundary_references'], context_paths)
    seeds = resolve_scope_seeds(descriptor, inventory)
    closure = verify_partial_scope_closure(seeds, bindings, manifest['boundary_references'])
    native, artifacts = _native_manifest(model, descriptor, inventory, seeds, closure, records, by_resource)
    _check_payload_inventory(container, model, closure, native, artifacts, proof, context_paths)
    if configuration_hash is not None:
        require(configuration_hash == native.data['configuration_sha256'],
                'bundle_partial_configuration_binding', code='SRV060')
    for key, actual in (('bundle_model_root_sha256', native.sha256),
            ('configuration_sha256', native.data['configuration_sha256']),
            ('profile_sha256', native.data['profile_sha256'])):
        require(manifest[key] == actual, 'bundle_model_binding_mismatch', code='SRV060')
    # origin_model_root_sha256 is provenance only; partial bytes cannot prove it.
    return native
