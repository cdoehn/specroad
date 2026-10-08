"""Detached target observations; never a transaction, approval or write permit."""
from dataclasses import dataclass
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..storage.json_syntax import parse_json_object
from .errors import ChangePlanError

TARGET_VERSION = 'change-target-v1'


class TargetError(ChangePlanError):
    def __init__(self, reason, *, pointer=''):
        super().__init__(reason, pointer=pointer, code='SRV146')

    def diagnostic(self):
        return {**super().diagnostic(), 'transaction_prepared': False,
                'write_authorized': False}


@dataclass(frozen=True)
class TargetPolicy:
    """Trusted command registration, separate from untrusted saved plan fields.

    Extra required command gates use extension: IDs and check the whole target.
    The model pipeline independently decides its required Core semantic gates.
    An explicit empty set is allowed; it cannot disable a Core prerequisite.
    """
    command_id: str
    version: str
    required_gate_ids: tuple

    def __post_init__(self):
        for value in (self.command_id, self.version):
            if type(value) is not str or not value.strip() or '\0' in value:
                raise TargetError('target_command_identity_required')
        ids = self.required_gate_ids
        if (type(ids) is not tuple or any(type(v) is not str or not v.startswith('extension:')
                or v == 'extension:' for v in ids) or len(set(ids)) != len(ids)):
            raise TargetError('target_command_gate_ids_required')

    def data(self):
        return {'command_id': self.command_id, 'version': self.version,
                'required_gate_ids': sorted(self.required_gate_ids)}


@dataclass(frozen=True, init=False)
class TargetAssessment:
    """Complete in-memory target evaluation over supplied files and trusted gates.

    target_validated is not physical inventory proof or durable staging. A real
    writer still needs fresh input checks, authorization, locking and fsync.
    """
    _encoded: bytes
    _plan: bytes
    _documents: tuple
    _resource_documents: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError('Use assess_change_target to obtain a bound observation')

    @classmethod
    def _create(cls, value, plan, documents, *, resource_documents=()):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_encoded', canonical_json_bytes(value))
        object.__setattr__(obj, '_plan', plan.source_bytes)
        object.__setattr__(obj, '_documents', tuple(documents))
        object.__setattr__(obj, '_resource_documents', tuple(resource_documents))
        return obj

    @property
    def data(self): return parse_json_object(self._encoded)
    @property
    def sha256(self): return canonical_json_sha256(self.data)
    @property
    def target_validated(self): return self.data['target_validated']
    @property
    def plan(self):
        from .values import ChangePlan
        return ChangePlan(self._plan)
    @property
    def documents(self): return self._documents
    @property
    def resource_documents(self): return self._resource_documents
    @property
    def publication_documents(self):
        return tuple(sorted(self._documents + self._resource_documents, key=lambda d: d.path))
    @property
    def artifacts(self): return [parse_json_object(d.content) for d in self._documents]
    @property
    def transaction_prepared(self): return False
    @property
    def write_authorized(self): return False
    @property
    def execution_ready(self): return False

    def require_valid(self):
        if not self.target_validated:
            raise TargetError('complete_target_validation_required')
        return self

    def __bool__(self):
        raise TypeError('Use target_validated explicitly; an incomplete target is not success')
