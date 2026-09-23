"""Declared-language and named-package behavior, not natural-language truth."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
import pytest
from specroad.model.language_policy import LanguagePolicy, LanguagePolicyError, default_language_policy
from specroad.model.configuration import ProjectConfiguration
from specroad.model.canonical import canonical_json_sha256
from specroad.model.language_packages import LanguagePackage, LanguagePackageError
from specroad.languages import evaluate_language, language_comparison_key, compose_language_packages
from specroad.storage.language_registry import bundled_language_registry
from specroad.storage.language_packages import load_bundled_package
from support.model import configuration_value
from support.languages import load_registry, registry_bytes

@pytest.fixture
def registry():
    return bundled_language_registry()


def package(name="example", ranges=None, rules=None, **changes):
    rules = [] if rules is None else rules
    value = {"package_id": name, "version": "1.0.0", "language_ranges": ["en"] if ranges is None else ranges,
             "labels": {}, "literal_rules": rules, "capabilities": ["metadata"] + (["literal_lint"] if rules else [])}
    value.update(changes)
    return LanguagePackage(json.dumps(value, ensure_ascii=False).encode())


def rule(**changes):
    value = {"format_version": 1, "policy_id": "placeholder_en", "version": "1.0.0", "language": "en",
             "fields": ["/statement"], "term_ids": [], "placeholders": ["XXX"], "references": []}
    value.update(changes)
    return value


def test_complete_defaults_and_owned_materialization():
    expected = {"version": "language-policy-v1", "default_language": "de-DE", "allowed_ranges": ["*"],
        "disallowed_language": "error", "unverified_registry": "warning", "unspecified_language": "error",
        "mixed_languages": {"comparison": "primary_language", "project": "allow", "document": "warning", "section": "warning"}}
    supplied = {}; p = LanguagePolicy(supplied)
    assert p.data == expected and supplied == {}
    assert p.sha256 == canonical_json_sha256(expected)
    d = p.data; d["allowed_ranges"].clear(); assert p.data == expected
    with pytest.raises(FrozenInstanceError): p._encoded = b"{}"


def test_nested_partial_defaults_without_overwriting_explicit_values():
    src = {"allowed_ranges": [], "mixed_languages": {"section": "allow"}}
    old = deepcopy(src); p = LanguagePolicy(src)
    assert p.data["allowed_ranges"] == []
    assert p.data["mixed_languages"] == {"comparison": "primary_language", "project": "allow", "document": "warning", "section": "allow"}
    assert src == old


@pytest.mark.parametrize("value", [None, [], True, "", 7])
def test_policy_requires_object(value):
    with pytest.raises(LanguagePolicyError): LanguagePolicy(value)


@pytest.mark.parametrize("delta", [
    {"version": "language-policy-v2"}, {"version": None}, {"default_language": "de_DE"},
    {"default_language": ""}, {"allowed_ranges": None}, {"allowed_ranges": "en"},
    {"allowed_ranges": ["en-*"]}, {"allowed_ranges": ["*-US"]}, {"allowed_ranges": ["en_US"]},
    {"allowed_ranges": ["é"]}, {"disallowed_language": "info"}, {"unverified_registry": False},
    {"unspecified_language": None}, {"mixed_languages": None}, {"mixed_languages": {"comparison": "detect"}},
    {"mixed_languages": {"project": "info"}}, {"mixed_languages": {"extra": "allow"}}, {"callback": "os.system"}])
def test_closed_policy_and_project_configuration_reject_bad_values(delta):
    with pytest.raises(LanguagePolicyError): LanguagePolicy(delta)
    with pytest.raises(LanguagePolicyError): ProjectConfiguration(configuration_value(language_policy=delta))


@pytest.mark.parametrize("ranges,language,allowed", [
    (["en"], "en-IN", True), (["EN"], "eN-uS", True), (["en"], "enm", False),
    (["en-US"], "en", False), (["zh"], "cmn", False), (["cmn-Hans"], "cmn-Hans-CN", True),
    (["zh-Hans"], "zh-Hans-CN", True), (["zh-Hans"], "zh-Hant", False),
    (["*"], "x-custom", True), (["*"], "qzz", True), ([], "en", False),
    (["iw"], "he", False), (["he"], "iw", False), (["i-klingon"], "tlh", False),
    (["x"], "x-a", True), (["en", "de"], "de-DE", True)])
def test_basic_filtering_boundaries_no_alias_inference(registry, ranges, language, allowed):
    report = evaluate_language(language, policy=LanguagePolicy({"allowed_ranges": ranges}), registry=registry)
    assert report["range_allowed"] is allowed
    assert any(d["code"] == "SRV179" for d in report["diagnostics"]) is (not allowed)


@pytest.mark.parametrize("action,threshold,strict,exit_code", [
    ("allow", "error", False, 0), ("warning", "error", False, 0),
    ("warning", "warning", False, 1), ("warning", "error", True, 1), ("error", "error", False, 1)])
def test_policy_severity_is_not_rewritten_by_fail_threshold(registry, action, threshold, strict, exit_code):
    report = evaluate_language("de", policy=LanguagePolicy({"allowed_ranges": ["en"], "disallowed_language": action}),
                               registry=registry, fail_on=threshold, strict=strict)
    assert report["exit_code"] == exit_code
    assert report["diagnostics"] == ([] if action == "allow" else
        [{"code": "SRV179", "severity": action, "reason": "disallowed_language", "pointer": "/language"}])


@pytest.mark.parametrize("language", ["de_DE", "x", "", None, 7, True])
def test_syntax_is_not_downgradable(registry, language):
    p = LanguagePolicy({"disallowed_language": "allow", "unverified_registry": "allow", "unspecified_language": "allow"})
    report = evaluate_language(language, policy=p, registry=registry)
    assert report["exit_code"] == 3 and report["diagnostics"][0]["code"] == "SRV177"
    assert report["metadata_policy_passed"] is False


@pytest.mark.parametrize("language", ["und", "mul", "zxx", "und-Latn"])
def test_unspecified_language_has_separate_policy_and_no_comparison_key(registry, language):
    result = evaluate_language(language, policy=LanguagePolicy({}), registry=registry)
    assert result["range_allowed"] is True
    assert any(d["code"] == "SRV181" for d in result["diagnostics"])
    assert result["comparison_key"] is None


def test_unknown_and_private_tags_are_distinct(registry):
    p = LanguagePolicy({})
    u = evaluate_language("qzz", policy=p, registry=registry)
    x = evaluate_language("x-qzz", policy=p, registry=registry)
    assert u["assessment"]["registry_state"] == "unverified_registry"
    assert u["diagnostics"][0]["code"] == "SRV178" and u["exit_code"] == 0
    assert x["assessment"]["registry_state"] == "private_use" and not x["diagnostics"]
    assert u["language_detection_performed"] is False and x["approval_granted"] is False


@pytest.mark.parametrize("language,mode,key", [
    ("en-IN", "primary_language", "en"), ("EN-us", "exact_tag", "en-us"),
    ("x-ONE", "primary_language", "x-one"), ("qzz-US", "primary_language", "qzz-us"),
    ("en-x-local", "primary_language", "en-x-local"), ("cmn-Hans", "primary_language", "cmn")])
def test_explicit_comparison_mode(registry, language, mode, key):
    assert language_comparison_key(language, registry=registry, comparison=mode) == key


def test_all_matching_packages_follow_activation_order_not_catalogue_order():
    broad = package("broad"); narrow = package("narrow", ["en-IN"]); other = package("other", ["de"])
    result = compose_language_packages("en-IN", activated=["narrow@1.0.0", "other@1.0.0", "broad@1.0.0"],
                                       resources=[broad, narrow, other]).data
    assert [p["package_id"] for p in result["packages"]] == ["narrow", "broad"]
    assert not result["unavailable"]


def test_no_implicit_activation_or_latest_fallback():
    p = package("example")
    assert not compose_language_packages("en", activated=[], resources=[p]).data["packages"]
    r = compose_language_packages("en", activated=["example@2.0.0"], resources=[p]).data
    assert not r["packages"] and r["unavailable"] == ["example@2.0.0"]


def test_missing_linguistic_capabilities_never_pass():
    p = load_bundled_package("en@1.0.0")
    data = compose_language_packages("en", activated=[p.key], resources=[p]).data
    assert data["capabilities"]["labels"] == "available"
    for name in ("literal_lint", "language_detection", "modality", "contradiction", "translation"):
        assert data["capabilities"][name] == "not_available"
    assert data["lint_passed"] is None and data["diagnostics"][0]["code"] == "SRV182"


def test_named_literal_resources_coalesce_with_provenance_without_execution():
    first = package("first", rules=[rule()]); second = package("second", rules=[rule()])
    result = compose_language_packages("en", activated=[first.key, second.key], resources=[second, first])
    data = result.data
    assert len(data["literal_rules"]) == 1
    assert data["literal_rules"][0]["packages"] == [first.key, second.key]
    assert data["capabilities"]["literal_lint"] == "available"
    assert data["rules_executed"] is False and data["lint_passed"] is None
    data["literal_rules"].clear(); assert len(result.data["literal_rules"]) == 1


@pytest.mark.parametrize("changes", [{"placeholders": ["YYY"]}, {"version": "2.0.0"}])
def test_same_literal_identity_cannot_silently_replace_definition(changes):
    a = package("first", rules=[rule()]); b = package("second", rules=[rule(**changes)])
    with pytest.raises(LanguagePackageError) as e:
        compose_language_packages("en", activated=[a.key, b.key], resources=[a,b])
    assert e.value.reason == "literal_rule_identity_conflict"


def test_same_package_identity_requires_identical_bytes():
    a = package(); b = package(capabilities=["metadata", "labels"])
    with pytest.raises(LanguagePackageError) as e:
        compose_language_packages("en", activated=[a.key], resources=[a,b])
    assert e.value.reason == "package_identity_conflict"


def test_literal_rules_have_no_callback_or_arbitrary_operation():
    with pytest.raises(LanguagePackageError): package(rules=[{"callback": "os.system"}])
    with pytest.raises(LanguagePackageError): package(rules=[rule(program={"op": "shell"})])
    with pytest.raises(LanguagePackageError): package(rules=[rule()], capabilities=["metadata"])


def test_label_pack_for_simplified_chinese_explicitly_supports_two_distinct_ranges():
    p = load_bundled_package("zh-Hans@1.0.0")
    for tag in ("zh-Hans-CN", "cmn-Hans-CN"):
        assert compose_language_packages(tag, activated=[p.key], resources=[p]).data["packages"]
    assert not compose_language_packages("zh-Hant", activated=[p.key], resources=[p]).data["packages"]


def test_basic_filtering_reference_corpus(registry):
    for ranges, tag, allowed in [(["en"],"en-IN",True),(["en"],"enm",False),
            (["en-US"],"en",False),(["zh"],"cmn",False),(["*"],"x-private",True),([],"en",False)]:
        assert evaluate_language(tag, policy=LanguagePolicy({"allowed_ranges":ranges}), registry=registry)["range_allowed"] is allowed


def test_comparison_modes_preserve_registry_and_private_boundaries(registry):
    for mode, same in [("primary_language", True), ("exact_tag", False)]:
        assert (language_comparison_key("en-IN",registry=registry,comparison=mode) ==
                language_comparison_key("en-US",registry=registry,comparison=mode)) is same
    for left,right in [("x-a","x-b"),("qzz-US","qzz-IN"),("cmn","zh")]:
        assert language_comparison_key(left,registry=registry,comparison="primary_language") != language_comparison_key(right,registry=registry,comparison="primary_language")


def test_threshold_and_strict_change_only_exit_not_warning(registry):
    policy=LanguagePolicy({"allowed_ranges":[],"disallowed_language":"warning"})
    a=evaluate_language("en",policy=policy,registry=registry)
    b=evaluate_language("en",policy=policy,registry=registry,strict=True)
    assert a["diagnostics"] == b["diagnostics"]
    assert a["exit_code"] == 0 and b["exit_code"] == 1
