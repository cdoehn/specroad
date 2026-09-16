"""Language declarations are data contracts, not translated display strings."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import unittest

from specroad.model.language_tags import LanguageTagError, parse_language_tag
from specroad.model.language_registry import LanguageRegistry, LanguageRegistryError
from specroad.storage.language_registry import bundled_language_registry
from support.languages import registry_bytes, load_registry


class LanguageSyntaxTests(unittest.TestCase):
    def test_minimum_declared_corpus(self):
        for value in ("en-US", "en-IN", "hi-IN", "id-ID", "pt-BR", "es-MX", "ru-RU", "ja-JP", "de-DE",
                      "zh-Hans-CN", "cmn-Hans-CN", "zh-Hant", "ar", "ur-IN", "und", "mul", "zxx"):
            with self.subTest(tag=value): self.assertEqual(parse_language_tag(value).original, value)

    def test_case_only_canonicalization(self):
        tag = parse_language_tag("ZH-hANS-cn")
        self.assertEqual((tag.original, tag.canonical), ("ZH-hANS-cn", "zh-Hans-CN"))

    def test_unknown_primary_syntax_is_not_a_language_allowlist(self):
        for tag in ("zz", "zzzz", "abcdefgh", "abcde-Latn-999"):
            self.assertEqual(parse_language_tag(tag).original, tag)

    def test_private_only(self):
        value = parse_language_tag("X-Project-A-42")
        self.assertEqual(value.canonical, "x-project-a-42")
        self.assertEqual(value.private_subtags, ("project", "a", "42"))
        self.assertIsNone(value.language)

    def test_script_region_and_variants(self):
        tag = parse_language_tag("sl-rozaj-biske-1994")
        self.assertEqual(tag.variants, ("rozaj", "biske", "1994"))
        self.assertEqual(parse_language_tag("es-419").region, "419")

    def test_extlang_parts(self):
        tag = parse_language_tag("zh-cmn-Hans-CN")
        self.assertEqual((tag.language, tag.extlangs, tag.script, tag.region), ("zh", ("cmn",), "Hans", "CN"))

    def test_extensions_preserved_in_original_order(self):
        tag = parse_language_tag("en-B-FOO-a-BAR-X-CUSTOM")
        self.assertEqual(tag.canonical, "en-b-foo-a-bar-x-custom")
        self.assertEqual(tag.extensions, (("b", ("foo",)), ("a", ("bar",))))

    def test_numeric_singleton(self):
        self.assertEqual(parse_language_tag("de-0-foo").extensions, (("0", ("foo",)),))

    def test_grandfathered_not_aliased(self):
        for tag in ("i-klingon", "en-GB-oed", "sgn-BE-FR", "zh-min-nan", "no-bok"):
            self.assertTrue(parse_language_tag(tag).grandfathered)
            self.assertEqual(parse_language_tag(tag.upper()).canonical, tag)

    def test_grandfathered_suffix_not_automatically_valid(self):
        for tag in ("i-klingon-US", "en-GB-oed-x-test"):
            with self.assertRaises(LanguageTagError): parse_language_tag(tag)

    def test_reject_non_ascii_and_separator_variations(self):
        for tag in ("de_DE", "de–DE", "еn", "zh-汉字", " de", "de ", "de\n", "de\x00", "de/DE"):
            with self.subTest(tag=tag), self.assertRaises(LanguageTagError): parse_language_tag(tag)

    def test_reject_empty_components(self):
        for tag in ("", "en--US", "en-", "-en", "x", "en-x", "en-a", "en-abcdefghi"):
            with self.subTest(tag=tag), self.assertRaises(LanguageTagError): parse_language_tag(tag)

    def test_reject_non_string_without_coercion(self):
        for value in (None, True, 12, b"en", [], {}):
            with self.assertRaises(LanguageTagError): parse_language_tag(value)

    def test_reject_component_order(self):
        for tag in ("en-US-Latn", "en-1234-US", "a-foo", "123", "abcd-abc"):
            with self.subTest(tag=tag), self.assertRaises(LanguageTagError): parse_language_tag(tag)

    def test_duplicate_variant_rejected_case_insensitively(self):
        with self.assertRaises(LanguageTagError) as caught: parse_language_tag("de-1901-1901")
        self.assertEqual(caught.exception.reason, "duplicate_variant")

    def test_duplicate_extension_rejected_case_insensitively(self):
        with self.assertRaises(LanguageTagError) as caught: parse_language_tag("en-a-one-A-two")
        self.assertEqual(caught.exception.reason, "duplicate_extension")

    def test_repeated_private_values_are_opaque(self):
        self.assertEqual(parse_language_tag("x-foo-foo-x").private_subtags, ("foo", "foo", "x"))

    def test_unspecified_is_independent_from_syntax(self):
        for tag in ("und", "mul", "zxx"):
            self.assertTrue(parse_language_tag(tag).unspecified)
        self.assertFalse(parse_language_tag("de").unspecified)

    def test_tag_value_is_immutable(self):
        with self.assertRaises(FrozenInstanceError): parse_language_tag("en").canonical = "fr"


class RegistryLookupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.registry = bundled_language_registry()

    def test_all_minimum_cases_are_registered(self):
        for tag in ("en-US", "en-IN", "hi-IN", "id-ID", "pt-BR", "es-MX", "ru-RU", "ja-JP", "de-DE", "zh-Hans-CN", "cmn-Hans-CN", "zh-Hant", "ar", "ur-IN"):
            with self.subTest(tag=tag): self.assertEqual(self.registry.inspect(tag).registry_state, "registered")

    def test_unsupported_language_is_retained_not_invalid(self):
        result = self.registry.inspect("zzzz-Latn")
        self.assertTrue(result.syntax_valid)
        self.assertEqual(result.registry_state, "unverified_registry")
        self.assertEqual(result.original, "zzzz-Latn")
        self.assertIn("language:zzzz", result.unknown_subtags)

    def test_all_four_states(self):
        for tag, state in (("en-US", "registered"), ("x-company", "private_use"), ("zzzz", "unverified_registry"), ("en_US", "invalid_syntax")):
            self.assertEqual(self.registry.inspect(tag).registry_state, state)

    def test_reserved_private_subtags(self):
        for tag in ("qaa", "qtz", "en-Qaaa", "en-Qabx", "en-AA", "en-QM", "en-XZ", "en-ZZ"):
            with self.subTest(tag=tag): self.assertEqual(self.registry.inspect(tag).registry_state, "private_use")

    def test_private_suffix_does_not_hide_unknown_subtags(self):
        self.assertEqual(self.registry.inspect("zzzz-x-foo").registry_state, "unverified_registry")
        self.assertEqual(self.registry.inspect("en-x-foo").registry_state, "private_use")

    def test_deprecated_subtags_preserved(self):
        result = self.registry.inspect("iw-IL")
        self.assertEqual(result.canonical, "iw-IL")
        self.assertIn("iw", result.deprecated)
        self.assertIn(("iw", "he"), result.preferred_values)

    def test_macro_language_not_equated(self):
        self.assertNotEqual(self.registry.inspect("zh-Hans-CN").canonical, self.registry.inspect("cmn-Hans-CN").canonical)

    def test_grandfathered_lookup(self):
        result = self.registry.inspect("I-KLINGON")
        self.assertEqual(result.registry_state, "registered")
        self.assertEqual(result.canonical, "i-klingon")
        self.assertIn(("i-klingon", "tlh"), result.preferred_values)

    def test_no_extension_registration_claim(self):
        result = self.registry.inspect("en-u-ca-gregory")
        self.assertTrue(result.syntax_valid)
        self.assertEqual(result.registry_state, "unverified_registry")
        self.assertIn("extension_registration_unverified", result.reasons)
        self.assertFalse(result.linguistic_validation)

    def test_extlang_context(self):
        self.assertEqual(self.registry.inspect("zh-cmn").registry_state, "registered")
        self.assertEqual(self.registry.inspect("en-cmn").registry_state, "unverified_registry")

    def test_assessment_carries_actual_snapshot_binding(self):
        result = self.registry.inspect("en")
        self.assertEqual(result.registry_sha256, sha256(self.registry.source_bytes).hexdigest())
        self.assertEqual(result.registry_version, self.registry.version)

    def test_assessment_data_is_detached(self):
        result = self.registry.inspect("zzzz")
        data = result.as_dict(); data["unknown_subtags"].clear()
        self.assertTrue(result.unknown_subtags)

    def test_snapshot_not_current_by_assumption(self):
        registry = load_registry()
        self.assertEqual(registry.inspect("de").registry_state, "unverified_registry")
        self.assertEqual(registry.inspect("en-US").registry_state, "registered")

    def test_whole_registry_records_are_immutable(self):
        record = self.registry.lookup("language", "de")
        with self.assertRaises(FrozenInstanceError): record.value = "en"

    def test_invalid_registry_hash(self):
        with self.assertRaises(LanguageRegistryError) as caught:
            LanguageRegistry(registry_bytes(), expected_sha256="a" * 64, expected_version="2020-01-01")
        self.assertEqual(caught.exception.exit_code, 3)

    def test_actual_date_must_match_binding(self):
        with self.assertRaises(LanguageRegistryError): load_registry(version="2021-01-01")
