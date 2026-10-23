"""14.j.R: real complete-input inventories, native changes and export gating."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest

from specroad.exchange import (ReqIFError, ReqIFLossError, assess_reqif_transfer,
                              prepare_reqif_export, restore_reqif_source)
from specroad.mappings import ExchangeMapping, MappingError
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from support.artifacts import artifact_bytes
from support.exchange_mappings import mapping_value
from support.read_only import no_write_attempts
from support.reqif_objects import LIMITS, datatype, definition, document, one, spec_object, value
from support.reqif_preservation import CONTEXT, opaque_source, source_entry, source_key, target_bytes
from support.reqif_structure import attachment, structured, xdocument


def digest(raw):
    return sha256(raw).hexdigest()


def binding(raw, target=None, kind='xml', **changes):
    args = dict(source_kind='xml', source_context=CONTEXT, expected_source_sha256=digest(raw), limits=LIMITS)
    if target is not None:
        args.update(target_bytes=target, target_kind=kind, expected_target_sha256=digest(target))
        if kind == 'json':
            args['extensions_pointer'] = '/extensions'
    args.update(changes)
    return args


def assess(raw, target=None, kind='xml', **changes):
    return assess_reqif_transfer(raw, direction='import', **binding(raw, target, kind, **changes))


def mapped(**changes):
    data = mapping_value(types=[{'external_type': 'type', 'artifact_type': 'requirement'}],
        fields=[{'external_type': 'type', 'external_field': 'field', 'target_field': 'statement', 'value_map': None}])
    data.update(changes)
    resource = ExchangeMapping(artifact_bytes(data))
    return dict(mappings=[resource], mapping_key=resource.key, expected_mapping_sha256=resource.sha256)


def native(raw, target, **changes):
    args = binding(raw, target, source_kind='json', record_identifier='object', **mapped())
    args.update(changes)
    return assess_reqif_transfer(raw, direction='export', **args)


def locations(raw, tag):
    result, pending = [], [(ET.fromstring(raw), [])]
    while pending:
        node, path = pending.pop()
        if node.tag.rsplit('}', 1)[-1] == tag:
            result.append(path)
        pending.extend((c, path + [i]) for i, c in enumerate(node))
    return result


def at(report, path, reason=None):
    return [i for i in report['items'] if i['location'].get('path') == path and
            (reason is None or i['reason'] == reason)]


def lost_pointers(report):
    return {i['location']['pointer'] for i in report['items'] if i['disposition'] == 'lost'}


@pytest.mark.parametrize('fixture', ['empty', 'opaque', 'negative_zero', 'structure', 'xhtml_original'])
@pytest.mark.parametrize('kind', ['xml', 'json'])
def test_complete_original_transport_keeps_unmapped_information_without_native_or_write_claim(fixture, kind):
    raw = {'empty': document(), 'opaque': opaque_source(), 'negative_zero': one('REAL', '-0.0'),
           'structure': structured(), 'xhtml_original': xdocument('<p>current</p>', original='<p>original</p>')}[fixture]
    target = raw if kind == 'xml' else target_bytes(source_entry(raw))
    with no_write_attempts():
        report = assess(raw, target, kind)
    assert report['assessment_complete'] and report['loss_free'] and report['items']
    assert not report['native_projection_complete'] and not report['import_complete']
    assert not report['execution_ready'] and not report['write_authorized']
    assert report['validation_scope'] == 'whole_reqif_original_source_transport'
    assert report['unassessed'] == [] and report['mapping_binding'] is None
    assert all(i['disposition'] == 'preserved' and i['preservation_ref']['target_sha256'] == digest(target) for i in report['items'])
    text = json.dumps(report)
    assert 'source_base64' not in text and 'owned fixture' not in text and 'original</p>' not in text


@pytest.mark.parametrize('target', [None, b'<not reqif/>'], ids=['absent', 'invalid'])
def test_missing_or_invalid_target_never_produces_a_success(target):
    raw = document()
    if target is not None:
        with pytest.raises(ReqIFError) as error:
            assess(raw, target)
        assert error.value.exit_code == 3
    else:
        report = assess(raw)
        assert not report['assessment_complete'] and not report['loss_free']
        assert report['unassessed'] == ['target_bytes_missing']
        assert all(i['disposition'] == 'lost' for i in report['items'])


def test_inventory_covers_metadata_independent_attributes_fields_edges_and_whole_opaque_tree():
    raw = structured().replace(b'</REQ-IF>', b'<TOOL-EXTENSIONS xmlns:v="urn:v"><v:one a="1"><v:two/></v:one></TOOL-EXTENSIONS></REQ-IF>')
    raw = raw.replace(b'xml:lang="de"', b'xml:lang="de" xmlns:v="urn:v" v:alpha="x" v:beta="y"')
    target = document()
    report = assess(raw, target)
    assert report['assessment_complete'] and not report['loss_free']
    for tag in ('TITLE', 'COMMENT', 'SOURCE', 'TARGET', 'OBJECT', 'SPECIFICATION', 'SPEC-HIERARCHY', 'SPEC-RELATION'):
        paths = locations(raw, tag)
        assert paths
        for path in paths:
            assert any(i['location']['path'][:len(path)] == path for i in report['items'])
    root_attrs = {i['location']['attribute']['name'] for i in at(report, []) if i['location']['attribute']}
    assert {'lang', 'alpha', 'beta'} <= root_attrs
    tree = locations(raw, 'TOOL-EXTENSIONS')[0]
    units = [i for i in report['items'] if i['location']['path'][:len(tree)] == tree]
    assert len(units) == 1 and units[0]['location'] == {'kind': 'xml', 'path': tree, 'attribute': None}
    assert units[0]['reason'] == 'uninterpreted_extensions'


@pytest.mark.parametrize('literal,reason', [('-0.0', 'negative_zero_not_representable'),
                                         ('9007199254740993', 'number_roundtrip_loss')])
def test_nonrepresentable_values_are_concrete_source_items_even_with_original_copy(literal, reason):
    raw = one('REAL', literal)
    report = assess(raw, raw)
    path = locations(raw, 'ATTRIBUTE-VALUE-REAL')[0]
    items = at(report, path, reason)
    assert len(items) == 1 and items[0]['disposition'] == 'preserved'
    assert not report['native_projection_complete']


def test_actual_mapping_consumes_only_compared_fields_and_inventories_independent_remainder():
    raw = document(datatypes=datatype('STRING'),
        definitions=definition('STRING', 'field', 'dt') + definition('STRING', 'rest', 'dt'),
        objects=spec_object(value('STRING', 'field', 'text') + value('STRING', 'rest', 'unmapped')))
    target = artifact_bytes({'artifact_type': 'requirement', 'statement': 'text', 'extensions': {}})
    report = assess(raw, target, 'json', record_bindings={'object': ''}, **mapped())
    remainder = locations(raw, 'ATTRIBUTE-VALUE-STRING')[0]
    field = locations(raw, 'ATTRIBUTE-VALUE-STRING')[1]
    assert at(report, remainder, 'reqif_mapping_remainder')
    assert not at(report, field)
    assert report['record_comparisons'][0]['fields'] == [
        {'external_field': 'field', 'target_pointer': '/statement', 'matches': True}]
    assert report['assessment_complete'] and not report['loss_free']
    assert report['mapping_binding'] == mapped()['mappings'][0].binding()


@pytest.mark.parametrize('changes', [{'statement': 'changed'}, {'artifact_type': 'risk'}, {}])
def test_mapping_needs_actual_target_values_and_type_not_a_source_projection(changes):
    raw = one()
    target = artifact_bytes({**changes, 'extensions': {}})
    report = assess(raw, target, 'json', record_bindings={'object': ''}, **mapped())
    assert at(report, locations(raw, 'ATTRIBUTE-VALUE-STRING')[0], 'reqif_mapping_target_mismatch')
    assert not report['record_comparisons'][0]['fields'][0]['matches']
    assert not report['loss_free']


def test_partly_bound_or_unrepresentable_mapping_stays_incomplete_even_with_all_source_bytes():
    for raw, bindings in ((one(), {}), (one('REAL', '-0.0'), {'object': ''})):
        data = json.loads(target_bytes(source_entry(raw)))
        data.update(artifact_type='requirement', statement='not evidence')
        report = assess(raw, artifact_bytes(data), 'json', record_bindings=bindings, **mapped())
        assert all(i['disposition'] == 'preserved' for i in report['items'])
        assert not report['assessment_complete'] and not report['loss_free']


@pytest.mark.parametrize('bindings,code', [({'missing': ''}, 6), ({'object': '/absent'}, 6),
                                         ({'object': '/bad~x'}, 2), ([], 2), ({'object': 0}, 2)])
def test_record_locations_are_explicit_existing_and_syntactically_valid(bindings, code):
    raw = one()
    with pytest.raises(ReqIFError) as error:
        assess(raw, b'{"extensions":{}}', 'json', record_bindings=bindings, **mapped())
    assert error.value.exit_code == code


def test_distinct_records_cannot_collapse_onto_the_same_native_candidate():
    raw = document(datatypes=datatype('STRING'), definitions=definition('STRING', 'field', 'dt', 'text'),
        objects=spec_object(identifier='a') + spec_object(identifier='b'))
    with pytest.raises(ReqIFError) as error:
        assess(raw, b'{"extensions":{}}', 'json', record_bindings={'a': '', 'b': ''}, **mapped())
    assert error.value.exit_code == 6


def test_reused_default_needs_comparison_for_every_record_and_deduplicates_same_loss_location():
    raw = document(datatypes=datatype('STRING'), definitions=definition('STRING', 'field', 'dt', 'text'),
        objects=spec_object(identifier='a') + spec_object(identifier='b'))
    target = artifact_bytes({'a': {'artifact_type': 'requirement', 'statement': 'text'},
        'b': {'artifact_type': 'requirement', 'statement': 'other'}, 'extensions': {}})
    report = assess(raw, target, 'json', record_bindings={'a': '/a', 'b': '/b'}, **mapped())
    path = locations(raw, 'ATTRIBUTE-VALUE-STRING')[0]
    assert len(at(report, path, 'reqif_mapping_target_mismatch')) == 1
    both_bad = target.replace(b'"text"', b'"also other"')
    report = assess(raw, both_bad, 'json', record_bindings={'a': '/a', 'b': '/b'}, **mapped())
    assert len(at(report, path, 'reqif_mapping_target_mismatch')) == 1


def test_mapped_xhtml_keeps_original_and_flags_separate_from_proven_current_content():
    raw = xdocument('<p>current</p>', original='<p>original</p>', simplified='false')
    target = artifact_bytes({'artifact_type': 'requirement', 'statement': 'current', 'extensions': {}})
    report = assess(raw, target, 'json', record_bindings={'object': ''}, **mapped())
    assert report['record_comparisons'][0]['fields'][0]['matches']
    assert at(report, locations(raw, 'THE-ORIGINAL-VALUE')[0], 'reqif_xhtml_original_not_projected')
    assert any(i['location']['attribute'] == {'namespace': '', 'name': 'IS-SIMPLIFIED'} for i in report['items'])


@pytest.mark.parametrize('direction', ['import', 'export'])
def test_item_ids_use_bound_bytes_context_location_and_reason_independent_of_disposition(direction):
    raw = opaque_source()
    loss = assess_reqif_transfer(raw, direction=direction, **binding(raw, document()))
    kept = assess_reqif_transfer(raw, direction=direction, **binding(raw, raw))
    assert [i['item_id'] for i in loss['items']] == [i['item_id'] for i in kept['items']]
    assert len({i['item_id'] for i in loss['items']}) == len(loss['items'])
    for item in loss['items']:
        identity = {k: item[k] for k in ('direction', 'source_sha256', 'source_context', 'location', 'reason')}
        assert item['item_id'] == item['loss_id'] == 'reqif-item-' + canonical_json_sha256(identity)
    assert loss['items'] == sorted(loss['items'], key=lambda i: i['item_id'])
    changed = assess(raw + b' ', raw + b' ')
    assert not {i['item_id'] for i in changed['items']} & {i['item_id'] for i in kept['items']}


def test_native_export_compares_current_fields_and_cannot_hide_edits_under_old_capsule():
    old = one(literal='old')
    source = artifact_bytes({'artifact_type': 'requirement', 'statement': 'current',
                            'extensions': json.loads(target_bytes(source_entry(old)))['extensions']})
    report = native(source, old)
    assert report['assessment_complete'] and not report['loss_free']
    assert lost_pointers(report) == {'/statement', '/extensions/specroad.reqif'}
    assert all(i['source_sha256'] == digest(source) for i in report['items'])
    assert all(i['disposition'] == 'lost' and 'preservation_ref' not in i for i in report['items'])
    with pytest.raises(ReqIFLossError) as error:
        prepare_reqif_export(source, fail_on_loss=True, **binding(source, old, source_kind='json',
                             record_identifier='object', **mapped()))
    assert error.value.report == report and error.value.exit_code == 3


def test_native_candidate_known_mapping_is_checked_without_inventing_project_or_write_approval():
    source = artifact_bytes({'artifact_type': 'requirement', 'statement': 'current'})
    target = one(literal='current')
    report = native(source, target)
    assert report['assessment_complete'] and report['loss_free'] and report['native_projection_complete']
    assert report['items'] == [] and report['validation_scope'] == 'whole_native_record_candidate_to_reqif'
    assert not report['import_complete'] and not report['execution_ready'] and not report['write_authorized']


def test_native_remainders_include_each_metadata_extension_and_relation_with_real_escaped_locations():
    data = {'artifact_type': 'requirement', 'statement': 'current', 'id': 'owned', 'revision': 2,
            'extensions': {'vendor/a~b': {'uninterpreted': 1}, 'other.tool': 'opaque'},
            'relations': [{'target': 'a'}, {'target': 'b'}], 'a/b~c': 'metadata'}
    source = artifact_bytes(data)
    report = native(source, one(literal='current'))
    assert lost_pointers(report) == {'/id', '/revision', '/extensions/vendor~1a~0b',
        '/extensions/other.tool', '/relations/0', '/relations/1', '/a~1b~0c'}
    assert report['assessment_complete'] and not report['native_projection_complete']
    assert all('owned' not in str(i) and 'metadata' not in str(i) for i in report['items'])


@pytest.mark.parametrize('missing', ['target', 'mapping', 'projection'])
def test_empty_or_partial_native_projection_is_incomplete_not_loss_free(missing):
    source = artifact_bytes({} if missing == 'target' else {'artifact_type': 'requirement', 'statement': 'value'})
    target = None if missing == 'target' else one('REAL', '-0.0') if missing == 'projection' else one()
    args = binding(source, target, source_kind='json', record_identifier='object')
    if missing != 'mapping':
        args.update(mapped())
    report = assess_reqif_transfer(source, direction='export', **args)
    assert not report['assessment_complete'] and not report['loss_free'] and not report['native_projection_complete']
    for flag in (True, False):
        with pytest.raises(ReqIFLossError) as error:
            prepare_reqif_export(source, fail_on_loss=flag, **args)
        assert error.value.reason == 'reqif_assessment_incomplete' and error.value.report == report


def test_export_returns_same_candidate_and_report_only_after_loss_gate_with_owned_error_report():
    raw = opaque_source()
    target = document()
    with no_write_attempts(), pytest.raises(ReqIFLossError) as error:
        prepare_reqif_export(raw, fail_on_loss=True, **binding(raw, target))
    report = error.value.report
    assert report['assessment_complete'] and not report['loss_free']
    report['items'].clear()
    assert error.value.report['items'] and not hasattr(error.value, 'xml_bytes')
    with no_write_attempts():
        permitted = prepare_reqif_export(raw, fail_on_loss=False, **binding(raw, target))
        retained = prepare_reqif_export(raw, fail_on_loss=True, **binding(raw, raw))
    assert permitted['xml_bytes'] == target and not permitted['assessment']['loss_free']
    assert retained['xml_bytes'] == raw and retained['assessment']['loss_free']
    assert not retained['write_authorized']


@pytest.mark.parametrize('flag', [None, 0, 1, 'true', [], {}])
def test_fail_on_loss_requires_boolean_and_never_uses_truthiness(flag):
    raw = document()
    with pytest.raises(ReqIFError) as error:
        prepare_reqif_export(raw, fail_on_loss=flag, **binding(raw, raw))
    assert error.value.exit_code == 2


def test_claimed_report_or_status_cannot_bypass_assessment():
    raw = document()
    with pytest.raises(TypeError):
        prepare_reqif_export(raw, fail_on_loss=True, assessment={'loss_free': True}, **binding(raw, raw))


@pytest.mark.parametrize('where', ['value', 'original', 'opaque'])
def test_attachment_source_resolution_is_required_inside_all_kinds_of_xml(where):
    content = '<object data="pictures/a.png" type="image/png"/>'
    raw = (xdocument(content) if where == 'value' else xdocument('<p>current</p>', original=content)
           if where == 'original' else document(extensions='<TOOL-EXTENSIONS><other data="pictures/a.png"/></TOOL-EXTENSIONS>'))
    with no_write_attempts(), pytest.raises(ReqIFError) as error:
        assess(raw, target_bytes(source_entry(raw)), 'json')
    assert error.value.reason == 'reqif_attachment_unresolved' and error.value.exit_code == 3


def test_carrier_retains_xml_but_not_attachment_bytes_and_explicit_payload_transport_can_preserve_them():
    raw = xdocument('<object data="pictures/a.png" type="image/png"/>')
    file = attachment()
    target = target_bytes(source_entry(raw))
    report = assess(raw, target, 'json', source_attachments=[file])
    losses = [i for i in report['items'] if i['disposition'] == 'lost']
    assert len(losses) == 1 and losses[0]['reason'] == 'reqif_attachment_not_transported'
    assert report['assessment_complete'] and not report['loss_free']
    kept = assess(raw, target, 'json', source_attachments=[file], target_attachments=[file])
    assert kept['loss_free'] and len(kept['attachment_transfers']) == 1
    assert kept['attachment_transfers'][0]['target_sha256'] == digest(file.content)
    assert file.content.hex() not in json.dumps(kept)


def test_export_returns_actual_attachment_bytes_and_missing_target_resolution_is_an_error():
    file = attachment(reference='pictures/a%20b.png')
    raw = xdocument('<object data="pictures/a%20b.png" type="image/png"/>')
    with pytest.raises(ReqIFError) as error:
        prepare_reqif_export(raw, fail_on_loss=False, **binding(raw, raw, source_attachments=[file]))
    assert error.value.reason == 'reqif_attachment_unresolved'
    result = prepare_reqif_export(raw, fail_on_loss=True,
        **binding(raw, raw, source_attachments=[file], target_attachments=[file]))
    assert result['attachments'] == (file,)
    assert result['attachments'][0].content == file.content
    assert result['assessment']['loss_free']


def test_distinct_attachment_references_under_one_opaque_subtree_have_distinct_loss_ids():
    raw = document(extensions='<TOOL-EXTENSIONS><other data="a.bin"/><other data="b.bin"/></TOOL-EXTENSIONS>')
    files = [attachment('a.bin', 'attachments/a.bin'), attachment('b.bin', 'attachments/b.bin')]
    report = assess(raw, target_bytes(source_entry(raw)), 'json', source_attachments=files)
    losses = [i for i in report['items'] if i['disposition'] == 'lost']
    assert len(losses) == 2 and len({i['loss_id'] for i in losses}) == 2


def test_native_attachment_descriptors_require_bound_bytes_and_real_transport():
    file = attachment()
    source = artifact_bytes({'artifact_type': 'requirement', 'statement': 'current', 'attachments': [file.descriptor.data]})
    target = one(literal='current')
    with pytest.raises(ReqIFError) as error:
        native(source, target)
    assert error.value.reason == 'reqif_attachment_unresolved'
    lost = native(source, target, source_attachments=[file])
    assert lost_pointers(lost) == {'/attachments/0'} and not lost['loss_free']
    kept = native(source, target, source_attachments=[file], target_attachments=[file])
    assert kept['loss_free'] and len(kept['attachment_transfers']) == 1


@pytest.mark.parametrize('change', ['bytes', 'path', 'media', 'duplicate', 'forged'])
def test_attachment_conflicts_and_forged_values_are_never_ordinary_losses(change):
    file = attachment()
    raw = xdocument('<object data="pictures/a.png" type="image/png"/>')
    other = (attachment(content=b'changed') if change == 'bytes' else attachment(path='attachments/other.png')
             if change == 'path' else attachment(media_type='application/octet-stream') if change == 'media' else attachment())
    files = [file, file] if change == 'duplicate' else [other]
    if change == 'forged':
        object.__setattr__(other, 'content', b'forged')
    with pytest.raises(ReqIFError) as error:
        assess(raw, target_bytes(source_entry(raw)), 'json', source_attachments=[file], target_attachments=files)
    assert error.value.exit_code == 6


@pytest.mark.parametrize('reference', ['../a', '/a', 'https://invalid/a', 'file:a', 'a%252fb', '%2e%2e/a', 'a\\b'])
def test_unsafe_references_do_not_become_accepted_loss_or_trigger_resolution(reference):
    raw = document(extensions='<TOOL-EXTENSIONS><other data="' + reference + '"/></TOOL-EXTENSIONS>')
    with no_write_attempts(), pytest.raises(ReqIFError) as error:
        prepare_reqif_export(raw, fail_on_loss=False, **binding(raw, document()))
    assert error.value.exit_code == 7


@pytest.mark.parametrize('prefix', [b'<!DOCTYPE REQ-IF []>', b'<!DOCTYPE REQ-IF [<!ENTITY e "x">]>', b'<?not-allowed now?>'])
def test_active_xml_never_turns_into_ordinary_loss(prefix):
    raw = document().replace(b'?>', b'?>' + prefix, 1)
    with pytest.raises(ReqIFError) as error:
        prepare_reqif_export(raw, fail_on_loss=False, **binding(raw, document()))
    assert error.value.exit_code == 7


@pytest.mark.parametrize('field,limit', [('max_bytes', 20), ('max_depth', 1), ('max_elements', 2),
    ('max_text_chars', 1), ('max_attributes_per_element', 1), ('max_name_chars', 2), ('max_expanded_name_chars', 2)])
def test_each_xml_budget_applies_to_whole_bound_source(field, limit):
    raw = one()
    with pytest.raises(ReqIFError) as error:
        assess(raw, limits=replace(LIMITS, **{field: limit}))
    assert error.value.exit_code == 7


@pytest.mark.parametrize('failure', [MemoryError('host'), OSError('host'), RecursionError('host')])
def test_host_failures_propagate_without_fake_report_or_export(failure):
    raw = document()
    with patch('specroad.exchange.reqif.read_bounded_xml', side_effect=failure):
        with pytest.raises(type(failure)) as error:
            prepare_reqif_export(raw, fail_on_loss=False, **binding(raw, raw))
    assert error.value is failure


def test_empty_carrier_still_requires_explicit_typed_reader_limits():
    with pytest.raises(ReqIFError) as error:
        restore_reqif_source(target_bytes(), expected_target_sha256=digest(target_bytes()),
            extensions_pointer='/extensions', source_key=source_key(document()), limits=None)
    assert error.value.exit_code == 2


@pytest.mark.parametrize('which', ['source', 'target', 'mapping'])
def test_stale_bindings_fail_before_any_assessment_or_export_return(which):
    raw = one()
    args = binding(raw, artifact_bytes({'extensions': {}}), 'json', record_bindings={'object': ''}, **mapped())
    args['expected_' + which + '_sha256'] = '0' * 64
    with pytest.raises((ReqIFError, MappingError)) as error:
        assess_reqif_transfer(raw, direction='import', **args)
    assert error.value.exit_code == (3 if which == 'mapping' else 6)


def test_mapping_specific_error_is_preserved_not_reclassified_as_a_loss():
    raw = one()
    target = artifact_bytes({'extensions': {}})
    with pytest.raises(MappingError) as error:
        assess(raw, target, 'json', record_bindings={'object': ''}, **mapped(types=[] , fields=[]))
    assert error.value.reason == 'mapping_type_unmapped'


@pytest.mark.parametrize('mutation', ['duplicate', 'trailing', 'nonobject'])
def test_native_source_uses_existing_strict_json_boundary(mutation):
    raw = {'duplicate': b'{"a":1,"a":2}', 'trailing': b'{} data', 'nonobject': b'[]'}[mutation]
    with pytest.raises(ReqIFError) as error:
        native(raw, one())
    assert error.value.exit_code == 3


def test_actual_target_entry_order_and_source_context_define_the_proof_not_guessed_indices():
    raw = opaque_source()
    other = source_entry(raw, {**CONTEXT, 'source_document': 'other'})
    target = target_bytes(other, source_entry(raw))
    report = assess(raw, target, 'json')
    assert all(i['preservation_ref']['location']['pointer'] == '/extensions/specroad.reqif/sources/1' for i in report['items'])
    foreign = assess(raw, target_bytes(other), 'json')
    assert foreign['assessment_complete'] and not foreign['loss_free']


def test_reports_are_owned_and_do_not_mutate_context_bindings_or_mapping_resources():
    raw = one()
    context = deepcopy(CONTEXT)
    bindings = {'object': '/a~1b/~0node/0'}
    target = artifact_bytes({'a/b': {'~node': [{'artifact_type': 'requirement', 'statement': 'owned text'}]}, 'extensions': {}})
    args = mapped()
    before = args['mappings'][0].source_bytes
    report = assess(raw, target, 'json', record_bindings=bindings, source_context=context, **args)
    report['record_bindings'].clear()
    report['source_context']['source_document'] = 'changed'
    assert bindings == {'object': '/a~1b/~0node/0'} and context == CONTEXT
    assert args['mappings'][0].source_bytes == before


@pytest.mark.parametrize('part', ['DEFINITION', 'ATTRIBUTE-DEFINITION-STRING-REF'])
def test_mapping_cannot_consume_foreign_attributes_on_reference_substructure(part):
    raw = one().replace(('<' + part + '>').encode(), ('<' + part + ' xmlns:v="urn:v" v:flag="retained">').encode())
    target = artifact_bytes({'artifact_type': 'requirement', 'statement': 'owned text', 'extensions': {}})
    # The existing closed reference grammar rejects attributes at these two
    # positions; loss reporting must not relax that format boundary.
    with pytest.raises(ReqIFError) as error:
        assess(raw, target, 'json', record_bindings={'object': ''}, **mapped())
    assert error.value.reason == 'reqif_invalid_reference' and error.value.exit_code == 3
    # An allowed foreign attribute on the partly mapped value is independent
    # of the successfully compared native field and must remain in inventory.
    raw = one().replace(b'THE-VALUE="owned text"', b'THE-VALUE="owned text" xmlns:v="urn:v" v:flag="retained"')
    report = assess(raw, target, 'json', record_bindings={'object': ''}, **mapped())
    path = locations(raw, 'ATTRIBUTE-VALUE-STRING')[0]
    assert any(i['location'] == {'kind': 'xml', 'path': path, 'attribute': {'namespace': 'urn:v', 'name': 'flag'}}
               and i['reason'] == 'uninterpreted_attribute' for i in report['items'])
    assert report['record_comparisons'][0]['fields'][0]['matches']


@pytest.mark.parametrize('attribute', ['DATA', 'Data', 'v:DATA'])
def test_case_and_namespaced_uri_attributes_in_opaque_data_still_require_source_bytes(attribute):
    raw = document(extensions='<TOOL-EXTENSIONS xmlns:v="urn:v"><v:other ' + attribute + '="pictures/a.png"/></TOOL-EXTENSIONS>')
    with pytest.raises(ReqIFError) as error:
        assess(raw, target_bytes(source_entry(raw)), 'json')
    assert error.value.reason == 'reqif_attachment_unresolved'
    report = assess(raw, target_bytes(source_entry(raw)), 'json', source_attachments=[attachment()])
    assert len([i for i in report['items'] if i['reason'] == 'reqif_attachment_not_transported']) == 1


@pytest.mark.parametrize('where', ['value', 'original', 'opaque'])
@pytest.mark.parametrize('invalid', ['bytes', 'media'])
def test_attachment_media_validation_is_not_masked_by_loss_reporting(where, invalid):
    content = '<object xmlns="http://www.w3.org/1999/xhtml" data="pictures/a.png" type="image/png"/>'
    raw = (xdocument(content) if where == 'value' else xdocument('<p>current</p>', original=content)
           if where == 'original' else document(extensions='<TOOL-EXTENSIONS>' + content + '</TOOL-EXTENSIONS>'))
    file = attachment(content=b'not PNG') if invalid == 'bytes' else attachment(media_type='application/octet-stream')
    with pytest.raises(ReqIFError) as error:
        assess(raw, target_bytes(source_entry(raw)), 'json', source_attachments=[file])
    assert error.value.reason == 'reqif_attachment_image_type_mismatch' and error.value.exit_code == 3


def test_native_prose_reference_requires_source_descriptor_and_bytes_even_if_target_is_resolved():
    file = attachment()
    target = xdocument('<object data="pictures/a.png" type="image/png"/>')
    source = artifact_bytes({'artifact_type': 'requirement', 'statement': '![](attachments/a.png)'})
    with pytest.raises(ReqIFError) as error:
        native(source, target, target_attachments=[file])
    assert error.value.reason == 'reqif_attachment_unresolved'
    data = json.loads(source); data['attachments'] = [file.descriptor.data]
    report = native(artifact_bytes(data), target, source_attachments=[file], target_attachments=[file])
    assert report['loss_free']


@pytest.mark.parametrize('field,value', [('direction', 'sideways'), ('source_kind', 'csv'), ('limits', None),
    ('source_context', {}), ('expected_source_sha256', 'X'), ('target_kind', 'yaml'),
    ('record_identifier', 'not for XML')])
def test_invalid_transfer_configuration_is_not_a_partial_success(field, value):
    raw = document(); args = dict(direction='import', **binding(raw, raw)); args[field] = value
    with pytest.raises(ReqIFError) as error:
        assess_reqif_transfer(raw, **args)
    assert error.value.exit_code == 2


def test_different_actual_xml_is_not_evidence_for_unknown_fragments_even_if_semantically_similar():
    raw = opaque_source()
    report = assess(raw, raw + b' ')
    assert report['assessment_complete'] and not report['loss_free']
    assert all(i['disposition'] == 'lost' for i in report['items'])


def test_import_report_is_observation_and_has_no_fail_flag_or_authorization_shortcut():
    raw = one(); report = assess(raw, document())
    assert not report['loss_free'] and not report['import_complete']
    assert not report['execution_ready'] and not report['write_authorized']
    with pytest.raises(TypeError):
        assess_reqif_transfer(raw, direction='import', fail_on_loss=False, **binding(raw, raw))


@pytest.mark.parametrize('source', [b'{}', b'{"artifact_type":"requirement"}'])
def test_missing_required_native_source_fields_cannot_pass_on_an_empty_loss_list(source):
    target = one()
    report = native(source, target)
    assert report['items'] == []
    assert report['unassessed'] == ['native_source_fields_missing']
    assert not report['assessment_complete'] and not report['loss_free'] and not report['native_projection_complete']
    with pytest.raises(ReqIFLossError) as error:
        prepare_reqif_export(source, fail_on_loss=True,
            **binding(source, target, source_kind='json', record_identifier='object', **mapped()))
    assert error.value.report == report
