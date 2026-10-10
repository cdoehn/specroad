"""Checked, passive continuation instructions for the existing host adapters.

Stored project data never chooses executable code. The fixed host entrypoints
still require their own fresh checks; this module executes none of them. Work
CLI registration and portable package discovery are separate integration work.
"""

from hashlib import sha256

from ..changes.authoring import bind_plan_authoring
from ..changes.idempotency import resolve_normative_request
from ..cli.commands import builtin_registry
from ..model.canonical import canonical_json_bytes
from .control import _initial, _read
from ._prompt_rendering import _render
from .publication import _arguments, _checked_work, _source, _transaction_clear
from .receipt_files import _receipt
from .result_files import _ensure_work
from .resume import (_checked_plan, _compatible_read, _require, _runtime_build,
                     _saved_outcome, WorkResumeError)


def _limit(value):
    if type(value) is not int or value < 1000:
        raise WorkResumeError('invalid_max_prompt_chars', exit_code=2)


def _action(entrypoint, inputs, *, project_write=False):
    return {'kind': 'trusted_host_call', 'entrypoint': entrypoint,
        'required_inputs': inputs, 'project_write_possible': project_write,
        'required_approvals': ['current_publication_authority'] if project_write else [],
        'authorization_granted': False, 'fresh_validation_required': True}


def _contract(held, current, action, native):
    value = current.as_dict()
    binding = {key: value[key] for key in
               ('actor', 'request_id', 'operations_sha256', 'plan_binding', 'source_bindings')}
    return {'format_version': 'work-continuation-v1',
        **{key: value[key] for key in ('work_id', 'checkpoint_generation',
            'checkpoint_sha256', 'command_id', 'tool_build', 'progress')},
        'work_directory': str(held.path),
        'remaining_manifest': value['manifests']['remaining'],
        'original_binding_sha256': sha256(canonical_json_bytes(binding)).hexdigest(),
        'next_action': action, 'native_state': native,
        'work_cli_available': False, 'portable_package_verified': False,
        'success_requirements': ['complete_original_work', 'complete_required_gates',
            'verified_required_receipts', 'verified_result_delivery', 'confirmed_process_exit'],
        'process_outcome_confirmed': False, 'command_execution_performed': False,
        'project_writes_performed': False, 'work_writes_performed': False}



def read_only_work_prompt(store, *, max_prompt_chars=6000):
    """Describe one real closed handler/finalization step without executing it."""
    _limit(max_prompt_chars)
    registry, build = builtin_registry(), _runtime_build()
    _initial(store, build)
    _checked_plan(store._initial, registry, build)
    with store._location.inspect_checkpoint() as held:
        pointer, current = _read(store, held, build)
        checked, request, invocation, unit = _checked_plan(current, registry, build)
        _require(checked.as_dict()['state'] == 'running', 'work_has_no_continuation')
        if checked.entries('completed'):
            _compatible_read(_saved_outcome, checked, request, invocation, unit)
            operation = 'specroad.work.finalization.finalize_read_only_work'
        else:
            operation = 'specroad.work.resume.resume_read_only_work'
        value = _contract(held, current, _action(operation, ['store']),
                          {'status': 'not_applicable', 'current_target_verified': False})
        result = _render(value, max_prompt_chars)
        _ensure_work(store, held, pointer, current, build)
        return result


def _native_state(current, model, plan):
    # Original request receipts take precedence over stale preparation metadata.
    # No success or fresh publication is inferred merely from a Work checkpoint.
    _require(plan.data['request_id'] is not None, 'normative_prompt_requires_request_id')
    source = _source(model)
    resolution = resolve_normative_request(source, bind_plan_authoring(plan)).data
    if resolution['action'] == 'replay':
        raw = _receipt(current, model, plan)
        result = {'status': 'committed', 'request_resolution_sha256': sha256(raw).hexdigest(),
                  'current_target_verified': False}
    else:
        _require(resolution['action'] == 'new_request', 'normative_request_state_unavailable')
        _transaction_clear(model)
        result = {'status': 'unpublished', 'request_resolution_sha256': None,
                  'current_target_verified': False}
    source.check_current()
    return result


def normative_work_prompt(store, *, registry, model, policy, actor, request_id,
                          max_prompt_chars=6000):
    """Describe preparation, guarded publication, or existing receipt delivery.

    Original actor/request/project inputs are checked now and required again by
    the chosen host operation. Unresolved native transactions refuse an ordinary
    continuation. No authority callback, handler, native write or Recovery runs.
    """
    _limit(max_prompt_chars)
    build = _arguments(store, registry, model, policy, actor, request_id)
    with store._location.inspect_checkpoint() as held:
        pointer, current = _read(store, held, build)
        current, plan = _checked_work(current, registry, build)
        native = _native_state(current, model, plan)
        inputs = ['store', 'registry', 'model', 'policy', 'actor', 'request_id']
        if native['status'] == 'committed':
            operation = 'specroad.work.receipt_files.publish_normative_receipt_files'
            write = False
        elif current.entries('remaining'):
            operation = 'specroad.work.publication.advance_normative_preparation'
            write = False
        else:
            operation = 'specroad.work.publication.publish_normative_work'
            inputs += ['transaction_id', 'authority']
            write = True
        value = _contract(held, current, _action(operation, inputs, project_write=write), native)
        result = _render(value, max_prompt_chars)
        _ensure_work(store, held, pointer, current, build)
        _require(_native_state(current, model, plan) == native, 'normative_prompt_source_changed')
        _ensure_work(store, held, pointer, current, build)
        return result
