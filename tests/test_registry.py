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
        preflight_profile=PreflightProfile.INPUT_READ,
        effect_scope=EffectScope.NONE, requires_project=False, handler=handler,
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
        self.assertEqual({c.command_id for c in builtin_registry().commands}, {"help", "version", "command.describe"})

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


class RegistryRobustnessTests(unittest.TestCase):
    def test_prefix_infix_and_suffix_options_share_one_binding(self):
        calls = []
        registry = CommandRegistry((read_command(lambda invocation: calls.append(dict(invocation.options)) or 0,
                                                 options=(OptionSpec("--mode", takes_value=True),)),))
        for args in (["--mode", "a", "fixture", "read"], ["fixture", "--mode=a", "read"],
                     ["fixture", "read", "--mode", "a"]):
            self.assertEqual(dispatch(args, registry=registry), 0)
        self.assertEqual(calls, [{"--mode": "a"}] * 3)

    def test_unknown_choice_duplicate_and_missing_value_are_not_executed(self):
        calls = []
        registry = CommandRegistry((read_command(lambda invocation: calls.append(invocation) or 0, options=(
            OptionSpec("--mode", takes_value=True, choices=("a", "b")), OptionSpec("--check"),
        )),))
        for tail in (["--mode", "c"], ["--mode"], ["--mode="], ["--mo", "a"], ["--check=true"],
                     ["--mode", "a", "--mode=b"], ["--check", "--check"], ["--mode", "--check"]):
            self.assertEqual(dispatch(["fixture", "read", *tail], registry=registry), 2)
        self.assertEqual(calls, [])

    def test_invalid_vectors_are_usage_errors_without_calling_handler(self):
        calls = []
        registry = CommandRegistry((read_command(lambda invocation: calls.append(invocation) or 0),))
        for argv in (None, "fixture read", {"fixture": "read"}, [], [1], ["fixture", "read", "x\0y"]):
            self.assertEqual(dispatch(argv, registry=registry), 2)
        self.assertEqual(calls, [])

    def test_route_and_alias_collisions_are_rejected(self):
        one = read_command(lambda invocation: 0)
        two = replace(one, command_id="other", words=("other",), aliases=(one.words,))
        for commands in ((one, two), (replace(one, aliases=(one.words,)),)):
            with self.assertRaises(CommandUsageError):
                CommandRegistry(commands)

    def test_nonwrite_commands_cannot_declare_write_options(self):
        for flag in ("--actor-type", "--actor-id", "--request-id", "--dry-run", "--as-proposal"):
            with self.assertRaises(CommandUsageError):
                read_command(lambda invocation: 0, options=(OptionSpec(flag),))

    def test_all_class_and_effect_boundaries_are_explicit(self):
        pairs = {
            CommandClass.NORMATIVE_WRITE: EffectScope.NORMATIVE_TRANSACTION,
            CommandClass.PLAN_OUTPUT: EffectScope.EXTERNAL_OUTPUT,
            CommandClass.GENERATED_OUTPUT: EffectScope.EXTERNAL_OUTPUT,
            CommandClass.READ_ONLY: EffectScope.NONE,
            CommandClass.LOCAL_OPERATIONAL: EffectScope.LOCAL_OPERATIONAL,
            CommandClass.RECOVERY_WRITE: EffectScope.RECOVERY_TRANSACTION,
            CommandClass.ROOT_CREATION: EffectScope.NEW_ROOT,
            CommandClass.WORK_OPERATIONAL: EffectScope.EXTERNAL_WORK,
        }
        self.assertEqual(set(pairs), set(CommandClass))
        for cls, scope in pairs.items():
            command = read_command(lambda invocation: 0, command_class=cls, effect_scope=scope)
            self.assertEqual(CommandRegistry((command,)).resolve(command.command_id).effect_scope, scope)
            with self.assertRaises(CommandUsageError):
                replace(command, effect_scope=EffectScope.NONE if scope is not EffectScope.NONE else EffectScope.NEW_ROOT)

    def test_collection_inputs_are_defensively_copied(self):
        options = [OptionSpec("--select", takes_value=True, repeatable=True)]
        words = ["fixture", "read"]
        command = read_command(lambda invocation: 0, words=words, options=options)
        options.clear()
        words.clear()
        registry = CommandRegistry((command,))
        invocation = registry.parse(["fixture", "read", "--select", "a"])
        self.assertEqual(invocation.options["--select"], ("a",))
        with self.assertRaises(TypeError):
            invocation.options["--select"] = "changed"

    def test_malformed_contracts_are_rejected_at_registration(self):
        for changes in ({"words": "read"}, {"aliases": ["other"]}, {"options": None},
                        {"requires_write_paths": "output"}, {"requires_project": 1},
                        {"budget_policy_version": "future"}):
            with self.assertRaises(CommandUsageError):
                read_command(lambda invocation: 0, **changes)
        with self.assertRaises(CommandUsageError):
            OptionSpec("--mode", takes_value=True, choices="abc")
        for excludes in (("--missing",), ("--one",)):
            with self.assertRaises(CommandUsageError):
                read_command(lambda invocation: 0, options=(OptionSpec("--one", excludes=excludes),))

    def test_async_and_generator_handlers_are_not_available(self):
        async def asynchronous(invocation):
            return 0
        def generator(invocation):
            yield 0
        for handler in (asynchronous, generator):
            with self.assertRaises(CommandUsageError):
                read_command(handler)

    def test_handler_failures_and_bare_continuations_cannot_claim_success(self):
        def failing(invocation):
            raise RuntimeError("controlled fault")
        for handler in (failing, lambda invocation: None, lambda invocation: True,
                        lambda invocation: 8, lambda invocation: -1, lambda invocation: "0"):
            registry = CommandRegistry((read_command(handler),))
            self.assertEqual(dispatch(["fixture", "read"], registry=registry), 4)
