"""Scope seed selection before closure. No file access, write or query engine."""
from dataclasses import dataclass
import re

from ..model.errors import ModelError
from .scope_descriptors import ScopeDescriptor
from ._scope_selector_contract import _artifact_id, _text
from .scope_inputs import ScopeSeedInputs
from .scope_query_page import QuerySeedPage
from .scope_admission import CONTROL_ARTIFACT_TYPES


@dataclass(frozen=True)
class ScopeSeeds:
    descriptor: ScopeDescriptor
    inputs_sha256: str
    artifact_ids: tuple
    resource_ids: tuple
    configuration_sha256: str | None

    def __post_init__(self):
        if type(self.descriptor) is not ScopeDescriptor:
            raise ModelError('scope_descriptor_required')
        for name, digest in (('inputs', self.inputs_sha256), ('configuration', self.configuration_sha256)):
            if name == 'configuration' and digest is None:
                continue
            if type(digest) is not str or re.fullmatch('[0-9a-f]{64}', digest) is None:
                raise ModelError('invalid_scope_seed_binding')
        for names, is_artifact in ((self.artifact_ids, True), (self.resource_ids, False)):
            if type(names) is not tuple:
                raise ModelError('scope_seed_tuple_required')
            for name in names:
                (_artifact_id if is_artifact else _text)(name)
            if len(set(names)) != len(names):
                raise ModelError('duplicate_scope_seed')
            if (not is_artifact or self.descriptor.scope_kind != 'query') and names != tuple(sorted(names, key=lambda name: name.encode('utf-8'))):
                raise ModelError('noncanonical_scope_seeds')

    @property
    def validation_scope(self):
        return 'seed_selection_only'

    @property
    def closure_complete(self):
        return False

    @property
    def canonical_artifact_ids(self):
        """Membership order for later closure; query page order remains intact."""
        return tuple(sorted(self.artifact_ids, key=lambda value: value.encode('utf-8')))


def _release_seeds(release_id, inputs):
    milestones = {edge.source.id for edge in inputs.references.relations
                  if edge.relation.type == 'part_of' and edge.source.artifact_type == 'milestone'
                  and edge.target.id == release_id}
    targets = milestones | {release_id}
    selected = set(targets)
    for edge in inputs.references.relations:
        if edge.target.id in targets and (edge.relation.type == 'scheduled_for'
                or (edge.relation.type == 'part_of' and edge.source.artifact_type == 'task')):
            selected.add(edge.source.id)
    return selected


def resolve_scope_seeds(descriptor, inputs, *, query_page=None):
    """Resolve seeds only from the supplied current inventory; never expand edges.

    Project/specification resource completeness is a caller precondition, not an
    outcome certified by this function. Configured scopes fail closed until the
    effective-configuration/applicability resolver is implemented in its step.
    """
    if type(descriptor) is not ScopeDescriptor or type(inputs) is not ScopeSeedInputs:
        raise ModelError('scope_values_required')
    data = descriptor.data
    by_id = {record.identity.id: record for record in inputs.records}
    config = data['configuration_id']
    if config is not None:
        if config not in by_id or by_id[config].identity.artifact_type != 'configuration':
            raise ModelError('scope_configuration_missing')
        raise ModelError('scope_configuration_resolver_required')
    kind, selector = data['scope_kind'], data['selector']
    if query_page is not None and kind != 'query':
        raise ModelError('unexpected_query_seed_page')
    resources = {resource.resource_id: resource for resource in inputs.resources}
    selected, selected_resources, config_hash = set(), set(), None
    if kind == 'specification':
        selected = {name for name, record in by_id.items() if record.identity.artifact_type not in CONTROL_ARTIFACT_TYPES}
        selected_resources = {name for name, resource in resources.items() if resource.active}
        config_hash = inputs.configuration_sha256
    elif kind == 'project':
        selected = set(by_id)
        selected_resources = {name for name, resource in resources.items() if resource.kind != 'archive'}
        for name, record in by_id.items():
            if record.identity.artifact_type == 'baseline':
                if name not in inputs.archive_bindings:
                    raise ModelError('scope_baseline_archive_inventory_required')
                selected_resources.update(inputs.archive_bindings[name])
        config_hash = inputs.configuration_sha256
    elif kind in ('release', 'document'):
        name = selector[kind + '_id']
        if name not in by_id or by_id[name].identity.artifact_type != kind:
            raise ModelError('scope_seed_missing')
        selected = _release_seeds(name, inputs) if kind == 'release' else {name}
    elif kind == 'explicit':
        selected, selected_resources = set(selector['artifact_ids']), set(selector['resource_ids'])
        if not selected <= by_id.keys() or not selected_resources <= resources.keys():
            raise ModelError('scope_seed_missing')
    elif kind == 'query':
        if type(query_page) is not QuerySeedPage:
            raise ModelError('bound_query_seed_page_required')
        if query_page.descriptor_sha256 != descriptor.sha256 or query_page.inputs_sha256 != inputs.fingerprint:
            raise ModelError('stale_query_seed_page')
        return ScopeSeeds(descriptor, inputs.fingerprint, query_page.artifact_ids, (), None)
    else:
        raise ModelError('unsupported_scope_seed_resolver')
    return ScopeSeeds(descriptor, inputs.fingerprint,
                      tuple(sorted(selected, key=lambda value: value.encode('utf-8'))),
                      tuple(sorted(selected_resources, key=lambda value: value.encode('utf-8'))), config_hash)
