"""Only completed built-in commands are installed in the runtime registry."""

from .registry import CommandClass, CommandRegistry, CommandSpec, EffectScope, PreflightProfile


def _help(invocation) -> int:
    return 0


def builtin_registry() -> CommandRegistry:
    return CommandRegistry((CommandSpec(
        command_id="help", words=("--help",), aliases=(("-h",),),
        command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.BOOTSTRAP,
        effect_scope=EffectScope.NONE, handler=_help,
    ),))
