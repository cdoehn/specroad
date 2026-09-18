"""Owned scope fixtures. No complete project, query evaluation or approval claim."""
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.graph.scope_inputs import ScopeSeedInputs
from specroad.model.configuration import ProjectConfiguration
from .artifacts import artifact_bytes
from .model import configuration_value


def descriptor(kind='specification', selector=None, **overrides):
    value = {'scope_version': 'scope-v1', 'scope_kind': kind, 'selector': {} if selector is None else selector,
             'configuration_id': None, 'closure_profile': 'core-closure-v1', 'boundary_policy': 'closed'}
    value.update(overrides)
    return value


def query(**overrides):
    value = {'filters': {}, 'srx_filters': [], 'select': [],
             'sort': [{'key': 'artifact_type', 'direction': 'asc'}, {'key': 'id', 'direction': 'asc'}],
             'evaluation': None, 'offset': 0, 'limit': 100}
    value.update(overrides)
    return value


def inputs(*values, resources=(), archive_bindings=None, configuration=None):
    return ScopeSeedInputs(ProjectConfiguration(configuration_value() if configuration is None else configuration),
                           [SourceRelations(artifact_bytes(value)) for value in values], resources,
                           archive_bindings=archive_bindings)
