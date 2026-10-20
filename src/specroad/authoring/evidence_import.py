"""Explicit Generic Evidence sets using the shared saved-plan transaction.

The embedding host supplies existing bound original attachments, reserved IDs,
actor/time, project model and publication authority. No CLI or ID discovery.
"""
from hashlib import sha256

from ..changes import AuthoringError, TargetModel, prepare_authoring_request
from ..changes._lock_files import LockFiles
from ..changes.receipt_read import _read_confirmed_request, _CompletionProof
from ..changes.receipt_values import ReceiptError
from ..changes.evidence_import import prepare_generic_operations
from ..model.paths import project_path
from ..security import SafetyViolation
from ..storage.project import ProjectSource
from .plans import preview_authoring_request
from .execution import apply_authoring_plan, _replay


def resolve_generic_import_request(source, *, source_bytes, source_path, policy,
        title, actor, request_id, configuration_id=None):
    """Resolve a confirmed input retry BEFORE allocating IDs or building a model.

    Returns the original native execution result, or None when no confirmed
    request exists. A miss grants no authority: the saved-plan writer still
    rechecks receipts under its lock. Receipt/journal damage is never a miss.
    Supplied original bytes bind mapping and run declarations; this historical
    read does not attest today's subjects, attachments, configuration or tool.
    """
    try:
        return _resolve_generic_import_request(source, source_bytes=source_bytes,
            source_path=source_path, policy=policy, title=title, actor=actor,
            request_id=request_id, configuration_id=configuration_id)
    except SafetyViolation as error:
        raise ReceiptError('unsafe_evidence_import_receipt', exit_code=7) from error
    except OSError as error:
        raise ReceiptError('evidence_import_receipt_io_failure', exit_code=5) from error


def _resolve_generic_import_request(source, *, source_bytes, source_path, policy,
        title, actor, request_id, configuration_id):
    if (type(source) is not ProjectSource or type(source_bytes) is not bytes
            or type(policy) is not str or policy not in (
                'abort_import', 'skip_invalid_with_diagnostic')
            or type(title) is not str or not title.strip()
            or (configuration_id is not None and type(configuration_id) is not str)):
        raise AuthoringError('explicit_evidence_import_retry_inputs_required')
    project_path(source_path)
    intent = prepare_authoring_request(command_id='evidence import', actor=actor,
        operations=[], request_id=request_id).data
    identity = intent['request_id']
    if identity is None:
        return None
    receipt = _read_confirmed_request(source, identity)
    if receipt is None:
        return None
    with LockFiles(source.boundary.root) as files:
        proof = _CompletionProof(files, source, receipt.data['transaction_id'])
        value = proof.journal.data
        if value['receipts']['request'] != {'path': receipt.path, 'sha256': receipt.sha256}:
            raise AuthoringError('request_receipt_changed', exit_code=6)
        operations = value['authoring_binding']['operations']
        expected = {'format_version': 'evidence-import-context-v1', 'import_format': 'generic',
            'source_path': source_path, 'source_sha256': sha256(source_bytes).hexdigest(),
            'policy': policy}
        if not operations or any(op['op'] != 'evidence_record'
                or any(op.get('import_context', {}).get(k) != v for k, v in expected.items())
                or op.get('configuration_id') != configuration_id
                or op['evidence']['title'] != title for op in operations):
            raise AuthoringError('request_operations_conflict', pointer='/request_id', exit_code=6)
        # Use the original complete native operations, including reserved IDs,
        # preparation hash and historical audit. Never synthesize a receipt.
        request = prepare_authoring_request(command_id='evidence import', actor=intent['actor'],
            operations=operations, request_id=identity)
        result = _replay(source, request, 'evidence.import')
        proof.check()
        if result is None:
            raise AuthoringError('request_receipt_changed', exit_code=6)
        return result


def preview_generic_import(model, *, source_path, policy, evidence_ids, title,
        actor, planned_at, change_plan_id, configuration_id=None, request_id=None,
        gates=(), strict=False, fail_on_change=False):
    """Plan every accepted observation together; originals remain immutable.

    The initial writer profile requires a nonempty prepared Generic set with
    explicitly mapped Verification targets. Each original/imported attachment
    must already be supplied in the native model and match its live project bytes.
    No parser outcome grants external-run authentication or verification success.
    """
    if type(model) is not TargetModel:
        raise AuthoringError('typed_authoring_model_required')
    operations, preparation = prepare_generic_operations(model, source_path=source_path, policy=policy,
        evidence_ids=evidence_ids, title=title, configuration_id=configuration_id,
        actor=actor, planned_at=planned_at)
    result = preview_authoring_request(model, 'evidence.import', operations,
        actor=actor, planned_at=planned_at, change_plan_id=change_plan_id,
        request_id=request_id, gates=gates, strict=strict, fail_on_change=fail_on_change)
    return {**result, 'import_preparation': preparation}


def import_evidence(plan, model, *, transaction_id, authority, gates=(),
                    strict=False, package_files=()):
    """Publish the saved complete set, or replay its confirmed native request.

    Retry uses the original saved plan/IDs. The ordinary request hash binds all
    source/mapping/preparation bytes, policy, run/configuration and record values.
    No reallocation, new write, approval or currentness is claimed on replay.
    """
    return apply_authoring_plan(plan, model, command_id='evidence.import',
        transaction_id=transaction_id, authority=authority, gates=gates,
        strict=strict, package_files=package_files)
