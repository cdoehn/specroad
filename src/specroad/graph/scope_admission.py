"""Permanent artifact admission rules, independent of selection or rendering.

The policy also recognizes a configuration wrapper around specification, but
never evaluates applicability or treats a configured scope as already resolved.
This guard is necessary, not a graph-validity or write-authorization decision.
"""
from ..model.errors import ModelError
from ..model.identity_values import ArtifactIdentity
from .scope_descriptors import ScopeDescriptor

CONTROL_ARTIFACT_TYPES = frozenset(('proposal', 'baseline'))


class ScopeControlDependencyError(ModelError):
    """An excluded control artifact was required by the selected closure."""
    code = 'SRV140'
    exit_code = 3

    def __init__(self, *, source_id, target_id, relation_id=None, pointer=''):
        super().__init__('scope_control_dependency', pointer=pointer)
        self.source_id = source_id
        self.target_id = target_id
        self.relation_id = relation_id

    def diagnostic(self):
        return {**super().diagnostic(), 'code': self.code, 'severity': 'error',
                'source_id': self.source_id, 'target_id': self.target_id,
                'relation_id': self.relation_id, 'exit_code': self.exit_code}


def excludes_control_artifacts(descriptor):
    """Return the base-scope rule; do not silently remove configuration filters."""
    if type(descriptor) is not ScopeDescriptor:
        raise ModelError('scope_descriptor_required')
    value = descriptor.data
    if value['scope_kind'] == 'configuration':
        value = value['selector']['base_scope_descriptor']
    return value['scope_kind'] == 'specification'


def require_artifact_admissible(descriptor, target, *, source_id=None,
                                relation_id=None, pointer=''):
    """Check a validated identity before admission, not an ID-looking label.

    Only actual visited dependencies pass through this guard. An omitted weak
    endpoint in a partial scope retains the normal boundary-reference contract.
    """
    excluded = excludes_control_artifacts(descriptor)
    if type(target) is not ArtifactIdentity:
        raise ModelError('artifact_identity_required')
    if excluded and target.artifact_type in CONTROL_ARTIFACT_TYPES:
        raise ScopeControlDependencyError(source_id=source_id, target_id=target.id,
                                          relation_id=relation_id, pointer=pointer)
