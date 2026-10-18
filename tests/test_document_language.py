"""Owned requirement render data; no markup, labels or layout as test oracles."""
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
from specroad.documents import (RequirementPresentation, RequirementPresentationError,
                               render_document, resolve_requirement_presentation)
from specroad.documents._render_formats import Emitter
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.model.language_packages import LanguagePackage
from specroad.profiles import compose_profiles
from specroad.storage.requirement import RequirementArtifact
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.model import configuration_value
from support.read_only import no_write_attempts
from support.records import block_value, record_value, ref
from support.targets import model, SCOPE
from test_document_includes import edge, include_project
from test_document_rendering_behavior import composed_values, render_project
from test_language_packages import MINIMUM, TEXT, package_data


def requirement(**overrides):
    value = domain_value('requirement', **overrides)
    if value['normative_force'] == 'should':
        value.update(deviation_conditions='Explicitly reviewed exception',
                     deviation_authority='engineering')
    return value


def supplied_with_packages(values, packages, *, display_locale='en-US'):
    supplied = model(values, config=configuration_value(default_locale=display_locale))
    profile = compose_profiles(supplied.profile_resources,
        core_key=supplied.profile_resources[0].key, language_packages=packages)
    return TargetModel(supplied.configuration_bytes, supplied.binding, supplied.documents,
        profile=profile, resource_files=supplied.resource_files, language_packages=packages)


@pytest.mark.parametrize('force', ['must', 'must_not', 'should', 'may'])
@pytest.mark.parametrize('statement', ['The system sends a packet.',
    'The system does not send a packet.', '  MUST NOT?\r\n' + TEXT + '\n'])
def test_force_is_a_separate_declaration_not_inferred_from_or_inserted_into_statement(force, statement):
    value = requirement(normative_force=force, statement=statement, priority='low')
    supplied = model([value]); before = supplied.source_files
    with no_write_attempts():
        result = resolve_requirement_presentation(supplied, ref())
    data = result.data
    assert (data['statement'], data['normative_force']) == (statement, force)
    assert data['statement_utf8_sha256'] == sha256(statement.encode('utf-8')).hexdigest()
    assert json.loads(result.source_bytes) == value and supplied.source_files == before
    assert data['requirement']['record_sha256'] == canonical_json_sha256(value)
    assert data['requirement']['source_sha256'] == sha256(result.source_bytes).hexdigest()
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert data['input_sha256'] == supplied._sources_sha256


@pytest.mark.parametrize('language', [*MINIMUM, 'ar', 'ur-IN', 'zh-Hant', 'EN-us', 'und', 'x-private'])
def test_declared_language_is_preserved_without_detection_or_registry_claim(language):
    supplied = model([requirement(language=language, statement=TEXT)])
    with no_write_attempts(): data = resolve_requirement_presentation(supplied, ref()).data
    assert data['content_language'] == {'language': language, 'text_direction': 'auto',
        'source': 'declaration', 'language_detected': False, 'direction_detected': False}
    assert data['text_direction_source'] == 'default' and data['statement'] == TEXT
    for key in ('language_policy_evaluated', 'language_registry_checked',
                'text_semantics_evaluated', 'translation_performed', 'rendering_performed',
                'project_files_verified', 'full_validation_passed', 'write_authorized', 'approval_granted'):
        assert data[key] is False


@pytest.mark.parametrize('language', ['en-US', 'ar'])
@pytest.mark.parametrize('direction', ['ltr', 'rtl', 'auto'])
def test_explicit_direction_does_not_depend_on_language_or_statement(language, direction):
    supplied = model([requirement(language=language, text_direction=direction, statement=TEXT)])
    data = resolve_requirement_presentation(supplied, ref()).data
    assert data['content_language']['language'] == language
    assert data['content_language']['text_direction'] == direction
    assert data['text_direction_source'] == 'declaration' and data['statement'] == TEXT


@pytest.mark.parametrize('field,value', [('revision', 2), ('title', 'Changed'),
    ('statement', 'e\u0301'), ('normative_force', 'may'), ('language', 'en-US'), ('text_direction', 'rtl')])
def test_presentation_rebinds_every_changed_requirement_source(field, value):
    original = requirement(); changed = {**original, field: value}
    first = resolve_requirement_presentation(model([original]), ref())
    second = resolve_requirement_presentation(model([changed]), ref())
    assert first.sha256 != second.sha256
    for key in ('input_sha256', 'model_root_sha256'):
        assert first.data[key] != second.data[key]
    assert first.data['requirement']['source_sha256'] != second.data['requirement']['source_sha256']
    assert second.source_bytes == canonical_json_bytes(changed)


def test_source_whitespace_is_bound_without_changing_statement_or_record_identity():
    supplied = model([requirement(statement=TEXT)])
    doc = supplied.documents[0]
    raw = json.dumps(json.loads(doc.content), ensure_ascii=False, indent=4).encode('utf-8') + b'\n'
    other = TargetModel(supplied.configuration_bytes, supplied.binding, [ModelDocument(doc.path, raw)],
                        profile=supplied.profile, resource_files=supplied.resource_files)
    first = resolve_requirement_presentation(supplied, ref())
    second = resolve_requirement_presentation(other, ref())
    assert first.data['requirement']['record_sha256'] == second.data['requirement']['record_sha256']
    assert first.data['requirement']['source_sha256'] != second.data['requirement']['source_sha256']
    assert first.data['statement_utf8_sha256'] == second.data['statement_utf8_sha256']
    assert second.source_bytes == raw and first.sha256 != second.sha256


def test_owned_value_cannot_be_constructed_or_used_as_approval_and_returns_detached_data():
    supplied = model([requirement()]); result = resolve_requirement_presentation(supplied, ref())
    digest = result.sha256
    data = result.data; data['statement'] = 'Changed'; data['content_language']['language'] = 'ar'
    with pytest.raises(TypeError): RequirementPresentation()
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(FrozenInstanceError): result.source_bytes = b'{}'
    assert result.sha256 == digest == resolve_requirement_presentation(supplied, ref()).sha256
    assert result.data['statement'] == requirement()['statement']
    assert result.data['content_language']['language'] == 'de-DE'


@pytest.mark.parametrize('identifier', [None, 0, [], {}, True])
def test_requirement_selection_requires_an_explicit_string_identity(identifier):
    with pytest.raises(RequirementPresentationError) as caught:
        resolve_requirement_presentation(model([requirement()]), identifier)
    assert caught.value.reason == 'presentation_requirement_id_required'
    assert caught.value.pointer == '/requirement_id' and caught.value.exit_code == 3


@pytest.mark.parametrize('identifier,reason', [(ref('REQ', '1'), 'presentation_requirement_not_found'),
                                            (ref('DOC'), 'presentation_requirement_required')])
def test_unavailable_or_nonrequirement_targets_are_not_substituted(identifier, reason):
    with pytest.raises(RequirementPresentationError) as caught:
        resolve_requirement_presentation(model([requirement(), record_value('document')]), identifier)
    assert caught.value.reason == reason and caught.value.pointer == '/requirement_id'


def test_presentation_requires_an_owned_model_and_rejects_modified_snapshot_sources():
    with pytest.raises(ModelError) as caught:
        resolve_requirement_presentation({'records': []}, ref())
    assert caught.value.reason == 'document_target_model_required'
    supplied = model([requirement()])
    object.__setattr__(supplied.documents[0], 'content', canonical_json_bytes(requirement(statement='Changed')))
    with pytest.raises(ModelError): resolve_requirement_presentation(supplied, ref())


@pytest.mark.parametrize('field', ['statement', 'normative_force', 'deviation_conditions', 'deviation_authority'])
def test_missing_meaning_fields_keep_native_requirement_error_contract(field):
    value = requirement(normative_force='should'); del value[field]
    supplied = model([value]); doc = supplied.documents[0]
    with pytest.raises(ModelError) as native:
        RequirementArtifact(doc.content, path=doc.path)
    with no_write_attempts(), pytest.raises(ModelError) as projected:
        resolve_requirement_presentation(supplied, ref())
    assert projected.value.diagnostic() == native.value.diagnostic()


@pytest.mark.parametrize('display_locale', ['en-US', 'de-DE'])
def test_only_explicit_packages_matching_display_locale_are_bound_in_activation_order(display_locale):
    packages = tuple(LanguagePackage(canonical_json_bytes(package_data(package_id=key,
        language_ranges=[language], labels={'normative_force': {'must_not': 'inert ' + key}})))
        for key, language in [('de', 'de'), ('en1', 'en'), ('en2', 'en')])
    value = requirement(normative_force='must_not', language='ar', statement=TEXT)
    supplied = supplied_with_packages([value], packages, display_locale=display_locale)
    with no_write_attempts(): data = resolve_requirement_presentation(supplied, ref()).data
    chosen = packages[:1] if display_locale == 'de-DE' else packages[1:]
    assert data['label_packages'] == [p.binding() for p in chosen]
    assert data['display_locale'] == display_locale
    assert data['content_language']['language'] == 'ar'
    assert (data['statement'], data['normative_force']) == (TEXT, 'must_not')


def test_display_resource_changes_rebind_presentation_without_rewriting_meaning():
    def package(label):
        return LanguagePackage(canonical_json_bytes(package_data(language_ranges=['en'],
            labels={'normative_force': {'must_not': label}})))
    value = requirement(normative_force='must_not', language='de-DE', statement=TEXT)
    supplied = [supplied_with_packages([value], [package(label)])
                for label in ('first label', '{{ __import__("os").system("false") }}')]
    with no_write_attempts():
        results = [resolve_requirement_presentation(item, ref()) for item in supplied]
    assert results[0].sha256 != results[1].sha256
    assert results[0].data['input_sha256'] != results[1].data['input_sha256']
    assert results[0].data['requirement'] == results[1].data['requirement']
    assert results[0].data['statement'] == results[1].data['statement'] == TEXT
    assert results[0].data['normative_force'] == results[1].data['normative_force'] == 'must_not'


def observe_render_nodes(monkeypatch, supplied, output_format):
    observed = []
    original = Emitter.output
    def output(self, metadata, title, nodes):
        observed.extend(deepcopy(nodes))
        return original(self, metadata, title, nodes)
    monkeypatch.setattr(Emitter, 'output', output)
    with no_write_attempts(): render_document(supplied, ref('DOC'), output_format=output_format)
    return observed


@pytest.mark.parametrize('output_format', ['html', 'markdown'])
@pytest.mark.parametrize('mode', ['full', 'summary', 'link'])
def test_document_reference_modes_pass_same_bound_meaning_to_presentation(monkeypatch, output_format, mode):
    values = render_project(mode)
    values[-1] = requirement(normative_force='must_not', language='ar', text_direction='ltr', statement=TEXT)
    supplied = model(values); before = supplied.source_files
    expected = resolve_requirement_presentation(supplied, ref()).data
    nodes = observe_render_nodes(monkeypatch, supplied, output_format)
    records = [n for n in nodes if n['type'] == 'record']
    assert [n['mode'] for n in records] == ([mode, 'summary'] if mode == 'link' else [mode])
    assert all(n['presentation'] == expected and n['record'] == values[-1] for n in records)
    assert all(n['content_language'] == expected['content_language'] for n in records)
    assert supplied.source_files == before


@pytest.mark.parametrize('output_format', ['html', 'markdown'])
def test_repeated_includes_preserve_distinct_occurrences_and_same_requirement_meaning(monkeypatch, output_format):
    values = include_project()
    values[-1] = block_value('artifact_ref'); values[-1]['id'] = ref('BLOCK', '2')
    values[-1]['relations'] = [edge('references', ref(), 8)]
    values.append(requirement(statement=TEXT))
    supplied = model(values)
    expected = resolve_requirement_presentation(supplied, ref()).data
    nodes = observe_render_nodes(monkeypatch, supplied, output_format)
    records = [n for n in nodes if n['type'] == 'record']
    assert len(records) == 2 and all(n['presentation'] == expected for n in records)
    records[0]['presentation']['statement'] = 'Changed'
    assert records[1]['presentation']['statement'] == TEXT


@pytest.mark.parametrize('output_format', ['html', 'markdown'])
def test_document_section_and_prose_keep_independent_language_declarations(monkeypatch, output_format):
    block = block_value('prose'); block.update(language='ar', text_direction='rtl')
    values = composed_values(block); values[0]['language'] = 'en-US'
    supplied = model(values)
    nodes = observe_render_nodes(monkeypatch, supplied, output_format)
    declarations = [(n['id'], n['content_language']['language'], n['content_language']['text_direction'])
                    for n in nodes if 'content_language' in n]
    assert declarations == [(ref('DOC'), 'en-US', 'auto'), (ref('SEC'), None, 'auto'),
                            (ref('BLOCK'), 'ar', 'rtl')]


@pytest.mark.parametrize('output_format', ['html', 'markdown'])
def test_presentation_and_rendering_never_load_resources_or_consult_host_locale(monkeypatch, output_format):
    values = render_project('full'); values[-1] = requirement(statement=TEXT)
    supplied = model(values); before = supplied.source_files
    def forbidden(*args, **kwargs):
        raise AssertionError('Unexpected external access or locale consultation')
    with no_write_attempts(), monkeypatch.context() as guard:
        for owner, name in ((builtins, 'open'), (io, 'open'), (os, 'open'),
                            (locale, 'setlocale'), (locale, 'getlocale'), (webbrowser, 'open')):
            guard.setattr(owner, name, forbidden)
        data = resolve_requirement_presentation(supplied, ref()).data
        render_document(supplied, ref('DOC'), output_format=output_format)
    assert data['label_packages'] == [] and data['statement'] == TEXT
    assert supplied.source_files == before
