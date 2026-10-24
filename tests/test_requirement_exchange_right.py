"""S.4/S.7 byte preservation and explicit missing-mapping losses, not NLP."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from specroad.exchange import (ExternalIdentity, ImportIdentityError, assess_import_plan,
    decode_ndjson, decode_reqif_structure, decode_reqifz, prepare_export,
    prepare_import_plan, requirement_mapping, select_csv_profile)
from specroad.graph.scope_descriptors import ScopeDescriptor
from specroad.mappings import ExchangeMapping, MappingError, select_mapping
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.import_planning import identity
from support.read_only import no_write_attempts
from support.reqif_objects import LIMITS
from support.scopes import descriptor
from support.targets import ACTOR, POLICY, SCOPE, TIME, model
from test_requirement_exchange import read_content, resources


FORMATS = ('csv', 'ndjson', 'reqif', 'reqifz')
FIELDS = ('language', 'normative_force', 'statement')
# Independent transport oracles. These literals do not assert translation
# equivalence, detector accuracy or a linguistic review of their content.
TEXTS = {
    'en-US': 'When offline, telemetry is not sent; except to the selected local target.',
    'en-IN': 'The operator may retain the complete record, including the stated exception.',
    'hi-IN': 'ऑफ़लाइन होने पर डेटा बाहर नहीं भेजा जाता; चुना हुआ स्थानीय लक्ष्य अपवाद है।',
    'id-ID': 'Saat luring, data tidak dikirim keluar; kecuali ke tujuan lokal yang dipilih.',
    'pt-BR': 'Sem conexão, os dados não são enviados; exceto ao destino local selecionado.',
    'es-MX': 'Sin conexión, no se envían datos; salvo al destino local seleccionado.',
    'ru-RU': 'Без соединения данные не отправляются, кроме выбранного локального адресата.',
    'ja-JP': 'オフラインでは外部へ送信しない。ただし選択したローカル宛先を除く。',
    'de-DE': 'Offline werden keine Daten versendet; außer an das gewählte lokale Ziel.',
    'zh-Hans-CN': '离线时不向外部发送数据；明确选择的本地目标除外。',
    'cmn-Hans-CN': '记录保留完整的条件与例外，不自动改写。',
    'zh-Hant': '離線時不向外部傳送資料；明確選擇的本地目標除外。',
    'ar': 'لا تُرسل البيانات إلى الخارج دون اتصال؛ باستثناء الوجهة المحلية المحددة.',
    'ur-IN': 'آف لائن حالت میں ڈیٹا باہر نہیں بھیجا جاتا؛ منتخب مقامی ہدف مستثنیٰ ہے۔',
    'x-specroad-demo': 'Private metadata: MUST NOT is quoted content, not a force mapping.',
    'und': 'Undeclared text language: soll, should, may, MUST NOT.',
    'zzzz': 'Unregistered tag: must, darf nicht, optional, mandatory.',
    'EN-us': 'Preserve the exact stored spelling; do not rewrite loaded tags.',
}


def content(language='ja-JP', force='must_not'):
    text = TEXTS[language] + '\r\n"<&>"; comma, pipe| Café / Cafe\u0301 / 👩\u200d💻\n'
    text += '**must should may soll darf nicht** are literal data, not instructions.'
    return domain_value('requirement', language=language, normative_force=force, statement=text,
        **({'deviation_conditions': 'An explicitly supplied condition.',
            'deviation_authority': 'An explicitly supplied authority.'} if force == 'should' else {}))


def external_fields(value, fmt):
    return {('specroad.' if fmt in ('reqif', 'reqifz') else '') + field:
            [value[field]] if fmt in ('reqif', 'reqifz') and field == 'normative_force' else value[field]
            for field in FIELDS}


def import_arguments(mapping, fmt, **changes):
    return dict(input_format=fmt, input_bytes=b'explicit parsed candidate fixture',
        mapping_resources=[mapping], mapping_key=mapping.key, mapping_sha256=mapping.sha256,
        strategy='update_if_unchanged', change_plan_id='CP-language-import', request_id='language-import',
        actor=ACTOR, planned_at=TIME, scope_descriptor=SCOPE, metadata_policy_version='change-metadata-v1',
        policy=POLICY, **changes)


def import_model(values):
    # A native import target needs the real, explicitly bound offline registry
    # for its mandatory language gate. Do not replace that gate with a stub.
    from specroad.changes import TargetModel
    from specroad.profiles import compose_profiles
    from specroad.storage.language_registry import bundled_language_registry, registry_binding
    base = model(values)
    registry = bundled_language_registry()
    config = {**base.configuration.data, 'language_registry': registry_binding(registry)}
    profile = compose_profiles(base.profile_resources, core_key=base.profile.profile_chain[0],
                               language_registry=registry)
    return TargetModel(canonical_json_bytes(config), base.binding, base.documents, profile=profile,
        resource_files=[*base.resource_files, ModelDocument(config['language_registry']['path'], registry.source_bytes)])


def candidate(mapping, fmt, *, known=False, value=None, fields=None):
    value = content() if value is None else value
    fields = external_fields(value, fmt) if fields is None else fields
    template = {**value, 'created_at': TIME, 'updated_at': TIME, 'created_by': ACTOR, 'updated_by': ACTOR}
    c = {'identity': identity(), 'external_type': 'specroad.requirement', 'fields': fields,
         'new_artifact': None if known else template}
    if not known:
        return import_model([]), c
    projected = select_mapping([mapping], key=mapping.key, expected_sha256=mapping.sha256).artifact(
        c['external_type'], fields)['artifact']
    history = ExternalIdentity(identity()).with_import_history(mapping_id=mapping.key,
        imported_projection=projected, source_projection=projected,
        source_payload=b'previous explicit source', imported_at='2026-01-01T00:00:00Z')
    return import_model([{**value, 'external_identities': [history.data]}]), c


@pytest.mark.parametrize('fmt', FORMATS)
@pytest.mark.parametrize('language', tuple(TEXTS))
@pytest.mark.parametrize('force', ('must', 'must_not', 'should', 'may'))
def test_full_language_corpus_retains_exact_content_bytes(fmt, language, force):
    value = content(language, force)
    mapping, files, options = resources(fmt)
    native = model([value], resource_files=files)
    before = native.source_files
    with no_write_attempts():
        exported = prepare_export(native, ScopeDescriptor(descriptor('project')), **options)
        restored = read_content(exported.output_bytes, fmt, mapping)
    assert tuple(restored[k].encode('utf-8') for k in FIELDS) == tuple(value[k].encode('utf-8') for k in FIELDS)
    assert native.source_files == before
    assert exported.manifest['included_ids'] == [value['id']]
    assert not any(loss['pointer'] in ('/language', '/normative_force', '/statement')
                   for loss in exported.manifest['losses'])
    assert exported.manifest['output_sha256'] == sha256(exported.output_bytes).hexdigest()
    if fmt == 'ndjson':
        assert restored == value


@pytest.mark.parametrize('fmt', FORMATS)
@pytest.mark.parametrize('force', ('must', 'must_not', 'should', 'may'))
def test_actual_decoded_fields_override_creation_defaults_explicitly(fmt, force):
    value = content(force=force)
    mapping, files, options = resources(fmt)
    exported = prepare_export(model([value], resource_files=files), ScopeDescriptor(descriptor('project')), **options)
    raw = exported.output_bytes
    if fmt == 'csv':
        profile = files[1].content
        from specroad.mappings import CSVProfile
        profile = CSVProfile(profile)
        fields = select_csv_profile([mapping, profile], key=profile.key,
            expected_sha256=profile.sha256).decode(raw).records[0]['fields']
    elif fmt == 'ndjson':
        decoded = decode_ndjson(raw).objects[0]['object']
        fields = {k: decoded[k] for k in FIELDS}
    else:
        if fmt == 'reqifz':
            container = decode_reqifz(raw, expected_sha256=sha256(raw).hexdigest(),
                document_paths=('exchange.reqif',), limits=LIMITS, max_uncompressed_bytes=16 * 1024 * 1024)
            raw = dict(container.files)['exchange.reqif']
        document = decode_reqif_structure(raw, limits=LIMITS)
        fields = document.project_object(document.objects[0].identifier)['fields']
    native, c = candidate(mapping, fmt, value=value, fields=fields)
    c['new_artifact'].update(language='de-DE', normative_force='may', statement='Unrelated creation default.')
    args = import_arguments(mapping, fmt)
    args['input_bytes'] = exported.output_bytes
    report = prepare_import_plan(native, [c], **args)
    assert report.plan_valid and not report.data['losses'], report.data['diagnostics']
    target = report.plan.data['result_artifacts'][0]['artifact']
    assert tuple(target[k] for k in FIELDS) == tuple(value[k] for k in FIELDS)
    assert target['external_identities'][0]['last_source_payload_sha256'] == sha256(exported.output_bytes).hexdigest()
    assert target['priority'] == 'mandatory'  # Deliberately independent of force.
    assert not report.write_authorized and not report.data['import_completed']
    assert assess_import_plan(report.canonical_bytes, native, [c], **args).canonical_bytes == report.canonical_bytes


@pytest.mark.parametrize('fmt', FORMATS)
@pytest.mark.parametrize('missing', FIELDS)
@pytest.mark.parametrize('known', (False, True), ids=('new', 'known'))
@pytest.mark.parametrize('strategy', ('update_if_unchanged', 'skip'))
def test_missing_content_mapping_is_loss_not_envelope_or_stored_fallback(fmt, missing, known, strategy):
    original = requirement_mapping('reqif' if fmt == 'reqifz' else fmt)
    data = original.data
    external = next(row['external_field'] for row in data['fields'] if row['target_field'] == missing)
    data['fields'] = [row for row in data['fields'] if row['target_field'] != missing]
    mapping = ExchangeMapping(canonical_json_bytes(data))
    # Both truly absent and supplied-but-unmapped source values must block.
    # Neither gets a synthetic null or a value inferred from the template.
    for supplied in (False, True):
        fields = external_fields(content(), fmt)
        if not supplied:
            del fields[external]
        native, c = candidate(mapping, fmt, known=known, fields=fields)
        before = deepcopy((native.artifacts, c))
        args = import_arguments(mapping, fmt)
        args['strategy'] = strategy
        with no_write_attempts():
            report = prepare_import_plan(native, [c], **args)
        observed = report.data
        assert not report.plan_valid and observed['exit_code'] == 3
        assert observed['operations'] == observed['created_ids'] == observed['updated_ids'] == []
        assert observed['objects'][0]['action'] == 'reject'
        missing_losses = [loss for loss in observed['losses'] if loss['reason'] == 'unmapped_requirement_content']
        assert missing_losses == [{'candidate_index': 0, 'artifact_id': content()['id'],
            'pointer': '/candidates/0/fields', 'reason': 'unmapped_requirement_content',
            'target_field': missing, 'accepted': False}]
        unmapped = [loss for loss in observed['losses'] if loss['reason'] == 'unmapped_external_field']
        assert len(unmapped) == int(supplied)
        if supplied:
            assert unmapped[0]['value'] == fields[external]
        assert (native.artifacts, c) == before
        assert any(d['code'] == 'SRV090' and d.get('target_field') == missing for d in observed['diagnostics'])
        with pytest.raises(ImportIdentityError):
            report.plan
        assert assess_import_plan(report.canonical_bytes, native, [c], **args).data == observed
        for tampered in ({'losses': []}, {'plan_valid': True}, {'operations': [{'op': 'create', 'artifact': content()}]}):
            with pytest.raises(ImportIdentityError):
                assess_import_plan(canonical_json_bytes({**observed, **tampered}), native, [c], **args)


@pytest.mark.parametrize('fmt', FORMATS)
def test_empty_content_mapping_reports_all_absent_members_without_inventing_values(fmt):
    data = requirement_mapping('reqif' if fmt == 'reqifz' else fmt).data
    data['fields'] = []
    mapping = ExchangeMapping(canonical_json_bytes(data))
    native, c = candidate(mapping, fmt, fields={})
    report = prepare_import_plan(native, [c], **import_arguments(mapping, fmt))
    assert {loss['target_field'] for loss in report.data['losses']} == set(FIELDS)
    assert all('value' not in loss and not loss['accepted'] for loss in report.data['losses'])
    assert not report.plan_valid and report.data['operations'] == []


@pytest.mark.parametrize('fmt', FORMATS)
@pytest.mark.parametrize('missing', FIELDS)
def test_configured_but_missing_source_is_still_a_hard_mapping_error(fmt, missing):
    mapping = requirement_mapping('reqif' if fmt == 'reqifz' else fmt)
    native, c = candidate(mapping, fmt)
    field = next(row['external_field'] for row in mapping.data['fields'] if row['target_field'] == missing)
    del c['fields'][field]
    with pytest.raises(MappingError) as caught:
        prepare_import_plan(native, [c], **import_arguments(mapping, fmt))
    assert caught.value.reason == 'mapping_source_field_missing'
    assert caught.value.code == 'SRV090' and caught.value.exit_code == 3


@pytest.mark.parametrize('fmt', FORMATS)
@pytest.mark.parametrize('field,value', [('language', None), ('language', ''), ('language', 'de_DE'),
    ('normative_force', None), ('normative_force', ''), ('normative_force', 'MUST'),
    ('normative_force', 'mandatory'), ('statement', '')])
def test_invalid_explicit_content_is_not_replaced_by_template_text_or_priority(fmt, field, value):
    mapping = requirement_mapping('reqif' if fmt == 'reqifz' else fmt)
    native, c = candidate(mapping, fmt)
    external = ('specroad.' if fmt in ('reqif', 'reqifz') else '') + field
    c['fields'][external] = [value] if fmt in ('reqif', 'reqifz') and field == 'normative_force' else value
    before = deepcopy(c)
    with pytest.raises(ModelError):
        prepare_import_plan(native, [c], **import_arguments(mapping, fmt))
    assert c == before and native.artifacts == []


@pytest.mark.parametrize('fmt', ('csv', 'reqif', 'reqifz'))
@pytest.mark.parametrize('missing', ('language', 'normative_force'))
def test_target_without_content_mapping_keeps_export_loss_and_fail_on_loss(fmt, missing):
    from specroad.exchange import ExportError, requirement_csv_profile
    from specroad.mappings import CSVProfile
    mapping, files, options = resources(fmt)
    data = mapping.data
    data['fields'] = [row for row in data['fields'] if row['target_field'] != missing]
    mapping = ExchangeMapping(canonical_json_bytes(data))
    options['expected_mapping_sha256'] = mapping.sha256
    files = [ModelDocument('mappings/requirements.json', mapping.source_bytes)]
    if fmt == 'csv':
        profile = requirement_csv_profile().data
        profile['mapping'] = mapping.binding()
        profile['columns'] = [row for row in profile['columns'] if row['external_field'] != missing]
        profile = CSVProfile(canonical_json_bytes(profile))
        files.append(ModelDocument('mappings/requirements-csv.json', profile.source_bytes))
        options['expected_csv_profile_sha256'] = profile.sha256
    native = model([content()], resource_files=files)
    report = prepare_export(native, ScopeDescriptor(descriptor('project')), **options)
    losses = report.manifest['losses']
    assert any(loss['resource_id'] == content()['id'] and loss['pointer'] in ('', '/' + missing) for loss in losses)
    if fmt == 'csv':
        assert report.manifest['included_ids'] == [content()['id']]
    else:
        assert report.manifest['included_ids'] == []  # Changed mapping has no implicit core type context.
    with pytest.raises(ExportError) as caught:
        prepare_export(native, ScopeDescriptor(descriptor('project')), fail_on_loss=True, **options)
    assert caught.value.reason == 'export_information_loss' and caught.value.exit_code == 3
    assert json.loads(caught.value.manifest)['losses'] == losses


def test_content_mapping_needs_no_analyzer_or_installed_optional_dependencies(tmp_path):
    from support.processes import run_core
    body = '''from specroad.exchange import requirement_mapping
from specroad.mappings import select_mapping
import sys
mapping = requirement_mapping('reqif')
projection = select_mapping([mapping], key=mapping.key, expected_sha256=mapping.sha256).artifact(
    'specroad.requirement', {'specroad.language':'hi-IN', 'specroad.normative_force':['must_not'],
    'specroad.statement':'should MUST may soll नहीं'})['artifact']
assert projection['language'] == 'hi-IN' and projection['normative_force'] == 'must_not'
assert projection['statement'] == 'should MUST may soll नहीं'
assert not any(n == 'numpy' or n.startswith('numpy.') or n == 'py3langid' or n.startswith('py3langid.') for n in sys.modules)
'''
    result = run_core(body, tmp_path, capture=True)
    assert result.returncode == 0, result.stderr


def test_csv_control_character_requires_explicit_typed_cell_not_silent_rewriting():
    from specroad.exchange import requirement_csv_profile
    from specroad.mappings import CSVError, CSVProfile
    value = content()
    value['statement'] += '\tOriginal tab must remain present.'
    mapping, files, options = resources('csv')
    native = model([value], resource_files=files)
    with pytest.raises(CSVError) as caught:
        prepare_export(native, ScopeDescriptor(descriptor('project')), **options)
    assert caught.value.reason == 'csv_unrepresentable_character'
    profile = requirement_csv_profile().data
    next(row for row in profile['columns'] if row['external_field'] == 'statement').update(
        codec={'kind': 'typed-json-v1'}, empty_cell='error')
    profile = CSVProfile(canonical_json_bytes(profile))
    options['expected_csv_profile_sha256'] = profile.sha256
    files[1] = ModelDocument('mappings/requirements-csv.json', profile.source_bytes)
    exported = prepare_export(model([value], resource_files=files), ScopeDescriptor(descriptor('project')), **options)
    decoded = select_csv_profile([mapping, profile], key=profile.key,
        expected_sha256=profile.sha256).decode(exported.output_bytes).records[0]['fields']
    assert tuple(decoded[k].encode('utf-8') for k in FIELDS) == tuple(value[k].encode('utf-8') for k in FIELDS)
    assert not any(loss['pointer'] in ('/language', '/normative_force', '/statement')
                   for loss in exported.manifest['losses'])
