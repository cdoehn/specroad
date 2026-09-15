"""Safety contracts through real file effects and inert adversarial inputs."""

import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from specroad.cli.application import dispatch, dispatch_result
from specroad.security import ProjectBoundary, SafetyViolation, require_builtin_execution
from support.portable import files_under
from support.processes import run_core
from test_options import metadata_registry, write_config


class SafetyWorkTests(unittest.TestCase):
    def test_regular_project_bytes_are_read_without_modification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data/value.json").write_bytes(b'{"keep":true}\n')
            before = files_under(root)
            boundary = ProjectBoundary(root)
            self.assertEqual(boundary.read_bytes("data/value.json"), b'{"keep":true}\n')
            self.assertEqual(files_under(root), before)

    def test_boundary_accepts_exactly_one_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            for roots in ([tmp], (tmp, tmp), {"first": tmp}, None):
                with self.subTest(roots=roots), self.assertRaises(SafetyViolation):
                    ProjectBoundary(roots)

    def test_traversal_and_absolute_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            boundary = ProjectBoundary(tmp)
            for name in ("../outside", "/etc/passwd", "C:/secret", "a/../../outside", "a//b", "./item",
                         "a/./b", "a\\b", "file:stream", "", "bad\0name"):
                with self.subTest(name=name), self.assertRaises(SafetyViolation):
                    boundary.read_bytes(name)

    def test_external_and_dangling_links_are_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "project"
            root.mkdir()
            secret = parent / "secret"
            secret.write_bytes(b'PRIVATE-CONTENT')
            (root / "outside").symlink_to(secret)
            (root / "missing").symlink_to(parent / "does-not-exist")
            boundary = ProjectBoundary(root)
            for name in ("outside", "missing"):
                with self.subTest(name=name), self.assertRaises(SafetyViolation):
                    boundary.read_bytes(name)
            self.assertEqual(secret.read_bytes(), b'PRIVATE-CONTENT')

    def test_nested_projects_cannot_be_merged_by_a_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {"project_id": "one"})
            write_config(root / "nested", {"project_id": "two"})
            (root / "nested/secret.json").write_bytes(b'not part of root one')
            boundary = ProjectBoundary(root)
            with self.assertRaises(SafetyViolation):
                boundary.read_bytes("nested/secret.json")
            self.assertEqual(ProjectBoundary(root / "nested").read_bytes("secret.json"), b'not part of root one')

    def test_changed_root_is_not_silently_rebound(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "root"
            root.mkdir()
            (root / "value").write_bytes(b'old')
            boundary = ProjectBoundary(root)
            root.rename(parent / "saved")
            root.mkdir()
            (root / "value").write_bytes(b'new')
            with self.assertRaises(SafetyViolation):
                boundary.read_bytes("value")
            self.assertEqual((parent / "saved/value").read_bytes(), b'old')

    def test_project_metadata_path_runs_without_git_network_or_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {"project_id": "one"})
            before = files_under(root)
            calls = []
            with patch.object(subprocess, "Popen", side_effect=AssertionError("external process")), \
                 patch.object(socket, "create_connection", side_effect=AssertionError("network")), \
                 patch.object(socket, "getaddrinfo", side_effect=AssertionError("DNS")), \
                 patch.object(os, "system", side_effect=AssertionError("shell")):
                self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry(calls), cwd=root), 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(files_under(root), before)
            self.assertFalse((root / ".git").exists())

    def test_project_execution_declarations_fail_before_handler(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for field in ("plugins", "plugin", "execution", "executor", "entrypoint", "hooks"):
                write_config(root, {field: {"module": "evil_module", "shell": "touch FORBIDDEN"}})
                before = files_under(root)
                calls = []
                self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry(calls), cwd=root), 7)
                self.assertEqual(calls, [])
                self.assertEqual(files_under(root), before)

    def test_unimplemented_executor_is_never_loaded(self):
        for declaration in ("evil.module:run", "py3langid", "git", {"command": ["sh", "-c", "false"]}, None):
            with self.subTest(declaration=declaration), self.assertRaises(SafetyViolation):
                require_builtin_execution(declaration)

    def test_multiple_project_declarations_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for data in ({"project_id": ["one", "two"]}, {"project_roots": ["a", "b"]},
                         {"project_ids": ["a"]}, {"repositories": ["a"]}, {"projects": {"one": "."}}):
                write_config(root, data)
                calls = []
                self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry(calls), cwd=root), 7)
                self.assertEqual(calls, [])

    def test_json_strings_remain_data_not_executable_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sentinel = root / "FOREIGN_CODE_EXECUTED"
            write_config(root, {"project_id": "one", "description": "__import__('os').system('touch FORBIDDEN')"})
            (root / "evil_module.py").write_text("open(" + repr(str(sentinel)) + ", 'w').write('bad')")
            before = files_under(root)
            calls = []
            self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry(calls), cwd=root), 0)
            self.assertEqual(files_under(root), before)
            self.assertFalse(sentinel.exists())

    def test_bootstrap_remains_usable_when_project_declarations_are_hostile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {"plugins": ["evil"]})
            before = files_under(root)
            for args in (["--help"], ["version", "--format", "json"]):
                result = dispatch_result(args, cwd=root)
                self.assertEqual(result.exit_code, 0)
                self.assertIsNone(result.project)
            self.assertEqual(files_under(root), before)
