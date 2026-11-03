"""Behavior checks for scaled PatchHarbor result discovery."""
import json
from pathlib import Path
import zipfile
from unittest.mock import patch
import warnings
import specroad_control.hints as scan
from specroad_control.exchange import Exchange, hint
from specroad_control.automation import Engine, Gate
from codex_control_tests.automation_support import AutomationCase, FakeCore, FakeCodex, read_package


def enlarge_result(path: Path):
    """A realistic tracked-file manifest beyond the former 64 KiB limit."""
    with zipfile.ZipFile(path) as original:
        manifest = json.loads(original.read("manifest.json"))
        facts = original.read("test-facts.json")
    manifest["base_entries"] = [
        {"path": f"src/module_{i:05d}.py", "git_mode": "100644", "object_id": "a" * 40, "size": i}
        for i in range(3000)
    ]
    raw = json.dumps(manifest, separators=(",", ":")).encode()
    assert 263559 <= len(raw) < 1024 * 1024  # Real SpecRoad scale; bounded fixture.
    temporary = path.with_suffix(".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        dst.writestr("manifest.json", raw)
        dst.writestr("test-facts.json", facts)
    temporary.replace(path)
    return read_package(path)


class LargeManifestTests(AutomationCase):
    def test_large_valid_result_is_discovered_by_run_and_exact_sha(self):
        seed = enlarge_result(Path(self.seed["path"]))
        self.assertEqual(hint(Path(seed["path"]))["manifest"]["run_id"], seed["run_id"])
        chosen = Exchange(self.config, FakeCore()).source(seed)
        self.assertEqual(chosen["sha256"], seed["sha256"])
        self.assertEqual(chosen["binding"], seed["binding"])

    def test_resource_budget_still_bounds_manifest_preview(self):
        seed = enlarge_result(Path(self.seed["path"]))
        with patch.object(scan, "MAX_RESULT_HINT_BYTES", 1024):
            self.assertIsNone(hint(Path(seed["path"])))
            self.assertFalse(list(Exchange(self.config, FakeCore()).candidates("result", lambda m: True)))
        self.assertIsNotNone(hint(Path(seed["path"])))

    def test_duplicate_manifest_is_not_a_usable_hint(self):
        candidate = self.exchange / "duplicate.zip"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(candidate, "w") as archive:
                payload = json.dumps({**self.binding, "marker": "patch-harbor-result-bundle",
                                      "run_id": self.seed["run_id"]})
                archive.writestr("manifest.json", payload)
                archive.writestr("manifest.json", payload)
        self.assertIsNone(hint(candidate))

    def test_duplicate_json_key_is_not_a_usable_hint(self):
        candidate = self.exchange / "duplicate-json.zip"
        with zipfile.ZipFile(candidate, "w") as archive:
            archive.writestr("manifest.json", b'{"marker":"patch-harbor-result-bundle","repo_id":"x","repo_id":"y"}')
        self.assertIsNone(hint(candidate))

    def test_large_followup_result_activates_one_dev_turn(self):
        codex = FakeCodex(self)
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=codex) as engine:
            engine.tick()
            followup = self.result("large-followup.zip", previous=self.seed,
                                   patch_sha=engine.exchange.patches(self.seed)[0]["sha256"])
            enlarge_result(Path(followup["path"]))
            engine.tick()
            self.assertEqual(codex.calls, 2)
            self.assertFalse(engine.tick()["again"])
            self.assertEqual(codex.calls, 2)
