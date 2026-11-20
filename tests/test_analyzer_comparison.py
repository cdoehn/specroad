"""Explicit primary-language oracles, independent of permission and scores."""
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.language_comparison import compare_language
from specroad.analyzers.language_scores import ScoreDecision
from specroad.model.language_packages import range_matches
from specroad.storage.language_registry import bundled_language_registry
from support.processes import run_core


@pytest.fixture
def registry():
    return bundled_language_registry()


def detected(code):
    return ScoreDecision('detected', None, code, ((code, '1.000000000000'),))


@pytest.mark.parametrize('declared,code,status,resolution', [
    ('en', 'en', 'compatible', 'primary_language'),
    ('en-US', 'en', 'compatible', 'primary_language'),
    ('en-IN', 'en', 'compatible', 'primary_language'),
    ('EN-us', 'en', 'compatible', 'primary_language'),
    ('zh-Hans-CN', 'zh', 'compatible', 'primary_language'),
    ('zh-Hant-TW', 'zh', 'compatible', 'primary_language'),
    ('cmn', 'zh', 'compatible_coarse', 'macrolanguage_only'),
    ('cmn-Hans-CN', 'zh', 'compatible_coarse', 'macrolanguage_only'),
    ('cmn-Hant-TW', 'zh', 'compatible_coarse', 'macrolanguage_only'),
    ('en-US', 'fr', 'mismatch', 'primary_language'),
    ('zh', 'cmn', 'mismatch', 'primary_language'),
    ('yue', 'zh', 'mismatch', 'primary_language'),
    ('nb', 'no', 'mismatch', 'primary_language'),
    ('iw', 'he', 'mismatch', 'primary_language'),
])
def test_exact_primary_and_only_directional_cmn_zh_exception(registry, declared, code, status, resolution):
    value = compare_language(declared, detected(code), registry=registry)
    assert value.data == dict(comparison_version='language-comparison-v1',
        declared_language=declared, detected_language=code, status=status,
        language_resolution=resolution, region_checked=False, script_checked=False,
        registry_version=registry.version, registry_sha256=sha256(registry.source_bytes).hexdigest())


@pytest.mark.parametrize('declared', ['zzzz', 'x-company', 'en-x-company', 'qaa', 'und', 'mul', 'zxx'])
def test_unknown_private_and_unspecified_declarations_are_unverifiable(registry, declared):
    value = compare_language(declared, detected('en'), registry=registry)
    assert value.status == 'unverifiable' and value.language_resolution is None
    assert value.declared_language == declared


@pytest.mark.parametrize('state,reason', [('undetermined', 'insufficient_text'),
    ('undetermined', 'low_score_or_margin'), ('undetermined', 'backend_abstention'),
    ('undetermined', 'non_linguistic'), ('unavailable', 'analyzer_model_unavailable'),
    ('failed', 'invalid_backend_output')])
def test_nondecisions_remain_nondecisions_not_matches_or_mismatches(registry, state, reason):
    decision = ScoreDecision(state, reason, None, ())
    assert compare_language('en', decision, registry=registry) is None
    assert (decision.status, decision.reason, decision.language) == (state, reason, None)


def test_coarse_comparison_does_not_merge_language_permissions(registry):
    assert compare_language('cmn-Hans-CN', detected('zh'), registry=registry).status == 'compatible_coarse'
    assert not range_matches('zh', 'cmn-Hans-CN')
    assert not range_matches('cmn', 'zh-Hans-CN')


def test_comparison_is_an_immutable_value_with_detached_data(registry):
    decision = detected('en')
    value = compare_language('EN-us', decision, registry=registry)
    value.data['declared_language'] = 'fr'
    assert value.data['declared_language'] == 'EN-us'
    assert decision == detected('en')
    with pytest.raises(FrozenInstanceError):
        value.status = 'mismatch'


@pytest.mark.parametrize('declared', [None, True, {}, 'en_US', ' en', 'en--US'])
def test_malformed_declarations_remain_input_errors(registry, declared):
    with pytest.raises(AnalyzerError, match='analyzer_declared_language') as error:
        compare_language(declared, detected('en'), registry=registry)
    assert error.value.exit_code == 3


def test_comparison_import_does_not_load_the_optional_backend(tmp_path):
    result = run_core('''
class RejectOptional:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('numpy', 'py3langid'):
            raise AssertionError('implicit optional model import')
sys.meta_path.insert(0, RejectOptional())
from specroad.analyzers.language_comparison import compare_language
assert 'numpy' not in sys.modules and 'py3langid' not in sys.modules
''', tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
