"""Separate early diagnostics from the mandatory native-lock publication gate.

Each final call reruns plan, authority and live-input checks. Early results and
final observations are never reusable write capabilities. A trusted backend
still owns actual publication, journals, receipts and durable readback.
"""
import os
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from .execution_values import ChangeExecutionError, PublicationRequest
from .locking import HeldProjectLock
from .lock_values import ProjectLockError
from .target import assess_change_target
from .target_model import TargetModel
from .target_values import TargetPolicy
from .values import ChangePlan
from .publication_values import (CHECK_VERSION, PublicationCheckError,
    PublicationAuthority, PublicationPreflight, PublicationRecheck)
from ._publication_observation import _root, _package_bindings, observe_publication_files

_ACCESS_SUPPORTED = os.access in os.supports_dir_fd and os.access in os.supports_effective_ids

def _rights(fd, path):
    # Advisory even under a cooperating writer lock: actual publication still
    # needs error handling for ACL/mount changes, quotas, ENOSPC and I/O errors.
    if not _ACCESS_SUPPORTED:
        raise PublicationCheckError('effective_permission_probe_unavailable', exit_code=7, path=path)
    mode = os.fstat(fd).st_mode
    if not mode & 0o222 or not mode & 0o111 or not os.access(
            '.', os.W_OK | os.X_OK, dir_fd=fd, effective_ids=True):
        raise PublicationCheckError('publication_parent_not_writable', exit_code=7, path=path)
    if hasattr(os, 'fstatvfs') and os.fstatvfs(fd).f_flag & getattr(os, 'ST_RDONLY', 1):
        raise PublicationCheckError('publication_mount_read_only', exit_code=7, path=path)


def _observe(source, model, request, package_files=()):
    return observe_publication_files(source, model, request, package_files, check_rights=_rights)


def _translate(error):
    if isinstance(error, PublicationCheckError):
        return error
    if isinstance(error, ProjectLockError):
        return PublicationCheckError(error.reason, exit_code=error.exit_code)
    if isinstance(error, PermissionError):
        return PublicationCheckError('publication_permission_denied', exit_code=7)
    if isinstance(error, FileNotFoundError):
        return PublicationCheckError('publication_resource_missing')
    if isinstance(error, ModelError):
        code = 6 if error.reason in ('configuration_changed', 'project_identity_mismatch') else 3
        return PublicationCheckError(error.reason, exit_code=code)
    if isinstance(error, SafetyViolation):
        return PublicationCheckError('unsafe_publication_path', exit_code=7)
    return PublicationCheckError('publication_check_io_failure', exit_code=5)


def _same_request(actual, expected):
    if (type(actual) is not PublicationRequest or actual._encoded != expected._encoded
            or actual._plan_bytes != expected._plan_bytes or actual.documents != expected.documents):
        raise PublicationCheckError('publication_request_changed')


def prepare_publication_check(plan, model, *, policy, gates=(), strict=False, package_files=()):
    """Early read-only diagnostic. Does not acquire any lock or create paths.

    Captures complete current normative JSON names and all explicitly bound raw
    resource bytes. A journal/authorization/permission observation now cannot
    replace the mandatory fresh checks at the later publication boundary.
    """
    if type(plan) is not ChangePlan or type(model) is not TargetModel or type(policy) is not TargetPolicy:
        raise PublicationCheckError('publication_plan_model_policy_required', exit_code=2)
    if type(gates) not in (list, tuple) or type(strict) is not bool:
        raise PublicationCheckError('publication_explicit_options_required', exit_code=2)
    plan, model = ChangePlan(plan.source_bytes), model.snapshot()
    try:
        source = _root(model)
        package_files = _package_bindings(source, model, package_files)
        checked = assess_change_target(plan, model, policy=policy, gates=tuple(gates), strict=strict)
        if not checked.target_validated:
            raise PublicationCheckError('publication_target_not_validated', exit_code=3)
        request = PublicationRequest._create(checked, model)
        first = _observe(source, model, request, package_files)
        if first != _observe(source, model, request, package_files):
            raise PublicationCheckError('publication_inputs_changed')
        return PublicationPreflight._create(request, model, policy, strict, first, package_files)
    except (OSError, SafetyViolation, ModelError) as error:
        if isinstance(error, PublicationCheckError):
            raise
        raise _translate(error) from error


def _require_uncompleted_request(source, request):
    # A prior absence observation never reserves an ID. Repeat under the real
    # writer lock, including after trusted callbacks, before any journal/write.
    from .authoring import bind_plan_authoring
    from .idempotency import resolve_normative_request
    from .receipt_values import ReceiptError
    try:
        decision = resolve_normative_request(source, bind_plan_authoring(request.plan))
    except ReceiptError as error:
        raise PublicationCheckError(error.reason, exit_code=error.exit_code, path=error.path) from error
    if decision.data['action'] == 'replay':
        raise PublicationCheckError('completed_request_requires_replay', exit_code=6)


def recheck_publication(preflight, request, *, held_lock, transaction_id,
                        authority, gates=()):
    """Recompute under the SAME native writer lock, never silently rebase.

    The trusted host is reauthorized and target gates rerun. Afterwards all raw
    bytes, current JSON names, parents, permissions, root, owner and recovery
    state are checked again. Returned observations cannot be used for a later
    write without another fresh check. No file mutation occurs here.
    """
    if type(preflight) is not PublicationPreflight or type(held_lock) is not HeldProjectLock:
        raise PublicationCheckError('preflight_and_native_writer_lock_required', exit_code=2)
    if type(authority) is not PublicationAuthority or type(gates) not in (tuple, list):
        raise PublicationCheckError('registered_authority_and_gates_required', exit_code=2)
    _same_request(request, preflight._request)
    model, plan = preflight._model.snapshot(), preflight._request.plan
    package_files = preflight._package_files
    try:
        source = _root(model)
        def lock_check():
            held_lock.require_publication(source, command='change apply',
                request_id=plan.data['request_id'], transaction_id=transaction_id)
        lock_check()
        _require_uncompleted_request(source, request)
        first = _observe(source, model, request, package_files)
        if canonical_json_bytes(first) != preflight._footprint:
            raise PublicationCheckError('publication_footprint_changed')
        checked = assess_change_target(plan, model, policy=preflight._policy,
                                      gates=tuple(gates), strict=preflight._strict)
        if not checked.target_validated:
            raise PublicationCheckError('publication_target_not_validated', exit_code=3)
        _same_request(PublicationRequest._create(checked, model), preflight._request)
        handoff = request.detached()
        try:
            allowed = authority.check(handoff)
        except Exception as error:
            raise PublicationCheckError('publication_authority_failed', exit_code=7) from error
        _same_request(handoff, preflight._request)
        if type(allowed) is not bool or not allowed:
            raise PublicationCheckError('publication_authorization_denied', exit_code=7)
        lock_check()
        _require_uncompleted_request(source, request)
        # Last complete read, after callbacks and immediately before the boundary.
        if canonical_json_bytes(_observe(source, model, request, package_files)) != preflight._footprint:
            raise PublicationCheckError('publication_footprint_changed')
        _same_request(request, preflight._request)
        lock_check()
        return PublicationRecheck._create(request, held_lock, authority)
    except (OSError, SafetyViolation, ModelError) as error:
        if isinstance(error, PublicationCheckError):
            raise
        raise _translate(error) from error


def publish_after_recheck(preflight, request, *, held_lock, transaction_id,
                          authority, publish, gates=()):
    """Invoke trusted host publication directly after the mandatory last check.

    The host retains the actual lock for staging/publication/readback, journal,
    recovery and durable receipt work. No built-in file writer is installed.
    The returned callback value is NOT a durable-commit or target-readback proof.
    This adapter can be used by ChangeBackend.publish; its existing receipt and
    target readback validation still apply. Never retries or rolls back.
    """
    if not callable(publish):
        raise PublicationCheckError('registered_publisher_required', exit_code=2)
    recheck_publication(preflight, request, held_lock=held_lock,
        transaction_id=transaction_id, authority=authority, gates=gates)
    outgoing = request.detached()
    try:
        result = publish(outgoing)
        _same_request(outgoing, preflight._request)
        held_lock.check()
        return result
    except Exception as error:
        reason = error.reason if isinstance(error, ChangeExecutionError) else 'publication_callback_failed'
        raise PublicationCheckError(reason, exit_code=5, write_state='unknown') from error
