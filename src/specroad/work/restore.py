"""Passive Restore execution checkpoints, not a published Work execution engine.

The trusted host supplies its registered command and complete finite unit plan.
No handler is invoked, no project or external transport path is opened, and no
saved lock/actor/authority is accepted as current permission to restore.
"""
from ..cli._restore_options import restore_request
from ..recovery.values import RestoreError, guarded, persisted_contract, require
from ._request_binding import _command
from ._restore_binding import plan_values
from .manifest import _create_manifest, read_work_manifest


@guarded
@persisted_contract
def create_restore_work_manifest(registry, request, *, plan, tool_build, units,
                                 affected_journals=None):
    """Retain original execution bytes; planning and execution remain separate."""
    request = restore_request(request)
    require(('--affected-journals' in request.options) == (affected_journals is not None),
            'restore_work_selection_bytes_required', exit_code=2)
    command = _command(registry, request, recovery=True)
    metadata, sources, inputs = plan_values(plan, request, affected_journals)
    return _create_manifest(registry, command, tool_build=tool_build,
        source_bindings=sources, inputs=inputs, units=units, authoring=metadata)


@guarded
@persisted_contract
def read_restore_work_manifest(raw, objects, *, registry, expected_tool_build):
    """Check saved Restore data with native Restore diagnostics; never execute it.

    This standalone reader does not authenticate a new work identity. Durable
    continuation still needs CheckpointStore's independently trusted initial
    generation and immutable successor checks, then fresh native Restore gates.
    """
    try:
        manifest = read_work_manifest(raw, objects, registry=registry, expected_tool_build=expected_tool_build)
    except RestoreError as error:
        if error.exit_code == 2:
            # This is a malformed saved request, not a new incomplete CLI call.
            raise RestoreError('restore_work_saved_request_invalid') from error
        raise
    value = manifest.as_dict()
    require(value['command_id'] == 'recover.restore' and value['command_class'] == 'recovery_write',
            'restore_work_command_invalid')
    return manifest
