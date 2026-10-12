"""Unicode search owns original sources and cannot change their byte identity."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, select_query
from specroad.query.full_text import SearchText
from support.artifacts import artifact_bytes, common_artifact
from support.domain import domain_value
from support.processes import run_core
from support.relations import aid


def requirement(number=1, **changes):
    value = domain_value('requirement', id=aid(number=number), title='ZZZ', statement='ZZZ')
    value.update(changes)
    return value


def select(records, term='CAFÉ', **options):
    return select_query(records, NormalizedQuery(filters={'full_text': [term]}, **options), project={})


@pytest.mark.parametrize('spelling', ['Café', 'Cafe\u0301', 'Straße', 'STRASSE', 'İzmir', 'i\u0307zmir'])
def test_owned_search_observation_keeps_exact_bytes_and_hash(spelling):
    value = requirement(description=spelling)
    raw = json.dumps(value, ensure_ascii=False, indent=3).encode() + b'\n'
    record = SourceRelations(raw)
    observation = SearchText(record)
    detached = record.data
    detached['description'] = 'changed'
    assert observation.artifact_id == value['id']
    assert observation.source_bytes == raw
    assert observation.source_sha256 == sha256(raw).hexdigest()
    assert record.source_bytes == raw and record.data == value
    for name, replacement in [('source_bytes', b'changed'), ('source_sha256', '0' * 64),
                              ('artifact_id', aid(number=2))]:
        with pytest.raises(FrozenInstanceError):
            setattr(observation, name, replacement)


def test_equivalent_unicode_sources_match_but_keep_distinct_original_bindings():
    values = [requirement(description='Café Straße'), requirement(description='Cafe\u0301 Straße')]
    records = [SourceRelations(artifact_bytes(value)) for value in values]
    results = [select([record], select=['/description']) for record in records]
    assert results[0].artifact_ids == results[1].artifact_ids == (aid(number=1),)
    assert results[0].query_sha256 == results[1].query_sha256
    assert results[0].inputs_sha256 != results[1].inputs_sha256
    assert [result.items[0]['values']['/description'] for result in results] == ['Café Straße', 'Cafe\u0301 Straße']
    assert records[0].source_bytes != records[1].source_bytes
    assert SearchText(records[0]).source_sha256 != SearchText(records[1]).source_sha256


def test_equivalent_json_encodings_do_not_collapse_raw_source_identity():
    value = requirement(description='Cafe\u0301')
    raws = [json.dumps(value, ensure_ascii=ascii_mode, indent=indent).encode() + suffix
            for ascii_mode, indent, suffix in [(False, None, b''), (True, 2, b'\n')]]
    records = [SourceRelations(raw) for raw in raws]
    results = [select([record], select=['']) for record in records]
    assert results[0].items == results[1].items == [{
        'id': value['id'], 'artifact_type': 'requirement', 'values': {'': value}}]
    assert results[0].inputs_sha256 != results[1].inputs_sha256
    assert [SearchText(record).source_bytes for record in records] == raws


def test_reusing_identity_after_source_change_cannot_reuse_an_old_search_copy():
    old = SourceRelations(artifact_bytes(requirement(description='Café')))
    current = SourceRelations(artifact_bytes(requirement(description='Library')))
    old_observation = SearchText(old)
    assert select([old]).artifact_ids == (aid(number=1),)
    assert select([current]).items == []
    assert select([current], 'LIBRARY').artifact_ids == (aid(number=1),)
    assert old_observation.matches(('café',)) and not old_observation.matches(('library',))
    assert old_observation.source_bytes == old.source_bytes
    assert SearchText(current).source_sha256 != old_observation.source_sha256


@pytest.mark.parametrize('foreign', [None, b'{}', {}, [], 'Café'])
def test_search_observation_requires_a_real_source_not_decoded_data_or_a_claim(foreign):
    with pytest.raises(ModelError) as caught:
        SearchText(foreign)
    assert caught.value.reason == 'query_search_source_required'


def test_foreign_source_lookalike_is_rejected_without_reading_its_properties():
    class Foreign:
        @property
        def source_bytes(self):
            raise AssertionError('Foreign source code executed')
    with pytest.raises(ModelError) as caught:
        SearchText(Foreign())
    assert caught.value.reason == 'query_search_source_required'


@pytest.mark.parametrize('bad', ['not-an-array', [1], ['Café', None]])
def test_malformed_scenario_main_text_never_becomes_searchable_python_text(bad):
    value = domain_value('scenario', id=aid('scenario', 1), main_flow=bad)
    record = SourceRelations(artifact_bytes(value))
    with pytest.raises(ModelError) as caught:
        select([record])
    assert (caught.value.reason, caught.value.pointer) == ('query_search_text_invalid', '/main_flow')
    assert record.source_bytes == artifact_bytes(value)


@pytest.mark.parametrize('payload', [None, {}, {'markdown': None}, {'markdown': ['Café']}])
def test_malformed_prose_text_is_an_error_without_modifying_source(payload):
    value = common_artifact('content_block', 'BLOCK', id=aid('content_block', 1),
                            block_kind='prose', payload=payload)
    record = SourceRelations(artifact_bytes(value))
    with pytest.raises(ModelError) as caught:
        select([record])
    assert (caught.value.reason, caught.value.pointer) == ('query_search_text_invalid', '/payload/markdown')
    assert record.source_bytes == artifact_bytes(value)


def test_search_normalization_never_changes_exact_owner_tags_or_projection():
    value = requirement(description='Cafe\u0301', owner='CAFÉ', tags=['Straße'])
    record = SourceRelations(artifact_bytes(value))
    query = NormalizedQuery(filters={'full_text': ['CAFÉ'], 'owner': ['café']})
    assert select_query([record], query, project={}).items == []
    query = NormalizedQuery(filters={'full_text': ['CAFÉ'], 'tag': ['STRASSE']})
    assert select_query([record], query, project={}).items == []
    assert select([record], select=['/description', '/owner', '/tags']).items[0]['values'] == {
        '/description': 'Cafe\u0301', '/owner': 'CAFÉ', '/tags': ['Straße']}


def test_equivalent_term_spellings_bind_the_same_query_without_rewriting_input():
    terms = ['CAFÉ', 'cafe\u0301', 'Café']
    queries = [NormalizedQuery(filters={'full_text': [term]}) for term in terms]
    assert len({query.sha256 for query in queries}) == 1
    assert terms == ['CAFÉ', 'cafe\u0301', 'Café']
    record = SourceRelations(artifact_bytes(requirement(description='Cafe\u0301')))
    results = [select_query([record], query, project={}) for query in queries]
    assert len({result.inputs_sha256 for result in results}) == 1
    assert all(result.artifact_ids == (aid(number=1),) for result in results)


def test_actual_locale_switches_in_isolated_process_preserve_hits_and_source_bytes(tmp_path):
    raws = [artifact_bytes(requirement(number, description=text)) for number, text in enumerate(
        ['Café Straße', 'Cafe\u0301 STRASSE', 'İzmir', 'Izmir', 'ΟΣ', 'ος'], 1)]
    body = '''
import json, locale
from hashlib import sha256
from specroad.graph.relations import SourceRelations
from specroad.query import NormalizedQuery, select_query
records = [SourceRelations(raw) for raw in RAW_INPUTS]
reports = []
for name in ('C', 'C.UTF-8', 'C.utf8', 'de_DE.UTF-8', 'de_DE.utf8',
             'tr_TR.UTF-8', 'en_US.UTF-8', '.UTF-8'):
    try:
        active = locale.setlocale(locale.LC_ALL, name)
    except locale.Error:
        continue
    results = []
    for term in ('CAFE\\u0301', 'STRASSE', 'i\\u0307ZMIR', 'οσ'):
        result = select_query(records, NormalizedQuery(filters={'full_text': [term]},
                              select=['/description']), project={})
        results.append({'ids': result.artifact_ids, 'items': result.items,
                        'query': result.query_sha256, 'inputs': result.inputs_sha256})
    reports.append({'locale': active, 'results': results,
                    'sources': [record.source_bytes.hex() for record in records]})
print(json.dumps(reports, ensure_ascii=False))
'''.replace('RAW_INPUTS', repr(raws))
    completed = run_core(body, tmp_path, capture=True)
    assert completed.returncode == 0, completed.stderr.decode()
    reports = json.loads(completed.stdout)
    assert reports and reports[0]['locale'] == 'C'
    expected_ids = [[aid(number=1), aid(number=2)], [aid(number=1), aid(number=2)],
                    [aid(number=3)], [aid(number=5), aid(number=6)]]
    for report in reports:
        assert report['sources'] == [raw.hex() for raw in raws]
        assert [result['ids'] for result in report['results']] == expected_ids
        assert report['results'] == reports[0]['results']
    assert reports[0]['results'][0]['items'][0]['values']['/description'] == 'Café Straße'
    assert reports[0]['results'][0]['items'][1]['values']['/description'] == 'Cafe\u0301 STRASSE'
