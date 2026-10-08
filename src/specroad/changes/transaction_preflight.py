"""Transaction gate for normal calls; automatic recovery ends this invocation.

Trusted hosts supply the real command class and authenticate RecoveryAuthority.
This library neither installs project CLI handlers nor executes a normal change.
The returned observation is not a write capability or a reusable project lease.
"""
from dataclasses import dataclass
from hashlib import sha256
import os

from ..cli.contracts import CommandClass
from ..model.canonical import canonical_json_bytes
from ..model.configuration import ProjectConfiguration
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from ..security.resource_access import opened_resource
from ..storage.json_reader import JsonResource, configuration_schema
from ..storage.json_syntax import parse_json_object
from ..storage.operational_preflight import observe_operational_preflight, MAX_METADATA_BYTES
from .authoring import normalize_authoring_actor, normalize_request_id
from .execution_values import ChangeExecutionError
from .locking import project_lock, inspect_project_lock
from .recovery_lock import transaction_recovery_lock
from .recovery_values import RecoveryAuthority, RecoveryError, DiscardedJournal
from .recovery import (discard_unpublished_transaction, complete_published_transaction,
                       rollback_interrupted_transaction)
from .recovery_cleanup import cleanup_recovered_transaction
from .discard_preflight import prepare_discard_recovery
from ._journal_codec import _text
from ._lock_files import LockFiles
from ._recovery_inputs import _read_journal, _parse
from ._recovery_integrity import inspect_critical_inputs


@dataclass(frozen=True, init=False)
class TransactionPreflight:
    _raw: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError('Use transaction_preflight with current project inputs')

    @classmethod
    def _create(cls, data):
        obj = object.__new__(cls)
        object.__setattr__(obj, '_raw', canonical_json_bytes(data))
        return obj

    @property
    def data(self):
        return parse_json_object(self._raw)

    @property
    def exit_code(self):
        return self.data['exit_code']

    def __bool__(self):
        raise TypeError('A transaction preflight is not write authorization')


def _configuration(boundary, available):
    with opened_resource(boundary, 'specroad.json') as (fd, info):
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
    raw = b''.join(chunks)
    resource = JsonResource(raw, configuration_schema(), path='specroad.json')
    return raw, ProjectConfiguration(resource.data)


def _authorize(authority, request):
    before = canonical_json_bytes(request)
    try:
        allowed = authority.check(request)
    except Exception as error:
        raise RecoveryError('automatic_recovery_authority_failed', exit_code=7) from error
    if type(allowed) is not bool or not allowed or canonical_json_bytes(request) != before:
        raise RecoveryError('automatic_recovery_not_authorized', exit_code=7)


def transaction_preflight(root, *, command_class, dry_run=False, request_id=None,
                          expected_project_id=None, authority=None, actor=None):
    """Observe first; recover at most one safely selected former transaction.

    Read-only/plan/generated/dry-run calls never read journal bodies or activate
    recovery. A write also needs explicit auto_recover=true and host authority.
    Successful automatic recovery returns code 5 and requires a new invocation;
    the original request is neither executed nor consumed. A clear transaction
    gate still requires the caller's ordinary configuration, model and write checks.
    """
    supported = (CommandClass.READ_ONLY, CommandClass.PLAN_OUTPUT,
                 CommandClass.GENERATED_OUTPUT, CommandClass.NORMATIVE_WRITE)
    if type(command_class) is not CommandClass or command_class not in supported or type(dry_run) is not bool:
        raise RecoveryError('normal_project_call_class_required', exit_code=2)
    if expected_project_id is not None and not _text(expected_project_id):
        raise RecoveryError('preflight_project_identity_required', exit_code=2)
    if request_id is not None:
        normalize_request_id(request_id)
    data = {'format_version': 'transaction-preflight-v1', 'command_class': command_class.value,
            'dry_run': dry_run, 'request_id': request_id, 'request_consumed': False,
            'phase': 'transaction_metadata', 'exit_code': 5, 'reason': 'recovery_required',
            'transaction_preflight_passed': False, 'normal_operation_started': False,
            'model_loaded': False, 'write_authorized': False, 'atomic_snapshot': False,
            'recovery_required': True, 'recovery_attempted': False, 'recovery_completed': False,
            'requires_new_invocation': False, 'mutation_possible': False, 'recovery': None}
    try:
        boundary = ProjectBoundary(root)
        observed = observe_operational_preflight(boundary)
        data['operational'] = observed
        if observe_operational_preflight(boundary) != observed:
            raise RecoveryError('preflight_operational_metadata_changed', exit_code=6)
        data['metadata_bytes_read'] = 2 * observed['metadata_bytes_read']
        if observed['consistency_state'] == 'consistent':
            data.update(exit_code=0, reason='transaction_gate_clear',
                        recovery_required=False, transaction_preflight_passed=True)
            return TransactionPreflight._create(data)
        if command_class is not CommandClass.NORMATIVE_WRITE or dry_run:
            return TransactionPreflight._create(data)
        paths = observed['unresolved_paths']
        if (not observed['inspection_complete'] or len(paths) != 1
                or not paths[0].startswith('.specroad/transactions/')
                or any(p != '.specroad/locks/project.json' for p in observed['unknown_paths'])):
            data['reason'] = 'explicit_recovery_selection_required'
            return TransactionPreflight._create(data)
        raw_config, config = _configuration(boundary, MAX_METADATA_BYTES - data['metadata_bytes_read'])
        data['metadata_bytes_read'] += len(raw_config)
        data['configuration_sha256'] = sha256(raw_config).hexdigest()
        if expected_project_id is not None and config.project_id != expected_project_id:
            raise RecoveryError('preflight_project_identity_mismatch', exit_code=6)
        if config.data.get('transaction_policy', {}).get('auto_recover') is not True:
            data['reason'] = 'automatic_recovery_disabled'
            return TransactionPreflight._create(data)
        if type(authority) is not RecoveryAuthority or request_id is None:
            raise RecoveryError('automatic_recovery_authority_and_request_required', exit_code=7)
        actor = normalize_authoring_actor(actor).as_fields()
        transaction_id = paths[0].rsplit('/', 1)[-1]
        _authorize(authority, {'action': 'automatic_recovery', 'actor': actor,
            'project_id': config.project_id, 'transaction_id': transaction_id,
            'normal_request_id': request_id, 'configuration_sha256': data['configuration_sha256']})

        def current_policy():
            if boundary.read_bytes('specroad.json') != raw_config:
                raise RecoveryError('preflight_configuration_changed', exit_code=6)
            boundary._check_root()

        # Full journal/resource diagnosis belongs to the explicitly selected
        # recovery phase, not the short transaction-metadata start check.
        data['phase'] = 'automatic_recovery'
        current_policy()
        if observe_operational_preflight(boundary) != observed:
            raise RecoveryError('preflight_operational_metadata_changed', exit_code=6)
        owner = inspect_project_lock(boundary.root, expected_project_id=config.project_id).data
        if owner['owner_state'] not in ('absent', 'dead'):
            data.update(reason='automatic_recovery_owner_unproven', owner_state=owner['owner_state'])
            return TransactionPreflight._create(data)
        with LockFiles(boundary.root) as files:
            raw, _ = _read_journal(files, transaction_id)
            journal = _parse(raw, transaction_id, files, config.project_id)
            integrity = inspect_critical_inputs(files, journal)
        if integrity['blockers']:
            raise RecoveryError(integrity['blockers'][0]['reason'], exit_code=6)
        state = journal.data['state']
        discard = state in ('building', 'prepared') or type(journal) is DiscardedJournal
        command = 'recover discard' if discard else 'recover run'
        proof = (prepare_discard_recovery(boundary.root, transaction_id,
            expected_project_id=config.project_id, expected_journal_sha256=journal.sha256) if discard else None)
        options = dict(command=command, project_id=config.project_id,
                       request_id=journal.data['request_id'], transaction_id=transaction_id)

        def guarded_authority(request):
            current_policy()
            _authorize(authority, request)
            current_policy()
            return True

        guarded = RecoveryAuthority(authority.authority_id, authority.version, guarded_authority)
        if owner['owner_state'] == 'dead':
            lock = transaction_recovery_lock(boundary.root, **options,
                expected_lock_sha256=owner['record_sha256'], expected_journal_sha256=journal.sha256,
                authority=guarded, actor=actor, reason='Authorized preflight recovery', force=True)
        else:
            lock = project_lock(boundary.root, kind='recovery', **options)
        current_policy()
        data.update(recovery_attempted=True, mutation_possible=True)
        with lock as held:
            current_policy()
            held.check()
            if held._files.journal_entries() != tuple(paths):
                raise RecoveryError('preflight_active_transactions_changed', exit_code=6)

            if discard:
                result = discard_unpublished_transaction(proof, transaction_id, held_lock=held,
                    authority=guarded, actor=actor, reason='Authorized preflight recovery',
                    expected_journal_sha256=journal.sha256).data
                cleanup = None
            else:
                complete = state == 'committed' or (state == 'committing' and integrity['complete_target_verified'])
                action = complete_published_transaction if complete else rollback_interrupted_transaction
                result = action(transaction_id, held_lock=held, authority=guarded,
                                expected_journal_sha256=journal.sha256).data
                data['recovery'] = result
                terminal_raw, _ = _read_journal(held._files, transaction_id)
                terminal = _parse(terminal_raw, transaction_id, held._files, config.project_id)
                cleanup = cleanup_recovered_transaction(transaction_id, held_lock=held, authority=guarded,
                    expected_journal_sha256=terminal.sha256).data
            data.update(recovery=result, cleanup=cleanup)
        after = observe_operational_preflight(boundary)
        data.update(exit_code=5, reason='recovery_completed_reinvoke', recovery_completed=True,
                    recovery_required=after['consistency_state'] != 'consistent',
                    requires_new_invocation=True, operational_after=after)
        return TransactionPreflight._create(data)
    except (ChangeExecutionError, ModelError, SafetyViolation, OSError) as error:
        data.update(exit_code=getattr(error, 'exit_code', 5),
                    reason=getattr(error, 'reason', 'transaction_preflight_unavailable'),
                    mutation_possible=data['mutation_possible'] or getattr(error, 'mutation_possible', False))
        return TransactionPreflight._create(data)
