"""Immutable publication observations, not reusable permissions or receipts."""
from dataclasses import dataclass
from hashlib import sha256
from ..model.canonical import canonical_json_bytes
from ..storage.json_syntax import parse_json_object
from ..validation import ModelDocument
from .execution_values import ChangeExecutionError, PublicationRequest
from .target_model import TargetModel
from .target_values import TargetPolicy

CHECK_VERSION = 'publication-recheck-v1'


class PublicationCheckError(ChangeExecutionError):
    """A refusal is not a rollback of earlier staging or a retry instruction."""
    def __init__(self, reason, *, path=None, exit_code=6, write_state='not_committed'):
        super().__init__(reason, exit_code=exit_code, write_state=write_state)
        self.path = path

    def diagnostic(self):
        return {**super().diagnostic(), 'path': self.path, 'write_authorized': False}


@dataclass(frozen=True)
class PublicationAuthority:
    """Trusted host registration, NEVER reconstructed from project/plan data.

    check(detached_request) must return an actual bool. The host implements real
    authentication/authorization; actor labels and this registration are not an
    authentication mechanism or a sandbox for callback code.
    """
    authority_id: str
    version: str
    check: object

    def __post_init__(self):
        if (any(type(v) is not str or not v.strip() or '\0' in v
                for v in (self.authority_id, self.version)) or not callable(self.check)):
            raise PublicationCheckError('registered_publication_authority_required', exit_code=2)


@dataclass(frozen=True, init=False)
class PublicationPreflight:
    _request: PublicationRequest
    _model: TargetModel
    _policy: TargetPolicy
    _strict: bool
    _footprint: bytes
    _package_files: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_publication_check')

    @classmethod
    def _create(cls, request, model, policy, strict, footprint, package_files):
        obj = object.__new__(cls)
        for name, value in (('_request', request.detached()), ('_model', model.snapshot()),
                ('_policy', policy), ('_strict', strict), ('_footprint', canonical_json_bytes(footprint)),
                ('_package_files', tuple(ModelDocument(d.path,d.content) for d in package_files))):
            object.__setattr__(obj, name, value)
        return obj

    @property
    def request(self):
        return self._request.detached()

    @property
    def data(self):
        return {'format_version': CHECK_VERSION, 'phase': 'early_diagnostic',
                'request_sha256': self._request.sha256,
                'footprint_sha256': sha256(self._footprint).hexdigest(),
                'observed_paths': sorted([*self._model.source_files, *(d.path for d in self._package_files)]),
                'final_check_required': True, 'write_authorized': False,
                'project_lock_acquired': False, 'atomic_snapshot': False}

    def __bool__(self):
        raise TypeError('A preflight is not a permission to publish')


@dataclass(frozen=True, init=False)
class PublicationRecheck:
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use recheck_publication')

    @classmethod
    def _create(cls, request, held_lock, authority):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_raw', canonical_json_bytes({
            'format_version': CHECK_VERSION, 'phase': 'locked_final_check',
            'request_sha256': request.sha256, 'plan_sha256': request.plan.sha256,
            'lock_id': held_lock.record.data['lock_id'],
            'authority_id': authority.authority_id, 'authority_version': authority.version,
            'host_authority_allowed': True, 'ready_for_backend': True,
            'preflight_reused_as_proof': False, 'write_authorized': False,
            'reusable_capability': False, 'normative_writes': 0,
            'atomic_snapshot': False, 'durability_verified': False}))
        return obj

    @property
    def data(self):
        return parse_json_object(self._raw)

    def __bool__(self):
        raise TypeError('A final observation is not a reusable write capability')


