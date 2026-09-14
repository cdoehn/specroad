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
from specroad.cli.options import CORE_PROFILE, global_options, resolve_options
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
