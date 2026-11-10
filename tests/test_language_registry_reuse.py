"""Exact-byte registry reuse preserves public bindings and independent values."""
from hashlib import sha256

import pytest

from specroad.model import _language_registry_parser as parser
from specroad.model.language_registry import LanguageRegistry, LanguageRegistryError
from support.languages import registry_bytes, load_registry


@pytest.fixture(autouse=True)
def empty_registry_cache():
    parser._cached_registry_values.cache_clear()
    yield
    parser._cached_registry_values.cache_clear()


def observe_parser(monkeypatch):
    native, calls = parser._parse_registry_records, []

    def observed(raw):
        calls.append(raw)
        return native(raw)

    monkeypatch.setattr(parser, '_parse_registry_records', observed)
    return calls


def test_equal_bytes_parse_once_but_return_independent_public_records(monkeypatch):
    raw = registry_bytes()
    calls = observe_parser(monkeypatch)
    first, second = load_registry(raw), load_registry(bytes(bytearray(raw)))
    assert calls == [raw]
    assert first.source_bytes == second.source_bytes == raw
    assert first.records == second.records and first._records is not second._records
    assert all(a is not b for a, b in zip(first.records, second.records))
    object.__setattr__(first.records[0], 'fields', (('Description', 'tampered'),))
    fresh = load_registry(raw)
    assert fresh.records == second.records
    assert fresh.lookup('language', 'en').values('Description') == ('Synthetic test record',)
    with pytest.raises(TypeError):
        fresh._records[('language', 'fr')] = first.records[0]


@pytest.mark.parametrize('field,expected', [
    ('hash', 'registry_hash_mismatch'), ('version', 'registry_version_mismatch'),
])
def test_warm_cache_does_not_replace_each_callers_binding_check(field, expected):
    raw = registry_bytes()
    load_registry(raw)
    options = dict(expected_sha256=sha256(raw).hexdigest(), expected_version='2020-01-01')
    options['expected_sha256' if field == 'hash' else 'expected_version'] = '0' * 64 if field == 'hash' else '2021-01-01'
    with pytest.raises(LanguageRegistryError) as error:
        LanguageRegistry(raw, **options)
    assert error.value.reason == expected
    assert load_registry(raw).inspect('en-US').registry_state == 'registered'


def test_distinct_registry_bytes_never_share_a_parsed_value(monkeypatch):
    first = registry_bytes()
    second = first.replace(b'Synthetic test record', b'A different description')
    calls = observe_parser(monkeypatch)
    a, b, again = load_registry(first), load_registry(second), load_registry(first)
    assert calls == [first, second]
    assert a.records == again.records and a.records != b.records
    assert b.lookup('language', 'en').values('Description') == ('A different description',)


def test_invalid_inputs_are_checked_again_and_never_become_a_cache_hit(monkeypatch):
    raw = b'File-Date: invalid\n'
    calls = observe_parser(monkeypatch)
    for _ in range(2):
        with pytest.raises(LanguageRegistryError) as error:
            load_registry(raw)
        assert error.value.reason == 'invalid_registry_date'
    assert calls == [raw, raw]
    assert parser._cached_registry_values.cache_info().currsize == 0
