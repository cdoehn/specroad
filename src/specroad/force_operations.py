"""Current-call operational overrides. Stored data never installs authority.

The lexical scope is reset on every exit and is bound to its creating process.
It records decisions; OS calls, byte observations and host authority still run.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from hashlib import sha256
import os
import re

from .force import ForceContractError, ForceDecisions, ForceRequest

_CURRENT = ContextVar('specroad_force_operations', default=None)
_SHA = re.compile(r'[0-9a-f]{64}\Z')
OWNER_PATHS = ('.specroad/locks/project.json', 'work-lock.json',
    'bootstrap-root.owner', 'bootstrap-container.owner')


def binding(value=None):
    """Closed detached owner selection; absence is not a takeover selection."""
    if value is None:
        return {'owners': []}
    if type(value) is not dict or set(value) != {'owners'} or type(value['owners']) is not list:
        raise ForceContractError('Invalid operational binding')
    rows = []
    for row in value['owners']:
        if (type(row) is not dict or set(row) != {'path', 'sha256'}
                or row['path'] not in OWNER_PATHS or type(row['sha256']) is not str
                or not _SHA.fullmatch(row['sha256'])):
            raise ForceContractError('Invalid observed owner binding')
        rows.append(dict(row))
    if len({r['path'] for r in rows}) != len(rows):
        raise ForceContractError('Duplicate owner selection')
    if rows != sorted(rows, key=lambda r: r['path']):
        raise ForceContractError('Owner selection must be sorted')
    return {'owners': rows}


def option_binding(options):
    values = options.get('--force-owner', ())
    if isinstance(values, str):
        values = (values,)
    rows = []
    for value in values:
        path, sep, digest = value.partition('=')
        if not sep:
            raise ForceContractError('Owner selection needs path=sha256')
        rows.append({'path': path, 'sha256': digest})
    return binding({'owners': sorted(rows, key=lambda r: r['path'])})


@dataclass(frozen=True)
class _Call:
    decisions: ForceDecisions
    owners: tuple
    pid: int


def current():
    call = _CURRENT.get()
    return call if call is not None and call.pid == os.getpid() else None


@contextmanager
def scope(decisions, selected=None):
    if type(decisions) is not ForceDecisions:
        raise TypeError('A current-call decision ledger is required')
    owners = binding(selected)['owners']
    if owners and not decisions.request.requested:
        raise ForceContractError('Explicit Force is required for an owner selection')
    token = _CURRENT.set(_Call(decisions, tuple((r['path'], r['sha256']) for r in owners), os.getpid()))
    try:
        yield decisions
    finally:
        _CURRENT.reset(token)


def permit(allowed, *, gate, subject, observed=None, requested=None,
           effect='execute_explicit_operation_preserving_negative_finding'):
    if allowed:
        return True
    call = current()
    if call is None or not call.decisions.request.requested:
        return False
    return call.decisions.decide(False, gate_id=gate, diagnostic_code='CORE_SECURITY',
        subject=str(subject), operation='operational.force', observed_binding=observed,
        requested_binding=requested, effect=effect)


def selected_owner(path, raw):
    call = current()
    return (call is not None and call.decisions.request.requested and raw is not None
        and dict(call.owners).get(path) == sha256(raw).hexdigest())


def read_access(root, observation):
    if observation['state'] == 'clean':
        return True
    call = current()
    if call is None or not call.decisions.request.requested:
        return False
    from .changes._lock_files import LockFiles
    from .changes._guarded_io import _read_path
    with LockFiles(root) as files:
        raw = _read_path(files, '.specroad/locks/project.json', optional=True)
        from .changes.lock_values import LockRecord
        from .changes._lock_owner_policy import observe_owner
        from .changes._lock_process import LinuxOwnerProbe
        from .model.errors import ModelError
        try:
            state = None if raw is None else observe_owner(LockRecord(raw), LinuxOwnerProbe())
        except (ValueError, TypeError, ModelError):
            state = 'unknown'
        with files.observe_mutex() as busy:
            if busy or state in ('alive', 'foreign', 'unverifiable', 'unknown'):
                if not selected_owner('.specroad/locks/project.json', raw):
                    return False
                permit(False, gate='lock:read_exclusivity', subject='project',
                    observed={'exclusive_access_proven': False}, requested=dict(call.owners))
    return permit(False, gate='write_marker:normal_read', subject='project',
        observed=observation, requested='read_actual_retained_bytes',
        effect='observe_without_recovery_or_validity_claim')


def explicit_path(value):
    """An exact root-relative byte address, not a guessed normalization.

Reserved portable names are software policy. Empty components, navigation,
NUL and absolute addresses do not identify a root-relative operation.
"""
    if (type(value) is not str or not value or value.startswith('/') or '\0' in value
            or any(p in ('', '.', '..') for p in value.split('/'))):
        raise ForceContractError('An unambiguous relative resource address is required')
    value.encode('utf-8')
    return value


def plan_scope(function):
    """Explicit Python apply calls get the same scope as CLI calls."""
    from functools import wraps
    @wraps(function)
    def call(root, plan, *args, **kwargs):
        request = ForceRequest(kwargs.get('force', False), kwargs.get('force_reason'))
        ledger = ForceDecisions(request)
        from .changes.values import ChangePlan
        selected = plan.data.get('operational_binding') if type(plan) is ChangePlan else None
        outer = current()
        if outer is not None and request.requested:
            supplied = _selection(outer)
            if selected is not None and supplied['owners'] and binding(selected) != supplied:
                from .changes.write_guard_values import require
                require(False, 'explicit_owner_plan_conflict', exit_code=6)
            if selected is None:
                selected = supplied
        with scope(ledger, selected):
            return function(root, plan, *args, **kwargs)
    return call


def invocation_scope(function):
    """A Python Force request has the same lexical boundary as a CLI request."""
    from functools import wraps
    @wraps(function)
    def call(*args, operational_binding=None, **kwargs):
        request = ForceRequest(kwargs.get('force', False), kwargs.get('force_reason'))
        outer = current()
        if operational_binding is None and outer is not None and request.requested:
            operational_binding = _selection(outer)
        with scope(ForceDecisions(request), operational_binding):
            return function(*args, **kwargs)
    return call


def _selection(call):
    """Detached typed projection shared by the two public scope adapters."""
    return {'owners': [{'path': path, 'sha256': digest} for path, digest in call.owners]}
