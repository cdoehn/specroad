"""Bind the explicit Restore modes through the existing CLI/data vocabulary.

This is the shared internal adapter, not a published registry capability or
a serialized authority. No project, environment or previous call supplies
missing options. Public registration and Work integration remain separate.
"""
from ._arguments import bind_options, bind_values
from .command_errors import CommandUsageError
from .parameters import OptionSpec
from .requests import CommandRequest
from ..changes.authoring import normalize_authoring_actor, normalize_request_id
from ..changes._journal_codec import _hash
from ..recovery._codec import root_path, safe_path
from ..recovery._execution_lock import takeover_options
from ..recovery.values import RestoreError, guarded, require


_PLAN = frozenset(('--from', '--source-root', '--source-kind', '--dry-run',
                   '--output-root', '--output', '--default-locale', '--generated-path'))
_EXECUTE = frozenset(('--plan-root', '--plan', '--expected-target-root', '--actor-type',
                      '--actor-id', '--request-id', '--selection-root', '--affected-journals',
                      '--force', '--expected-lock-sha256', '--reason', '--accept-remote-risk'))
_PLAN_REQUIRED = _PLAN - {'--default-locale', '--generated-path'}
_EXECUTE_REQUIRED = frozenset(('--plan-root', '--plan', '--expected-target-root',
                              '--actor-type', '--actor-id'))
_ROOTS = frozenset(('--project', '--source-root', '--output-root', '--plan-root', '--selection-root'))
_PATHS = frozenset(('--from', '--output', '--plan', '--affected-journals'))
_FLAGS = frozenset(('--dry-run', '--force', '--accept-remote-risk'))
_CHOICES = {'--source-kind': ('project_bundle', 'baseline'),
            '--actor-type': ('human', 'tool', 'ai', 'ci')}

RESTORE_OPTIONS = tuple(OptionSpec(flag, takes_value=flag not in _FLAGS,
    required=flag == '--project', choices=_CHOICES.get(flag, ()))
    for flag in sorted(_PLAN | _EXECUTE | {'--project'}))


@guarded
def restore_request(value):
    """Return an owned request after syntax and mode checks, without file I/O."""
    try:
        if isinstance(value, (list, tuple)):
            if not value or not all(type(v) is str and v and '\0' not in v for v in value):
                raise CommandUsageError('Invalid Restore argument vector')
            options, arguments = bind_options(tuple(value), ('recover', 'restore'), RESTORE_OPTIONS)
            request = CommandRequest('recover.restore', options, arguments)
        else:
            request = value if type(value) is CommandRequest else CommandRequest.from_mapping(value)
            if request.command_id != 'recover.restore' or request.arguments:
                raise CommandUsageError('An explicit Restore request is required')
            request = CommandRequest(request.command_id, bind_values(request.options, RESTORE_OPTIONS))
    except CommandUsageError as error:
        raise RestoreError('restore_call_invalid', exit_code=2) from error
    options = request.options
    planning = '--from' in options
    required, forbidden = (_PLAN_REQUIRED, _EXECUTE) if planning else (_EXECUTE_REQUIRED, _PLAN)
    require(required <= options.keys() and not forbidden.intersection(options),
            'restore_call_mode_invalid', exit_code=2)
    if planning:
        supplied = {'--default-locale', '--generated-path'}.intersection(options)
        required_operational = {'--default-locale', '--generated-path'} if options['--source-kind'] == 'baseline' else set()
        require(supplied == required_operational, 'restore_call_operational_invalid', exit_code=2)
    else:
        require(('--selection-root' in options) == ('--affected-journals' in options),
                'restore_selection_file_required', exit_code=2)
        require(_hash(options['--expected-target-root']), 'restore_expected_target_required', exit_code=2)
        actor = normalize_authoring_actor({'actor_type': options['--actor-type'], 'actor_id': options['--actor-id']})
        request_id = normalize_request_id(options.get('--request-id'))
        require(actor.actor_type not in ('ai', 'ci') or request_id is not None,
                'restore_request_id_required', exit_code=2)
        takeover_options(options.get('--force', False), options.get('--expected-lock-sha256'),
                         options.get('--reason'), options.get('--accept-remote-risk', False))
    for flag in _ROOTS.intersection(options):
        root_path(options[flag])
    for flag in _PATHS.intersection(options):
        safe_path(options[flag])
    return request
