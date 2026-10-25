"""Explicit, read-only document input over verified partial membership.

This type is deliberately not a TargetModel. Change planners, exporters and
publication authorities keep their existing exact-type checks.
"""
from dataclasses import dataclass

from ..model.errors import ModelError
from ..validation import ModelDocument


@dataclass(frozen=True, init=False)
class PartialDocumentModel:
    def __init__(self, observation):
        from ..bundles._partial_read import PartialReadSnapshot
        if type(observation) is not PartialReadSnapshot:
            raise ModelError('partial_document_observation_required')
        observation.verify_current()
        payload = observation.payload_model
        for name in ('configuration', 'binding', 'profile', 'resource_files',
                     'resources', 'attachment_descriptors', 'language_packages'):
            object.__setattr__(self, name, getattr(payload, name))
        object.__setattr__(self, 'partial', observation)
        object.__setattr__(self, 'documents', tuple(ModelDocument(r.path, r.source_bytes)
            for r in observation.records))
        object.__setattr__(self, '_sources_sha256', observation.observation_sha256)

    @property
    def source_files(self):
        return {**{d.path: d.content for d in self.documents},
                **{d.path: d.content for d in self.resource_files}}

    @property
    def artifacts(self):
        return tuple(r.data for r in self.partial.records)

    def snapshot(self):
        self.partial.verify_current()
        return self


def require_read_model(model):
    from ..changes.target_model import TargetModel
    if type(model) not in (TargetModel, PartialDocumentModel):
        raise ModelError('document_target_model_required')


def partial_observation(model):
    return model.partial if type(model) is PartialDocumentModel else None


def read_scope(model):
    from ..changes.target_model import _default_scope
    partial = partial_observation(model)
    return _default_scope() if partial is None else partial.manifest['scope_descriptor']


def read_root(model, descriptor=None):
    partial = partial_observation(model)
    if partial is not None:
        return partial.manifest['bundle_model_root_sha256']
    return model.manifest(model.artifacts, read_scope(model) if descriptor is None else descriptor).sha256


def local_references(model, records):
    from ..graph.references import RelationReferences
    from ..bundles._partial_graph import PartialGraph
    partial = partial_observation(model)
    return RelationReferences(records) if partial is None else PartialGraph(partial).references
