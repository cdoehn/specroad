"""Resolve an artifact-reference block from an owned supplied model snapshot.

Resolution is a data projection of the target's actual bytes. It does not store
a second artifact, render output, determine document ownership or grant approval.
"""
from ._read_model import read_root, read_scope
from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..storage.json_syntax import parse_json_object
from ._reference_sources import _resolve_reference_sources


class ArtifactReferenceError(ModelError):
    exit_code = 3


@dataclass(frozen=True, init=False)
class ArtifactReferenceResolution:
    """Immutable source binding and detached target values, not publication."""
    _encoded: bytes
    block_source_bytes: bytes
    target_source_bytes: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use resolve_artifact_reference with actual model bytes')

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def target_record(self):
        return parse_json_object(self.target_source_bytes, path=self.data['target']['path'])

    @property
    def sha256(self):
        return canonical_json_sha256(self.data)

    def __bool__(self):
        raise TypeError('A resolved reference is not rendering or publication approval')


def resolve_artifact_reference(model, block_id):
    """Resolve exactly one stored references edge, with no label/ID fallback.

    TargetModel supplies the complete inventory. Its native snapshot, relation
    identity/matrix checks and source bytes remain authoritative; this function
    neither discovers files nor proves that the supplied inventory is complete
    on disk. Only the selected block and target receive type-specific field
    validation. Document composition and full model validation remain separate.
    """
    from ..changes.target_model import _default_scope
    model, source, block, position, relation, target, value = _resolve_reference_sources(
        model, block_id, ArtifactReferenceError)
    descriptor = read_scope(model)
    data = {'format_version': 'artifact-reference-v1', 'project_id': model.binding.project_id,
        'scope_descriptor': descriptor,
        'model_root_sha256': read_root(model, descriptor),
        'input_sha256': model._sources_sha256,
        'validation_scope': 'supplied_model_artifact_reference', 'reference_resolved': True,
        'block': block.binding,
        'render_mode': block.payload['render_mode'],
        'relation': {'relation_id': relation.identity.id, 'source_id': source.identity.id,
            'target_id': target.identity.id, 'pointer': '/relations/' + str(position),
            'record': relation.data, 'record_sha256': canonical_json_sha256(relation.data)},
        'target': {'artifact_id': value['id'], 'artifact_type': value['artifact_type'],
            'revision': value['revision'], 'path': target.path,
            'source_sha256': sha256(target.source_bytes).hexdigest(),
            'record_sha256': canonical_json_sha256(value), 'record': value},
        'project_files_verified': False, 'full_validation_passed': False,
        'document_structure_checked': False, 'document_roles_checked': False,
        'include_graph_checked': False, 'payload_semantics_evaluated': False,
        'rendering_performed': False, 'write_authorized': False, 'approval_granted': False}
    result = object.__new__(ArtifactReferenceResolution)
    object.__setattr__(result, '_encoded', canonical_json_bytes(data))
    object.__setattr__(result, 'block_source_bytes', source.source_bytes)
    object.__setattr__(result, 'target_source_bytes', target.source_bytes)
    return result
