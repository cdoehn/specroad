"""Root and option data contracts. No presentation or documentation oracles."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import json
import tempfile
import unittest

from specroad.cli.application import dispatch
from specroad.cli.commands import builtin_registry
from specroad.cli.contracts import CommandClass, CommandSpec, EffectScope, PreflightProfile
from specroad.cli.options import (
    CORE_PROFILE, OptionLayer, OptionResolutionError,
    global_options, policy_exit_code, resolve_options,
)
from specroad.cli.registry import CommandRegistry


def metadata_registry(calls, *, flags=("--project", "--profile", "--configuration")):
    def handle(invocation):
        calls.append(invocation.resolved)
        return 0
    return CommandRegistry((CommandSpec(
        command_id="fixture.metadata", words=("fixture", "metadata"),
        command_class=CommandClass.READ_ONLY,
        preflight_profile=PreflightProfile.PROJECT_METADATA,
        effect_scope=EffectScope.NONE, requires_project=True,
        options=global_options(*flags), handler=handle,
    ),))


def write_config(root, data):
    root.mkdir(parents=True, exist_ok=True)
    (root / "specroad.json").write_text(json.dumps(data), encoding="utf-8")


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class OptionWorkTests(unittest.TestCase):
    def test_closest_ancestor_wins_without_modifying_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            outer = Path(tmp)
            inner = outer / "nested"
            cwd = inner / "sub"
            write_config(outer, {"profiles": ["outer@1.0.0"]})
            write_config(inner, {"profiles": ["inner@1.0.0"]})
            cwd.mkdir()
            before = snapshot(outer)
            calls = []
            self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry(calls), cwd=cwd), 0)
            self.assertEqual(calls[0].project_root, inner.resolve())
            self.assertEqual(calls[0].project_source, "discovery")
            self.assertEqual(calls[0].values["profiles"], (CORE_PROFILE, "inner@1.0.0"))
            self.assertEqual(snapshot(outer), before)

    def test_explicit_relative_project_overrides_ancestor_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            explicit = parent / "other"
            write_config(parent, {"profiles": ["ancestor@1.0.0"]})
            write_config(explicit, {"profiles": ["selected@1.0.0"]})
            calls = []
            self.assertEqual(dispatch(["--project", "other", "fixture", "metadata"], registry=metadata_registry(calls), cwd=parent), 0)
            self.assertEqual(calls[0].project_root, explicit.resolve())
            self.assertEqual(calls[0].project_source, "cli")
            self.assertEqual(calls[0].values["profiles"], (CORE_PROFILE, "selected@1.0.0"))

    def test_explicit_invalid_root_never_falls_back_or_initializes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {})
            (root / "empty").mkdir()
            before = snapshot(root)
            calls = []
            for target in ("missing", "empty", "specroad.json"):
                self.assertEqual(dispatch(["fixture", "metadata", "--project", target],
                                          registry=metadata_registry(calls), cwd=root), 2)
            self.assertEqual(calls, [])
            self.assertEqual(snapshot(root), before)
            self.assertFalse((root / "missing").exists())
            self.assertEqual(list((root / "empty").iterdir()), [])

    def test_profiles_replace_project_list_and_keep_order_and_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {"profiles": ["project@1.0.0"]})
            registry = metadata_registry([])
            invocation = registry.parse(["fixture", "metadata", "--profile", "second@1.0.0", "--profile", "first@1.0.0",
                                         "--configuration", "variant-a"])
            result = resolve_options(invocation, cwd=root)
            self.assertEqual(result.values["profiles"], (CORE_PROFILE, "second@1.0.0", "first@1.0.0"))
            self.assertEqual(result.values["configuration"], "variant-a")
            self.assertEqual(result.origins["profiles"], "cli")
            self.assertEqual([item.source for item in result.history["profiles"]], ["default", "project", "cli"])
            self.assertEqual(result.history["profiles"][1].value, (CORE_PROFILE, "project@1.0.0"))

    def test_bootstrap_never_reads_project_or_needs_working_directory(self):
        with patch("pathlib.Path.cwd", side_effect=AssertionError("cwd requested")), \
             patch("pathlib.Path.lstat", side_effect=AssertionError("project read")):
            self.assertEqual(dispatch(["--help"]), 0)
            result = resolve_options(builtin_registry().parse(["--help"]))
        self.assertIsNone(result.project_root)
        self.assertIsNone(result.project_source)

    def test_selected_malformed_config_does_not_fall_back_to_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            child = parent / "child"
            write_config(parent, {})
            write_config(child, {})
            calls = []
            for raw in (b"{", b"[]", b'{"profiles":[],"profiles":[]}', b'{"bad":NaN}', b'{"profiles":"not-a-list"}'):
                (child / "specroad.json").write_bytes(raw)
                self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry(calls), cwd=child), 2)
                self.assertEqual((child / "specroad.json").read_bytes(), raw)
            self.assertEqual(calls, [])

    def test_configuration_symlink_is_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "project"
            root.mkdir()
            target = parent / "outside.json"
            target.write_bytes(b"{}")
            (root / "specroad.json").symlink_to(target)
            calls = []
            self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry(calls), cwd=root), 7)
            self.assertEqual(calls, [])
            self.assertEqual(target.read_bytes(), b"{}")
            self.assertTrue((root / "specroad.json").is_symlink())

    def test_configuration_io_error_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {})
            calls = []
            with patch("os.open", side_effect=PermissionError("controlled denial")):
                self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry(calls), cwd=root), 5)
            self.assertEqual(calls, [])
            self.assertEqual(json.loads((root / "specroad.json").read_text()), {})

    def test_roots_are_fresh_between_invocations(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots = [Path(tmp) / "one", Path(tmp) / "two"]
            for root in roots:
                write_config(root, {})
            calls = []
            registry = metadata_registry(calls)
            for root in roots:
                self.assertEqual(dispatch(["fixture", "metadata"], registry=registry, cwd=root), 0)
            self.assertEqual([call.project_root for call in calls], [root.resolve() for root in roots])

    def test_option_values_and_origin_views_are_immutable(self):
        result = resolve_options(builtin_registry().parse(["--help"]))
        for view in (result.values, result.history, result.origins):
            with self.assertRaises(TypeError):
                view["profiles"] = "changed"


class OptionRobustnessTests(unittest.TestCase):
    def _resolved(self, root, *, args=(), profiles=(), configuration=None):
        registry = metadata_registry([], flags=("--project", "--profile", "--configuration", "--strict", "--fail-on"))
        invocation = registry.parse(["fixture", "metadata", *args])
        return resolve_options(invocation, cwd=root, profile_layers=profiles, configuration_layer=configuration)

    def test_policy_precedence_and_full_override_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {"validation_policy": {"fail_on": "warning"}})
            profiles = (OptionLayer("a@1.0.0", {"fail_on": "error"}), OptionLayer("b@1.0.0", {"fail_on": "warning"}))
            configuration = OptionLayer("release", {"fail_on": "error"})
            result = self._resolved(root, args=("--fail-on", "warning"), profiles=profiles, configuration=configuration)
            self.assertEqual(result.values["fail_on"], "warning")
            self.assertEqual(result.origins["fail_on"], "cli")
            self.assertEqual([change.source for change in result.history["fail_on"]],
                             ["default", "project", "profile:a@1.0.0", "profile:b@1.0.0", "configuration:release", "cli"])
            self.assertEqual(self._resolved(root, profiles=profiles, configuration=configuration).values["fail_on"], "error")
            self.assertEqual(self._resolved(root, profiles=profiles[:1]).values["fail_on"], "error")
            self.assertEqual(self._resolved(root).values["fail_on"], "warning")

    def test_warning_threshold_changes_policy_result_not_diagnostic_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {})
            severities = ["info", "warning"]
            self.assertEqual(policy_exit_code(severities, self._resolved(root)), 0)
            self.assertEqual(policy_exit_code(severities, self._resolved(root, args=("--fail-on", "warning"))), 1)
            self.assertEqual(policy_exit_code(["error"], self._resolved(root)), 1)
            self.assertEqual(policy_exit_code([], self._resolved(root)), 0)
            self.assertEqual(severities, ["info", "warning"])

    def test_strict_enables_optional_core_lint_and_always_uses_warning_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {"validation_policy": {"fail_on": "error"}})
            for args in (("--strict",), ("--strict", "--fail-on", "error"), ("--fail-on", "error", "--strict")):
                resolved = self._resolved(root, args=args)
                self.assertTrue(resolved.values["strict"])
                self.assertTrue(resolved.values["core_lint_optional"])
                self.assertEqual(resolved.values["fail_on"], "warning")
                self.assertEqual(policy_exit_code(["warning"], resolved), 1)
                self.assertEqual(resolved.origins["fail_on"], "cli:strict")

    def test_strict_does_not_import_analyzer_or_spawn_any_process(self):
        import sys
        class NoAnalyzer:
            def find_spec(self, fullname, path=None, target=None):
                if any(part in fullname.lower() for part in ("analyz", "langid", "numpy")):
                    raise AssertionError("Analyzer was loaded")
                return None
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {})
            guard = NoAnalyzer()
            sys.meta_path.insert(0, guard)
            try:
                with patch("subprocess.Popen", side_effect=AssertionError("Process started")):
                    result = self._resolved(root, args=("--strict",))
                    self.assertEqual(policy_exit_code(["warning"], result), 1)
            finally:
                sys.meta_path.remove(guard)

    def test_disallowed_threshold_or_write_flag_does_not_run_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {})
            calls = []
            restricted = metadata_registry(calls, flags=("--project",))
            allowed = metadata_registry(calls, flags=("--fail-on", "--strict"))
            for registry, tail in ((restricted, ["--strict"]), (restricted, ["--fail-on", "warning"]),
                                   (allowed, ["--fail-on", "info"]), (allowed, ["--actor-id", "x"]),
                                   (allowed, ["--dry-run"]), (allowed, ["--strict=false"])):
                self.assertEqual(dispatch(["fixture", "metadata", *tail], registry=registry, cwd=root), 2)
            self.assertEqual(calls, [])
            self.assertEqual(snapshot(root), {"specroad.json": b"{}"})

    def test_invalid_configuration_policy_is_not_hidden_by_cli_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []
            registry = metadata_registry(calls, flags=("--fail-on",))
            for policy in ([], None, {"fail_on": "info"}, {"fail_on": False}):
                write_config(root, {"validation_policy": policy})
                before = snapshot(root)
                self.assertEqual(dispatch(["fixture", "metadata", "--fail-on", "error"], registry=registry, cwd=root), 2)
                self.assertEqual(snapshot(root), before)
            self.assertEqual(calls, [])

    def test_project_and_layers_are_reloaded_without_mutating_the_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = {"fail_on": "warning"}
            layer = OptionLayer("profile", source)
            source["fail_on"] = "error"
            write_config(root, {"validation_policy": {"fail_on": "error"}})
            self.assertEqual(self._resolved(root, profiles=(layer,)).values["fail_on"], "warning")
            with self.assertRaises(TypeError):
                layer.values["fail_on"] = "error"
            self.assertEqual(self._resolved(root).values["fail_on"], "error")
            write_config(root, {"validation_policy": {"fail_on": "warning"}})
            self.assertEqual(self._resolved(root).values["fail_on"], "warning")

    def test_core_profile_cannot_be_replaced_by_other_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {"profiles": ["core@0.2.0", "base@1.0.0"]})
            resolved = self._resolved(root, args=("--profile", "core", "--profile", "extra"))
            self.assertEqual(resolved.values["profiles"], (CORE_PROFILE, "extra"))
            with self.assertRaises(OptionResolutionError):
                self._resolved(root, args=("--profile", "core@9.0.0"))

    def test_nonregular_or_missing_config_is_not_implicitly_repaired(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "specroad.json").mkdir()
            calls = []
            self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry(calls), cwd=root), 2)
            self.assertTrue((root / "specroad.json").is_dir())
            self.assertEqual(calls, [])

    def test_absolute_project_does_not_depend_on_unavailable_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {})
            calls = []
            with patch("pathlib.Path.cwd", side_effect=AssertionError("cwd should not be consulted")):
                status = dispatch(["fixture", "metadata", "--project", str(root)], registry=metadata_registry(calls))
            self.assertEqual(status, 0)
            self.assertEqual(calls[0].project_root, root.resolve())

    def test_registered_global_options_cannot_change_shape(self):
        from specroad.cli.contracts import CommandUsageError, OptionSpec
        command = metadata_registry([]).resolve("fixture.metadata")
        for option in (OptionSpec("--project"), OptionSpec("--profile", takes_value=True),
                       OptionSpec("--fail-on", takes_value=True, choices=("info",))):
            with self.assertRaises(CommandUsageError):
                CommandRegistry((replace(command, options=(option,)),))
        with self.assertRaises(CommandUsageError):
            CommandRegistry((replace(builtin_registry().resolve("help"), options=global_options("--project")),))

    def test_invalid_layer_and_unknown_severity_are_rejected(self):
        for values in ({"strict": True}, {"fail_on": "info"}, [], None):
            with self.assertRaises(OptionResolutionError):
                OptionLayer("fixture", values)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {})
            for profiles in (None, "profile", ({"fail_on": "warning"},)):
                with self.assertRaises(OptionResolutionError):
                    self._resolved(root, profiles=profiles)
            with self.assertRaises(OptionResolutionError):
                policy_exit_code(["fatal"], self._resolved(root))
