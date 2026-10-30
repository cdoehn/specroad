"""Native original bytes and content bindings, independent of persisted reviews.

These values do not introduce a file format or authenticate an actor. In
particular a content hash is not a successful check or a human decision.
"""
from dataclasses import dataclass
from hashlib import sha256

from ..changes.values import ChangePlan
from ..graph.scope_descriptors import ScopeDescriptor
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.errors import ModelError
from ..model.paths import artifact_path
from ..storage.record_artifact import RecordArtifact


CONTENT_EXCLUSIONS = frozenset(('revision', 'created_at', 'created_by',
    'updated_at', 'updated_by', 'content_revision', 'content_sha256', 'maturity',
    'proposal_status', 'reviews', 'control_history'))
SPECIFICATION_SCOPE = {'scope_version': 'scope-v1', 'scope_kind': 'specification',
    'selector': {}, 'configuration_id': None, 'closure_profile': 'core-closure-v1',
    'boundary_policy': 'closed'}


class ProposalError(ModelError):
    def __init__(self, reason, *, path=None, pointer='', exit_code=3):
        super().__init__(reason, path=path, pointer=pointer)
        self.exit_code = exit_code


def require(condition, reason, *, path=None, pointer='', exit_code=3):
    if not condition:
        raise ProposalError(reason, path=path, pointer=pointer, exit_code=exit_code)


def content_sha256(value):
    """Exclude only management fields at the top level, never nested keys."""
    require(type(value) is dict, 'proposal_object_required')
    return canonical_json_sha256({k: v for k, v in value.items()
                                 if k not in CONTENT_EXCLUSIONS})


@dataclass(frozen=True)
class ProposalBinding:
    proposal_id: str
    content_revision: int
    content_sha256: str
    base_model_root_sha256: str
    change_plan_sha256: str

    def __post_init__(self):
        from ..changes._common import _reference
        identity = _reference(self.proposal_id, '/proposal_id')
        require(identity.artifact_type == 'proposal', 'proposal_identity_required')
        require(type(self.content_revision) is int and self.content_revision > 0,
                'proposal_content_revision_invalid')
        for digest in (self.content_sha256, self.base_model_root_sha256,
                       self.change_plan_sha256):
            require(type(digest) is str and len(digest) == 64
                    and all(c in '0123456789abcdef' for c in digest),
                    'proposal_binding_hash_invalid')

    @property
    def data(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, init=False)
class ProposalOriginal:
    """Complete byte-preserving original, NOT qualified historical evidence."""
    source_bytes: bytes
    path: str

    def __init__(self, raw, *, path):
        require(type(raw) is bytes, 'proposal_original_bytes_required', path=path)
        record = RecordArtifact(raw, expected_type='proposal', path=path)
        value = record.data
        from ..model.identity_values import artifact_identity
        identity = artifact_identity(value)
        require(path == artifact_path('proposal', record.id, identity.id_prefix),
                'proposal_original_path_mismatch', path=path)
        require(content_sha256(value) == value['content_sha256'],
                'proposal_content_hash_mismatch', path=path)
        base = value['base']
        require('scope_descriptor' in base
                and ScopeDescriptor(base['scope_descriptor']).data == SPECIFICATION_SCOPE,
                'proposal_specification_scope_required', path=path)
        plan = ChangePlan(canonical_json_bytes(value['change_plan']))
        require(plan.data['base'] == base, 'proposal_plan_base_mismatch', path=path)
        for operation in plan.operations:
            require(operation.op not in ('proposal_control', 'baseline_create'),
                    'proposal_control_target_forbidden', path=path)
            from ..changes._common import _reference
            require(all(_reference(key, '').artifact_type not in ('proposal', 'baseline')
                        for key in operation.result_ids),
                    'proposal_control_target_forbidden', path=path)
        object.__setattr__(self, 'source_bytes', raw)
        object.__setattr__(self, 'path', path)

    @property
    def data(self):
        return RecordArtifact(self.source_bytes, expected_type='proposal', path=self.path).data

    @property
    def sha256(self):
        return sha256(self.source_bytes).hexdigest()

    @property
    def binding(self):
        value = self.data
        return ProposalBinding(value['id'], value['content_revision'], value['content_sha256'],
            value['base']['model_root_sha256'], value['change_plan']['change_plan_sha256'])
