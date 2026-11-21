"""Lazy ownership and passive commands; no inferred classifier quality."""
import builtins
import gc
import weakref
from unittest.mock import patch

import pytest

from specroad.analyzers._model_session import ModelSession
from specroad.analyzers._values import AnalyzerError, encoded
from specroad.analyzers.requests import AnalyzerRequest, analyzer_binding, create_request
from specroad.analyzers.registry import builtin_descriptor
from specroad.analyzers.worker import run_request
from specroad.cli.application import dispatch_result
from support.processes import run_core
from support.read_only import inventory
from test_analyzer_requests import inputs
from support.domain import domain_value
from support.inspection import inspection_project
from test_analyzer_cli import observation_files
from test_analyzer_worker import request_value


class OwnedModel:
    pass


def test_session_is_lazy_reuses_one_model_and_releases_it(monkeypatch):
    loaded = []
    def load():
        value = OwnedModel()
        loaded.append(weakref.ref(value))
        return value
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model', load)
    with ModelSession() as session:
        assert loaded == []
        assert session.model() is session.model() is session.model()
        assert len(loaded) == 1 and loaded[0]() is not None
    gc.collect()
    assert loaded[0]() is None
    with pytest.raises(AnalyzerError, match='session_closed'):
        session.model()


def test_failed_initialization_is_not_retried_within_the_worker(monkeypatch):
    attempts = []
    def missing():
        attempts.append(1)
        raise AnalyzerError('missing_dependency', exit_code=5)
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model', missing)
    with ModelSession() as session:
        for _ in range(3):
            with pytest.raises(AnalyzerError, match='missing_dependency') as caught:
                session.model()
            assert caught.value.exit_code == 5
    assert attempts == [1]


def test_explicit_worker_loads_once_and_preserves_every_analyzer(monkeypatch):
    value = inputs()
    value['analyzers'].append(analyzer_binding(builtin_descriptor(), ['language_detection']))
    value['analyzers'].sort(key=lambda row: row['descriptor']['analyzer_id'])
    from specroad.analyzers.language_policy import materialize_policy
    value['settings']['specroad.py3langid'] = {'language_detection':materialize_policy()}
    request = create_request(**value)
    living = []
    def load():
        model = OwnedModel(); living.append(weakref.ref(model)); return model
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model', load)
    def unavailable_engine(descriptor):
        raise AnalyzerError('missing_dependency', exit_code=5)
    monkeypatch.setattr('specroad.analyzers._work_engine._engine', unavailable_engine)
    package = run_request(request)
    gc.collect()
    assert len(living) == 1 and living[0]() is None
    assert package.request.canonical_bytes == request.canonical_bytes
    assert [r.data['analyzer'] for r in package.reports] == request.data['analyzers']
    # The deliberately incomplete model has no verified numeric backend; its
    # lifetime and the complete external coverage remain observable.
    assert all(r.data['coverage']['open'] == r.data['coverage']['expected'] for r in package.reports)


def test_external_only_worker_never_imports_an_optional_backend():
    with patch('specroad.analyzers._model_session.load_reference_model',
               side_effect=AssertionError('external descriptor selected a model')):
        package = run_request(create_request(**inputs()))
    assert all(r.data['run_status'] == 'unavailable' for r in package.reports)


def test_loader_failure_keeps_the_full_request_open(monkeypatch):
    def missing():
        raise AnalyzerError('missing_dependency', exit_code=5)
    monkeypatch.setattr('specroad.analyzers._model_session.load_reference_model', missing)
    request = AnalyzerRequest(encoded(request_value()))
    package = run_request(request)
    assert package.request.canonical_bytes == request.canonical_bytes
    assert package.reports[0].data['run_status'] == 'unavailable'
    assert package.reports[0].data['coverage']['open'] == package.reports[0].data['coverage']['expected']


@pytest.mark.parametrize('command', ['help', 'version', 'validate', 'show', 'list'])
def test_passive_commands_neither_import_dependencies_nor_initialize_model(tmp_path, command):
    # Passive validation needs real profile and language-register resources.
    values = [domain_value('requirement')]
    inspection_project(tmp_path, artifacts=values)
    args = {'help':['--help'], 'version':['version'], 'validate':['validate'],
            'show':['show', values[0]['id']], 'list':['analyzer', 'list']}[command]
    before = inventory(tmp_path)
    original = builtins.__import__
    def guarded(name, *arguments, **options):
        if name.split('.')[0] in ('numpy', 'py3langid'):
            raise AssertionError('optional import during passive command: ' + name)
        return original(name, *arguments, **options)
    with patch('builtins.__import__', guarded), patch(
            'specroad.analyzers._model_session.load_reference_model',
            side_effect=AssertionError('implicit model load')):
        result = dispatch_result(args, cwd=tmp_path)
    assert result.exit_code == 0, result.as_dict()
    assert inventory(tmp_path) == before


def test_saved_report_show_never_initializes_a_model(tmp_path):
    observation_files(tmp_path)
    before = inventory(tmp_path)
    with patch('specroad.analyzers._model_session.load_reference_model',
               side_effect=AssertionError('implicit model load')):
        result = dispatch_result(['analyzer', 'show', 'report.json'], cwd=tmp_path)
    assert result.exit_code == 0 and inventory(tmp_path) == before


def test_fresh_worker_and_session_imports_do_not_import_optional_dependencies(tmp_path):
    result = run_core('''
class ForbidOptional:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('numpy', 'py3langid'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, ForbidOptional())
from specroad.analyzers import worker
from specroad.analyzers._model_session import ModelSession
with ModelSession():
    pass
assert 'numpy' not in sys.modules and 'py3langid' not in sys.modules
''', tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
