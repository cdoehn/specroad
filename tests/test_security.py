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


class SafetyRobustnessTests(unittest.TestCase):
    def test_directory_link_cannot_cross_the_root_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "root"
            outside = parent / "outside"
            root.mkdir()
            outside.mkdir()
            (outside / "secret").write_bytes(b'private')
            (root / "data").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(SafetyViolation):
                ProjectBoundary(root).read_bytes("data/secret")
            self.assertEqual((outside / "secret").read_bytes(), b'private')

    def test_internal_links_are_conservatively_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "value").write_bytes(b'ordinary')
            (root / "alias").symlink_to("value")
            with self.assertRaises(SafetyViolation):
                ProjectBoundary(root).read_bytes("alias")
            self.assertEqual(ProjectBoundary(root).read_bytes("value"), b'ordinary')

    def test_fifo_is_not_opened_or_consumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.mkfifo(root / "pipe")
            with self.assertRaises(SafetyViolation):
                ProjectBoundary(root).read_bytes("pipe")
            self.assertTrue((root / "pipe").exists())

    def test_directory_replacement_between_check_and_open_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "root"
            (root / "data").mkdir(parents=True)
            (root / "data/value").write_bytes(b'original')
            outside = parent / "outside"
            outside.mkdir()
            (outside / "value").write_bytes(b'private')
            boundary = ProjectBoundary(root)
            real_open = os.open
            swapped = []
            def switch(path, *args, **kwargs):
                if path == "data" and not swapped:
                    swapped.append(True)
                    (root / "data").rename(root / "preserved")
                    (root / "data").symlink_to(outside, target_is_directory=True)
                return real_open(path, *args, **kwargs)
            with patch.object(os, "open", side_effect=switch), self.assertRaises(SafetyViolation):
                boundary.read_bytes("data/value")
            self.assertTrue(swapped)
            self.assertEqual((root / "preserved/value").read_bytes(), b'original')
            self.assertEqual((outside / "value").read_bytes(), b'private')

    def test_leaf_replacement_between_check_and_open_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "root"
            root.mkdir()
            (root / "value").write_bytes(b'original')
            outside = parent / "private"
            outside.write_bytes(b'private')
            boundary = ProjectBoundary(root)
            real_open = os.open
            swapped = []
            def switch(path, *args, **kwargs):
                if path == "value" and not swapped:
                    swapped.append(True)
                    (root / "value").rename(root / "preserved")
                    (root / "value").symlink_to(outside)
                return real_open(path, *args, **kwargs)
            with patch.object(os, "open", side_effect=switch), self.assertRaises(SafetyViolation):
                boundary.read_bytes("value")
            self.assertTrue(swapped)
            self.assertEqual((root / "preserved").read_bytes(), b'original')
            self.assertEqual(outside.read_bytes(), b'private')

    def test_in_place_mutation_is_not_returned_as_a_stable_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "value"
            target.write_bytes(b'original')
            boundary = ProjectBoundary(root)
            real_fdopen = os.fdopen
            class ChangingStream:
                def __init__(self, *args, **kwargs):
                    self.stream = real_fdopen(*args, **kwargs)
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    self.stream.close()
                def fileno(self):
                    return self.stream.fileno()
                def read(self):
                    target.write_bytes(b'deliberately longer changed content')
                    return self.stream.read()
            with patch.object(os, "fdopen", side_effect=ChangingStream), self.assertRaises(SafetyViolation):
                boundary.read_bytes("value")
            self.assertEqual(target.read_bytes(), b'deliberately longer changed content')

    def test_unknown_secure_open_capability_fails_closed(self):
        import errno
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "value").write_bytes(b'kept')
            with patch.object(sys.modules[ProjectBoundary.__module__], "_HAS_SAFE_OPEN", False):
                with self.assertRaises(OSError) as caught:
                    ProjectBoundary(root).read_bytes("value")
            self.assertEqual(caught.exception.errno, errno.ENOTSUP)
            self.assertEqual((root / "value").read_bytes(), b'kept')

    def test_invalid_unicode_path_is_rejected_before_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            boundary = ProjectBoundary(tmp)
            with patch.object(os, "open", side_effect=AssertionError("unexpected I/O")), self.assertRaises(SafetyViolation):
                boundary.read_bytes("bad\ud800path")

    def test_managed_paths_cannot_request_traversal_or_another_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for data in ({"managed_paths": ["../outside"]}, {"managed_paths": ["/other"]},
                         {"managed_paths": "spec"}, {"generated_path": "../../generated"}):
                write_config(root, data)
                calls = []
                self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry(calls), cwd=root), 7)
                self.assertEqual(calls, [])
            # Safety validation is not a model scan; declared targets may not exist yet.
            write_config(root, {"managed_paths": ["spec", "rules"], "generated_path": "generated"})
            self.assertEqual(dispatch(["fixture", "metadata"], registry=metadata_registry([]), cwd=root), 0)
            self.assertEqual({p.name for p in root.iterdir()}, {"specroad.json"})

    def test_private_environment_is_not_forwarded_to_future_adapters(self):
        from specroad.security import isolated_process_environment
        with patch.dict(os.environ, {"SECRET": "DO-NOT-FORWARD", "PYTHONPATH": "DO-NOT-FORWARD",
                                     "GIT_CONFIG_COUNT": "1", "HTTPS_PROXY": "DO-NOT-FORWARD",
                                     "LD_PRELOAD": "DO-NOT-FORWARD"}):
            environment = isolated_process_environment()
        self.assertEqual(set(environment), {"PATH", "LC_ALL", "PYTHONNOUSERSITE"})
        self.assertNotIn("DO-NOT-FORWARD", environment.values())
        with self.assertRaises(TypeError):
            environment["SECRET"] = "bad"
        # Environment data alone is not permission to start a process.
        with self.assertRaises(SafetyViolation):
            require_builtin_execution("git")

    def test_configuration_error_does_not_disclose_raw_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "PRIVATE-CONFIG-CONTENT"
            (root / "specroad.json").write_text('{"password":"' + secret + '" BROKEN}')
            result = dispatch_result(["fixture", "metadata"], registry=metadata_registry([]), cwd=root)
            self.assertEqual(result.exit_code, 2)
            self.assertNotIn(secret, json.dumps(result.as_dict()))

    def test_execution_rejection_does_not_disclose_secret_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = "PRIVATE-EXECUTOR-ARGUMENT"
            write_config(root, {"plugins": [{"command": "curl", "token": secret}]})
            result = dispatch_result(["fixture", "metadata"], registry=metadata_registry([]), cwd=root)
            self.assertEqual(result.exit_code, 7)
            self.assertNotIn(secret, json.dumps(result.as_dict()))

    def test_io_exception_details_are_not_project_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, {})
            with patch.object(os, "open", side_effect=PermissionError("PRIVATE-OS-DETAIL")):
                result = dispatch_result(["fixture", "metadata"], registry=metadata_registry([]), cwd=root)
            self.assertEqual(result.exit_code, 5)
            self.assertNotIn("PRIVATE-OS-DETAIL", json.dumps(result.as_dict()))

    def test_denied_read_closes_owned_directory_descriptors(self):
        import errno
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "data/link").symlink_to(root / "missing")
            boundary = ProjectBoundary(root)
            real_open = os.open
            opened = []
            def observe(*args, **kwargs):
                descriptor = real_open(*args, **kwargs)
                opened.append(descriptor)
                return descriptor
            with patch.object(os, "open", side_effect=observe), self.assertRaises(SafetyViolation):
                boundary.read_bytes("data/link")
            self.assertGreaterEqual(len(opened), 2)
            for descriptor in opened:
                with self.assertRaises(OSError) as caught:
                    os.fstat(descriptor)
                self.assertEqual(caught.exception.errno, errno.EBADF)

    def test_audited_core_invocations_do_not_spawn_connect_or_write(self):
        body = r"""
import os
from pathlib import Path
from specroad.cli.application import dispatch_result
from specroad.runtime.identity import version_info
from specroad.security import ProjectBoundary
root = Path.cwd()
forbidden = {"subprocess.Popen", "os.system", "os.posix_spawn", "socket.__new__", "socket.connect",
             "socket.getaddrinfo", "socket.bind", "os.mkdir", "os.remove", "os.rename", "os.rmdir"}
def guard(event, args):
    if event in forbidden:
        raise AssertionError("prohibited effect")
    if event == "open":
        path, mode, flags = args
        if (isinstance(mode, str) and any(char in mode for char in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            raise AssertionError("write attempt")
sys.addaudithook(guard)
assert dispatch_result(["--help"]).exit_code == 0
assert dispatch_result(["version"]).exit_code == 0
assert ProjectBoundary(root).read_bytes("specroad.json") == b"{}"
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "specroad.json").write_bytes(b'{}')
            before = files_under(root)
            result = run_core(body, root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(files_under(root), before)

    def test_data_read_does_not_modify_global_process_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "value").write_bytes(b'kept')
            before_cwd = Path.cwd()
            before_env = dict(os.environ)
            self.assertEqual(ProjectBoundary(root).read_bytes("value"), b'kept')
            self.assertEqual(Path.cwd(), before_cwd)
            self.assertEqual(dict(os.environ), before_env)
