"""Offline snapshot transport, integrity and relocatable distributions."""
from pathlib import Path
from hashlib import sha256
import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.model.language_registry import LanguageRegistryError
from specroad.storage.language_registry import bundled_language_registry, read_language_registry, registry_binding
from specroad.storage.project import ProjectSource
from specroad.security import SafetyViolation
from support.languages import project_registry, load_registry
from support.model import configuration_file, put
from support.portable import build_distribution, files_under


class RegistryStorageTests(unittest.TestCase):
    def test_bound_snapshot_read_preserves_all_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); binding = project_registry(root); before = files_under(root)
            result = read_language_registry(ProjectSource(root))
            self.assertEqual(result.sha256, binding["sha256"])
            self.assertEqual(files_under(root), before)

    def test_absent_binding_does_not_use_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); configuration_file(root)
            with self.assertRaises(LanguageRegistryError): read_language_registry(ProjectSource(root))

    def test_missing_file_does_not_use_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); binding = project_registry(root); (root / binding["path"]).unlink()
            with self.assertRaises(LanguageRegistryError): read_language_registry(ProjectSource(root))

    def test_modified_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); binding = project_registry(root)
            path = root / binding["path"]; path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaises(LanguageRegistryError): read_language_registry(ProjectSource(root))

    def test_bound_project_not_silently_upgraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project_registry(root)
            value = read_language_registry(ProjectSource(root)).inspect("de")
            self.assertEqual(value.registry_state, "unverified_registry")
            self.assertEqual(value.registry_version, "2020-01-01")

    def test_no_network_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project_registry(root)
            with patch("socket.socket", side_effect=AssertionError("network forbidden")):
                self.assertEqual(read_language_registry(ProjectSource(root)).inspect("en").registry_state, "registered")

    def test_registry_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); binding = project_registry(root); path = root / binding["path"]
            original = path.read_bytes(); path.unlink(); put(root, "outside.txt", original)
            path.symlink_to(root / "outside.txt")
            with self.assertRaises((SafetyViolation, LanguageRegistryError)): read_language_registry(ProjectSource(root))

    def test_binding_is_data_not_write(self):
        registry = load_registry(); binding = registry_binding(registry)
        self.assertEqual(set(binding), {"registry_id", "registry_version", "path", "sha256"})
        self.assertEqual(binding["sha256"], sha256(registry.source_bytes).hexdigest())

    def test_binding_rejects_path_outside_registry_area(self):
        with self.assertRaises(LanguageRegistryError): registry_binding(load_registry(), path="spec/registry.txt")

    def test_relocatable_module_and_zipapp_ship_snapshot(self):
        expected = bundled_language_registry()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); module, zipapp = build_distribution(root / "dist")
            moved = root / "moved"; (root / "dist").rename(moved)
            script = ("import sys,json;sys.path.insert(0,sys.argv[1]);"
                      "from specroad.storage.language_registry import bundled_language_registry;"
                      "r=bundled_language_registry();print(json.dumps([r.sha256,r.version,r.inspect('en-US').registry_state]))")
            for target in (moved / "module", moved / "specroad.pyz"):
                process = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(target)],
                                         cwd=root, stdin=subprocess.DEVNULL, capture_output=True, check=True)
                self.assertEqual(json.loads(process.stdout), [expected.sha256, expected.version, "registered"])
