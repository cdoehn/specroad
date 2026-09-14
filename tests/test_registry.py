"""Command behavior and metadata contracts, never human-readable output."""

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from specroad.cli.application import dispatch
from specroad.cli.commands import builtin_registry
from specroad.cli.registry import (
    CommandClass, CommandRegistry, CommandSpec, CommandUsageError,
    EffectScope, OptionSpec, PreflightProfile,
)


def read_command(handler, **changes):
    command = CommandSpec(
        command_id="fixture.read", words=("fixture", "read"),
        command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.PROJECT_METADATA,
        effect_scope=EffectScope.NONE, requires_project=True, handler=handler,
    )
    return replace(command, **changes)


class RegistryWorkTests(unittest.TestCase):
    def test_resolves_real_bootstrap_and_executes_read_only_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input"
            source.write_bytes(b"unchanged")
            read_values = []
            reader = read_command(lambda invocation: read_values.append(source.read_bytes()) or 0)
            registry = CommandRegistry((*builtin_registry().commands, reader))
            self.assertEqual(registry.resolve("help").preflight_profile, PreflightProfile.BOOTSTRAP)
            self.assertEqual(registry.resolve("fixture.read").command_class, CommandClass.READ_ONLY)
            self.assertEqual(registry.invoke(["--help"]), 0)
            self.assertEqual(registry.invoke(["fixture", "read"]), 0)
            self.assertEqual(read_values, [b"unchanged"])
            self.assertEqual(source.read_bytes(), b"unchanged")
            self.assertEqual({path.name for path in Path(tmp).iterdir()}, {"input"})

    def test_option_values_are_normalized_without_modifying_argv(self):
        calls = []
        command = read_command(lambda invocation: calls.append(invocation) or 0, options=(
            OptionSpec("--select", takes_value=True, repeatable=True),
            OptionSpec("--check"), OptionSpec("--mode", takes_value=True, choices=("a", "b")),
        ))
        argv = ["fixture", "read", "--select", "x", "--mode=b", "--select=y", "--check"]
        before = list(argv)
        self.assertEqual(CommandRegistry((command,)).invoke(argv), 0)
        self.assertEqual(argv, before)
        self.assertEqual(dict(calls[0].options), {"--select": ("x", "y"), "--mode": "b", "--check": True})

    def test_unknown_command_and_unknown_option_do_not_call_handler(self):
        calls = []
        registry = CommandRegistry((read_command(lambda invocation: calls.append(invocation) or 0),))
        for args in (["missing"], ["fixture", "read", "--unknown"], ["fixture", "read", "extra"]):
            self.assertEqual(dispatch(args, registry=registry), 2)
        self.assertEqual(calls, [])

    def test_duplicate_and_unavailable_declarations_are_rejected(self):
        command = read_command(lambda invocation: 0)
        with self.assertRaises(CommandUsageError):
            CommandRegistry((command, command))
        with self.assertRaises(CommandUsageError):
            replace(command, handler=None)
        with self.assertRaises(CommandUsageError):
            builtin_registry().resolve("init")
        self.assertEqual({c.command_id for c in builtin_registry().commands}, {"help"})

    def test_side_effect_limits_cannot_contradict_read_only_or_bootstrap(self):
        command = read_command(lambda invocation: 0)
        for changes in ({"effect_scope": EffectScope.NORMATIVE_TRANSACTION},
                        {"command_class": "bootstrap"}, {"preflight_profile": "unknown"}):
            with self.assertRaises(CommandUsageError):
                replace(command, **changes)
        with self.assertRaises(CommandUsageError):
            replace(builtin_registry().resolve("help"), requires_project=True)

    def test_alias_uses_the_same_canonical_contract_and_handler(self):
        calls = []
        registry = CommandRegistry((read_command(lambda invocation: calls.append(invocation.command.command_id) or 0,
                                                 aliases=(("fixture-read",),)),))
        self.assertEqual(registry.invoke(["fixture-read"]), 0)
        self.assertEqual(registry.invoke(["fixture", "read"]), 0)
        self.assertEqual(calls, ["fixture.read", "fixture.read"])

    def test_undeclared_global_options_remain_usage_errors(self):
        for flag in ("--project", "--strict", "--format", "--actor-id", "--request-id", "--dry-run"):
            self.assertEqual(dispatch(["--help", flag]), 2)

    def test_required_and_excluded_options_fail_before_execution(self):
        calls = []
        registry = CommandRegistry((read_command(lambda invocation: calls.append(invocation) or 0, options=(
            OptionSpec("--input", takes_value=True, required=True),
            OptionSpec("--one", excludes=("--two",)), OptionSpec("--two"),
        )),))
        for args in ([], ["--input"], ["--input", "x", "--one", "--two"]):
            self.assertEqual(dispatch(["fixture", "read", *args], registry=registry), 2)
        self.assertEqual(calls, [])
