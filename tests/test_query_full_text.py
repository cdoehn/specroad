"""Independent literal Unicode search expectations over owned artifact bytes."""
from hashlib import sha256
import pytest

from specroad.graph.relations import SourceRelations
from specroad.model.errors import ModelError
from specroad.query import NormalizedQuery, select_query
from support.artifacts import common_artifact, artifact_bytes
from support.domain import domain_value
from support.relations import aid
from support.srx import binary, expression_document, field, literal


def requirement(number, **changes):
    return domain_value('requirement', id=aid(number=number), title='ZZZ', statement='ZZZ', **changes)


def search(values, *terms, **options):
    filters = {'full_text': list(terms), **options.pop('filters', {})}
    query = NormalizedQuery(filters=filters, **options)
    return select_query([SourceRelations(artifact_bytes(value)) for value in values], query, project={})


@pytest.mark.parametrize('term', ['CAFÉ', 'cafe\u0301', 'CafÉ'])
def test_canonically_equivalent_terms_match_both_stored_forms(term):
    values = [requirement(1, description='Le café reste ouvert.'),
              requirement(2, description='Le cafe\u0301 reste ouvert.'), requirement(3)]
    assert search(values, term).artifact_ids == (aid(number=1), aid(number=2))


@pytest.mark.parametrize('term', ['STRASSE', 'Straße', 'strasse'])
def test_casefold_handles_sharp_s_without_lowercase_shortcuts(term):
    values = [requirement(1, description='Die Straße ist frei.'), requirement(2, description='STRASSE')]
    assert search(values, term).artifact_ids == (aid(number=1), aid(number=2))


def test_greek_sigma_forms_share_casefold_search():
    values = [requirement(1, description='ΟΣ'), requirement(2, description='ος'),
              requirement(3, description='οσ')]
    assert search(values, 'οσ').artifact_ids == tuple(aid(number=n) for n in (1, 2, 3))


def test_dotted_i_uses_unicode_mapping_without_locale_specific_replacement():
    values = [requirement(1, description='İzmir'), requirement(2, description='Izmir')]
    assert search(values, 'i\u0307ZMIR').artifact_ids == (aid(number=1),)


def test_nfc_does_not_remove_accents_or_apply_compatibility_normalization():
    values = [requirement(1, description='Café'), requirement(2, description='Cafe'),
              requirement(3, description='Ａ')]
    assert search(values, 'cafe').artifact_ids == (aid(number=2),)
    assert search([values[2]], 'a').items == []
    assert search([values[2]], 'ａ').artifact_ids == (aid(number=3),)


@pytest.mark.parametrize('kind,field_name,text', [
    ('goal', 'statement', 'Ziel Café'), ('need', 'statement', 'Bedarf Café'),
    ('requirement', 'statement', 'Pflicht Café'), ('assumption', 'statement', 'Annahme Café'),
    ('decision', 'decision', 'Entscheidung Café'), ('component', 'responsibility', 'Aufgabe Café'),
    ('release', 'objective', 'Release Café'), ('milestone', 'objective', 'Meilenstein Café'),
    ('term', 'definition', 'Definition Café')])
def test_declared_type_specific_main_text_is_searched(kind, field_name, text):
    value = domain_value(kind, id=aid(kind, 1), relations=[], **{field_name: text})
    assert search([value], 'CAFE\u0301').artifact_ids == (value['id'],)


def test_title_description_term_and_scenario_steps_are_searchable():
    values = [domain_value('goal', id=aid('goal', 1), title='Café heading'),
              domain_value('capability', id=aid('capability', 1), description='Café service'),
              domain_value('term', id=aid('term', 1), term='Café'),
              domain_value('scenario', id=aid('scenario', 1), main_flow=['Open app', 'Visit Café'])]
    assert set(search(values, 'CAFÉ').artifact_ids) == {value['id'] for value in values}


@pytest.mark.parametrize('block_kind', ['prose', 'admonition'])
def test_document_prose_is_passive_text_at_its_own_block_identity(block_kind):
    payload = {'markdown': '**Café** remains offline. [local](files/menu.txt)'}
    if block_kind == 'admonition':
        payload['level'] = 'note'
    value = common_artifact('content_block', 'BLOCK', id=aid('content_block', 1),
        block_kind=block_kind, payload=payload)
    assert search([value], 'cafe\u0301', select=['/payload/markdown']).items == [{
        'id': value['id'], 'artifact_type': 'content_block',
        'values': {'/payload/markdown': value['payload']['markdown']}}]


def test_repeated_search_terms_are_or_and_other_groups_and_srx_remain_and():
    values = [requirement(1, description='Café', owner='a'),
              requirement(2, description='Straße', owner='a'),
              requirement(3, description='Café', owner='b'), requirement(4, owner='a')]
    expression = expression_document(binary('ne', field('/id'), literal(aid(number=2))))
    result = search(values, 'cafe\u0301', 'STRASSE', filters={'owner': ['a']}, srx_filters=[expression])
    assert result.artifact_ids == (aid(number=1),)
    assert search(values, 'Café', 'CAFE\u0301').items == search(values, 'café').items


def test_punctuation_and_regex_looking_terms_are_literal_substrings():
    values = [requirement(1, description='Literal .* and [x]'), requirement(2, description='Anything else')]
    assert search(values, '.*').artifact_ids == (aid(number=1),)
    assert search(values, '[x]').artifact_ids == (aid(number=1),)


def test_identity_owner_tags_and_extension_payload_are_not_arbitrary_search_text():
    value = requirement(1, owner='needle', tags=['needle'], extensions={'org.example': {'text': 'needle'}})
    assert search([value], 'needle').items == []
    assert search([value], value['id']).items == []


def test_prose_includes_and_non_prose_payload_are_not_opened_or_stringified():
    value = common_artifact('content_block', 'BLOCK', id=aid('content_block', 1),
        block_kind='query', payload={'query': {'filters': {'owner': ['needle']}}})
    assert search([value], 'needle').items == []


def test_source_bytes_hashes_and_projection_stay_in_their_original_unicode_form():
    value = requirement(1, description='Cafe\u0301 Straße')
    raw = artifact_bytes(value);record = SourceRelations(raw);digest = sha256(raw).hexdigest()
    query = NormalizedQuery(filters={'full_text': ['CAFÉ']}, select=['/description'])
    result = select_query([record], query, project={})
    assert result.items[0]['values']['/description'] == 'Cafe\u0301 Straße'
    assert record.source_bytes == raw and sha256(record.source_bytes).hexdigest() == digest
    assert record.data == value


def test_search_does_not_consult_host_locale_or_execute_host_operations(monkeypatch):
    import builtins, locale, socket, subprocess
    records = [SourceRelations(artifact_bytes(requirement(1, description='Straße')))]
    query = NormalizedQuery(filters={'full_text': ['STRASSE']})
    def forbidden(*args, **kwargs):
        raise AssertionError('Fulltext search consulted host state')
    with monkeypatch.context() as guard:
        for name in ('setlocale', 'strxfrm', 'strcoll'):guard.setattr(locale, name, forbidden)
        guard.setattr(builtins, 'open', forbidden);guard.setattr(socket, 'socket', forbidden)
        guard.setattr(subprocess, 'Popen', forbidden)
        result = select_query(records, query, project={})
    assert result.artifact_ids == (aid(number=1),)


def test_selected_known_text_field_with_wrong_type_is_error_not_python_repr():
    value = requirement(1, description={'secret': 'needle'})
    with pytest.raises(ModelError) as caught:search([value], 'needle')
    assert caught.value.reason == 'query_search_text_invalid'
    assert caught.value.pointer == '/description'
