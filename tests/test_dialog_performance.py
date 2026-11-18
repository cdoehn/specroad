"""Less repeated pure work, with complete native inputs and isolated results."""
from copy import deepcopy

import pytest

from specroad.model import _schema, _language_registry_parser as parser
from specroad.model.errors import ModelError
from specroad.model.language_values import RegistryRecord
from specroad.model.language_registry import LanguageRegistry
from specroad.qualification import project as qualification
from specroad.qualification.owned import owned_checks
from specroad.storage.language_registry import bundled_language_registry
from test_proposal_basis import project


def test_full_registry_reuses_parsing_without_building_thousands_of_unused_records(monkeypatch):
    parser._cached_registry_values.cache_clear()
    reference = bundled_language_registry()
    expected = reference.records
    native, created = RegistryRecord.__init__, []
    def observed(self, *args, **kwargs):
        created.append(args)
        native(self, *args, **kwargs)
    monkeypatch.setattr(RegistryRecord, '__init__', observed)
    fresh = LanguageRegistry(reference.source_bytes, expected_sha256=reference.sha256,
                             expected_version=reference.version)
    assert not created
    assert fresh.lookup('language', 'en') == reference.lookup('language', 'en')
    assert len(created) == 1
    assert fresh.lookup('language', 'not-registered') is None
    assert len(created) == 1
    assert fresh.lookup('language', 'qaa') == reference.lookup('language', 'qaa')
    assert len(created) == 2
    assert fresh.records == expected
    assert len(created) == len(expected)
    assert all(a is not b for a, b in zip(fresh.records, expected))


def test_warm_schema_reuses_only_vocabulary_and_still_checks_each_instance(monkeypatch):
    _schema._checked_vocabulary.cache_clear()
    native, checked = _schema._check_vocabulary_uncached, []
    def observed(value):
        checked.append(deepcopy(value))
        return native(value)
    monkeypatch.setattr(_schema, '_check_vocabulary_uncached', observed)
    definition = {'type':'object', 'properties':{'value':{'type':'integer'}}, 'required':['value']}
    _schema.validate_builtin({'value':1}, definition)
    _schema.validate_builtin({'value':2}, deepcopy(definition))
    with pytest.raises(ModelError) as failed:
        _schema.validate_builtin({'value':'bad'}, definition)
    assert (failed.value.reason, failed.value.pointer) == ('schema_type', '/value')
    assert checked == [definition]
    definition['properties']['unused'] = {'unsupported-keyword':True}
    for _ in range(2):
        with pytest.raises(ValueError, match='Unsupported built-in schema vocabulary'):
            _schema.validate_builtin({'value':3}, definition)
    assert len(checked) == 3  # failed definitions never become a cache hit


def test_reused_project_model_never_exposes_the_cached_prototype(tmp_path, monkeypatch):
    files = project(tmp_path).source_files
    native, calls = qualification._project_bytes, []
    def observed(values):
        calls.append(dict(values))
        return native(values)
    monkeypatch.setattr(qualification, '_project_bytes', observed)

    @owned_checks
    def operation():
        first, expected_root = qualification.project_bytes(files)
        expected_binding = deepcopy(first.binding)
        expected_registry = first.language_registry.lookup('language', 'de')
        original_record = deepcopy(expected_registry)
        object.__setattr__(expected_registry, 'value', 'foreign')
        object.__setattr__(first.binding, 'source_root', 'foreign')
        object.__setattr__(first.configuration, '_encoded', b'{}')
        object.__setattr__(first.documents[0], 'content', b'{}')
        object.__setattr__(first.profile, '_encoded', b'{}')
        second, root = qualification.project_bytes(dict(files))
        assert second is not first and root == expected_root
        assert second.source_files == files and second.binding == expected_binding
        assert second.language_registry.lookup('language', 'de') == original_record
        assert second.snapshot().source_files == files
        return second

    retained = operation()
    assert len(calls) == 1
    again = operation()
    assert len(calls) == 2 and retained is not again
    qualification.project_bytes(files)
    qualification.project_bytes(files)
    assert len(calls) == 4  # no reuse survives the outer invocation
