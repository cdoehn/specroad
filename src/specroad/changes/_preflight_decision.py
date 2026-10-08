"""Bounded automatic-recovery decision; no lock or recovery write is acquired."""
from dataclasses import dataclass
from hashlib import sha256
import os

from ..model.configuration import ProjectConfiguration
from ..security import ProjectBoundary
from ..security.resource_access import opened_resource
from ..model.canonical import canonical_json_bytes
from ..storage.json_reader import JsonResource, configuration_schema
from ..storage.operational_preflight import MAX_METADATA_BYTES
from .authoring import normalize_authoring_actor
from .recovery_values import RecoveryAuthority, RecoveryError
from ._recovery_evidence import EvidenceRecord
from ._preflight_selection import select_recovery


@dataclass(frozen=True)
class RecoveryDecision:
    """Internal observed inputs, never a model or reusable write permission.

    Policy bytes and root identity remain subject to every existing live check.
    The execution phase still proves ownership, journal and resources itself.
    """
    boundary: ProjectBoundary
    observation: dict
    configuration: ProjectConfiguration
    configuration_bytes: bytes
    transaction_id: str
    barrier: EvidenceRecord | None
    authority: RecoveryAuthority
    actor: dict
    request_id: str

    def check_policy(self):
        if self.boundary.read_bytes('specroad.json') != self.configuration_bytes:
            raise RecoveryError('preflight_configuration_changed', exit_code=6)
        self.boundary._check_root()

    def authorize(self, request):
        self.check_policy()
        _authorize(self.authority, request)
        self.check_policy()
        return True


def _metadata(boundary, path, available):
    with opened_resource(boundary, path) as (fd, info):
        if info.st_size > available:
            raise RecoveryError('automatic_recovery_policy_requires_explicit_inspection', exit_code=5)
        chunks, remaining = [], info.st_size
        while remaining:
            raw = os.read(fd, min(65536, remaining))
            if not raw:
                raise RecoveryError('preflight_configuration_changed', exit_code=6)
            chunks.append(raw)
            remaining -= len(raw)
        if os.read(fd, 1):
            raise RecoveryError('preflight_configuration_changed', exit_code=6)
    return b''.join(chunks)


def _authorize(authority, request):
    before = canonical_json_bytes(request)
    try:
        allowed = authority.check(request)
    except Exception as error:
        raise RecoveryError('automatic_recovery_authority_failed', exit_code=7) from error
    if type(allowed) is not bool or not allowed or canonical_json_bytes(request) != before:
        raise RecoveryError('automatic_recovery_not_authorized', exit_code=7)


def prepare_automatic_recovery(boundary, observed, data, *, expected_project_id,
                               request_id, authority, actor):
    """Record a blocked decision or select one explicitly authorized recovery.

    Updates only the current invocation's observation. The pending descriptor
    belongs to the bounded metadata budget; full journal/resource proof does not.
    """
    paths = observed['unresolved_paths']
    if (not observed['inspection_complete'] or not 1 <= len(paths) <= 2
            or any(p != '.specroad/locks/project.json' for p in observed['unknown_paths'])):
        data['reason'] = 'explicit_recovery_selection_required'
        return None
    raw_config = _metadata(boundary, 'specroad.json', MAX_METADATA_BYTES - data['metadata_bytes_read'])
    config = ProjectConfiguration(JsonResource(raw_config, configuration_schema(), path='specroad.json').data)
    data['metadata_bytes_read'] += len(raw_config)
    data['configuration_sha256'] = sha256(raw_config).hexdigest()
    if expected_project_id is not None and config.project_id != expected_project_id:
        raise RecoveryError('preflight_project_identity_mismatch', exit_code=6)
    if config.data.get('transaction_policy', {}).get('auto_recover') is not True:
        data['reason'] = 'automatic_recovery_disabled'
        return None
    def metadata(path):
        raw = _metadata(boundary, path, MAX_METADATA_BYTES - data['metadata_bytes_read'])
        data['metadata_bytes_read'] += len(raw)
        return raw

    transaction_id, barrier = select_recovery(observed, config.project_id, boundary, metadata)
    if type(authority) is not RecoveryAuthority or request_id is None:
        raise RecoveryError('automatic_recovery_authority_and_request_required', exit_code=7)
    actor = normalize_authoring_actor(actor).as_fields()
    _authorize(authority, {'action': 'automatic_recovery', 'actor': actor,
        'project_id': config.project_id, 'transaction_id': transaction_id,
        'normal_request_id': request_id, 'configuration_sha256': data['configuration_sha256']})

    return RecoveryDecision(boundary, observed, config, raw_config, transaction_id,
                            barrier, authority, actor, request_id)
