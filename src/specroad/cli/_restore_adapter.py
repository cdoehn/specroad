"""Renderer-free Restore invocation backed by the native plan/file/execution APIs.

The host supplies the existing RecoveryAuthority independently of request data.
This internal integration step does not register an incomplete public command,
invent a default authority, or claim Work/CLI release readiness.
"""
from ._restore_options import restore_request
from ..changes.recovery_values import RecoveryAuthority
from ..recovery import prepare_restore_plan, publish_restore_plan, read_restore_inputs, execute_restore
from ..recovery._inventory import boundary
from ..recovery.values import guarded, require


@guarded
def run_restore(value, *, authority=None, owner_probe=None, services=None):
    """Bind one fresh argv/request and return the actual native typed outcome.

    No saved resolved context or caller-selected preflight bypass is accepted.
    Original plan reading is passive: only the executor distinguishes an initial
    publication from completion/rollback of proven interrupted effects.
    """
    options = restore_request(value).options
    planning = '--from' in options
    if not planning:
        require(type(authority) is RecoveryAuthority, 'restore_authority_required', exit_code=2)
    project = boundary(options['--project'])
    if planning:
        # Reuse full independent identity/coverage checks, including damaged
        # current configuration. No ordinary ProjectSource or profile fallback.
        operational = ({'default_locale': options['--default-locale'],
                        'generated_path': options['--generated-path']}
                       if options['--source-kind'] == 'baseline' else {})
        plan = prepare_restore_plan(options['--project'], source_root=options['--source-root'],
            source_path=options['--from'], source_kind=options['--source-kind'], services=services, **operational)
        project._check_root()
        return publish_restore_plan(plan.source_bytes,
            output_root=options['--output-root'], output=options['--output'], services=services)
    plan, selection = read_restore_inputs(options['--plan-root'], options['--plan'],
        selection_root=options.get('--selection-root'), selection_path=options.get('--affected-journals'))
    require(str(project.root) == plan.data['project_root'], 'restore_project_binding_conflict', exit_code=6)
    project._check_root()
    return execute_restore(plan.source_bytes, expected_target_root=options['--expected-target-root'],
        authority=authority, actor={'actor_type': options['--actor-type'], 'actor_id': options['--actor-id']},
        request_id=options.get('--request-id'), affected_journals=selection,
        force=options.get('--force', False), expected_lock_sha256=options.get('--expected-lock-sha256'),
        reason=options.get('--reason'), accept_remote_risk=options.get('--accept-remote-risk', False),
        owner_probe=owner_probe, services=services)
