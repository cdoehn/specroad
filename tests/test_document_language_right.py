"""Lossless table/view language bindings; rendered text is not an oracle."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import builtins
import io
import json
import locale
import os
import webbrowser

import pytest

from specroad.changes import TargetModel
from specroad.documents import (TablePresentation, render_document, render_view,
    resolve_requirement_presentation, resolve_table_block, resolve_view,
    resolve_table_presentation, resolve_view_presentation)
from specroad.documents._render_formats import Emitter
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.language_packages import LanguagePackage
from specroad.srx.errors import SrxError
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.read_only import no_write_attempts
from support.records import block_value, ref
from support.srx import binary, expression_document, field, literal
from support.targets import model
from test_document_language import requirement, supplied_with_packages
from test_document_rendering_behavior import composed_values
from test_document_tables import table_project
from test_document_views import view_project, aid
from test_document_view_variants import variant_project
from test_document_view_variants_right import field_column, nested_view, only_first
from test_language_packages import package_data

TEXT = '  e\u0301 é\r\n日本語 हिन्दी العربية اردو \u2067RTL\u2069\t MUST NOT?  '


def language_view():
    values = view_project()
    for number, value in enumerate(values[:4]):
        value.update(statement=TEXT + str(number), language=['ar', 'en-US', 'qzz', 'x-private'][number],
                     text_direction=['ltr', 'rtl', 'auto', 'rtl'][number])
    values[-1].update(columns=[field_column('/statement'), field_column('/normative_force')],
                     grouping=[], relation_projections=[], formats=['html', 'markdown'])
    return values


def annotated_row(data, identifier):
    return next(row for row in data['rows'] if row['source']['artifact_id'] == identifier)


def assert_bound_rows(supplied, data):
    pending = [(data['projection']['rows'], data['rows'])]
    sources = {json.loads(d.content)['id']: d for d in supplied.documents}
    while pending:
        native, annotations = pending.pop()
        assert len(native) == len(annotations)
        for row, annotation in zip(native, annotations):
            bound = annotation['source']; source = sources[bound['artifact_id']]
            value = json.loads(source.content)
            assert bound['source_sha256'] == sha256(source.content).hexdigest()
            assert bound['record_sha256'] == canonical_json_sha256(value)
            assert bound['path'] == source.path and bound['revision'] == value['revision']
            assert annotation['content_language']['language'] == value.get('language')
            assert annotation['content_language']['text_direction'] == value.get('text_direction', 'auto')
            assert len(row['cells']) == len(annotation['cells'])
            if annotation['requirement'] is not None:
                assert annotation['requirement']['statement'] == value['statement']
                assert annotation['requirement']['normative_force'] == value['normative_force']
            for cell, note in zip(row['cells'], annotation['cells']):
                if note['records'] is not None:
                    pending.append((cell['value'], note['records']))


@pytest.mark.parametrize('branch', ['embedded', 'query_view', 'table_view'])
@pytest.mark.parametrize('force', ['must', 'must_not', 'should', 'may'])
def test_query_and_table_views_keep_original_statement_and_independent_force(branch, force):
    values = table_project(branch)
    for value in values[1:4]:
        value.update(requirement(id=value['id'], owner=value['owner'], revision=value['revision'],
            statement=TEXT, normative_force=force, language='ar', text_direction='ltr', priority='low'))
    columns = [field_column('/statement'), field_column('/normative_force')]
    if branch == 'table_view': values[-1]['columns'] = columns
    else: values[0]['payload']['columns'] = [{'field': '/statement'}, {'field': '/normative_force'}]
    supplied = model(values); before = supplied.source_files
    native = resolve_table_block(supplied, ref('BLOCK'))
    with no_write_attempts(): resolved = resolve_table_presentation(supplied, ref('BLOCK'))
    data = resolved.data
    assert data['projection'] == native.data and data['projection_sha256'] == native.sha256
    assert resolved.source_bytes == native.block_source_bytes
    assert_bound_rows(supplied, data)
    for row, annotation in zip(data['projection']['rows'], data['rows']):
        assert row['cells'] == [{'type': 'string', 'value': TEXT}, {'type': 'string', 'value': force}]
        assert [n['requirement_field'] for n in annotation['cells']] == ['statement', 'normative_force']
        assert annotation['requirement']['statement_utf8_sha256'] == sha256(TEXT.encode()).hexdigest()
    assert supplied.source_files == before


@pytest.mark.parametrize('language', ['zh-Hant', 'ar', 'ur-IN', 'x-private', 'und', 'mul', 'zxx', 'qzz', 'EN-us'])
def test_view_cells_preserve_explicit_tags_and_raw_unicode_without_semantic_claims(language):
    values = language_view(); values[0]['language'] = language
    supplied = model(values); native = resolve_view(supplied, ref('VIEW'))
    with no_write_attempts(): resolved = resolve_view_presentation(supplied, ref('VIEW'))
    data = resolved.data
    assert data['projection'] == native.data and data['projection_sha256'] == native.sha256
    assert resolved.source_bytes == native.view_source_bytes
    assert_bound_rows(supplied, data)
    row = annotated_row(data, aid(number=1))
    assert row['content_language']['language'] == language
    assert row['content_language']['text_direction'] == 'ltr'
    assert row['requirement']['statement'] == TEXT + '0'
    assert row['cells'][0]['content_language'] == row['content_language']
    for key in ('language_policy_evaluated', 'language_registry_checked', 'text_semantics_evaluated',
                'translation_performed', 'project_files_verified', 'full_validation_passed',
                'rendering_performed', 'write_authorized', 'approval_granted'):
        assert data[key] is False


@pytest.mark.parametrize('platform', ['linux', 'windows'])
@pytest.mark.parametrize('declared', [False, True])
def test_configured_nested_relations_use_each_targets_language_and_same_selection(platform, declared):
    values = variant_project(platform, declared=declared); view = values[-2]
    nested_view(view); only_first(view)
    for definition in view['relation_projections']:
        definition['columns'][0] = field_column('/statement')
    for value, language in zip(values[:4], ['en-US', 'ar', 'zh-Hant', 'qzz']):
        value.update(language=language, statement=TEXT + language)
    supplied = model(values); options = {} if declared else {'configuration_id': ref('CFG')}
    native = resolve_view(supplied, ref('VIEW'), **options)
    with no_write_attempts(): data = resolve_view_presentation(supplied, ref('VIEW'), **options).data
    assert data['projection'] == native.data
    assert_bound_rows(supplied, data)
    outer = data['rows'][0]['cells'][1]
    assert outer['content_language'] is None and outer['requirement_field'] is None
    if platform == 'linux': assert outer['records'] == []
    else:
        middle = outer['records'][0]; last = middle['cells'][1]['records'][0]
        assert middle['content_language']['language'] == 'ar'
        assert last['content_language']['language'] == 'zh-Hant'
        assert middle['cells'][0]['requirement_field'] == last['cells'][0]['requirement_field'] == 'statement'


def test_ids_and_counts_do_not_inherit_a_language_or_become_requirement_records():
    supplied = model(view_project()); native = resolve_view(supplied, ref('VIEW'))
    data = resolve_view_presentation(supplied, ref('VIEW')).data
    assert data['projection'] == native.data
    for row in data['rows']:
        for cell in row['cells'][2:]:
            assert cell == {'source_pointer': None, 'requirement_field': None,
                            'content_language': None, 'records': None}


@pytest.mark.parametrize('language', [None, 'ja-JP'])
def test_nonrequirement_statements_keep_optional_language_without_inventing_force(language):
    goal = domain_value('goal', statement=TEXT)
    if language is not None: goal['language'] = language
    view = language_view()[-1]
    view['columns'] = [field_column('/statement')]
    view['filter'] = expression_document(binary('eq', field('/artifact_type'), literal('goal')))
    supplied = model([goal, view]); data = resolve_view_presentation(supplied, ref('VIEW')).data
    assert data['projection'] == resolve_view(supplied, ref('VIEW')).data
    assert len(data['rows']) == 1 and data['rows'][0]['requirement'] is None
    assert data['rows'][0]['cells'][0]['requirement_field'] is None
    assert data['rows'][0]['content_language']['language'] == language
    assert data['projection']['rows'][0]['cells'] == [{'type': 'string', 'value': TEXT}]


@pytest.mark.parametrize('present', [None, False, 0, '', [], {}, {'artifact_id': ref(), 'statement': TEXT, 'normative_force': 'may'}])
def test_literal_values_are_not_parsed_as_requirements_or_inferred_from_column_labels(present):
    block = block_value('table')
    block.update(language='ar', text_direction='rtl')
    block['payload'] = {'columns': [{'field': 'statement'}], 'rows': [[present]]}
    supplied = model([block]); native = resolve_table_block(supplied, ref('BLOCK'))
    with no_write_attempts(): data = resolve_table_presentation(supplied, ref('BLOCK')).data
    assert data['projection'] == native.data
    assert data['projection']['rows'][0]['cells'][0]['value'] == present
    row = data['rows'][0]
    assert row['source_kind'] == 'literal_block' and row['requirement'] is None
    assert row['content_language']['language'] == 'ar'
    assert row['cells'][0]['source_pointer'] == '/payload/rows/0/0'
    assert row['cells'][0]['requirement_field'] is None and row['cells'][0]['records'] is None
    assert_bound_rows(supplied, data)


@pytest.mark.parametrize('kind,present', [('null', None), ('boolean', False), ('number', 0), ('string', ''), ('array', []), ('object', {})])
def test_missing_cells_and_lookalike_extension_fields_keep_native_types(kind, present):
    values = language_view()
    for artifact in values[:4]: artifact['extensions'] = {'org.example': {'statement': present}}
    del values[0]['extensions']['org.example']['statement']
    values[-1]['columns'] = [field_column('/extensions/org.example/statement', kind, 'preserve')]
    supplied = model(values); data = resolve_view_presentation(supplied, ref('VIEW')).data
    assert data['projection'] == resolve_view(supplied, ref('VIEW')).data
    assert next(r for r in data['projection']['rows'] if r['artifact_id'] == aid(number=1))['cells'] == [{'type': 'missing'}]
    assert all(row['cells'][0]['requirement_field'] is None for row in data['rows'])
    assert all(row['cells'][0]['records'] is None for row in data['rows'])


@pytest.mark.parametrize('direction', ['asc', 'desc'])
def test_group_keys_keep_native_collation_but_present_original_representative_cells(direction):
    values = language_view()
    for value, statement in zip(values[:4], ['é', 'e\u0301', 'z', 'a']): value['statement'] = statement
    values[-1]['grouping'] = [{'column': 0, 'direction': direction}]
    supplied = model(values); native = resolve_view(supplied, ref('VIEW')).data
    data = resolve_view_presentation(supplied, ref('VIEW')).data
    assert data['projection'] == native
    index = {row['artifact_id']: row for row in native['rows']}
    for group, original in zip(native['groups'], data['groups']):
        identifier = group['artifact_ids'][0]
        assert original['representative_artifact_id'] == identifier
        assert original['keys'] == [index[identifier]['cells'][0]]
    group = next(g for g in native['groups'] if g['keys'][0]['value'] == 'é')
    original = next(g for g in data['groups'] if g['representative_artifact_id'] == group['artifact_ids'][0])
    assert original['keys'] == [{'type': 'string', 'value': 'e\u0301'}]
    assert original['requirement']['statement'] == 'e\u0301'


def test_empty_query_preserves_native_outcome_without_synthetic_rows_or_language():
    values = table_project(limit=0); supplied = model(values)
    data = resolve_table_presentation(supplied, ref('BLOCK')).data
    assert data['projection'] == resolve_table_block(supplied, ref('BLOCK')).data
    assert data['projection']['outcome'] == 'omit' and data['rows'] == data['groups'] == []


def test_empty_view_does_not_resolve_or_repair_unselected_requirement_meaning():
    values = language_view(); values[-1]['filter'] = expression_document(literal(False))
    del values[0]['normative_force']
    supplied = model(values)
    data = resolve_view_presentation(supplied, ref('VIEW')).data
    assert data['projection'] == resolve_view(supplied, ref('VIEW')).data and data['rows'] == []
    assert 'normative_force' not in json.loads(next(d.content for d in supplied.documents
        if json.loads(d.content)['id'] == aid(number=1)))


def test_owned_presentation_and_nested_values_do_not_allow_mutation_or_approval():
    values = language_view(); nested_view(values[-1]); supplied = model(values)
    resolved = resolve_view_presentation(supplied, ref('VIEW')); expected = resolved.data
    edited = resolved.data; edited['projection']['rows'].clear(); edited['rows'][0]['cells'].clear()
    assert resolved.data == expected and resolved.sha256 == canonical_json_sha256(expected)
    with pytest.raises(TypeError): TablePresentation()
    with pytest.raises(TypeError): bool(resolved)
    with pytest.raises(FrozenInstanceError): resolved.source_bytes = b'{}'


def test_raw_source_whitespace_changes_binding_without_touching_semantic_cell_values():
    supplied = model(language_view()); documents = []
    for doc in supplied.documents:
        raw = json.dumps(json.loads(doc.content), ensure_ascii=False, indent=3).encode() + b'\n'
        documents.append(ModelDocument(doc.path, raw))
    other = TargetModel(supplied.configuration_bytes, supplied.binding, documents,
                        profile=supplied.profile, resource_files=supplied.resource_files)
    first = resolve_view_presentation(supplied, ref('VIEW'))
    second = resolve_view_presentation(other, ref('VIEW'))
    assert first.sha256 != second.sha256 and first.source_bytes != second.source_bytes
    assert [r['cells'] for r in first.data['projection']['rows']] == [r['cells'] for r in second.data['projection']['rows']]
    assert_bound_rows(other, second.data)


@pytest.mark.parametrize('operation,native,identifier', [(resolve_view_presentation, resolve_view, ref('VIEW')),
    (resolve_table_presentation, resolve_table_block, ref('BLOCK'))])
@pytest.mark.parametrize('case', ['model', 'id_type', 'missing', 'wrong_type', 'changed_snapshot'])
def test_wrappers_preserve_native_admission_failures(operation, native, identifier, case):
    supplied = model(language_view() if native is resolve_view else table_project())
    if case == 'model': supplied = {'records': []}
    elif case == 'id_type': identifier = []
    elif case == 'missing': identifier = ref('VIEW', '7')
    elif case == 'wrong_type': identifier = aid(number=1)
    else: object.__setattr__(supplied.documents[0], 'content', b'{}')
    with pytest.raises(ModelError) as expected: native(supplied, identifier)
    with no_write_attempts(), pytest.raises(ModelError) as caught: operation(supplied, identifier)
    assert caught.value.diagnostic() == expected.value.diagnostic()


@pytest.mark.parametrize('case', ['template', 'pointer', 'type', 'missing_meaning'])
def test_invalid_view_fields_fail_before_language_presentation_and_keep_native_errors(case):
    values = language_view()
    if case == 'template': values[-1]['columns'][0]['template'] = '{{ execute() }}'
    elif case == 'pointer': values[-1]['columns'][0]['source']['pointer'] = '/bad~2escape'
    elif case == 'type': values[-1]['columns'][0]['data_type'] = 'number'
    else: del values[0]['normative_force']
    supplied = model(values)
    with pytest.raises((ModelError, SrxError)) as expected: resolve_view(supplied, ref('VIEW'))
    with no_write_attempts(), pytest.raises((ModelError, SrxError)) as caught:
        resolve_view_presentation(supplied, ref('VIEW'))
    assert caught.value.diagnostic() == expected.value.diagnostic()


@pytest.mark.parametrize('display_locale', ['en-US', 'de-DE'])
def test_table_labels_use_bound_display_resources_and_never_rewrite_cell_values(display_locale):
    packages = tuple(LanguagePackage(canonical_json_bytes(package_data(package_id=lang,
        language_ranges=[lang], labels={'normative_force': {'must': '{{ inert ' + lang + ' }}'}})))
        for lang in ('de', 'en'))
    supplied = supplied_with_packages(language_view(), packages, display_locale=display_locale)
    native = resolve_view(supplied, ref('VIEW')).data
    with no_write_attempts(): data = resolve_view_presentation(supplied, ref('VIEW')).data
    assert data['projection'] == native
    expected = packages[0] if display_locale == 'de-DE' else packages[1]
    for row in data['rows']:
        assert row['requirement']['display_locale'] == display_locale
        assert row['requirement']['label_packages'] == [expected.binding()]
        assert row['requirement']['statement'] == resolve_requirement_presentation(supplied, row['source']['artifact_id']).data['statement']


@pytest.mark.parametrize('output_format', ['html', 'markdown'])
@pytest.mark.parametrize('kind', ['view', 'nested_view', 'query', 'literal'])
def test_renderers_consume_exact_native_values_and_bound_annotations_without_external_access(monkeypatch, output_format, kind):
    if kind in ('view', 'nested_view'):
        values = language_view()
        if kind == 'nested_view': nested_view(values[-1])
        supplied = model(values); expected = resolve_view_presentation(supplied, ref('VIEW')).data
        render = lambda: render_view(supplied, ref('VIEW'), output_format=output_format)
    else:
        values = table_project() if kind == 'query' else [block_value('table')]
        supplied = model(composed_values(values[0], *values[1:]))
        expected = resolve_table_presentation(supplied, ref('BLOCK')).data
        render = lambda: render_document(supplied, ref('DOC'), output_format=output_format)
    before = supplied.source_files; observed = []; original = Emitter.output
    def output(self, metadata, title, nodes):
        observed.extend(deepcopy(nodes))
        return original(self, metadata, title, nodes)
    def forbidden(*args, **kwargs): raise AssertionError('Unexpected external access')
    monkeypatch.setattr(Emitter, 'output', output)
    with no_write_attempts(), monkeypatch.context() as guard:
        for owner, name in ((builtins, 'open'), (io, 'open'), (os, 'open'),
                            (locale, 'setlocale'), (locale, 'getlocale'), (webbrowser, 'open')):
            guard.setattr(owner, name, forbidden)
        render()
    tables = [node for node in observed if node['type'] == 'table']
    assert len(tables) == 1 and tables[0]['data'] == expected['projection']
    assert tables[0]['presentation'] == expected and supplied.source_files == before
