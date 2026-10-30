"""Pure Restore parameter declarations for registry and schema inspection."""
from .parameters import OptionSpec


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
