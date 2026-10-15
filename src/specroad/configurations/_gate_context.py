"""Detached configuration selection for a validation gate, never an artifact."""
from dataclasses import dataclass

from ..model.canonical import canonical_json_sha256
from .values import resolve_configuration


@dataclass(frozen=True, init=False)
class _ConfigurationGateContext:
    configuration_id: str
    configuration_sha256: str
    resources_sha256: str

    def __init__(self, sources, configuration_id):
        selected = resolve_configuration(sources, configuration_id)
        resources = canonical_json_sha256({'gate': 'selected-stored-configuration-v1',
                                          'configuration': selected.manifest})
        object.__setattr__(self, 'configuration_id', selected.configuration_id)
        object.__setattr__(self, 'configuration_sha256', selected.sha256)
        object.__setattr__(self, 'resources_sha256', resources)
