"""Continuation binds every relevant component; parity is not byte identity."""
from dataclasses import replace

import pytest

from specroad.analyzers._values import AnalyzerError, decode, digest, encoded
from specroad.analyzers.engine_identity import bind_engine, engine_identity, numeric_inventory
from specroad.analyzers.requests import create_request
from test_analyzer_engine import engine
from test_analyzer_policy import case, assess
from test_analyzer_comparison import detected


def changed(field):
    original = engine()
    if field == 'model':
        return replace(original, model_sha256='d' * 64)
    if field == 'library':
        return replace(original, library_versions=(('numpy', '2.3.5'), ('py3langid', '0.4.1')))
    if field == 'unicode':
        return replace(original, unicode_version='16.0.0')
    if field == 'candidates':
        candidates = tuple(reversed(original.candidates))
        return replace(original, candidates=candidates, candidates_sha256=digest(list(candidates)))
    name = 'numpy' if field in ('numpy', 'binary', 'cpu') else 'runtime'
    value = decode(getattr(original, name + '_inventory'))
    if field == 'numpy':
        value['version'] = '2.4.0'
        original = replace(original, library_versions=(('numpy', '2.4.0'), ('py3langid', '0.4.0')))
    elif field == 'binary':
        value['binaries'][0]['sha256'] = 'e' * 64
    elif field == 'cpu':
        value['cpu_features']['SSE2'] = False
    elif field == 'python':
        value['python_version'] = '3.13.0'
        original = replace(original, python_version='3.13.0')
    elif field in ('blas_core', 'blas_config', 'threads'):
        value['loaded_numeric_runtime'] = {field: 'changed-observed-value'}
    elif field == 'rounding':
        value['floating_point_rounding'] = 1024
    else:
        value['executable_sha256'] = 'f' * 64
    return replace(original, **{name + '_inventory': encoded(value)})


@pytest.mark.parametrize('field', ['model', 'library', 'unicode', 'candidates', 'numpy',
    'binary', 'cpu', 'python', 'rounding', 'executable', 'blas_core', 'blas_config', 'threads'])
def test_changed_component_prevents_continuation_of_old_engine(field):
    request, _ = case([('en', detected('en'))])
    binding = bind_engine(request, engine())
    binding.require_current(request, engine())
    assert engine_identity(changed(field)).sha256 != engine_identity(engine()).sha256
    with pytest.raises(AnalyzerError) as error:
        binding.require_current(request, changed(field))
    assert error.value.exit_code == 6


def test_changed_preprocessing_version_invalidates_engine_binding(monkeypatch):
    request, _ = case([('en', detected('en'))])
    binding = bind_engine(request, engine())
    monkeypatch.setattr('specroad.analyzers.engine_identity.TEXT_POLICY_VERSION', 'different-v2')
    with pytest.raises(AnalyzerError) as error:
        binding.require_current(request, engine())
    assert error.value.exit_code == 6


@pytest.mark.parametrize('field', ['runtime_inventory', 'numpy_inventory'])
def test_missing_numeric_identity_is_unavailable_not_compatible(field):
    request, _ = case([('en', detected('en'))])
    binding = bind_engine(request, engine())
    with pytest.raises(AnalyzerError) as error:
        binding.require_current(request, replace(engine(), **{field: None}))
    assert error.value.exit_code == 5


def test_observed_version_must_agree_with_declared_engine():
    for field, value in [('python_version', '3.99.0'), ('python_implementation', 'foreign'),
        ('library_versions', (('numpy', 'different'), ('py3langid', '0.4.0')))]:
        with pytest.raises(AnalyzerError) as error:
            engine_identity(replace(engine(), **{field: value}))
        assert error.value.exit_code == 6


def test_same_decisions_across_runtimes_do_not_pretend_byte_equal_reports():
    request, decisions = case([('en-US', detected('en'))])
    first = assess(request, replace(decisions, engine=engine()))
    other = assess(request, replace(decisions, engine=changed('python')))
    assert first.data == other.data and first.report.data['subjects'] == other.report.data['subjects']
    assert first.report.result_sha256 != other.report.result_sha256
    assert first.report.data['engine'] != other.report.data['engine']


def test_continuation_binding_is_json_only_and_request_specific():
    request, _ = case([('en', detected('en'))])
    binding = bind_engine(request, engine())
    assert binding.data == dict(binding_version='language-engine-v1', **request.binding,
        analyzer=request.data['analyzers'][0], engine_sha256=engine_identity(engine()).sha256)
    data = request.data
    other = create_request(**{k: data[k] for k in ('analyzers', 'subjects', 'settings', 'context', 'extensions')},
                           analysis_id='different-request')
    with pytest.raises(AnalyzerError) as error:
        binding.require_current(other, engine())
    assert error.value.exit_code == 6
    assert 'model' not in binding.data and 'pickle' not in binding.data


def test_missing_inventory_api_is_explicit_unknown_not_invented_measurement(monkeypatch):
    from types import SimpleNamespace
    from pathlib import Path
    original = Path.read_text
    def read(path, *args, **kwargs):
        if path.as_posix() == '/proc/self/maps':
            raise OSError('measurement unavailable')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    assert numeric_inventory(SimpleNamespace(__version__='test-only')) == (None, None)
