"""Explicit, immutable input inventory for scope seed selection.

This is a data adapter, not an inventory scanner, archive verifier or profile
composer. The caller supplies the current resource identities and active flags.
Every supplied source is bound by its original bytes. No authority is inferred
from a digest or from a caller's declaration of active resources.
"""
from dataclasses import dataclass
from hashlib import sha256
import re
from types import MappingProxyType

from ..model.canonical import canonical_json_sha256
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..model.semantic_configuration import semantic_configuration
from .references import RelationReferences
from .scope_descriptors import _text, _artifact_id


def _sequence(values):
    if isinstance(values, (str, bytes, dict)):
        raise ModelError('scope_sequence_required')
    try:
        return tuple(values)
    except TypeError as error:
        raise ModelError('scope_sequence_required') from error


@dataclass(frozen=True)
class ScopeResource:
    """Opaque logical resource identity, never an instruction to open a path."""
    resource_id: str
    kind: str
    sha256: str
    version: str | None = None
    active: bool = False

    def __post_init__(self):
        _text(self.resource_id)
        if type(self.kind) is not str or self.kind not in (
                'profile', 'rule', 'mapping', 'language_registry', 'attachment', 'archive'):
            raise ModelError('non_normative_scope_resource')
        if type(self.sha256) is not str or re.fullmatch('[0-9a-f]{64}', self.sha256) is None:
            raise ModelError('invalid_scope_resource_hash')
        if self.kind in ('profile', 'rule', 'mapping'):
            _text(self.version)
        elif self.version is not None:
            _text(self.version)
        if type(self.active) is not bool or (self.active and self.kind not in ('profile', 'rule', 'mapping')):
            raise ModelError('invalid_scope_active_resource')

    @property
    def data(self):
        return {'resource_id': self.resource_id, 'kind': self.kind, 'sha256': self.sha256,
                'version': self.version, 'active': self.active}


@dataclass(frozen=True, init=False)
class ScopeSeedInputs:
    """An explicitly supplied inventory, not proof of complete project coverage.

    archive_bindings maps each supplied baseline ID to its required archive IDs.
    For project scope every baseline needs an explicit entry, including an empty
    one. The later baseline reader must establish actual recursive completeness.
    """
    project_id: str
    records: tuple
    resources: tuple
    references: RelationReferences
    archive_bindings: object
    configuration_sha256: str
    fingerprint: str

    def __init__(self, configuration, records, resources=(), *, archive_bindings=None):
        if type(configuration) is not ProjectConfiguration:
            raise ModelError('scope_configuration_required')
        records = _sequence(records)
        references = RelationReferences(records)
        if any(source.id_prefix != configuration.id_prefix for source in references.sources):
            raise ModelError('scope_project_prefix_mismatch')
        ordered = tuple(sorted(records, key=lambda record: record.identity.id.encode('utf-8')))
        resources = _sequence(resources)
        seen = set()
        for resource in resources:
            if type(resource) is not ScopeResource:
                raise ModelError('scope_resource_required')
            if resource.resource_id in seen:
                raise ModelError('duplicate_scope_resource')
            seen.add(resource.resource_id)
        resources = tuple(sorted(resources, key=lambda value: value.resource_id.encode('utf-8')))
        bindings = {} if archive_bindings is None else archive_bindings
        if type(bindings) is not dict:
            raise ModelError('scope_archive_bindings_required')
        checked = {}
        identities = {record.identity.id: record.identity for record in ordered}
        by_resource = {resource.resource_id: resource for resource in resources}
        for baseline_id, names in bindings.items():
            _artifact_id(baseline_id, 'baseline')
            if baseline_id not in identities:
                raise ModelError('scope_archive_baseline_missing')
            names = _sequence(names)
            for name in names:
                _text(name)
                if name not in by_resource or by_resource[name].kind != 'archive':
                    raise ModelError('scope_archive_resource_missing')
            if len(set(names)) != len(names):
                raise ModelError('duplicate_scope_archive_binding')
            checked[baseline_id] = tuple(sorted(names, key=lambda name: name.encode('utf-8')))
        config_hash = canonical_json_sha256(semantic_configuration(configuration))
        fingerprint = canonical_json_sha256({
            'binding_version': 'scope-seed-inputs-v1', 'project_id': configuration.project_id,
            'configuration_sha256': config_hash,
            'artifacts': [{'id': record.identity.id, 'sha256': sha256(record.source_bytes).hexdigest()}
                          for record in ordered],
            'resources': [resource.data for resource in resources],
            'archive_bindings': {name: list(values) for name, values in checked.items()},
        })
        for name, value in (('project_id', configuration.project_id), ('records', ordered),
                            ('resources', resources), ('references', references),
                            ('archive_bindings', MappingProxyType(checked)),
                            ('configuration_sha256', config_hash), ('fingerprint', fingerprint)):
            object.__setattr__(self, name, value)

    @property
    def validation_scope(self):
        return 'supplied_seed_inventory_only'
