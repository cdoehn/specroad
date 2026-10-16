"""Closed payload branches and complete passive relation records, no rendering."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.documents import ContentBlock, content_block_payload_schema
from specroad.model._schema import validate_builtin
from specroad.model.errors import ModelError
from specroad.storage.record_artifact import RecordArtifact
from support.domain import relation
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import block_value, ref
from test_content_blocks import source_bytes


def referenced_block(kind):
    value = block_value(kind)
    if kind == 'table':
        value['payload'] = {'source': 'view'}
        value['relations'] = [relation('references', ref('VIEW'))]
    return value


@pytest.mark.parametrize('kind', ['artifact_ref', 'query', 'table', 'include_document'])
@pytest.mark.parametrize('missing', ['identity_pair', 'external_identities', 'extensions'])
def test_local_reference_cardinality_does_not_replace_complete_relation_fields(kind, missing):
    value = referenced_block(kind)
    fields = ('relation_id', 'id_scheme') if missing == 'identity_pair' else (missing,)
    for field in fields: value['relations'][0].pop(field)
    raw = source_bytes(value)
    # The general record reader deliberately checks only its local projection.
    assert RecordArtifact(raw).data == value
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        ContentBlock(raw, path='provided/block.json')
    assert caught.value.reason == 'missing_relation_field'
    assert caught.value.pointer == '/relations/0/' + fields[0]
    assert caught.value.path == 'provided/block.json'


@pytest.mark.parametrize('kind', ['artifact_ref', 'query', 'table', 'include_document'])
@pytest.mark.parametrize('count', [0, 2])
def test_required_reference_is_exactly_one_even_when_payload_alone_is_valid(kind, count):
    value = referenced_block(kind)
    value['relations'] *= count
    if count == 2: value['relations'][1] = dict(value['relations'][1], relation_id='REL-' + '1' * 26)
    validate_builtin(value['payload'], content_block_payload_schema(kind))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        ContentBlock(source_bytes(value), path='reference.json')
    assert caught.value.reason == 'block_reference_cardinality'
    assert caught.value.pointer == '/relations' and caught.value.path == 'reference.json'


@pytest.mark.parametrize('kind,mode,wrong', [
    ('query', None, 'DOC'), ('table', None, 'REQ'),
    ('include_document', 'content', 'SEC'), ('include_document', 'section', 'DOC'),
])
def test_required_reference_target_kind_is_checked_at_its_original_array_position(kind, mode, wrong):
    value = referenced_block(kind)
    if mode is not None: value['payload']['mode'] = mode
    value['relations'][0]['target'] = ref(wrong)
    extra = dict(relation('derived_from', ref('SRC')), relation_id='REL-' + '1' * 26)
    value['relations'].insert(0, extra)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        ContentBlock(source_bytes(value), path='reference.json')
    assert caught.value.reason == 'block_reference_type'
    assert caught.value.pointer == '/relations/1/target' and caught.value.path == 'reference.json'


@pytest.mark.parametrize('field,reason,pointer', [
    ('foreign', 'unknown_relation_field', '/relations/0'),
    ('position', 'position_only_for_contains', '/relations/0/position'),
    ('external_identities', 'external_identity_array_required', '/relations/0/external_identities'),
    ('rationale', 'rationale_string_required', '/relations/0/rationale'),
    ('created_by', 'invalid_actor', '/relations/0/created_by'),
])
def test_malformed_reference_metadata_is_not_treated_as_a_complete_reference(field, reason, pointer):
    value = block_value('artifact_ref'); value['relations'][0][field] = 0
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        ContentBlock(source_bytes(value), path='metadata.json')
    assert (caught.value.reason, caught.value.pointer, caught.value.path) == (reason, pointer, 'metadata.json')


def test_duplicate_relation_identity_across_reference_and_provenance_is_rejected():
    value = block_value('artifact_ref')
    value['relations'].append(relation('derived_from', ref('SRC')))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        ContentBlock(source_bytes(value), path='duplicate.json')
    assert caught.value.reason == 'duplicate_relation_id'
    assert caught.value.pointer == '/relations/1/relation_id'
    assert caught.value.path == 'duplicate.json'


def test_complete_reference_metadata_is_retained_without_resolving_or_approving_targets():
    value = block_value('artifact_ref')
    value['relations'][0].update(rationale='A non-owning reference.',
        external_identities=[{'source_system': 'fixture', 'source_document': 'synthetic',
                              'external_id': 'external-1', 'external_revision': 'rev-3'}])
    value['relations'].append(dict(relation('derived_from', ref('SRC')), relation_id='REL-' + '1' * 26))
    raw = source_bytes(value)
    with no_write_attempts(): block = ContentBlock(raw, path='does-not-exist.json')
    assert block.data == value and block.source_bytes == raw
    assert block.binding['source_sha256'] == sha256(raw).hexdigest()
    assert not block.binding['target_references_resolved'] and not block.binding['approval_granted']


@pytest.mark.parametrize('kind,extra', [
    ('prose', {'render_mode': 'full'}), ('artifact_ref', {'markdown': 'copied content'}),
    ('query', {'query': {}}), ('table', {'source': 'view'}),
    ('admonition', {'mode': 'content'}), ('page_break', {'markdown': ''}),
    ('include_document', {'target': ref('DOC')}),
])
def test_mixed_payload_branches_are_rejected_without_discarding_the_foreign_data(kind, extra):
    value = block_value(kind); value['payload'].update(extra); before = deepcopy(value)
    with no_write_attempts(), pytest.raises(ModelError):
        validate_builtin(value['payload'], content_block_payload_schema(kind))
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        ContentBlock(source_bytes(value), path='mixed.json')
    assert caught.value.path == 'mixed.json' and value == before


@pytest.mark.parametrize('kind,field', [
    ('prose', 'markdown'), ('artifact_ref', 'render_mode'), ('query', 'columns'),
    ('query', 'empty_policy'), ('table', 'rows'), ('admonition', 'level'),
    ('admonition', 'markdown'), ('include_document', 'mode'),
])
def test_missing_payload_fields_are_not_defaulted_or_synthesized(kind, field):
    value = block_value(kind); value['payload'].pop(field)
    with no_write_attempts(), pytest.raises(ModelError):
        validate_builtin(value['payload'], content_block_payload_schema(kind))
    with no_write_attempts(), pytest.raises(ModelError): ContentBlock(source_bytes(value))
    assert field not in value['payload']


@pytest.mark.parametrize('kind,field,bad', [
    ('prose', 'markdown', []), ('artifact_ref', 'render_mode', 'execute'),
    ('query', 'columns', []), ('query', 'empty_policy', 'ignore'),
    ('table', 'rows', ['not-a-row-array']), ('admonition', 'level', 'debug'),
    ('admonition', 'title', ''), ('include_document', 'mode', 'external'),
])
def test_wrong_payload_types_or_choices_do_not_become_valid_through_coercion(kind, field, bad):
    value = block_value(kind); value['payload'][field] = bad
    with no_write_attempts(), pytest.raises(ModelError):
        validate_builtin(value['payload'], content_block_payload_schema(kind))
    with no_write_attempts(), pytest.raises(ModelError): ContentBlock(source_bytes(value))


@pytest.mark.parametrize('kind', ['unknown', 'PROSE', '', None, ['prose']])
def test_unknown_or_nonstring_kind_cannot_select_a_fallback_payload_schema(kind):
    with no_write_attempts(), pytest.raises(ModelError) as caught: content_block_payload_schema(kind)
    assert caught.value.reason == 'content_block_kind_not_supported'
    assert caught.value.pointer == '/block_kind'


@pytest.mark.parametrize('version', ['0.1', '0.3', None])
def test_payload_schema_requires_the_supported_explicit_version(version):
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        content_block_payload_schema('prose', version)
    assert caught.value.reason == 'unsupported_schema_version' and caught.value.pointer == '/schema_version'


def test_duplicate_json_keys_cannot_hide_a_mixed_payload_or_replace_a_reference():
    for old, new, pointer in (
        ('"render_mode": "summary"', '"render_mode": "summary", "render_mode": "full"', '/payload/render_mode'),
        ('"target": "' + ref() + '"', '"target": "' + ref() + '", "target": "' + ref('DOC') + '"', '/relations/0/target'),
    ):
        raw = source_bytes(block_value('artifact_ref')); assert old.encode() in raw
        raw = raw.replace(old.encode(), new.encode())
        with no_write_attempts(), pytest.raises(ModelError) as caught: ContentBlock(raw, path='duplicate-key.json')
        assert caught.value.reason == 'duplicate_key' and caught.value.pointer == pointer
        assert caught.value.path == 'duplicate-key.json'


def test_rejected_incomplete_reference_preserves_the_real_source_and_inventory(tmp_path):
    value = block_value('include_document'); value['relations'][0].pop('external_identities')
    path = tmp_path / 'block.json'; raw = source_bytes(value); path.write_bytes(raw); before = inventory(tmp_path)
    with no_write_attempts(), pytest.raises(ModelError): ContentBlock(raw, path=str(path))
    assert inventory(tmp_path) == before and path.read_bytes() == raw


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_incomplete_reference_failure_matches_in_isolated_core_and_pyz(tmp_path, mode):
    value = block_value('artifact_ref')
    value['relations'][0].pop('relation_id'); value['relations'][0].pop('id_scheme')
    raw = source_bytes(value)
    body = '''import json
from specroad.documents import ContentBlock
from specroad.model.errors import ModelError
'''
    body += 'raw=' + repr(raw) + '\n'
    body += '''try:
 ContentBlock(raw,path='provided.json')
except ModelError as error:
 print(json.dumps(error.diagnostic(),sort_keys=True))
else:
 raise AssertionError('incomplete reference accepted')
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'reason': 'missing_relation_field', 'path': 'provided.json',
        'pointer': '/relations/0/relation_id', 'position': None, 'line': None, 'column': None,
        'highest_supported': None}
