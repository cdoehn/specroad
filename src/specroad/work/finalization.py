"""Durably finalize the existing closed read-only handler plan."""

from dataclasses import dataclass

from ..cli.commands import builtin_registry
from ..cli.invocation_context import InvocationContextBuilder
from ..model.canonical import canonical_json_bytes
from ._data_contract import _parse
from .checkpoints import CheckpointStore
from .manifest import complete_work_manifest
from .resume import (_checked_plan, _compatible_read, _require, _runtime_build,
                     _saved_outcome)


def _checked_completion(current, request, invocation, unit_id):
    _require(not current.entries('remaining'), 'unfinished_work_cannot_complete')
    return _saved_outcome(current, request, invocation, unit_id)


@dataclass(frozen=True, init=False)
class ReadOnlyWorkCompletion:
    """A returned complete result after durable finalization, not a receipt."""

    manifest: object
    outcome_bytes: bytes
    command_exit_code: int
    finalized: bool

    def __init__(self, *args, **kwargs):
        raise TypeError('Use finalize_read_only_work')

    def as_dict(self):
        value = self.manifest.as_dict()
        return {'format_version': 'read-only-work-completion-v1', 'work_id': value['work_id'],
            'checkpoint_generation': value['checkpoint_generation'],
            'checkpoint_sha256': value['checkpoint_sha256'], 'work_state': value['state'],
            'next_action': value['next_action'], 'finalized': self.finalized,
            'command_exit_code': self.command_exit_code, 'command_outcome': _parse(self.outcome_bytes),
            'semantic_receipt_created': False, 'project_writes_performed': False}


def finalize_read_only_work(store, *, cwd=None):
    """Check all saved handler work, persist its full result, then return it.

    This adapter accepts only the independently bound closed bootstrap plan.
    No output, diagnostic, pending unit or global phase can be supplied as an
    override. Generic planner candidates remain data, not live completion proof.
    """
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    registry, build = builtin_registry(), _runtime_build()
    initial, _, _, _ = _checked_plan(store._initial, registry, build)
    _require(initial.as_dict()['checkpoint_generation'] == 0
             and not initial.entries('completed'), 'initial_work_required')
    current = _compatible_read(store.read)
    _require(current is not None, 'published_work_required')
    checked, request, invocation, unit_id = _checked_plan(current, registry, build)
    _require(checked.as_dict()['state'] in ('running', 'completed'), 'work_cannot_complete')
    _compatible_read(_checked_completion, checked, request, invocation, unit_id)
    saved = {}

    def finish(previous):
        current, request, invocation, unit_id = _checked_plan(previous, registry, _runtime_build())
        _require(current.as_dict()['state'] in ('running', 'completed'), 'work_cannot_complete')
        InvocationContextBuilder().prepare(invocation, cwd=cwd)
        outcome, exit_code = _checked_completion(current, request, invocation, unit_id)
        _require(_runtime_build() == build, 'runtime_build_changed')
        finalized = current.as_dict()['state'] != 'completed'
        saved.update(outcome=outcome, exit_code=exit_code, finalized=finalized)
        return complete_work_manifest(current, outcome, exit_code=exit_code) if finalized else previous

    confirmed = _compatible_read(store._update, finish)
    # Publication can succeed before a later compatibility failure is noticed.
    # Preserve that actual generation, but never return a stale runtime claim.
    _require(_runtime_build() == build, 'runtime_build_changed')
    result = object.__new__(ReadOnlyWorkCompletion)
    object.__setattr__(result, 'manifest', confirmed)
    object.__setattr__(result, 'outcome_bytes', canonical_json_bytes(saved['outcome']))
    object.__setattr__(result, 'command_exit_code', saved['exit_code'])
    object.__setattr__(result, 'finalized', saved['finalized'])
    return result
