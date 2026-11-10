"""Resource bounds, concurrent clients and rejected registry images stay isolated."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from specroad.model import _language_registry_parser as parser
from specroad.model.language_registry import LanguageRegistryError
from support.languages import registry_bytes, load_registry
from test_language_registry_reuse import empty_registry_cache, observe_parser


def test_registry_entry_limit_evicts_without_changing_results(monkeypatch):
    images = [registry_bytes().replace(b'Synthetic test record', f'Entry {n}'.encode()) for n in range(5)]
    calls = observe_parser(monkeypatch)
    expected = [load_registry(raw).records for raw in images]
    assert parser._cached_registry_values.cache_info().currsize == 4
    assert load_registry(images[-1]).records == expected[-1]
    assert calls == images
    assert load_registry(images[0]).records == expected[0]
    assert calls == images + images[:1]


def test_large_valid_registry_is_allowed_without_retention(monkeypatch):
    raw = registry_bytes().replace(b'Synthetic test record', b'x' * (1024 * 1024), 1)
    calls = observe_parser(monkeypatch)
    first, second = load_registry(raw), load_registry(raw)
    assert first.records == second.records
    assert first.inspect('en-US').registry_state == 'registered'
    assert calls == [raw, raw]
    assert parser._cached_registry_values.cache_info().currsize == 0


def test_concurrent_registry_clients_own_all_exported_record_objects():
    raw = registry_bytes()
    with ThreadPoolExecutor(max_workers=4) as pool:
        registries = list(pool.map(load_registry, [raw] * 12))
    assert len({id(registry._records) for registry in registries}) == len(registries)
    assert len({id(registry.records[0]) for registry in registries}) == len(registries)
    expected = registries[-1].records
    object.__setattr__(registries[0].records[0], 'value', 'foreign')
    assert all(registry.records == expected for registry in registries[1:])
    assert load_registry(raw).records == expected


@pytest.mark.parametrize('raw', [bytearray(b'registry'), b'\xef\xbb\xbfFile-Date: 2020-01-01', b'\xff'])
def test_reuse_keeps_strict_encoding_and_exact_bytes_type(raw):
    with pytest.raises(LanguageRegistryError):
        parser.parse_registry_records(raw)
    assert parser._cached_registry_values.cache_info().currsize == 0
