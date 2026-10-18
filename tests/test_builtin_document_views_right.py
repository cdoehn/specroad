"""Unavailable calculations and exact read-only fallback source contracts."""
from copy import deepcopy
from hashlib import sha256
import builtins
import io
import json
import os

import pytest

from specroad.documents import (BuiltinViewError, BuiltinViewProviderError,
    resolve_builtin_view, render_builtin_view, resolve_type_fallback, render_type_fallback)
from specroad.documents._render_formats import Emitter
from specroad.graph.boundaries import BoundaryReference, boundary_for_relation
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import record_value
from support.relations import aid, edge, rid
from support.targets import model, SCOPE
from test_builtin_document_views import trace_project, partial_project, legacy_documents


def weak_partial(kind='conflicts_with', *, omitted=True, reverse=False, duplicate=False):
    source_number, target_number = (2, 1) if reverse else (1, 2)
    target = domain_value('requirement', id=aid(number=target_number))
    source = domain_value('requirement', id=aid(number=source_number),
        relations=[edge(kind, target['id'], 1)])
    if duplicate: source['relations'].append(edge(kind, target['id'], 2))
    release = domain_value('release', id=aid('release'))
    supplied = model([source, release] + ([] if omitted else [target]))
    boundaries = []
    if omitted:
        loaded = SourceRelations(canonical_json_bytes(source))
        target_source = SourceRelations(canonical_json_bytes(target))
        boundaries = [boundary_for_relation(relation, target_source).data for relation in loaded.relations]
    return supplied.documents, {'source_kind': 'partial', 'scope_descriptor': {
        **SCOPE, 'scope_kind': 'release', 'selector': {'release_id': release['id']},
        'boundary_policy': 'partial'}, 'boundary_references': boundaries}


def unavailable():
    return {name: {'status': 'unavailable', 'reason': 'provider_required',
                   'required_milestone': milestone, 'result': None}
            for name, milestone in (('verification', 'M12'), ('roadmap', 'M13'))}


@pytest.mark.parametrize('name,milestone', [('verification', 'M12'), ('roadmap', 'M13')])
@pytest.mark.parametrize('entrypoint', ['resolve', 'render'])
@pytest.mark.parametrize('empty', [False, True])
def test_missing_computation_providers_refuse_with_owned_structured_unavailability(monkeypatch, name, milestone, entrypoint, empty):
    supplied = model([] if empty else trace_project()); before = supplied.source_files
    def no_output(*args): raise AssertionError('Unavailable report reached presentation')
    monkeypatch.setattr(Emitter, 'output', no_output)
    operation = resolve_builtin_view if entrypoint == 'resolve' else render_builtin_view
    with no_write_attempts(), pytest.raises(BuiltinViewProviderError) as caught:
        operation(supplied, name)
    error = caught.value; data = error.diagnostic()
    assert isinstance(error, BuiltinViewError) and error.exit_code == 3
    assert data['reason'] == 'builtin_view_provider_required' and data['pointer'] == '/view_name'
    assert data['view_name'] == name
    assert data['calculation'] == {'status': 'unavailable', 'reason': 'provider_required',
                                   'required_milestone': milestone, 'result': None}
    data['calculation'].update(status='passed', result={})
    assert error.diagnostic()['calculation'] == unavailable()[name]
    assert supplied.source_files == before


@pytest.mark.parametrize('source', ['specification', 'traceability', 'empty_trace', 'partial', 'legacy'])
def test_every_projection_reports_absent_calculations_without_promoting_stored_content(source):
    if source == 'specification':
        value = record_value('document', extensions={'example.reports': {'verification': {'status': 'passed'}}})
        result = resolve_builtin_view(model([value]), source)
    elif source in ('traceability', 'empty_trace'):
        result = resolve_builtin_view(model(trace_project() if source == 'traceability' else []), 'traceability')
    else:
        docs, options = partial_project() if source == 'partial' else (legacy_documents(), {'source_kind': 'legacy'})
        result = resolve_type_fallback(docs, **options)
    data = result.data
    assert data['computed_reports'] == unavailable()
    assert not data['verification_evaluated'] and not data['release_readiness_evaluated']
    assert not data['full_validation_passed'] and not data['approval_granted'] and not data['write_authorized']
    if source in ('traceability', 'empty_trace'):
        assert all(row['verification_result'] is None and row['release_readiness'] is None for row in data['rows'])
        if source == 'empty_trace': assert data['row_count'] == 0
    data['computed_reports']['roadmap']['status'] = 'passed'
    assert result.data['computed_reports'] == unavailable()


@pytest.mark.parametrize('result_value', ['passed', 'failed', 'blocked', 'unknown'])
def test_stored_evidence_results_never_become_computed_verification_or_readiness(result_value):
    values = trace_project()
    for value in values:
        if value['artifact_type'] == 'evidence': value['result'] = result_value
    data = resolve_builtin_view(model(values), 'traceability').data
    assert data['records'][aid('evidence')]['record']['result'] == result_value
    assert data['rows'][0]['evidence']['artifact_ids'] == [aid('evidence')]
    assert data['rows'][0]['verification_result'] is None and data['rows'][0]['release_readiness'] is None
    assert data['computed_reports'] == unavailable()


@pytest.mark.parametrize('reverse_relations', [False, True])
def test_trace_edges_bind_the_actual_source_pointer_bytes_and_record(reverse_relations):
    values = trace_project()
    if reverse_relations: values[0]['relations'].reverse()
    supplied = model(values)
    result = resolve_builtin_view(supplied, 'traceability')
    for bound in result.data['relations'].values():
        binding = bound['source_binding']; raw = result.source_files[binding['path']]
        value = json.loads(raw); number = int(bound['pointer'].split('/')[-1])
        assert bound['pointer'].startswith('/relations/')
        assert value['id'] == bound['source_id']
        assert value['relations'][number] == bound['stored_relation']
        assert bound['relation_sha256'] == canonical_json_sha256(value['relations'][number])
        assert binding['source_sha256'] == sha256(raw).hexdigest()
        assert binding['record_sha256'] == canonical_json_sha256(value)
        assert result.data['records'][value['id']]['record'] == value


@pytest.mark.parametrize('kind', ['conflicts_with', 'duplicates'])
@pytest.mark.parametrize('omitted', [False, True])
def test_partial_fallback_rejects_reversed_symmetric_storage_at_local_and_missing_targets(kind, omitted):
    docs, options = weak_partial(kind, omitted=omitted, reverse=True)
    before = {d.path: d.content for d in docs}
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_type_fallback(docs, **options)
    assert caught.value.reason == 'noncanonical_symmetric_relation'
    assert caught.value.path.endswith(aid(number=2) + '.json')
    assert caught.value.pointer == '/relations/0'
    assert {d.path: d.content for d in docs} == before


@pytest.mark.parametrize('kind', ['conflicts_with', 'duplicates'])
@pytest.mark.parametrize('omitted', [False, True])
def test_partial_fallback_rejects_two_identities_for_one_symmetric_pair(kind, omitted):
    docs, options = weak_partial(kind, omitted=omitted, duplicate=True)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_type_fallback(docs, **options)
    assert caught.value.reason == 'duplicate_symmetric_relation'
    assert caught.value.path.endswith(aid() + '.json') and caught.value.pointer == '/relations/1'


@pytest.mark.parametrize('kind', ['conflicts_with', 'duplicates'])
@pytest.mark.parametrize('omitted', [False, True])
def test_valid_symmetric_pair_keeps_original_storage_and_never_invents_the_omitted_record(kind, omitted):
    docs, options = weak_partial(kind, omitted=omitted)
    result = resolve_type_fallback(docs, **options); data = result.data
    assert (aid(number=2) in data['records']) is not omitted
    assert data['boundary_references'] == options['boundary_references']
    assert data['records'][aid()]['record']['relations'] == [edge(kind, aid(number=2), 1)]
    assert result.source_files == {d.path: d.content for d in docs}


def test_different_symmetric_kinds_and_parallel_directed_edges_remain_distinct():
    docs, options = weak_partial(omitted=False)
    values = [json.loads(d.content) for d in docs]
    source = next(v for v in values if v['id'] == aid())
    source['relations'].extend([edge('duplicates', aid(number=2), 2),
        edge('depends_on', aid(number=2), 3), edge('depends_on', aid(number=2), 4)])
    supplied = model(values)
    data = resolve_type_fallback(supplied.documents, **options).data
    assert data['records'][aid()]['record']['relations'] == source['relations']


@pytest.mark.parametrize('replacement', [{'origin_target_sha256': 'not-a-hash'},
    {'extra': 'unrecognized'}, {'reason': ''}, {'target_type': 'goal'}])
def test_cached_boundary_values_are_revalidated_before_their_current_data_is_trusted(replacement):
    docs, options = weak_partial()
    boundary = BoundaryReference(options['boundary_references'][0])
    changed = {**boundary.data, **replacement}
    object.__setattr__(boundary, '_encoded', canonical_json_bytes(changed))
    options['boundary_references'] = [boundary]
    with no_write_attempts(), pytest.raises(ModelError): resolve_type_fallback(docs, **options)


@pytest.mark.parametrize('as_value', [False, True])
def test_valid_boundary_data_and_native_values_produce_the_same_owned_projection(as_value):
    docs, options = weak_partial()
    expected = resolve_type_fallback(docs, **options)
    raw = deepcopy(options['boundary_references'][0])
    declaration = BoundaryReference(raw) if as_value else raw
    options['boundary_references'] = [declaration]
    result = resolve_type_fallback(docs, **options)
    raw['origin_target_sha256'] = 'e' * 64
    if as_value: object.__setattr__(declaration, '_encoded', canonical_json_bytes(raw))
    assert result.data == expected.data and result.sha256 == expected.sha256


@pytest.mark.parametrize('target', ['holder', 'boundary'])
def test_midprojection_caller_mutation_cannot_split_hashes_validation_and_returned_bytes(monkeypatch, target):
    from specroad.documents import type_fallback
    docs, options = weak_partial()
    if target == 'boundary': options['boundary_references'] = [BoundaryReference(options['boundary_references'][0])]
    expected = resolve_type_fallback(docs, **options)
    original = type_fallback._typed_records
    def mutate(owned):
        if target == 'holder': object.__setattr__(docs[0], 'content', b'{}')
        else: object.__setattr__(options['boundary_references'][0], '_encoded', b'{}')
        return original(owned)
    monkeypatch.setattr(type_fallback, '_typed_records', mutate)
    with no_write_attempts(): actual = resolve_type_fallback(docs, **options)
    assert actual.data == expected.data and actual.source_files == expected.source_files
    assert actual.sha256 == expected.sha256


@pytest.mark.parametrize('paths', [('legacy/A.json', 'legacy/a.json'),
    ('legacy/é.json', 'legacy/e\u0301.json'), ('legacy/É.json', 'legacy/e\u0301.json')])
def test_legacy_source_path_aliases_cannot_bind_two_distinct_records(paths):
    raw = legacy_documents()
    docs = [ModelDocument(path, document.content) for path, document in zip(paths, raw)]
    with no_write_attempts(), pytest.raises(BuiltinViewError) as caught:
        resolve_type_fallback(docs, source_kind='legacy')
    assert caught.value.reason == 'builtin_fallback_duplicate_path'


def test_noncolliding_legacy_paths_and_original_unicode_remain_byte_exact():
    raw = legacy_documents()
    docs = [ModelDocument('legacy/e\u0301.json', raw[0].content), raw[1]]
    result = resolve_type_fallback(docs, source_kind='legacy')
    assert result.source_files == {d.path: d.content for d in docs}
    assert result.data['records']['SR-REQ-0002']['path'] == 'legacy/e\u0301.json'
    assert result.data['records']['SR-REQ-0002']['record'] == json.loads(raw[0].content)


@pytest.mark.parametrize('maturity,allowed', [('retired', True), ('draft', False), ('approved', False)])
@pytest.mark.parametrize('source_kind', ['legacy', 'partial'])
def test_only_an_actually_retired_primary_can_coexist_with_the_type_fallback(maturity, allowed, source_kind):
    if source_kind == 'partial':
        docs, options = partial_project()
        docs += model([record_value('document', maturity=maturity)]).documents
    else:
        value = {'schema_version': '0.1.0', 'id': 'SR-DOC-0001', 'artifact_type': 'document',
                 'title': 'Original', 'revision': 4, 'document_role': 'primary_specification', 'maturity': maturity}
        docs = (*legacy_documents(), ModelDocument('legacy/document.json', canonical_json_bytes(value)))
        options = {'source_kind': 'legacy'}
    with no_write_attempts():
        if allowed:
            result = resolve_type_fallback(docs, **options)
            assert result.data['primary_document'] is None
            assert result.source_files == {d.path: d.content for d in docs}
        else:
            with pytest.raises(BuiltinViewError) as caught: resolve_type_fallback(docs, **options)
            assert caught.value.reason == 'builtin_fallback_primary_present'


def test_supporting_document_partial_keeps_contains_identity_and_has_no_primary():
    document = record_value('document', id=aid('document'), document_role='supporting',
        relations=[edge('contains', aid('section'), 1, position=0)])
    section = record_value('section', id=aid('section'))
    supplied = model([document, section])
    descriptor = {**SCOPE, 'scope_kind': 'document', 'selector': {'document_id': document['id']},
                  'boundary_policy': 'partial'}
    with no_write_attempts():
        result = resolve_type_fallback(supplied.documents, source_kind='partial', scope_descriptor=descriptor)
    assert result.data['primary_document'] is None
    assert result.data['artifact_ids'] == [document['id'], section['id']]
    assert result.data['records'][document['id']]['record'] == document
    assert result.source_files == {d.path: d.content for d in supplied.documents}


@pytest.mark.parametrize('source_kind', ['legacy', 'partial'])
def test_fallback_result_has_no_claimed_model_root_even_when_source_fields_assert_success(source_kind):
    docs, options = partial_project() if source_kind == 'partial' else (legacy_documents(), {'source_kind': 'legacy'})
    changed = []
    for document in docs:
        value = json.loads(document.content)
        value['extensions'] = {'example.report': {'model_root_sha256': 'a' * 64, 'full_validation_passed': True,
                               'verification_result': 'passed', 'write_authorized': True}}
        changed.append(ModelDocument(document.path, canonical_json_bytes(value)))
    result = resolve_type_fallback(changed, **options); data = result.data
    assert data['model_root_sha256'] is None and data['primary_document'] is None
    assert data['computed_reports'] == unavailable() and data['full_validation_passed'] is False
    assert data['source_context_verified'] is False and data['write_authorized'] is False
    assert all(bound['record']['extensions']['example.report']['verification_result'] == 'passed'
               for bound in data['records'].values())


@pytest.mark.parametrize('output_format', ['markdown', 'html'])
@pytest.mark.parametrize('source', ['traceability', 'legacy', 'partial'])
def test_rendering_receives_unavailability_metadata_and_preserves_every_real_file(monkeypatch, tmp_path, output_format, source):
    if source == 'traceability':
        supplied = model(trace_project()); expected = resolve_builtin_view(supplied, source)
        inputs = supplied.source_files
        invoke = lambda: render_builtin_view(supplied, source, output_format=output_format)
    else:
        docs, options = partial_project() if source == 'partial' else (legacy_documents(), {'source_kind': 'legacy'})
        expected = resolve_type_fallback(docs, **options); inputs = expected.source_files
        invoke = lambda: render_type_fallback(docs, **options, output_format=output_format)
    for name, raw in inputs.items():
        target = tmp_path / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    (tmp_path / 'sentinel.bin').write_bytes(b'untouched')
    before = inventory(tmp_path); observed = []
    original = Emitter.output
    def capture(self, metadata, title, nodes):
        observed.append(deepcopy(metadata))
        return original(self, metadata, title, nodes)
    monkeypatch.setattr(Emitter, 'output', capture)
    def refuse(*args, **kwargs): raise AssertionError('Unexpected read')
    with no_write_attempts(), monkeypatch.context() as guarded:
        for module, name in ((builtins, 'open'), (io, 'open'), (os, 'open')):
            guarded.setattr(module, name, refuse)
        invoke()
    assert inventory(tmp_path) == before
    metadata, = observed
    assert metadata['computed_reports'] == unavailable()
    assert metadata['verification_evaluated'] is False and metadata['release_readiness_evaluated'] is False
    assert metadata['projection_sha256'] == expected.sha256


@pytest.mark.parametrize('output_format', ['text', None, [], True])
def test_fallback_rejects_unsupported_output_formats_before_presenting_anything(output_format):
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        render_type_fallback(legacy_documents(), source_kind='legacy', output_format=output_format)
    assert caught.value.reason == 'render_format_not_supported'


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_partial_fallback_and_provider_refusals_have_core_pyz_machine_contract_parity(tmp_path, mode):
    docs, options = weak_partial('duplicates')
    expected = resolve_type_fallback(docs, **options).data
    supplied = model([])
    try: resolve_builtin_view(supplied, 'verification')
    except BuiltinViewProviderError as error: diagnostic = error.diagnostic()
    body = '''import json
from specroad.documents import resolve_type_fallback, resolve_builtin_view, BuiltinViewProviderError
from specroad.changes import TargetModel
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'documents=' + repr([(d.path, d.content) for d in docs]) + '\n'
    body += 'options=' + repr(options) + '\n'
    body += 'configuration=' + repr(supplied.configuration_bytes) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += '''profile=ProfileResource(dict(resources)['profiles/core.json'])
supplied=TargetModel(configuration,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [],profile=compose_profiles([profile],core_key=profile.key),
 resource_files=[ModelDocument(p,b) for p,b in resources])
try: resolve_builtin_view(supplied,'verification')
except BuiltinViewProviderError as error: diagnostic=error.diagnostic()
print(json.dumps([resolve_type_fallback([ModelDocument(p,b) for p,b in documents],**options).data,diagnostic],sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [expected, diagnostic]
