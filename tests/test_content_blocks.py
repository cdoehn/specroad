"""Seven passive payload contracts and exact owned source bindings, no rendering."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json

import pytest

from specroad.documents import ContentBlock, content_block_payload_schema
from specroad.model._schema import validate_builtin
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from support.domain import relation
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import block_value, record_value, ref


KINDS = ['prose', 'artifact_ref', 'query', 'table', 'admonition', 'page_break', 'include_document']


def source_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


@pytest.mark.parametrize('kind', KINDS)
def test_all_seven_payload_kinds_have_loadable_exact_source_and_schema_bindings(kind):
    value = block_value(kind); raw = source_bytes(value); path = 'provided-block.json'
    with no_write_attempts():
        block = ContentBlock(raw, path=path)
        schema = content_block_payload_schema(kind)
        validate_builtin(block.payload, schema)
    assert block.source_bytes == raw and block.data == value and block.block_kind == kind
    assert block.payload == value['payload']
    binding = block.binding
    assert binding['artifact_id'] == value['id'] and binding['revision'] == value['revision']
    assert binding['path'] == path and binding['block_kind'] == kind
    assert binding['source_sha256'] == sha256(raw).hexdigest()
    assert binding['record_sha256'] == canonical_json_sha256(value)
    assert binding['payload_sha256'] == canonical_json_sha256(value['payload'])
    assert binding['payload_schema_id'] == schema['$id']
    assert binding['payload_schema_sha256'] == canonical_json_sha256(schema)
    assert not any(binding[k] for k in ('target_references_resolved', 'payload_semantics_evaluated',
        'rendering_performed', 'write_authorized', 'approval_granted'))


@pytest.mark.parametrize('kind', KINDS)
def test_foreign_payload_fields_fail_in_both_standalone_and_complete_record_contracts(kind):
    value = block_value(kind); value['payload']['foreign_field'] = True
    with no_write_attempts(), pytest.raises(ModelError):
        validate_builtin(value['payload'], content_block_payload_schema(kind))
    with no_write_attempts(), pytest.raises(ModelError) as error:
        ContentBlock(source_bytes(value), path='broken-block.json')
    assert error.value.path == 'broken-block.json'


@pytest.mark.parametrize('variant', ['embedded_query', 'view_table', 'titled_admonition', 'section_include'])
def test_declared_alternative_payload_branches_remain_passive_and_exact(variant):
    if variant == 'embedded_query':
        value = block_value('query'); value['payload'].pop('source')
        value['payload']['query'] = {'filter': {'op': 'literal', 'value': True}}
        value['relations'] = []
    elif variant == 'view_table':
        value = block_value('table'); value['payload'] = {'source': 'view'}
        value['relations'] = [relation('references', ref('VIEW'))]
    elif variant == 'titled_admonition':
        value = block_value('admonition'); value['payload']['title'] = 'Review required'
    else:
        value = block_value('include_document'); value['payload']['mode'] = 'section'
        value['relations'][0]['target'] = ref('SEC')
    block = ContentBlock(source_bytes(value))
    validate_builtin(block.payload, content_block_payload_schema(block.block_kind))
    assert block.data == value and block.payload == value['payload']
    assert not block.binding['payload_semantics_evaluated']


def test_payload_record_and_binding_are_detached_from_the_owned_original_bytes():
    value = block_value('table'); block = ContentBlock(source_bytes(value)); before = block.binding
    block.payload['rows'][0][0] = 'Foreign value'
    block.data['payload']['rows'].clear()
    block.binding['record_sha256'] = '0' * 64
    assert block.data == value and block.binding == before
    with pytest.raises(FrozenInstanceError): block.source_bytes = b'{}'
    with pytest.raises(TypeError): bool(block)


def test_returned_payload_schema_cannot_reconfigure_later_loads():
    expected = content_block_payload_schema('prose'); changed = content_block_payload_schema('prose')
    changed['additionalProperties'] = True; changed['properties'].clear(); changed['$defs'].clear()
    assert content_block_payload_schema('prose') == expected
    value = block_value('prose'); value['payload']['execute'] = 'foreign'
    with pytest.raises(ModelError): ContentBlock(source_bytes(value))


def test_reference_target_is_not_fetched_or_claimed_resolved_by_passive_block_loading():
    value = block_value('artifact_ref')
    with no_write_attempts(): block = ContentBlock(source_bytes(value), path='absent/source.json')
    assert block.data['relations'] == value['relations']
    assert not block.binding['target_references_resolved']
    assert not block.binding['approval_granted']


def test_original_bytes_remain_available_without_reopening_or_rewriting_the_source(tmp_path):
    path = tmp_path / 'block.json'; value = block_value('prose'); value['payload']['markdown'] = 'ä\r\ntext'
    raw = source_bytes(value); path.write_bytes(raw); before = inventory(tmp_path)
    with no_write_attempts(): block = ContentBlock(raw, path=str(path))
    assert inventory(tmp_path) == before and block.source_bytes == raw
    path.unlink()
    with no_write_attempts():
        assert block.data == value and block.payload == value['payload']
        assert block.binding['source_sha256'] == sha256(raw).hexdigest()
    assert not path.exists()


def test_another_record_type_cannot_be_relabelled_as_a_content_block():
    with no_write_attempts(), pytest.raises(ModelError):
        ContentBlock(canonical_json_bytes(record_value('document')))


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_all_payload_contracts_run_in_isolated_core_and_pyz(tmp_path, mode):
    sources = [source_bytes(block_value(kind)) for kind in KINDS]
    expected = [{'data': ContentBlock(raw).data, 'binding': ContentBlock(raw).binding,
                 'schema': content_block_payload_schema(kind)} for raw, kind in zip(sources, KINDS)]
    body = '''import json
from specroad.documents import ContentBlock, content_block_payload_schema
'''
    body += 'sources=' + repr(sources) + '\n'
    body += '''results=[]
for raw in sources:
 block=ContentBlock(raw)
 results.append({'data':block.data,'binding':block.binding,
  'schema':content_block_payload_schema(block.block_kind)})
print(json.dumps(results,sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
