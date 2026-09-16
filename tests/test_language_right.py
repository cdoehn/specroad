"""Boundary cases: corrupt registries, read races and original-data retention."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path
import json
import locale
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from specroad.model.language_tags import LanguageTagError, parse_language_tag
from specroad.model.language_registry import LanguageRegistryError, LanguageRegistry
from specroad.storage.language_registry import (bundled_language_registry, read_language_registry,
                                                require_registry_current, registry_binding)
from specroad.model.artifact_schemas import validate_common_fields
from specroad.model.domain_schemas import validate_domain_fields
from specroad.storage.requirement import RequirementArtifact
from specroad.storage.project import ProjectSource
from specroad.model.errors import ModelError
from support.languages import registry_bytes, load_registry, project_registry
from support.model import configuration_file, put
from support.domain import domain_value
from support.artifacts import common_artifact
from support.portable import build_distribution, copy_source_fixture
from test_requirement import fields, prepare


class RegistryRobustnessTests(unittest.TestCase):
    def test_invalid_encoding(self):
        for raw in (b"\xff", b"\xef\xbb\xbf" + registry_bytes(), registry_bytes() + b"\x00"):
            with self.assertRaises(LanguageRegistryError): load_registry(raw)

    def test_reject_bad_header_dates(self):
        for value in (b"2020-02-30", b"20200101", b"yesterday", b"2020-1-1"):
            with self.assertRaises(LanguageRegistryError): load_registry(registry_bytes().replace(b"2020-01-01", value))

    def test_duplicate_records_case_insensitive(self):
        with self.assertRaises(LanguageRegistryError): load_registry(registry_bytes(("language", "en"), ("language", "EN")))

    def test_missing_required_fields(self):
        for field in (b"Type: language\n", b"Added: 2005-10-16\n", b"Description: Synthetic test record\n"):
            with self.assertRaises(LanguageRegistryError): load_registry(registry_bytes().replace(field, b""))

    def test_duplicate_singular_fields(self):
        raw = registry_bytes().replace(b"Type: language", b"Type: language\nType: language")
        with self.assertRaises(LanguageRegistryError): load_registry(raw)

    def test_folded_and_repeated_descriptions_are_passive(self):
        raw = registry_bytes().replace(b"Description: Synthetic test record", b"Description: First\n  folded\nDescription: Second")
        record = load_registry(raw).lookup("language", "en")
        self.assertEqual(record.values("Description"), ("First folded", "Second"))

    def test_reject_empty_records(self):
        for raw in (registry_bytes() + b"%%\n", registry_bytes().replace(b"%%\n", b"%%\n%%\n", 1)):
            with self.assertRaises(LanguageRegistryError): load_registry(raw)

    def test_malformed_subtag_type(self):
        for kind, value in (("language", "1a"), ("script", "Latin"), ("region", "USA"), ("variant", "abc")):
            with self.subTest(kind=kind), self.assertRaises(LanguageRegistryError): load_registry(registry_bytes((kind, value)))

    def test_unsupported_record_type(self):
        with self.assertRaises(LanguageRegistryError): load_registry(registry_bytes(("python", "evil")))

    def test_reserved_range_lookup(self):
        registry = load_registry(registry_bytes(("language", "qaa..qtz")))
        self.assertEqual(registry.inspect("qat").registry_state, "private_use")
        self.assertEqual(registry.inspect("qua").registry_state, "unverified_registry")

    def test_arbitrary_ranges_rejected(self):
        with self.assertRaises(LanguageRegistryError): load_registry(registry_bytes(("language", "aaa..zzz")))

    def test_overlapping_range_and_single_record_rejected(self):
        with self.assertRaises(LanguageRegistryError): load_registry(registry_bytes(("language", "qaa..qtz"), ("language", "qat")))

    def test_extlang_prefix_required(self):
        with self.assertRaises(LanguageRegistryError): load_registry(registry_bytes(("extlang", "cmn")))

    def test_variant_prefix_advice_is_not_allowlist(self):
        registry = bundled_language_registry()
        self.assertEqual(registry.inspect("en-1901").registry_state, "registered")

    def test_no_alias_resolution_for_regions(self):
        registry = bundled_language_registry(); result = registry.inspect("en-BU")
        self.assertEqual(result.canonical, "en-BU")
        self.assertIn(("BU", "MM"), result.preferred_values)

    def test_all_grandfathered_records_parse(self):
        registry = bundled_language_registry()
        for record in registry.records:
            if record.kind == "grandfathered":
                with self.subTest(tag=record.value): self.assertEqual(registry.inspect(record.value).registry_state, "registered")

    def test_numeric_region(self):
        self.assertEqual(bundled_language_registry().inspect("es-419").registry_state, "registered")

    def test_unknown_script_and_region_kept(self):
        result = bundled_language_registry().inspect("en-Abcd-999")
        self.assertTrue(result.syntax_valid); self.assertEqual(result.registry_state, "unverified_registry")
        self.assertEqual(result.canonical, "en-Abcd-999")

    def test_invalid_syntax_has_no_registration_claim(self):
        result = bundled_language_registry().inspect("de_DE")
        self.assertFalse(result.syntax_valid); self.assertIsNone(result.canonical)
        self.assertFalse(result.linguistic_validation)

    def test_long_private_tags_are_not_silently_truncated(self):
        tag = "x-" + "-".join(["abcdefgh"] * 200)
        self.assertEqual(parse_language_tag(tag).canonical, tag)

    def test_invalid_tag_does_not_call_conversion_hooks(self):
        class Dangerous:
            def __str__(self): raise AssertionError("conversion executed")
        self.assertEqual(bundled_language_registry().inspect(Dangerous()).registry_state, "invalid_syntax")

    def test_snapshot_hash_covers_representation_bytes(self):
        raw = registry_bytes(); crlf = raw.replace(b"\n", b"\r\n")
        self.assertNotEqual(load_registry(raw).sha256, load_registry(crlf).sha256)
        self.assertEqual(load_registry(raw).inspect("en").registry_state, load_registry(crlf).inspect("en").registry_state)

    def test_old_and_new_snapshots_remain_separate(self):
        old = load_registry(); new = load_registry(registry_bytes(("language", "en"), ("language", "de"), version="2021-01-01"), version="2021-01-01")
        self.assertEqual(old.inspect("de").registry_state, "unverified_registry")
        self.assertEqual(new.inspect("de").registry_state, "registered")
        self.assertEqual(old.inspect("de").registry_state, "unverified_registry")


class LanguageIntegrationTests(unittest.TestCase):
    def test_bad_language_rejected_by_common_schema(self):
        for kind, prefix in (("requirement", "REQ"), ("document", "DOC"), ("term", "TERM"), ("goal", "GOAL")):
            with self.subTest(kind=kind), self.assertRaises(LanguageTagError) as caught:
                validate_common_fields(common_artifact(kind, prefix, language="de_DE"))
            self.assertEqual(caught.exception.pointer, "/language")

    def test_unknown_private_and_unspecified_remain_schema_valid(self):
        for tag in ("zzzz", "x-project", "und", "mul", "zxx", "en-u-foo"):
            with self.subTest(tag=tag): validate_domain_fields(domain_value("requirement", language=tag))

    def test_loaded_tag_and_bytes_unchanged(self):
        raw = json.dumps(domain_value("requirement", language="DE-de"), indent=3).encode()
        artifact = RequirementArtifact(raw)
        self.assertEqual(artifact.source_bytes, raw)
        self.assertEqual(artifact.data["language"], "DE-de")

    def test_new_draft_uses_case_only_normalization(self):
        original = fields(language="ZH-hANS-cn", statement="e\u0301 unchanged")
        draft = prepare(original)
        self.assertEqual(draft.data["language"], "zh-Hans-CN")
        self.assertEqual(draft.data["statement"], original["statement"])
        self.assertEqual(original["language"], "ZH-hANS-cn")

    def test_new_draft_does_not_apply_preferred_values(self):
        self.assertEqual(prepare(fields(language="IW-il")).data["language"], "iw-IL")
        self.assertEqual(prepare(fields(language="cmn-hans-cn")).data["language"], "cmn-Hans-CN")

    def test_locale_services_are_not_used(self):
        registry = bundled_language_registry()
        with patch("locale.setlocale", side_effect=AssertionError("host locale used")):
            self.assertEqual(registry.inspect("TR-tr").canonical, "tr-TR")

    def test_configuration_changed_after_source_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project_registry(root); source = ProjectSource(root)
            configuration_file(root)
            with self.assertRaises(ModelError): read_language_registry(source)

    def test_registry_changes_between_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); binding = project_registry(root); source = ProjectSource(root)
            original = source.boundary.read_bytes; count = 0
            def read(boundary, path):
                nonlocal count
                data = original(path)
                if path == binding["path"]:
                    count += 1
                    if count == 1: (root / path).write_bytes(data + b"\n")
                return data
            with patch.object(type(source.boundary), "read_bytes", read), self.assertRaises(LanguageRegistryError): read_language_registry(source)

    def test_changed_observation_not_refreshed_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); binding = project_registry(root); source = ProjectSource(root)
            old = read_language_registry(source)
            newer = registry_bytes(("language", "en"), ("language", "de"))
            project_registry(root, newer)
            with self.assertRaises(LanguageRegistryError): require_registry_current(ProjectSource(root), old)

    def test_same_observation_can_be_revalidated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project_registry(root); source = ProjectSource(root)
            old = read_language_registry(source)
            self.assertEqual(require_registry_current(source, old).source_bytes, old.source_bytes)

    def test_invalid_bound_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); binding = project_registry(root); binding["registry_version"] = "2021-01-01"
            configuration_file(root, language_registry=binding)
            with self.assertRaises(LanguageRegistryError): read_language_registry(ProjectSource(root))

    def test_nested_project_is_not_read_as_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); project_registry(root); put(root, "profiles/specroad.json", b"{}")
            with self.assertRaises(LanguageRegistryError): read_language_registry(ProjectSource(root))

    def test_data_bytes_participate_in_build_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = copy_source_fixture(root / "src"); first, _ = build_distribution(root / "first", source)
            registry = source / "specroad/language_data/registry.txt"; registry.write_bytes(registry.read_bytes() + b"\n")
            second, _ = build_distribution(root / "second", source)
            # _build is an explicitly machine-readable identity, not CLI text.
            a = {}; b = {}
            exec((first / "specroad/_build.py").read_text(), a)
            exec((second / "specroad/_build.py").read_text(), b)
            self.assertNotEqual(a["BUILD_METADATA"]["build_sha256"], b["BUILD_METADATA"]["build_sha256"])

    def test_corrupt_shipped_registry_not_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = copy_source_fixture(root / "src")
            (source / "specroad/language_data/registry.txt").write_bytes(b"corrupt")
            module, _ = build_distribution(root / "built", source)
            script = ("import sys;sys.path.insert(0,sys.argv[1]);"
                      "from specroad.storage.language_registry import bundled_language_registry;"
                      "bundled_language_registry()")
            result = subprocess.run([sys.executable,"-I","-B","-c",script,str(module)],stdin=subprocess.DEVNULL,capture_output=True)
            self.assertNotEqual(result.returncode, 0)


class DistributionBindingTests(unittest.TestCase):
    def _load(self, transform):
        registry = load_registry()
        manifest = {"format_version": 1, "registry_id": "iana-language-subtags", "registry_version": registry.version,
                    "filename": "registry.txt", "sha256": registry.sha256, "validator_version": "specroad-bcp47-v1",
                    "record_count": len(registry.records), "source": {}}
        raw = transform(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); put(root, "registry.txt", registry.source_bytes); put(root, "snapshot.json", raw)
            with patch("specroad.storage.language_registry.files", return_value=root):
                return bundled_language_registry()

    def test_distribution_binding_rejects_duplicate_json_keys(self):
        def duplicate(value):
            raw = json.dumps(value).encode(); return b'{"format_version":1,' + raw[1:]
        with self.assertRaises(LanguageRegistryError): self._load(duplicate)

    def test_distribution_cannot_redirect_registry_path(self):
        def redirect(value): value["filename"] = "../outside.txt"; return json.dumps(value).encode()
        with self.assertRaises(LanguageRegistryError): self._load(redirect)

    def test_distribution_requires_actual_integer_version_and_count(self):
        for key in ("format_version", "record_count"):
            def corrupt(value): value[key] = True; return json.dumps(value).encode()
            with self.subTest(field=key), self.assertRaises(LanguageRegistryError): self._load(corrupt)

    def test_distribution_requires_matching_validator(self):
        def corrupt(value): value["validator_version"] = "unknown-v99"; return json.dumps(value).encode()
        with self.assertRaises(LanguageRegistryError): self._load(corrupt)
