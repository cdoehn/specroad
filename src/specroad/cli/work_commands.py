"""Installed Work routes; saved data selects no executable code or authority."""
from .contracts import (CommandClass, CommandProtocol, CommandSpec, EffectScope,
                        PositionalSpec, PreflightProfile, WorkContract)
from .parameters import OptionSpec


def restore_work_contract():
    return WorkContract('native_restore_phase', ('original_work_bindings',), True,
                        ('external_work_directory',), ('work-manifest-segments-v1',))


def _handle(invocation):
    from .work_handler import work_command
    return work_command(invocation)


def work_commands():
    from .commands import _read_runtime_options
    result = []
    display = (OptionSpec('--format', takes_value=True, choices=('pretty', 'json')),
               OptionSpec('--quiet'), OptionSpec('--no-color'))
    for operation in ('status', 'resume', 'prompt', 'export', 'restore', 'cancel'):
        position = 'file' if operation == 'restore' else 'work_dir'
        options = ()
        example = {}
        if operation in ('export', 'restore'):
            options = (OptionSpec('--output', takes_value=True, required=True),)
            example['--output'] = '/external/output'
        elif operation == 'cancel':
            options = (OptionSpec('--reason', takes_value=True, required=True),)
            example['--reason'] = 'Explicitly cancel pending preparation'
        elif operation == 'prompt':
            options = (OptionSpec('--max-prompt-chars', takes_value=True),)
        elif operation == 'resume':
            options = (OptionSpec('--project', takes_value=True),
                OptionSpec('--expected-work-lock-sha256', takes_value=True),
                OptionSpec('--work-recovery-reason', takes_value=True),
                OptionSpec('--force'), OptionSpec('--expected-lock-sha256', takes_value=True),
                OptionSpec('--reason', takes_value=True), OptionSpec('--accept-remote-risk'),
                *_read_runtime_options())
        result.append(CommandSpec(command_id='work.' + operation, words=('work', operation),
            command_class=CommandClass.WORK_OPERATIONAL, preflight_profile=PreflightProfile.INPUT_READ,
            effect_scope=EffectScope.EXTERNAL_WORK, handler=_handle,
            positionals=(PositionalSpec(position),), options=(*options, *display),
            budget_policy_version='runtime-budget-v2' if operation == 'resume' else None,
            protocol=CommandProtocol('work-command-v1', {'command_id': 'work.' + operation,
                'arguments': {position: '/external/work'}, 'options': example},
                handler_exit_codes=(0, 2, 3, 4, 5, 6, 7, 8) if operation == 'resume' else (0, 2, 3, 4, 5, 6, 7),
                work=restore_work_contract() if operation == 'resume' else WorkContract('work_' + operation))))
    return tuple(result)
