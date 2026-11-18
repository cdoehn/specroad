"""Warm-cache mutations, rejected definitions, scope limits and native models."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json

import pytest

from specroad.bundles.errors import BundleError
from specroad.model import _schema
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.errors import ModelError
from specroad.qualification import project as qualification
from specroad.qualification.owned import owned_checks, checked_bytes
from support.languages import load_registry, registry_bytes
from test_proposal_basis import project


@pytest.mark.parametrize('change', ['type', 'format', 'reference', 'cycle', 'unknown'])
def test_warm_schema_cannot_hide_changes_in_an_unselected_branch(change):
    schema = {'$defs': {'value': {'type':'string'}},
              'properties': {'unused': {'$ref':'#/$defs/value'}}}
    _schema.validate_builtin({}, schema)
    target = schema['$defs']['value']
    target.clear()
    target.update({'type': 'unknown'} if change == 'type' else
                  {'format':'unknown'} if change == 'format' else
                  {'$ref':'#/$defs/missing'} if change == 'reference' else
                  {'$ref':'#/$defs/value'} if change == 'cycle' else
                  {'unsupported':True})
    for _ in range(2):
        with pytest.raises(ValueError):
            _schema.validate_builtin({}, schema)


def test_schema_keys_keep_boolean_number_and_first_diagnostic_order_distinct():
    _schema.validate_builtin(True, {'const':True})
    with pytest.raises(ModelError, match='schema_const'):
        _schema.validate_builtin(True, {'const':1})
    for names in (['a','b'], ['b','a']):
        schema = {'required': names}
        for _ in range(2):
            with pytest.raises(ModelError) as error:
                _schema.validate_builtin({}, schema)
            assert error.value.pointer == '/' + names[0]


def test_schema_cache_evicts_and_large_valid_definitions_use_full_check(monkeypatch):
    _schema._checked_vocabulary.cache_clear()
    native, calls = _schema._check_vocabulary_uncached, []
    def observe(value):
        calls.append(value)
        return native(value)
    monkeypatch.setattr(_schema, '_check_vocabulary_uncached', observe)
    for n in range(129):
        _schema.validate_builtin(n, {'const':n})
    assert _schema._checked_vocabulary.cache_info().currsize == 128
    _schema.validate_builtin(128, {'const':128})
    assert len(calls) == 129
    _schema.validate_builtin(0, {'const':0})
    assert len(calls) == 130
    large = {'description':'x'*(512*1024+1)}
    _schema.validate_builtin({}, large)
    _schema.validate_builtin({}, large)
    assert len(calls) == 132


def test_non_json_annotation_retains_original_path_without_conversion_or_cache():
    class Opaque:
        def __str__(self):
            raise AssertionError('No conversion of schema annotation values')
    value = {'default': Opaque()}
    before = _schema._checked_vocabulary.cache_info()
    for _ in range(2):
        _schema.validate_builtin(None, value)
    assert _schema._checked_vocabulary.cache_info() == before


def test_cloned_registry_keeps_mutated_records_local_and_ranges_lazy():
    raw = registry_bytes(('language', 'en'), ('language', 'qaa..qtz'))
    original = load_registry(raw)
    record = original.lookup('language', 'en')
    object.__setattr__(record, 'fields', (('Description','locally changed'),))
    clone = deepcopy(original)
    assert clone.lookup('language', 'en').fields == record.fields
    assert clone.lookup('language', 'en') is not record
    object.__setattr__(clone.lookup('language', 'en'), 'fields', ())
    assert record.fields == (('Description','locally changed'),)
    assert clone.lookup('language', 'qaz') == original.lookup('language', 'qaz')
    assert clone.lookup('language', 'qaz') is not original.lookup('language', 'qaz')
    assert load_registry(raw).lookup('language', 'en').values('Description') == ('Synthetic test record',)


def test_changed_original_bytes_requalify_and_invalid_bytes_do_not_poison_cache(tmp_path, monkeypatch):
    files = project(tmp_path).source_files
    path = next(p for p in files if p.startswith('spec/goals/'))
    data = json.loads(files[path]); data['title'] += ' changed'
    changed = {**files, path:jcs(data)}
    broken = {**files, path:b'{}'}
    native, calls = qualification._project_bytes, []
    def observed(values):
        calls.append(dict(values))
        return native(values)
    monkeypatch.setattr(qualification, '_project_bytes', observed)
    @owned_checks
    def operation():
        first, root = qualification.project_bytes(files)
        second, other = qualification.project_bytes(changed)
        assert root != other and second.source_files == changed
        for _ in range(2):
            with pytest.raises(BundleError) as error:
                qualification.project_bytes(broken)
            assert error.value.as_dict() == {
                'reason': 'bundle_artifact_type', 'code': 'SRV002', 'exit_code': 3}
        again, retained = qualification.project_bytes(files)
        assert retained == root and again.source_files == first.source_files == files
    operation()
    assert calls == [files, changed, broken, broken]


def test_context_eviction_and_exception_exit_cannot_retain_mutable_results():
    calls = []
    def check(key):
        calls.append(key)
        return {'key':key}
    @owned_checks
    def operation(fail):
        for key in range(9):
            result = checked_bytes('isolation-test', key, lambda:check(key), copy_result=deepcopy)
            result.clear()
        assert checked_bytes('isolation-test', 8, lambda:check(8), copy_result=deepcopy) == {'key':8}
        assert checked_bytes('isolation-test', 0, lambda:check(0), copy_result=deepcopy) == {'key':0}
        if fail:
            raise RuntimeError('abort outer call')
    with pytest.raises(RuntimeError, match='abort outer call'):
        operation(True)
    operation(False)
    assert calls == (list(range(9)) + [0]) * 2


def test_concurrent_outer_scopes_return_independent_native_models(tmp_path):
    files = project(tmp_path).source_files
    @owned_checks
    def operation(_):
        first, digest = qualification.project_bytes(files)
        second, again = qualification.project_bytes(files)
        assert first is not second and digest == again
        object.__setattr__(first.documents[0], 'content', b'{}')
        assert second.source_files == files
        return second
    with ThreadPoolExecutor(max_workers=2) as executor:
        models = list(executor.map(operation, range(4)))
    assert len({id(m.binding) for m in models}) == 4
    assert all(m.source_files == files for m in models)


def test_native_legacy_project_reuse_keeps_original_bytes_and_own_registry():
    from support.legacy_manifest import migrated, BASELINE
    _, files, _ = migrated()
    @owned_checks
    def operation():
        first, root = qualification.project_bytes(files)
        second, other = qualification.project_bytes(files)
        assert root == other and first.source_files == second.source_files
        assert first.source_files[BASELINE] == files[BASELINE]
        assert first.legacy_manifest is not second.legacy_manifest
        object.__setattr__(first.legacy_manifest, '_encoded', b'{}')
        assert second.snapshot().source_files == second.source_files
    operation()
