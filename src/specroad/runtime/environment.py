"""Current environment diagnosis; no semantic model, probes or target execution."""
from . import check_runtime, UnsupportedRuntimeError
from .identity import version_info, BuildMetadataError
from .resource_observations import resource_observations
from .resource_profiles import profile_targets


def environment_report(invocation):
    """Return a complete diagnosis and its actual error class, never a write lease."""
    options, registry = invocation.options, invocation.registry
    target = registry.resolve_selector(options['--for-command']) if '--for-command' in options else None
    root = invocation.resolved.project_root
    checks = []

    def check(name, state, reason, *, required=True, code=0):
        checks.append({'check_id': name, 'required': required, 'state': state,
                       'reason': reason, 'exit_code': code})

    try:
        check_runtime()
    except UnsupportedRuntimeError:
        check('runtime.python', 'failed', 'unsupported_runtime', code=5)
    else:
        check('runtime.python', 'passed', 'supported_executable_runtime')
    try:
        identity = version_info()
    except BuildMetadataError:
        # Runtime identity is independent of the unusable generated build record.
        import sys
        python = {'implementation': sys.implementation.name,
                  'python_version': '.'.join(map(str, sys.version_info[:3])),
                  'supported': not any(c['state'] == 'failed' for c in checks)}
        distribution = {'distribution_kind': 'unknown', 'build_id': None, 'build_sha256': None,
                        'build_identity_status': 'unavailable', 'release_approved': False}
        check('distribution.metadata', 'failed', 'invalid_distribution_metadata', code=5)
    else:
        python = {**identity['runtime'], 'support': identity['python_support'],
                  'supported': not any(c['state'] == 'failed' for c in checks)}
        distribution = {k: identity[k] for k in ('distribution_kind', 'build_id', 'build_sha256',
                                                'build_identity_status', 'release_approved')}
        check('distribution.metadata', 'passed', 'current_distribution_metadata')

    recovery_required = None
    metadata = None
    if root is not None:
        from ..security import ProjectBoundary, SafetyViolation
        from ..model.errors import ModelError
        from ..storage.json_reader import JsonResource, configuration_schema
        from ..storage.operational_preflight import observe_operational_preflight
        from ..storage.preflight_metadata import MetadataPhases
        ledger = MetadataPhases()
        try:
            boundary = ProjectBoundary(root)
            raw = ledger.read_bytes(boundary, 'specroad.json')
            JsonResource(raw, configuration_schema(), path='specroad.json')
            observed = observe_operational_preflight(boundary, metadata=ledger)
            if observe_operational_preflight(boundary, metadata=ledger) != observed:
                check('project.metadata', 'failed', 'project_metadata_changed', code=6)
            elif ledger.read_bytes(boundary, 'specroad.json') != raw:
                check('project.metadata', 'failed', 'project_configuration_changed', code=6)
            else:
                check('project.metadata', 'passed', 'current_configuration_readable')
                blocked = observed['consistency_state'] != 'consistent'
                # An unclassified entry or uninspected writer is a blocker,
                # but does not establish that a recoverable journal exists.
                recovery_required = True if observed['recovery_required'] else None if blocked else False
                reason = ('recovery_required' if recovery_required else
                          'operational_state_unknown' if blocked else 'no_active_conflict_observed')
                check('project.operational', 'failed' if blocked else 'passed', reason,
                      code=5 if blocked else 0)
        except ModelError as error:
            check('project.metadata', 'failed', error.reason, code=3)
        except SafetyViolation:
            check('project.metadata', 'failed', 'unsafe_project_metadata', code=7)
        except OSError:
            check('project.metadata', 'failed', 'project_metadata_unavailable', code=5)
        metadata = ledger.summary()
    else:
        check('project.metadata', 'not_applicable', 'no_explicit_project_selected', required=False)

    if target is not None:
        from ..cli.contracts import EffectScope, PreflightProfile
        target_options = {} if root is None else {'--project': str(root)}
        profile = target.preflight_for(target_options)
        needs_project = target.requires_project or profile in (
            PreflightProfile.PROJECT_READ, PreflightProfile.PROJECT_WRITE, PreflightProfile.RECOVERY)
        check('command.project', 'unknown' if needs_project and root is None else
              'passed' if needs_project else 'not_applicable',
              'explicit_project_missing' if needs_project and root is None else
              'explicit_project_selected' if needs_project else 'project_not_required', required=needs_project)
        missing = bool(any(p.required for p in target.positionals)
                       or any(o.required and o.flag != '--project' for o in target.options))
        check('command.arguments', 'unknown' if missing else 'passed',
              'target_arguments_not_supplied' if missing else 'no_required_target_arguments')
        check('command.git', 'unknown' if target.requires_git else 'not_applicable',
              'git_not_probed' if target.requires_git else 'git_not_required', required=target.requires_git)
        write = bool(target.effect_scope is not EffectScope.NONE or target.requires_write_paths or profile in (
            PreflightProfile.PROJECT_WRITE, PreflightProfile.ROOT_CREATION, PreflightProfile.RECOVERY))
        check('command.write_paths', 'unknown' if write else 'not_applicable',
              'write_capability_not_probed' if write else 'write_paths_not_required', required=write)

    observations = resource_observations()
    for name, observation in observations.items():
        check('resources.' + name, 'passed' if observation['state'] == 'observed' else 'unknown',
              'qualified_process_limit' if observation['state'] == 'observed' else 'no_trustworthy_quota',
              required=False)
    failed = [c for c in checks if c['required'] and c['state'] == 'failed']
    unknown = any(c['required'] and c['state'] == 'unknown' for c in checks)
    compatible = False if failed else None if unknown else True
    result = {'environment_format_version': '1.0.0', 'compatible': compatible,
              'operation_readiness': 'not_requested' if target is None else
                  'blocked' if failed else 'unknown' if unknown else 'ready',
              'python': python, 'distribution': distribution,
              'checks': sorted(checks, key=lambda c: c['check_id']),
              'recovery_required': recovery_required,
              'resource_policy': profile_targets(options.get('--resource-profile', 'constrained'),
                  source='cli' if '--resource-profile' in options else 'default'),
              'observations': observations, 'semantic_validation_performed': False,
              'target_command_id': None if target is None else target.command_id,
              'metadata': metadata}
    return result, failed[0]['exit_code'] if failed else 0
