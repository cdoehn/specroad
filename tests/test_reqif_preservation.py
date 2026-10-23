"""14.j.W: original bytes, passive native carrier and verified target evidence."""
import base64
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from unittest.mock import patch

import pytest

from specroad.exchange import (ReqIFError, assess_reqif_preservation, decode_reqif_structure,
                              merge_reqif_source, restore_reqif_source)
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.metadata import validate_extensions
from specroad.storage.domain_artifact import DomainArtifact
from support.artifacts import artifact_bytes
from support.domain import domain_value
from support.read_only import no_write_attempts
from support.reqif_objects import LIMITS, document, one
from support.reqif_preservation import CONTEXT, opaque_source, source_entry, source_key, target_bytes
from support.reqif_structure import xdocument


def digest(raw):
    return sha256(raw).hexdigest()


def merge(raw, extensions=None, context=None, **overrides):
    extensions = {} if extensions is None else extensions
    args = {'source_context': CONTEXT if context is None else context,
            'expected_source_sha256': digest(raw), 'extensions': extensions,
            'expected_extensions_sha256': canonical_json_sha256(extensions), 'limits': LIMITS}
    args.update(overrides)
    return merge_reqif_source(raw, **args)


def restore(target, raw, **overrides):
    args = {'expected_target_sha256': digest(target), 'extensions_pointer': '/extensions',
            'source_key': source_key(raw), 'limits': LIMITS}
    args.update(overrides)
    return restore_reqif_source(target, **args)


def assess(raw, target=None, kind=None, **overrides):
    args = {'source_context': CONTEXT, 'expected_source_sha256': digest(raw), 'direction': 'import', 'limits': LIMITS}
    if target is not None:
        args.update(target_bytes=target, expected_target_sha256=digest(target), target_kind=kind,
                    extensions_pointer='/extensions' if kind == 'json' else None)
    args.update(overrides)
    return assess_reqif_preservation(raw, **args)


@pytest.mark.parametrize('raw', [opaque_source(), opaque_source().replace(b'\n', b'\r\n'),
    opaque_source().decode().replace('encoding="UTF-8"', 'encoding="UTF-16"').encode('utf-16'),
    one('REAL', '-0.0'), xdocument('<p>text</p>', original='<p>original</p>')])
def test_native_extensions_roundtrip_keeps_exact_xml_and_passive_foreign_values(raw):
    foreign = {'other.tool': {'raw': ['e\u0301', None, False], 'entrypoint': 'never.execute'}}
    before = deepcopy(foreign)
    with no_write_attempts():
        extensions = merge(raw, foreign)
        validate_extensions(extensions)
        native = domain_value('requirement', extensions=extensions)
        target = artifact_bytes(native)
        assert DomainArtifact(target).data['extensions'] == extensions
        returned = restore(target, raw)
    assert returned == raw and foreign == before
    assert extensions['other.tool'] == foreign['other.tool']
    assert extensions['specroad.reqif'] == {'format_version': 'reqif-preservation-v1', 'sources': [source_entry(raw)]}
    extensions['other.tool']['raw'].append('changed')
    assert foreign == before


def test_idempotent_merge_preserves_revisions_same_revision_different_bytes_and_canonical_order():
    versions = [(opaque_source(), CONTEXT), (opaque_source('other'), CONTEXT),
        (opaque_source(), {**CONTEXT, 'external_revision': '1'}),
        (opaque_source(), {**CONTEXT, 'source_system': 'another'}),
        (opaque_source(), {**CONTEXT, 'source_document': 'another'})]
    results = []
    for sequence in (versions, list(reversed(versions))):
        extensions = {'other.tool': {'unchanged': [1, 2]}}
        for raw, context in sequence:
            old = deepcopy(extensions)
            updated = merge(raw, extensions, context)
            assert extensions == old
            assert merge(raw, updated, context) == updated
            extensions = updated
        results.append(extensions)
    assert results[0] == results[1]
    actual = results[0]['specroad.reqif']['sources']
    expected = sorted([source_entry(raw, context) for raw, context in versions],
        key=lambda e: canonical_json_bytes([e[k] for k in ('source_system', 'source_document', 'external_revision', 'source_sha256')]))
    assert actual == expected and len(actual) == 5
    for raw, context in versions:
        target = json.dumps({'extensions': results[0]}).encode()
        assert restore(target, raw, source_key=source_key(raw, context)) == raw


@pytest.mark.parametrize('value', [None, False, [], 'foreign format', {},
    {'format_version': 'future-v2', 'sources': []},
    {'format_version': 'reqif-preservation-v1', 'sources': [], 'extra': 1}])
def test_incompatible_existing_key_is_passive_generally_but_conflicts_on_explicit_merge(value):
    old = {'specroad.reqif': value, 'other.tool': [1]}; before = deepcopy(old)
    validate_extensions(old)
    assert DomainArtifact(artifact_bytes(domain_value('requirement', extensions=old))).data['extensions'] == old
    with no_write_attempts(), pytest.raises(ReqIFError) as error:
        merge(opaque_source(), old)
    assert error.value.exit_code == 6 and old == before


@pytest.mark.parametrize('field,value', [
    ('source_size', True), ('source_size', -1), ('source_size', 1.5), ('source_size', 999),
    ('source_sha256', '0' * 64), ('source_sha256', 'A' * 64), ('source_sha256', 'abc'),
    ('source_base64', ''), ('source_base64', 'not base64'), ('source_base64', 1),
    ('source_system', ''), ('source_document', None), ('external_revision', ''),
    ('external_revision', False), ('extra', 'not part of closed entry'),
])
def test_manipulated_entry_cannot_restore_or_overwrite_previous_data(field, value):
    raw = opaque_source(); entry = source_entry(raw); entry[field] = value
    target = target_bytes(entry)
    with no_write_attempts(), pytest.raises(ReqIFError) as error: restore(target, raw)
    assert error.value.exit_code == 3
    old = json.loads(target)['extensions']; before = deepcopy(old)
    with pytest.raises(ReqIFError) as error: merge(raw, old)
    assert error.value.exit_code == 6 and old == before


@pytest.mark.parametrize('mutation', ['space', 'newline', 'extra_padding', 'nonzero_pad_bits', 'trailing_data'])
def test_noncanonical_base64_is_rejected_even_when_a_permissive_decoder_returns_original(mutation):
    raw = opaque_source()
    while len(raw) % 3 != 1: raw += b' '
    entry = source_entry(raw); encoded = entry['source_base64']
    if mutation == 'space': changed = ' ' + encoded
    elif mutation == 'newline': changed = encoded + '\n'
    elif mutation == 'extra_padding': changed = encoded + '='
    elif mutation == 'trailing_data': changed = encoded + 'AAAA'
    else:
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        changed = encoded[:-3] + alphabet[alphabet.index(encoded[-3]) + 1] + '=='
        assert base64.b64decode(changed) == raw
    entry['source_base64'] = changed
    with pytest.raises(ReqIFError) as error: restore(target_bytes(entry), raw)
    assert error.value.exit_code == 3


def test_duplicate_input_sources_fail_even_when_identical_and_unused_sources_are_validated():
    raw = opaque_source(); entry = source_entry(raw)
    for entries in ([entry, entry], [entry, {**entry, 'source_system': 'other', 'source_size': 1}]):
        with pytest.raises(ReqIFError) as error: restore(target_bytes(*entries), raw)
        assert error.value.exit_code == 3


@pytest.mark.parametrize('context', [{}, {**CONTEXT, 'extra': 1}, {**CONTEXT, 'source_system': ''},
    {**CONTEXT, 'source_document': 1}, {**CONTEXT, 'external_revision': ''},
    {**CONTEXT, 'source_system': '\ud800'}])
def test_context_is_explicit_closed_and_never_inferred_from_header_or_filename(context):
    with pytest.raises(ReqIFError) as error: merge(opaque_source(), context=context)
    assert error.value.exit_code == 2


def test_bound_source_target_and_extensions_changes_conflict_before_returning_data():
    raw = opaque_source(); target = target_bytes(source_entry(raw))
    calls = [lambda: merge(raw, expected_source_sha256='0' * 64),
             lambda: merge(raw, expected_extensions_sha256='0' * 64),
             lambda: restore(target + b' ', raw, expected_target_sha256=digest(target)),
             lambda: restore(target, raw, source_key=source_key(opaque_source('changed'))),
             lambda: assess(raw, target + b' ', 'json', expected_target_sha256=digest(target)),
             lambda: assess(raw + b' ', target, 'json', expected_source_sha256=digest(raw))]
    for call in calls:
        with no_write_attempts(), pytest.raises(ReqIFError) as error: call()
        assert error.value.exit_code == 6


@pytest.mark.parametrize('expected', [None, '', 'f' * 63, 'F' * 64, False])
def test_invalid_binding_is_configuration_error(expected):
    with pytest.raises(ReqIFError) as error: merge(opaque_source(), expected_source_sha256=expected)
    assert error.value.exit_code == 2


@pytest.mark.parametrize('fragment', [
    '<script/>', '<v:x xmlns:v="urn:other" onload="bad"/>',
    '<v:x xmlns:v="urn:other" href="https://example.invalid/a"/>',
    '<v:x xmlns:v="urn:other" data="../escape"/>',
    '<xi:include xmlns:xi="http://www.w3.org/2001/XInclude" href="local.xml"/>',
])
def test_carrying_passive_bytes_does_not_bypass_xml_safety(fragment):
    raw = document(extensions='<TOOL-EXTENSIONS>' + fragment + '</TOOL-EXTENSIONS>')
    target = target_bytes(source_entry(raw))
    for call in (lambda: merge(raw), lambda: restore(target, raw), lambda: assess(raw)):
        with no_write_attempts(), pytest.raises(ReqIFError) as error: call()
        assert error.value.exit_code == 7


@pytest.mark.parametrize('prefix', [b'<!DOCTYPE REQ-IF []>', b'<!DOCTYPE REQ-IF [<!ENTITY e "x">]>', b'<?bad instruction?>'])
def test_dtd_entities_and_instructions_remain_safety_errors_inside_carrier(prefix):
    raw = opaque_source().replace(b'?>', b'?>' + prefix, 1)
    with pytest.raises(ReqIFError) as error: restore(target_bytes(source_entry(raw)), raw)
    assert error.value.exit_code == 7


@pytest.mark.parametrize('kind', ['claim', 'encoded', 'xml_depth'])
def test_budget_failures_are_not_loss_or_success_and_base64_size_is_checked_before_decode(kind):
    raw = opaque_source(); entry = source_entry(raw)
    limits = replace(LIMITS, max_bytes=len(raw)-1) if kind != 'xml_depth' else replace(LIMITS, max_depth=1)
    if kind == 'encoded':
        entry['source_size'] = 1
        entry['source_base64'] += 'AAAA'
    target = target_bytes(entry)
    if kind == 'xml_depth':
        with pytest.raises(ReqIFError) as error: restore(target, raw, limits=limits)
    else:
        with patch('specroad.exchange.reqif_preservation.base64.b64decode', side_effect=AssertionError('allocated')):
            with pytest.raises(ReqIFError) as error: restore(target, raw, limits=limits)
    assert error.value.exit_code == 7


@pytest.mark.parametrize('failure', [MemoryError('host'), OSError('host'), RecursionError('host')])
def test_host_failures_propagate_without_converting_to_loss(failure):
    raw = opaque_source(); target = target_bytes(source_entry(raw))
    with patch('specroad.exchange.reqif.read_bounded_xml', side_effect=failure):
        for call in (lambda: merge(raw), lambda: restore(target, raw), lambda: assess(raw)):
            with pytest.raises(type(failure)) as error: call()
            assert error.value is failure


@pytest.mark.parametrize('pointer', ['/a~1b/~0key/0', ''])
def test_exact_json_target_location_resolves_escaped_tokens_and_root(pointer):
    raw = opaque_source(); extensions = merge(raw)
    target = json.dumps({'a/b': {'~key': [extensions]}} if pointer else extensions).encode()
    assert restore(target, raw, extensions_pointer=pointer) == raw
    result = assess(raw, target, 'json', extensions_pointer=pointer)
    assert all(i['preservation_ref']['location']['pointer'] == pointer + '/specroad.reqif/sources/0' for i in result['items'])


@pytest.mark.parametrize('pointer,code', [('relative', 2), ('/~2', 2), ('/absent', 6), ('/extensions/0', 6), (None, 2)])
def test_invalid_or_missing_location_does_not_search_other_objects(pointer, code):
    raw = opaque_source(); target = target_bytes(source_entry(raw))
    with pytest.raises(ReqIFError) as error: restore(target, raw, extensions_pointer=pointer)
    assert error.value.exit_code == code


@pytest.mark.parametrize('raw', [b'{"extensions":{},"extensions":{}}', b'{"extensions":{}} trailing', b'[]'])
def test_target_json_uses_strict_existing_syntax_contract(raw):
    with pytest.raises(ReqIFError) as error: restore(raw, opaque_source())
    assert error.value.exit_code == 3


def test_inventory_is_source_derived_individual_stable_and_does_not_promote_decoder_copy():
    raw = opaque_source()
    with no_write_attempts():
        decoded = decode_reqif_structure(raw, limits=LIMITS)
        result = assess(raw)
    assert decoded.source_bytes == raw
    expected = [({'kind': 'xml', 'path': [], 'attribute': {'namespace': 'urn:vendor/a', 'name': 'flag'}}, 'uninterpreted_attribute'),
                ({'kind': 'xml', 'path': [2], 'attribute': None}, 'uninterpreted_extensions')]
    ids = []
    for location, reason in expected:
        identity = {'direction': 'import', 'source_sha256': digest(raw), 'source_context': CONTEXT,
                    'location': location, 'reason': reason}
        # Independent canonical oracle for this small object uses sorted keys.
        expected_id = 'reqif-item-' + digest(json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode())
        item = next(i for i in result['items'] if i['item_id'] == expected_id)
        assert item == {**identity, 'item_id': expected_id, 'loss_id': expected_id, 'disposition': 'lost'}
        ids.append(expected_id)
    assert [i['item_id'] for i in result['items']] == sorted(ids)
    assert result == assess(raw)
    assert not any(result[k] for k in ('assessment_complete', 'loss_free', 'native_projection_complete'))
    assert 'write_authorized' not in result and 'execution_ready' not in result
    assert result['mapping_binding'] is None and result['target_binding'] is None
    assert raw.decode() not in json.dumps(result) and source_entry(raw)['source_base64'] not in json.dumps(result)


@pytest.mark.parametrize('direction', ['import', 'export'])
@pytest.mark.parametrize('kind', ['xml', 'json'])
def test_preserved_requires_exact_actual_target_but_does_not_claim_native_projection(kind, direction):
    raw = opaque_source(); target = raw if kind == 'xml' else target_bytes(source_entry(raw))
    with no_write_attempts(): result = assess(raw, target, kind, direction=direction)
    lost = assess(raw, direction=direction)
    assert len(result['items']) == 2
    assert [i['item_id'] for i in result['items']] == [i['item_id'] for i in lost['items']]
    for item in result['items']:
        assert item['disposition'] == 'preserved' and 'loss_id' not in item
        assert item['preservation_ref'] == {'target_sha256': digest(target),
            'location': {'kind': 'xml', 'path': [], 'attribute': None} if kind == 'xml'
                        else {'kind': 'json', 'pointer': '/extensions/specroad.reqif/sources/0'},
            'source_key': None if kind == 'xml' else source_key(raw)}
    assert not result['assessment_complete'] and not result['loss_free'] and not result['native_projection_complete']


@pytest.mark.parametrize('target,kind', [(opaque_source('edited'), 'xml'),
    (b'{"extensions":{}}', 'json'),
    (target_bytes(source_entry(opaque_source('other'))), 'json'),
    (target_bytes(source_entry(opaque_source(), {**CONTEXT, 'source_system': 'other'})), 'json')])
def test_other_target_bytes_or_context_do_not_count_source_copy_as_retention(target, kind):
    result = assess(opaque_source(), target, kind)
    assert all(i['disposition'] == 'lost' and 'preservation_ref' not in i for i in result['items'])
    assert not result['loss_free']


def test_target_ref_uses_actual_entry_index_not_a_guessed_sorted_index():
    raw = opaque_source(); other = source_entry(opaque_source('other'))
    result = assess(raw, target_bytes(other, source_entry(raw)), 'json')
    assert {i['preservation_ref']['location']['pointer'] for i in result['items']} == {'/extensions/specroad.reqif/sources/1'}


def test_partial_xhtml_has_separate_unknown_attributes_without_duplicate_counts():
    raw = xdocument('<p class="kept" title="also kept">text</p>')
    result = assess(raw)
    assert len(result['items']) == 2
    assert {i['location']['attribute']['name'] for i in result['items']} == {'class', 'title'}
    assert len({i['item_id'] for i in result['items']}) == 2


def test_comment_and_mixed_text_do_not_change_element_child_location_convention():
    raw = opaque_source().replace(b'<TOOL-EXTENSIONS', b'<!--ignore index-->\n<TOOL-EXTENSIONS')
    result = assess(raw)
    item = next(i for i in result['items'] if i['reason'] == 'uninterpreted_extensions')
    assert item['location'] == {'kind': 'xml', 'path': [2], 'attribute': None}


def test_empty_inventory_and_source_roundtrip_still_do_not_certify_full_projection_or_attachments():
    for raw in (one(), xdocument('<p><object data="image.png" type="image/png"/></p>')):
        result = assess(raw, raw, 'xml')
        assert not result['assessment_complete'] and not result['loss_free'] and not result['native_projection_complete']
        assert 'attachment_transport' in result['unassessed']


def test_claimed_hash_without_actual_target_bytes_is_not_an_evidence_api():
    with pytest.raises(ReqIFError) as error:
        assess(opaque_source(), expected_target_sha256='0' * 64, target_kind='json')
    assert error.value.exit_code == 2
