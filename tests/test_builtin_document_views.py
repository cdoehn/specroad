"""Built-in source identity, trace facts and fallback effects, never markup."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import builtins
import io
import json
import os

import pytest

from specroad.changes import TargetModel
from specroad.documents import (BuiltinViewData, BuiltinViewError, DocumentRoleError,
    compose_document, resolve_builtin_view, render_builtin_view,
    resolve_type_fallback, render_type_fallback)
from specroad.documents._render_formats import Emitter
from specroad.graph.boundaries import boundary_for_relation
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.validation import ModelDocument
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import record_value
from support.relations import aid, edge, rid
from support.targets import model, SCOPE
from test_document_includes import include_project


def trace_project():
    req = domain_value('requirement', id=aid(), statement='Exact e\u0301\r\nمعنى',
        relations=[edge('derived_from', aid('need'), 1), edge('implemented_by', aid('task'), 2),
                   edge('verified_by', aid('verification'), 3), edge('scheduled_for', aid('milestone'), 4)])
    return [req,
        domain_value('need', id=aid('need'), relations=[edge('addresses', aid('goal'), 5)]),
        domain_value('goal', id=aid('goal')),
        domain_value('task', id=aid('task'), relations=[edge('part_of', aid('release'), 6)]),
        record_value('verification', id=aid('verification'), subjects=[aid()],
                     relations=[edge('produces', aid('evidence'), 7)]),
        record_value('evidence', id=aid('evidence'), result='passed',
                     subjects=[{'artifact_id': aid(), 'revision': 99, 'artifact_sha256': 'a' * 64,
                                'verification_context_sha256': 'b' * 64}]),
        domain_value('milestone', id=aid('milestone'), relations=[edge('part_of', aid('release'), 8)]),
        domain_value('release', id=aid('release')),
        domain_value('requirement', id=aid(number=2), title='No stored traces')]


def partial_project(*, boundary=False):
    release = domain_value('release', id=aid('release'))
    req = domain_value('requirement', id=aid(), relations=[edge('scheduled_for', release['id'], 1)])
    if boundary:
        req['relations'].append(edge('conflicts_with', aid(number=2), 2))
    documents = model([req, release]).documents
    descriptor = {**SCOPE, 'scope_kind': 'release', 'selector': {'release_id': release['id']},
                  'boundary_policy': 'partial'}
    boundaries = []
    if boundary:
        source = SourceRelations(canonical_json_bytes(req))
        target = SourceRelations(canonical_json_bytes(domain_value('requirement', id=aid(number=2))))
        relation = next(r for r in source.relations if r.type == 'conflicts_with')
        boundaries = [boundary_for_relation(relation, target).data]
    return documents, {'source_kind': 'partial', 'scope_descriptor': descriptor,
                       'boundary_references': boundaries}


def legacy_documents():
    # No current-schema defaults are present or permissible to insert here.
    return tuple(ModelDocument('legacy/' + value['id'] + '.json',
        json.dumps(value, ensure_ascii=False, indent=3).encode('utf-8') + b'\n') for value in (
            {'schema_version': '0.1.0', 'id': 'SR-REQ-0002', 'artifact_type': 'requirement',
             'title': 'Original', 'revision': 7, 'statement': '  e\u0301\r\nبيان  ',
             'relations': [{'type': 'derived_from', 'target': 'SR-NEED-0001'}]},
            {'schema_version': '0.1.0', 'id': 'SR-GOAL-0001', 'artifact_type': 'goal',
             'title': 'Goal', 'revision': 3, 'statement': 'Historical goal'}))


def test_specification_selects_primary_and_preserves_the_native_repeated_composition():
    values = include_project()
    primary = next(v for v in values if v.get('document_role') == 'primary_specification')
    supplied = model(values)
    expected = compose_document(supplied, primary['id'])
    with no_write_attempts(): resolved = resolve_builtin_view(supplied, 'specification')
    data = resolved.data
    assert data['composition'] == expected.data and data['composition_sha256'] == expected.sha256
    assert data['primary_document']['record'] == primary and data['primary_document']['artifact_id'] == primary['id']
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    assert data['input_sha256'] == supplied._sources_sha256 and resolved.source_files == supplied.source_files
    assert data['mode'] == 'primary_document' and data['fallback'] is False
    occurrences = data['composition']['occurrences']
    assert len(occurrences) > len({item['artifact_id'] for item in occurrences})


@pytest.mark.parametrize('records,reason', [([], 'document_primary_missing'),
    ([record_value('document', document_role='supporting')], 'document_primary_missing'),
    ([record_value('document', maturity='retired')], 'document_primary_missing'),
    ([record_value('document', id=aid('document')), record_value('document', id=aid('document', 2))],
     'document_primary_multiple')])
def test_full_project_never_silently_substitutes_a_type_fallback(records, reason):
    with no_write_attempts(), pytest.raises(DocumentRoleError) as caught:
        resolve_builtin_view(model(records), 'specification')
    assert caught.value.reason == reason and caught.value.exit_code == 3


def test_invalid_supporting_document_cannot_be_hidden_by_a_valid_primary():
    broken = record_value('document', id=aid('document', 2), document_role='supporting')
    broken.pop('purpose')
    with pytest.raises(DocumentRoleError) as caught:
        resolve_builtin_view(model([record_value('document'), broken]), 'specification')
    assert caught.value.reason == 'missing_field' and caught.value.pointer == '/purpose'


def test_traceability_binds_actual_origin_implementation_verification_evidence_and_release():
    values = trace_project(); supplied = model(values)
    with no_write_attempts(): result = resolve_builtin_view(supplied, 'traceability')
    data = result.data; first, empty = data['rows']
    assert data['row_count'] == 2 and first['requirement_id'] == aid() and empty['requirement_id'] == aid(number=2)
    assert first['origin'] == {'artifact_ids': sorted([aid('need'), aid('goal')]), 'relation_ids': [rid(1), rid(5)]}
    assert first['implementation'] == {'artifact_ids': [aid('task')], 'relation_ids': [rid(2)]}
    assert first['verification'] == {'artifact_ids': [aid('verification')], 'relation_ids': [rid(3)]}
    assert first['evidence']['artifact_ids'] == [aid('evidence')]
    assert first['evidence']['relation_ids'] == [rid(7)]
    evidence = next(v for v in values if v['artifact_type'] == 'evidence')
    assert first['evidence']['subject_bindings'] == [{'artifact_id': aid('evidence'),
        'pointer': '/subjects/0', 'subject': evidence['subjects'][0]}]
    assert first['release'] == {'artifact_ids': sorted([aid('release'), aid('milestone')]),
                                'relation_ids': [rid(4), rid(6), rid(8)]}
    for category in ('origin', 'implementation', 'verification', 'evidence', 'release'):
        assert empty[category]['artifact_ids'] == [] and empty[category]['relation_ids'] == []
    for row in data['rows']:
        assert row['verification_result'] is None and row['release_readiness'] is None
    assert data['model_root_sha256'] == supplied.manifest(supplied.artifacts, SCOPE).sha256
    for value in values:
        bound = data['records'][value['id']]
        assert bound['record'] == value and bound['record_sha256'] == canonical_json_sha256(value)
        assert bound['source_sha256'] == sha256(result.source_files[bound['path']]).hexdigest()
    for bound in data['relations'].values():
        stored = next(r for v in values if v['id'] == bound['source_id']
                      for r in v['relations'] if r['relation_id'] == bound['relation_id'])
        assert bound['stored_relation'] == stored and bound['target_id'] == stored['target']
        assert bound['relation_sha256'] == canonical_json_sha256(stored)
    assert not any(data[key] for key in ('verification_evaluated', 'release_readiness_evaluated',
        'full_validation_passed', 'write_authorized', 'project_files_verified', 'approval_granted'))


def test_evidence_subject_without_produces_is_a_bound_field_not_a_fabricated_relation():
    values = trace_project()
    next(v for v in values if v['artifact_type'] == 'verification')['relations'] = []
    data = resolve_builtin_view(model(values), 'traceability').data
    assert data['rows'][0]['evidence']['artifact_ids'] == [aid('evidence')]
    assert data['rows'][0]['evidence']['relation_ids'] == [] and rid(7) not in data['relations']
    assert data['records'][aid('evidence')]['record']['result'] == 'passed'
    assert data['rows'][0]['verification_result'] is None


def test_cyclic_origin_references_terminate_without_duplicate_ids_or_reverse_edges():
    values = [domain_value('requirement', id=aid(number=n),
        relations=[edge('refines', aid(number=2 if n == 1 else 1), n)]) for n in (1, 2)]
    data = resolve_builtin_view(model(values), 'traceability').data
    assert [r['origin']['artifact_ids'] for r in data['rows']] == [[aid(number=2)], [aid()]]
    assert all(r['origin']['relation_ids'] == [rid(1), rid(2)] for r in data['rows'])
    assert data['relations'][rid(1)]['source_id'] == aid()


@pytest.mark.parametrize('order', [list(range(9)), list(reversed(range(9))), [3, 0, 5, 8, 1, 6, 4, 7, 2]])
def test_trace_projection_is_deterministic_under_source_inventory_reordering(order):
    values = trace_project()
    expected = resolve_builtin_view(model(values), 'traceability')
    actual = resolve_builtin_view(model([values[n] for n in order]), 'traceability')
    assert actual.data == expected.data and actual.sha256 == expected.sha256


def test_traceability_does_not_turn_text_mentions_or_stored_status_into_traces():
    req = domain_value('requirement', id=aid(), statement=aid('goal'),
                       implementation_status='implemented', verification_plan_status='planned')
    result = resolve_builtin_view(model([req, domain_value('goal', id=aid('goal'))]), 'traceability').data
    assert result['rows'][0]['origin']['artifact_ids'] == []
    assert result['rows'][0]['implementation']['artifact_ids'] == []
    assert result['rows'][0]['verification_result'] is None


@pytest.mark.parametrize('broken', ['missing_target', 'invalid_pair', 'missing_statement'])
def test_trace_projection_preserves_native_rejection_of_invalid_data(broken):
    values = trace_project()
    if broken == 'missing_target': values = [v for v in values if v['id'] != aid('need')]
    elif broken == 'invalid_pair': values[0]['relations'][0]['target'] = aid('evidence')
    else: del values[0]['statement']
    with no_write_attempts(), pytest.raises(ModelError):
        resolve_builtin_view(model(values), 'traceability')


@pytest.mark.parametrize('name', ['verification', 'roadmap'])
def test_unavailable_computed_view_is_an_error_not_an_empty_or_successful_report(name):
    with no_write_attempts(), pytest.raises(BuiltinViewError) as caught:
        resolve_builtin_view(model(trace_project()), name)
    assert caught.value.reason == 'builtin_view_provider_required' and caught.value.exit_code == 3


@pytest.mark.parametrize('name', ['unknown', '', None, [], True])
def test_unknown_or_untyped_builtin_names_are_usage_errors(name):
    with pytest.raises(BuiltinViewError) as caught:
        resolve_builtin_view(model([]), name)
    assert caught.value.reason == 'builtin_view_not_supported' and caught.value.exit_code == 2


def test_changed_source_bytes_rebind_even_when_record_values_do_not_change():
    supplied = model(trace_project()); changed = [ModelDocument(d.path,
        json.dumps(json.loads(d.content), ensure_ascii=False, indent=2).encode()) for d in supplied.documents]
    other = TargetModel(supplied.configuration_bytes, supplied.binding, changed,
                        profile=supplied.profile, resource_files=supplied.resource_files)
    first = resolve_builtin_view(supplied, 'traceability'); second = resolve_builtin_view(other, 'traceability')
    assert first.sha256 != second.sha256 and first.data['input_sha256'] != second.data['input_sha256']
    assert first.data['model_root_sha256'] == second.data['model_root_sha256']
    assert first.data['rows'] == second.data['rows']
    for identifier, bound in first.data['records'].items():
        assert bound['record_sha256'] == second.data['records'][identifier]['record_sha256']
        assert bound['source_sha256'] != second.data['records'][identifier]['source_sha256']


@pytest.mark.parametrize('boundary', [False, True])
def test_partial_fallback_preserves_actual_records_and_exact_omitted_boundaries(boundary):
    documents, options = partial_project(boundary=boundary)
    with no_write_attempts(): result = resolve_type_fallback(documents, **options)
    data = result.data
    assert data['artifact_ids'] == [aid('release'), aid()]
    assert data['groups'] == [{'artifact_type': 'release', 'artifact_ids': [aid('release')]},
                              {'artifact_type': 'requirement', 'artifact_ids': [aid()]}]
    assert data['boundary_references'] == options['boundary_references']
    assert data['scope_descriptor'] == options['scope_descriptor']
    assert data['primary_document'] is None and data['model_root_sha256'] is None
    assert data['source_context_verified'] is False and data['origin_hashes_verified'] is False
    assert data['fallback'] and data['source_kind'] == 'partial'
    assert result.source_files == {d.path: d.content for d in documents}
    assert set(data['records']) == {json.loads(d.content)['id'] for d in documents}
    assert aid(number=2) not in data['records']


@pytest.mark.parametrize('failure,reason', [('missing', 'boundary_reference_missing'),
    ('wrong_relation', 'boundary_reference_missing'), ('strong', 'missing_relation_target')])
def test_partial_fallback_never_replaces_bad_or_missing_bindings_with_placeholder_records(failure, reason):
    documents, options = partial_project(boundary=True)
    if failure == 'missing': options['boundary_references'] = []
    elif failure == 'wrong_relation': options['boundary_references'][0]['relation_id'] = rid(99)
    else:
        value = json.loads(next(d.content for d in documents if json.loads(d.content)['id'] == aid()))
        value['relations'][-1]['type'] = 'depends_on'
        documents = tuple(ModelDocument(d.path, canonical_json_bytes(value)) if json.loads(d.content)['id'] == aid() else d for d in documents)
        options['boundary_references'] = []
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_type_fallback(documents, **options)
    # A wrong edge ID leaves the actual omitted edge without a declaration.
    assert caught.value.reason == reason


@pytest.mark.parametrize('scope_change,reason', [({'boundary_policy': 'closed'}, 'builtin_fallback_partial_scope_required'),
    ({'scope_kind': 'project', 'selector': {}}, 'builtin_fallback_partial_scope_required'),
    ({'selector': {'release_id': aid('release', 2)}}, 'builtin_fallback_scope_root_missing')])
def test_fallback_requires_the_supplied_partial_scope_and_its_actual_root(scope_change, reason):
    documents, options = partial_project()
    options['scope_descriptor'].update(scope_change)
    with pytest.raises(BuiltinViewError) as caught: resolve_type_fallback(documents, **options)
    assert caught.value.reason == reason


def test_partial_with_a_primary_cannot_request_a_second_invented_specification():
    documents, options = partial_project()
    primary = model([record_value('document')]).documents
    with pytest.raises(BuiltinViewError) as caught: resolve_type_fallback(documents + primary, **options)
    assert caught.value.reason == 'builtin_fallback_primary_present'


def test_legacy_fallback_keeps_original_versions_ids_missing_fields_and_bytes():
    documents = legacy_documents()
    with no_write_attempts(): result = resolve_type_fallback(documents, source_kind='legacy')
    data = result.data
    assert data['artifact_ids'] == ['SR-GOAL-0001', 'SR-REQ-0002']
    assert data['primary_document'] is None and data['model_root_sha256'] is None
    assert not any(data[key] for key in ('legacy_semantics_verified', 'full_validation_passed',
                                       'source_context_verified', 'write_authorized', 'approval_granted'))
    for document in documents:
        value = json.loads(document.content); bound = data['records'][value['id']]
        assert bound['record'] == value and bound['revision'] == value['revision']
        assert 'id_scheme' not in bound['record'] and bound['record']['schema_version'] == '0.1.0'
        assert bound['source_sha256'] == sha256(document.content).hexdigest()
        assert result.source_files[document.path] == document.content
    assert data['records']['SR-REQ-0002']['record']['statement'] == '  e\u0301\r\nبيان  '


@pytest.mark.parametrize('field,value', [('schema_version', '0.2.0'), ('schema_version', '9.0.0'),
    ('id', 'SR-REQ-00001'), ('id', aid()), ('artifact_type', 'goal'),
    ('revision', True), ('revision', 0), ('title', None), ('title', '')])
def test_legacy_fallback_rejects_invalid_envelopes_without_silent_repairs(field, value):
    document = legacy_documents()[0]; changed = json.loads(document.content); changed[field] = value
    with no_write_attempts(), pytest.raises(ModelError):
        resolve_type_fallback([ModelDocument(document.path, canonical_json_bytes(changed))], source_kind='legacy')


@pytest.mark.parametrize('source_kind', ['project', 'unknown', None, True])
def test_fallback_cannot_be_requested_as_a_full_project_or_inferred_from_paths(source_kind):
    with pytest.raises(BuiltinViewError) as caught:
        resolve_type_fallback(legacy_documents(), source_kind=source_kind)
    assert caught.value.reason == 'builtin_fallback_source_kind_required' and caught.value.exit_code == 2


@pytest.mark.parametrize('case', ['path', 'identity', 'mixed_prefix', 'unsafe_path', 'untyped'])
def test_fallback_rejects_ambiguous_or_unbound_input_inventory(case):
    documents = list(legacy_documents()); first = documents[0]
    if case == 'path': documents.append(first)
    elif case == 'identity': documents.append(ModelDocument('legacy/another.json', first.content))
    elif case == 'mixed_prefix':
        value = json.loads(first.content); value['id'] = 'XX-REQ-0003'
        documents.append(ModelDocument('legacy/foreign.json', canonical_json_bytes(value)))
    elif case == 'unsafe_path': documents[0] = ModelDocument('../outside.json', first.content)
    else: documents[0] = {'path': first.path, 'content': first.content}
    with no_write_attempts(), pytest.raises(ModelError): resolve_type_fallback(documents, source_kind='legacy')


@pytest.mark.parametrize('source_kind', ['partial', 'legacy'])
def test_fallback_order_is_type_then_identity_not_source_path_or_enumeration(source_kind):
    documents, options = (partial_project() if source_kind == 'partial' else
                           (legacy_documents(), {'source_kind': 'legacy'}))
    first = resolve_type_fallback(documents, **options)
    second = resolve_type_fallback(tuple(reversed(documents)), **options)
    assert first.data == second.data and first.sha256 == second.sha256


@pytest.mark.parametrize('kind', ['project', 'partial', 'legacy'])
def test_projection_values_are_owned_not_mutation_handles_or_approval_tokens(kind):
    if kind == 'project': result = resolve_builtin_view(model(trace_project()), 'traceability')
    else:
        docs, options = partial_project() if kind == 'partial' else (legacy_documents(), {'source_kind': 'legacy'})
        result = resolve_type_fallback(docs, **options)
    before = result.data; digest = result.sha256; sources = result.source_files
    changed = result.data; changed['records'].clear(); changed['write_authorized'] = True
    result.source_files.clear()
    assert result.data == before and result.source_files == sources and result.sha256 == digest
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(TypeError): BuiltinViewData(before)
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'


def test_builtin_projection_refuses_nonowned_and_tampered_models():
    with pytest.raises(ModelError) as caught: resolve_builtin_view({}, 'traceability')
    assert caught.value.reason == 'document_target_model_required'
    supplied = model(trace_project())
    object.__setattr__(supplied.documents[0], 'content', b'{}')
    with pytest.raises(ModelError): resolve_builtin_view(supplied, 'traceability')


@pytest.mark.parametrize('output_format', ['markdown', 'html'])
@pytest.mark.parametrize('kind', ['specification', 'traceability', 'partial', 'legacy'])
def test_render_entrypoints_use_original_records_without_io_or_template_execution(monkeypatch, output_format, kind):
    observed = []
    original = Emitter.output
    def capture(self, metadata, title, nodes):
        observed.append((deepcopy(metadata), deepcopy(nodes)))
        return original(self, metadata, title, nodes)
    monkeypatch.setattr(Emitter, 'output', capture)
    if kind == 'specification':
        supplied = model([record_value('document')])
        invoke = lambda: render_builtin_view(supplied, kind, output_format=output_format)
    elif kind == 'traceability':
        supplied = model(trace_project()); expected = resolve_builtin_view(supplied, kind)
        invoke = lambda: render_builtin_view(supplied, kind, output_format=output_format)
    else:
        docs, options = partial_project() if kind == 'partial' else (legacy_documents(), {'source_kind': 'legacy'})
        expected = resolve_type_fallback(docs, **options)
        invoke = lambda: render_type_fallback(docs, **options, output_format=output_format)
    def refuse(*args, **kwargs): raise AssertionError('Unexpected file access')
    with no_write_attempts(), monkeypatch.context() as guarded:
        for module, name in ((builtins, 'open'), (io, 'open'), (os, 'open')):
            guarded.setattr(module, name, refuse)
        invoke()
    metadata, nodes = observed[0]
    if kind == 'specification':
        assert nodes[0]['id'] == record_value('document')['id']
    else:
        assert metadata['projection_sha256'] == expected.sha256
        bound = {n['record']['id']: n['record'] for n in nodes if n['type'] == 'record'}
        expected_ids = ([aid(), aid(number=2)] if kind == 'traceability' else expected.data['artifact_ids'])
        assert bound == {identifier: expected.data['records'][identifier]['record'] for identifier in expected_ids}
        if kind == 'traceability':
            annotations = [n['presentation'] for n in nodes if n['type'] == 'record']
            assert annotations[0]['statement'] == trace_project()[0]['statement']
            assert metadata['verification_evaluated'] is False


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_builtin_and_legacy_projection_contracts_work_in_isolated_distributions(tmp_path, mode):
    supplied = model(trace_project()); docs = legacy_documents()
    expected = [resolve_builtin_view(supplied, 'traceability').data,
                resolve_type_fallback(docs, source_kind='legacy').data]
    body = '''import json
from specroad.documents import resolve_builtin_view, resolve_type_fallback
from specroad.changes import TargetModel
from specroad.model.model_manifest import ProjectReadBinding
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'configuration=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'legacy=' + repr([(d.path, d.content) for d in docs]) + '\n'
    body += '''profile=ProfileResource(dict(resources)['profiles/core.json'])
supplied=TargetModel(configuration,ProjectReadBinding('sample','/explicit/provider',(1,2)),
 [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key),
 resource_files=[ModelDocument(p,b) for p,b in resources])
print(json.dumps([resolve_builtin_view(supplied,'traceability').data,
 resolve_type_fallback([ModelDocument(p,b) for p,b in legacy],source_kind='legacy').data],sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
