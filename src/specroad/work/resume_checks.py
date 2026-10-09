"""Fresh read-only checks of a saved normative plan; never write authorization.

The trusted host supplies its actual registry, current model and policy. No
handler is executed, no plan is rebased and no project/work file is modified.
The existing native-lock publication gate remains mandatory for later Apply.
"""

from dataclasses import dataclass
from pathlib import Path

from ..changes.authoring import normalize_authoring_actor
from ..changes.publication_check import prepare_publication_check
from ..changes.publication_values import PublicationCheckError
from ..changes.request_ids import normalize_request_id
from ..changes.target_model import TargetModel
from ..changes.target_values import TargetPolicy
from ._normative_binding import read_plan
from ._resume_restore import check_initial_normative, restore_normative_checkpoint
from .checkpoints import CheckpointStore
from .resume import WorkResumeError, _runtime_build, _require, _compatible_read


@dataclass(frozen=True, init=False)
class NormativeResumeCheck:
    """Original plan and current early diagnostics, not a reusable capability."""

    manifest: object
    plan: object
    preflight: object

    def __init__(self, *args, **kwargs):
        raise TypeError('Use prepare_normative_resume')

    def as_dict(self):
        value = self.manifest.as_dict()
        return {'format_version': 'normative-resume-check-v1',
                'work_id': value['work_id'], 'checkpoint_generation': value['checkpoint_generation'],
                'checkpoint_sha256': value['checkpoint_sha256'], 'actor': value['actor'],
                'request_id': value['request_id'], 'operations_sha256': value['operations_sha256'],
                'plan_binding': value['plan_binding'], 'preflight': self.preflight.data,
                'write_authorized': False, 'final_locked_check_required': True,
                'normative_writes': 0, 'checkpoint_changed': False}

    def __bool__(self):
        raise TypeError('A resume check does not authorize publication')


def _check_current_target(current, *, model, policy, current_actor, current_request,
                          gates, strict, package_files):
    """Recheck current identities, target basis and rights against the saved plan."""
    value = current.as_dict()
    _require(current_actor == value['actor'], 'resume_actor_changed')
    _require(current_request == value['request_id'], 'resume_request_changed')
    _require(model.binding.project_id == value['source_bindings']['project_id'],
             'resume_project_changed')
    plan = read_plan(value, current.objects)
    try:
        preflight = prepare_publication_check(plan, model, policy=policy, gates=gates,
                                              strict=strict, package_files=package_files)
    except PublicationCheckError as error:
        if error.reason == 'target_base_root_mismatch':
            raise WorkResumeError('stale_resume_target', exit_code=6) from error
        raise
    return plan, preflight


def prepare_normative_resume(store, *, registry, model, policy, actor, request_id,
                             gates=(), strict=False, package_files=()):
    """Recheck original authoring identity and actual current target bytes.

    An explicit current actor or request mismatch is a conflict, not an override.
    The supplied registry is trusted host code; only its data contract is bound.
    Actual authorization, native writer lock and final recheck stay with Apply.
    """
    _require(type(store) is CheckpointStore, 'trusted_work_store_required')
    _require(type(model) is TargetModel and type(policy) is TargetPolicy,
             'current_resume_model_and_policy_required')
    build = _runtime_build()
    check_initial_normative(store, registry, build)
    if not any(boundary.root == Path(model.binding.source_root)
               for boundary in store._location._protected):
        raise WorkResumeError('unprotected_resume_target', exit_code=7)
    current_actor = normalize_authoring_actor(actor).as_fields()
    identity = normalize_request_id(request_id)
    current_request = None if identity is None else identity.value
    with store._location.inspect_checkpoint() as held:
        pointer, current = restore_normative_checkpoint(store, held, registry, build)
        plan, preflight = _check_current_target(current, model=model, policy=policy,
            current_actor=current_actor, current_request=current_request,
            gates=gates, strict=strict, package_files=package_files)
        _require(_runtime_build() == build, 'runtime_build_changed')
        _require(store._pointer(held) == pointer, 'checkpoint_pointer_changed')
        _require(_compatible_read(store._read_chain, held, pointer[0]).raw == current.raw,
                 'checkpoint_bytes_changed')
        _require(store._pointer(held) == pointer, 'checkpoint_pointer_changed')
        held.check()
        result = object.__new__(NormativeResumeCheck)
        for name, content in (('manifest', current), ('plan', plan), ('preflight', preflight)):
            object.__setattr__(result, name, content)
        return result
