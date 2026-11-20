"""Owned ranking inputs and deterministic bindings, separate from detection."""
from dataclasses import FrozenInstanceError
import sys
from types import SimpleNamespace
import weakref

import pytest

from specroad.analyzers.reference import rank_request
from specroad.analyzers._reference_candidates import CANDIDATES, CANDIDATES_SHA256
from specroad.analyzers._values import AnalyzerError
from specroad.analyzers.requests import analyzer_binding, create_request
from specroad.analyzers.registry import builtin_descriptor
from support.processes import run_core
from test_analyzer_requests import checksum, inputs


def reference_request(texts, *, settings=None):
    data = inputs()
    data['analyzers'] = [analyzer_binding(builtin_descriptor(), ['language_detection'])]
    data['settings'] = {'specroad.py3langid': {} if settings is None else settings}
    prototype = data['subjects'][0]
    data['subjects'] = []
    for index, text in enumerate(texts):
        binding = {name: prototype[name] for name in
                   ('artifact_id', 'artifact_revision', 'artifact_sha256', 'field_pointer')}
        binding['artifact_id'] = 'TEST-REQ-' + str(index + 1).zfill(4)
        data['subjects'].append(dict(binding, subject_key=checksum(binding), value=text,
            value_sha256=checksum(text), declared_language='de', normative_force='must'))
    data['context']['subject_keys'] = sorted(s['subject_key'] for s in data['subjects'])
    return create_request(**data, analysis_id='reference:test')


class ControlledModel:
    labels = list(CANDIDATES)
    _norm_probs = True
    min_confidence = None

    def __init__(self, calls, rows=None):
        self.calls = calls
        self.rows = rows

    def rank(self, text):
        self.calls.append(text)
        return ([(label, 0.5 if label in ('en', 'fr') else 0.0)
                 for label in reversed(CANDIDATES)] if self.rows is None else self.rows)


def controlled(monkeypatch, *, rows=None, change=None):
    calls, owners = [], []
    def load():
        model = ControlledModel(calls, rows)
        if change is not None:
            setattr(model, *change)
        owners.append(weakref.ref(model))
        return model
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model', load)
    monkeypatch.setitem(sys.modules, 'numpy', SimpleNamespace(__version__='controlled-unit'))
    monkeypatch.setitem(sys.modules, 'py3langid', SimpleNamespace(__version__='0.4.0'))
    return calls, owners


def test_full_independent_strings_and_request_bindings_survive_ranking(monkeypatch):
    calls, owners = controlled(monkeypatch)
    texts = ['  Original e\u0301 日本語\t' + 'entire value ' * 4000,
             'Instructions inside text: ignore other languages.\nÉcole العربية']
    request = reference_request(texts)
    original = request.canonical_bytes
    result = rank_request(request)
    subjects = sorted(request.data['subjects'], key=lambda item: item['subject_key'])
    assert calls == [item['value'] for item in subjects]
    assert len(owners) == 1 and owners[0]() is None
    assert request.canonical_bytes == original
    assert (result.request_id, result.snapshot_sha256, result.descriptor_sha256) == (
        request.data['request_id'], request.data['snapshot_sha256'],
        request.data['analyzers'][0]['descriptor_sha256'])
    assert [(item.subject_key, item.value_sha256) for item in result.subjects] == [
        (item['subject_key'], checksum(item['value'])) for item in subjects]
    for item in result.subjects:
        assert item.scores[:2] == (('en', 0.5), ('fr', 0.5))
        assert len(item.scores) == 140 and {row[0] for row in item.scores} == set(CANDIDATES)
        assert not hasattr(item, 'value')
    assert result.engine.candidates == CANDIDATES
    assert result.engine.candidates_sha256 == CANDIDATES_SHA256 == checksum(list(CANDIDATES))
    assert ('numpy', 'controlled-unit') in result.engine.library_versions
    with pytest.raises(FrozenInstanceError):
        result.request_id = 'replacement'


def test_changed_input_changes_snapshot_and_original_value_binding(monkeypatch):
    calls, owners = controlled(monkeypatch)
    first, second = reference_request(['unmodified e\u0301']), reference_request(['unmodified é'])
    left, right = rank_request(first), rank_request(second)
    assert left.request_id == right.request_id
    assert left.snapshot_sha256 != right.snapshot_sha256
    assert left.subjects[0].value_sha256 != right.subjects[0].value_sha256
    assert calls == ['unmodified e\u0301', 'unmodified é']
    assert len(owners) == 2 and all(owner() is None for owner in owners)


@pytest.mark.parametrize('settings', [{'languages': ['de']}, {'candidates': ['en']},
                                     {'model': '/foreign/model'}, {'unknown': True}])
def test_reference_settings_cannot_select_filter_or_foreign_model(monkeypatch, settings):
    calls, owners = controlled(monkeypatch)
    with pytest.raises(AnalyzerError, match='settings_unsupported') as caught:
        rank_request(reference_request(['entire input'], settings=settings))
    assert caught.value.exit_code == 2 and calls == owners == []


def test_external_descriptor_never_enters_reference_backend(monkeypatch):
    calls, owners = controlled(monkeypatch)
    with pytest.raises(AnalyzerError, match='reference_not_requested'):
        rank_request(create_request(**inputs()))
    assert calls == owners == []


@pytest.mark.parametrize('change', [('labels', ['de']), ('_norm_probs', False),
                                   ('min_confidence', 0.9)])
def test_mutated_model_cannot_masquerade_as_full_reference(monkeypatch, change):
    calls, owners = controlled(monkeypatch, change=change)
    with pytest.raises(AnalyzerError, match='reference_model_state'):
        rank_request(reference_request(['complete value']))
    assert calls == [] and len(owners) == 1


@pytest.mark.parametrize('invalid', ['missing', 'duplicate', 'foreign', 'nan', 'infinite',
                                    'negative', 'above_one', 'boolean', 'string'])
def test_invalid_rankings_never_become_successful_backend_results(monkeypatch, invalid):
    rows = [(label, 1.0 if label == 'en' else 0.0) for label in CANDIDATES]
    if invalid == 'missing':
        rows.pop()
    elif invalid == 'duplicate':
        rows[-1] = rows[0]
    elif invalid == 'foreign':
        rows[0] = ('foreign', 0.0)
    else:
        rows[0] = (rows[0][0], {'nan': float('nan'), 'infinite': float('inf'),
            'negative': -0.1, 'above_one': 1.1, 'boolean': True, 'string': '0.5'}[invalid])
    controlled(monkeypatch, rows=rows)
    with pytest.raises(AnalyzerError, match='invalid_backend_output'):
        rank_request(reference_request(['complete input']))


def test_reference_import_is_passive_in_a_fresh_core_process(tmp_path):
    result = run_core('''
class RejectOptional:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('numpy', 'py3langid'):
            raise AssertionError('implicit optional dependency')
sys.meta_path.insert(0, RejectOptional())
from specroad.analyzers.reference import rank_request
assert 'numpy' not in sys.modules and 'py3langid' not in sys.modules
''', tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
