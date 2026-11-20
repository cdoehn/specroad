"""Incomplete backends fail closed before exposing a partial ranking."""
import sys
from types import SimpleNamespace

import pytest

from specroad.analyzers.reference import rank_request
from specroad.analyzers._values import AnalyzerError
from test_analyzer_reference import ControlledModel, controlled, reference_request


@pytest.mark.parametrize('name', ['labels', '_norm_probs', 'min_confidence'])
def test_missing_model_contract_is_an_explicit_failure(monkeypatch, name):
    calls, owners = controlled(monkeypatch)
    monkeypatch.delattr(ControlledModel, name)
    with pytest.raises(AnalyzerError, match='reference_model_state') as caught:
        rank_request(reference_request(['Complete original input']))
    assert caught.value.exit_code == 5 and calls == []
    assert len(owners) == 1


def test_noniterable_model_candidates_fail_before_rank(monkeypatch):
    calls, _ = controlled(monkeypatch, change=('labels', None))
    with pytest.raises(AnalyzerError, match='reference_model_state') as caught:
        rank_request(reference_request(['Complete original input']))
    assert caught.value.exit_code == 5 and calls == []


@pytest.mark.parametrize('library', ['numpy', 'py3langid'])
@pytest.mark.parametrize('version', [None, False, 4, '', 'missing_attribute'])
def test_missing_or_invalid_library_version_never_claims_a_binding(monkeypatch, library, version):
    calls, owners = controlled(monkeypatch)
    module = SimpleNamespace() if version == 'missing_attribute' else SimpleNamespace(__version__=version)
    monkeypatch.setitem(sys.modules, library, module)
    with pytest.raises(AnalyzerError) as caught:
        rank_request(reference_request(['Complete original input']))
    assert caught.value.exit_code == 5 and calls == []
    assert len(owners) == 1


@pytest.mark.parametrize('library', ['numpy', 'py3langid'])
def test_dependency_loss_after_model_load_cannot_produce_a_success(monkeypatch, library):
    calls, _ = controlled(monkeypatch)
    monkeypatch.setitem(sys.modules, library, None)
    with pytest.raises(AnalyzerError, match='model_unavailable') as caught:
        rank_request(reference_request(['Complete original input']))
    assert caught.value.exit_code == 5 and calls == []


@pytest.mark.parametrize('failure', [AttributeError, TypeError, ValueError, OverflowError, ZeroDivisionError])
def test_later_subject_failure_does_not_return_partial_results(monkeypatch, failure):
    calls, owners = controlled(monkeypatch)
    original = ControlledModel.rank
    def rank(model, text):
        if calls:
            raise failure('invalid backend')
        return original(model, text)
    monkeypatch.setattr(ControlledModel, 'rank', rank)
    request = reference_request(['first original', 'second original'])
    before = request.canonical_bytes
    with pytest.raises(AnalyzerError, match='invalid_backend_output') as caught:
        rank_request(request)
    assert caught.value.exit_code == 5 and len(calls) == 1
    assert len(owners) == 1
    assert request.canonical_bytes == before


@pytest.mark.parametrize('rows', [None, (), {}, 0, [None] * 140, [('en',)] * 140,
                                 [(1, 0.0)] * 140, [('en', 0, 0)] * 140])
def test_malformed_backend_shapes_have_no_success_projection(monkeypatch, rows):
    controlled(monkeypatch)
    monkeypatch.setattr(ControlledModel, 'rank', lambda *args: rows)
    with pytest.raises(AnalyzerError, match='invalid_backend_output') as caught:
        rank_request(reference_request(['Complete original input']))
    assert caught.value.exit_code == 5


@pytest.mark.parametrize('failure', [KeyboardInterrupt, SystemExit, MemoryError])
def test_process_control_and_resource_failures_are_not_disguised(monkeypatch, failure):
    controlled(monkeypatch)
    def rank(*args):
        raise failure()
    monkeypatch.setattr(ControlledModel, 'rank', rank)
    with pytest.raises(failure):
        rank_request(reference_request(['Complete original input']))
