"""Explicit Evidence input for the shared preview and saved-plan writer.

The embedding host supplies the complete native record, reserved identity,
actor/time and model. Its bindings are recomputed by the Evidence planner.
This input adapter does not register a CLI writer or discover project history.
"""
from ..changes import AuthoringError, ChangeOperation
from ..changes._common import _reference
from ..cli._arguments import bind_options
from ..cli.command_errors import CommandUsageError
from ..cli.parameters import OptionSpec
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..security import SafetyViolation
from ..storage.json_syntax import parse_json_object
from ..storage.record_artifact import RecordArtifact
from .inputs import _read_input


def _verification_reference(verification_id):
    identity = _reference(verification_id, '/verification_id')
    if identity.artifact_type != 'verification':
        raise AuthoringError('verification_reference_required', pointer='/verification_id', exit_code=3)


def prepare_evidence_operation(verification_id, record, *, configuration_id=None):
    """Bind a prepared immutable record to its explicitly named contract.

    Use preview_authoring_request(..., 'evidence.record', ...) and then
    apply_authoring_plan with that same command and saved plan. No allocation,
    successful verification, authorization or durable publication is implied.
    """
    if type(record) is not RecordArtifact:
        raise AuthoringError('typed_evidence_record_required')
    _verification_reference(verification_id)
    value = RecordArtifact(record.source_bytes, expected_type='evidence').data
    contracts = [item['artifact_id'] for item in value['subjects']
                 if _reference(item['artifact_id'], '/subjects').artifact_type == 'verification']
    if contracts != [verification_id]:
        raise AuthoringError('evidence_verification_binding_mismatch', exit_code=3)
    return ChangeOperation({'op': 'evidence_record', 'evidence': value,
                            'configuration_id': configuration_id})


def preview_evidence_record(model, verification_id, record, *, actor, planned_at,
        change_plan_id, configuration_id=None, request_id=None, gates=(), strict=False,
        fail_on_change=False):
    """Prepare a read-only saveable plan for the explicitly supplied record."""
    from .plans import preview_authoring_request
    operation = prepare_evidence_operation(verification_id, record, configuration_id=configuration_id)
    return preview_authoring_request(model, 'evidence.record', [operation.data],
        actor=actor, planned_at=planned_at, change_plan_id=change_plan_id,
        request_id=request_id, gates=gates, strict=strict, fail_on_change=fail_on_change)


def record_evidence(plan, model, *, transaction_id, authority, gates=(),
                    strict=False, package_files=()):
    """Publish exactly the checked saved plan via the existing native writer."""
    from .execution import apply_authoring_plan
    return apply_authoring_plan(plan, model, command_id='evidence.record',
        transaction_id=transaction_id, authority=authority, gates=gates,
        strict=strict, package_files=package_files)


def _input_record(input, run_context, cwd, stdin):
    """Decode explicit inputs through the shared reader, without planning writes."""
    value = parse_json_object(_read_input(input, cwd, stdin))
    if run_context is not None:
        run = parse_json_object(_read_input(run_context, cwd, stdin))
        if 'run_context' in value and canonical_json_bytes(value['run_context']) != canonical_json_bytes(run):
            raise AuthoringError('evidence_run_context_conflict', pointer='/run_context', exit_code=3)
        value['run_context'] = run
    elif 'run_context' not in value:
        reason = value.get('unbound_reason')
        if type(reason) is not str or not reason.strip():
            raise AuthoringError('evidence_unbound_reason_required', pointer='/unbound_reason', exit_code=3)
        value['run_context'] = None
    return RecordArtifact(canonical_json_bytes(value), expected_type='evidence')


def read_evidence_record_input(verification_id, *, input, run_context=None,
                               configuration_id=None, cwd=None, stdin=None):
    """Read explicit record/run JSON; bind contents, never paths or implicit stdin.

    --run-context can supply an absent run_context field or repeat an identical
    one. It cannot overwrite contrary measured provenance, including null.
    An omitted context without a run file becomes null only when the caller
    supplied a nonblank unbound_reason. Partial run objects are never filled in.
    Attachments are declarations for existing project bytes, not file imports.
    """
    if input == '-' and run_context == '-':
        raise AuthoringError('multiple_stdin_inputs')
    try:
        # Validate explicit operand identities before consuming either input.
        _verification_reference(verification_id)
        if configuration_id is not None:
            identity = _reference(configuration_id, '/configuration_id')
            if identity.artifact_type != 'configuration':
                raise AuthoringError('configuration_reference_required', pointer='/configuration_id', exit_code=3)
        record = _input_record(input, run_context, cwd, stdin)
        return prepare_evidence_operation(verification_id, record, configuration_id=configuration_id)
    except AuthoringError:
        raise
    except ModelError as error:
        raise AuthoringError(error.reason, pointer=error.pointer, exit_code=3) from error
    except SafetyViolation as error:
        raise AuthoringError('unsafe_evidence_input', exit_code=7) from error
    except OSError as error:
        raise AuthoringError('evidence_input_io', exit_code=5) from error


def parse_evidence_record_input(argv, *, cwd=None, stdin=None):
    """Bind VERIFICATION-ID --input FILE|- [--run-context FILE] for a host."""
    if (type(argv) not in (list, tuple) or not argv
            or any(type(item) is not str for item in argv)):
        raise AuthoringError('evidence_record_arguments_required')
    try:
        options = tuple(OptionSpec(flag, takes_value=True)
                        for flag in ('--input', '--run-context', '--configuration'))
        bound, _ = bind_options(argv, (argv[0],), options)
        if '--input' not in bound:
            raise AuthoringError('evidence_record_input_required')
        return read_evidence_record_input(argv[0], input=bound['--input'],
            run_context=bound.get('--run-context'), configuration_id=bound.get('--configuration'),
            cwd=cwd, stdin=stdin)
    except CommandUsageError as error:
        raise AuthoringError('invalid_evidence_record_options') from error
