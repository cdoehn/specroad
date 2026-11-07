"""17.h.W: complete source-bound single decisions and the native machine CLI."""
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from specroad.merge import (build_merge_conflicts, parse_resolution_value,
    parse_merge_resolutions, read_merge_resolutions, resolve_merge_conflict)
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256 as digest
from specroad.model.errors import ModelError
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.results import thaw
from specroad.cli.result_schemas import validate_result_document
from support.merge_lifecycle import artifact, bound_records, changed
from support.merge_relations import bound_relations, edge, history_for
from support.merge_resolution import ACTOR, WHEN, PLAN_ID, ROLES, case, request_files, argv
from support.read_only import inventory
from support.languages import small_restore_registry
from test_merge_inventory import bind_files
from test_merge_sources import read_only_sources
from test_project_bundle import project


@pytest.fixture(scope='module')
def original(tmp_path_factory):
    return project(tmp_path_factory.mktemp('resolution-seed') / 'project',
                   language_registry=small_restore_registry()).raw


@pytest.fixture
def bound(tmp_path, original):
    return case(tmp_path / 'sources', original)


def resolve(bound, *, pointer='/title', plan=None, **decision):
    sources, history, original = bound
    plan = original if plan is None else plan
    catalogue = original.data
    row = next(row for row in catalogue['conflicts'] if row['pointer'] == pointer)
    return resolve_merge_conflict(plan.canonical_bytes, sources, history=history,
        expected_plan_sha256=plan.sha256, conflict_id=row['conflict_id'],
        actor=ACTOR, resolved_at=WHEN, **decision)


@pytest.mark.parametrize('role', ROLES)
def test_take_binds_exact_one_original_with_explicit_actor_and_time(bound, tmp_path, role):
    sources, history, before = bound
    snapshot = inventory(tmp_path)
    with read_only_sources():
        result = resolve(bound, take=role)
    data = result.data
    assert jcs(data['catalogue']) == before.canonical_bytes
    assert data['catalogue_sha256'] == before.sha256
    event, = data['resolutions']
    row = next(r for r in before.conflicts if r['pointer'] == '/title')
    assert event['choice'] == {'kind': 'take', 'role': role}
    assert event['value'] == row['values'][role]
    assert event['actor'] == ACTOR and event['resolved_at'] == WHEN
    assert event['previous_sha256'] == before.sha256
    assert event['resolution_id'] == 'MR-' + digest({k:v for k,v in event.items() if k != 'resolution_id'})
    assert data['targets'] == [{'conflict_id': row['conflict_id'], 'identity': row['identity'],
                               'pointer': '/title', 'value': row['values'][role]}]
    assert data['unresolved_conflict_ids'] == [r['conflict_id'] for r in before.conflicts if r != row]
    assert data['pending_gates'] == ['audited_resolution','merge_metadata','target_validation','publication']
    assert not result.ready and not result.write_authorized and data['approval_granted'] is False
    reread = read_merge_resolutions(result.canonical_bytes,sources,history=history,expected_plan_sha256=result.sha256)
    assert reread.canonical_bytes == result.canonical_bytes
    assert inventory(tmp_path) == snapshot


@pytest.mark.parametrize('value', [None, False, 0, 'explicit', [1, None], {'a/b~c': {'x': True}}])
def test_explicit_json_value_is_a_declarative_candidate_with_target_gate_pending(bound, value):
    # Semantic validity of the eventual project is deliberately a later mandatory gate.
    result = resolve(bound, pointer='/extensions/vendor.resolve/item', value=value)
    event, = result.data['resolutions']
    assert event['choice'] == {'kind':'value','value':value}
    assert event['value'] == {'state':'present','domain':'json-v1','value':value}
    assert result.data['targets'][0]['value'] == event['value']
    assert 'target_validation' in result.data['pending_gates']


def test_second_decision_preserves_original_catalogue_first_event_and_other_target(bound):
    first = resolve(bound,take='ours')
    second = resolve(bound,plan=first,pointer='/extensions/vendor.resolve/item',value=42)
    data = second.data
    assert data['catalogue'] == first.data['catalogue']
    assert jcs(data['resolutions'][0]) == jcs(first.data['resolutions'][0])
    assert data['resolutions'][1]['previous_sha256'] == digest(data['resolutions'][0])
    assert first.data['targets'][0] in data['targets']
    assert data['resolutions_sha256'] == digest(data['resolutions'])
    assert data['unresolved_conflict_ids'] == []
    assert data['pending_gates'] == ['merge_metadata','target_validation','publication']
    assert not second.ready and not second.write_authorized


def test_missing_member_cannot_be_selected_but_null_is_an_explicit_value(tmp_path, original):
    path, value = artifact(original)
    sources, history = bound_records(tmp_path,original,path,[
        changed(value,extensions={'vendor.resolve':{'x':1}}),
        changed(value,extensions={'vendor.resolve':{}}),
        changed(value,extensions={'vendor.resolve':{'x':None}})])
    plan = build_merge_conflicts(sources,plan_id=PLAN_ID,history=history)
    bound = sources, history, plan
    with pytest.raises(ModelError, match='merge_resolution_not_allowed'):
        resolve(bound,pointer='/extensions/vendor.resolve/x',take='ours')
    result = resolve(bound,pointer='/extensions/vendor.resolve/x',value=None)
    assert result.data['targets'][0]['value'] == {'state':'present','domain':'json-v1','value':None}


def test_relation_resolution_keeps_owner_identity_other_fields_and_impact(tmp_path, original):
    versions = [edge(rationale=role,extensions={'vendor.resolve': {'x':index}})
                for index,role in enumerate(ROLES)]
    sources, history, owner = bound_relations(tmp_path,original,[[value] for value in versions])
    plan = build_merge_conflicts(sources,plan_id=PLAN_ID,history=history)
    result = resolve((sources,history,plan),pointer='/relation/rationale',take='theirs')
    assert result.data['catalogue'] == plan.data
    target, = result.data['targets']
    assert target['identity'] == {'kind':'relation','id':versions[0]['relation_id'],'version':None}
    assert target['pointer'] == '/relation/rationale' and target['value']['value'] == 'theirs'
    assert len(result.data['unresolved_conflict_ids']) == 1
    assert plan.conflicts[0]['artifact_ids'] == [owner]


def test_binary_take_keeps_exact_original_hash_and_size_without_writing(tmp_path, original):
    from hashlib import sha256
    import json
    path = next(name for name in original if name.startswith('attachments/'))
    versions = []
    for raw in (b'base', b'', b'theirs'):
        files = dict(original); files[path] = raw
        # All fixture descriptors remain bound to real bytes. Recorded evidence
        # changes stay protected conflicts; selecting the attachment cannot bypass them.
        for name, content in list(files.items()):
            if not name.startswith('spec/'):
                continue
            value = json.loads(content)
            def update(item):
                if type(item) is dict:
                    if item.get('path') == path and 'sha256' in item:
                        item['sha256'] = sha256(raw).hexdigest()
                        if 'size' in item: item['size'] = len(raw)
                    for child in item.values(): update(child)
                elif type(item) is list:
                    for child in item: update(child)
            update(value); files[name] = jcs(value)
        versions.append(files)
    sources = bind_files(tmp_path,versions)
    history = history_for(sources)
    plan = build_merge_conflicts(sources,plan_id=PLAN_ID,history=history)
    row = next(row for row in plan.conflicts if row['identity']['kind'] == 'attachment')
    args = dict(history=history, expected_plan_sha256=plan.sha256, conflict_id=row['conflict_id'],
                actor=ACTOR, resolved_at=WHEN)
    result = resolve_merge_conflict(plan.canonical_bytes,sources,**args,take='ours')
    assert result.data['targets'][0]['value'] == {'state':'present','domain':'bytes-v1','size':0,'sha256':sha256(b'').hexdigest()}
    assert result.data['unresolved_conflict_ids']
    with pytest.raises(ModelError, match='merge_resolution_not_allowed'):
        resolve_merge_conflict(plan.canonical_bytes,sources,**args,value='fake-bytes')


def test_collections_keep_whole_stable_keyed_value(tmp_path, original):
    from support.records import record_value
    from specroad.model.paths import artifact_path
    value = record_value('configuration'); path = artifact_path('configuration',value['id'],'SR')
    variants = [value,deepcopy(value),deepcopy(value)]
    variants[1]['dimensions'] = []; variants[1]['selection'] = {}
    variants[2]['dimensions'][0]['default'] = 'windows'
    sources,history = bound_records(tmp_path,original,path,variants)
    plan = build_merge_conflicts(sources,plan_id=PLAN_ID,history=history)
    result = resolve((sources,history,plan),pointer='/dimensions',take='theirs')
    assert plan.conflicts[0]['element_keys'] == ['platform']
    assert result.data['targets'][0]['pointer'] == '/dimensions'
    assert result.data['targets'][0]['value']['value'] == variants[2]['dimensions']
    assert result.data['catalogue'] == plan.data


@pytest.mark.parametrize('decision', ['ours','theirs','base','value'])
def test_native_cli_and_structured_request_produce_identical_bound_plan(bound, tmp_path, decision):
    sources,history,plan = bound
    request = request_files(tmp_path/'plans',sources,history,plan)
    options = request['options']
    if decision == 'value':
        del options['--take']; options['--value'] = '"resolved title"'
    else:
        options['--take'] = decision
    snapshot = inventory(tmp_path)
    first = dispatch_result(argv(request))
    second = execute_request(request).result
    assert first.exit_code == 0 and second.exit_code == 0
    data = thaw(first.result)
    assert data == thaw(second.result)
    validate_result_document('merge-resolve-command-v1',data)
    assert data['source_validation'] == 'revalidated'
    result = parse_merge_resolutions(jcs(data['plan']))
    assert result.sha256 == data['plan_sha256']
    assert inventory(tmp_path) == snapshot
    output = tmp_path/'result-plan.json'; output.write_bytes(result.canonical_bytes)
    inspected = dispatch_result(['merge','conflicts',str(output),'--format','json'])
    assert inspected.exit_code == 0
    assert thaw(inspected.result)['source_validation'] == 'not_revalidated'
    assert thaw(inspected.result)['plan'] == result.data
    validate_result_document('merge-conflicts-command-v1',thaw(inspected.result))


def test_result_owns_audit_and_value_and_is_not_truthy_authority(bound):
    value = {'x':[1]}
    result = resolve(bound,value=value)
    value['x'].clear(); result.data['resolutions'].clear(); result.data['catalogue'].clear()
    assert result.data['resolutions'][0]['choice']['value'] == {'x':[1]}
    assert parse_merge_resolutions(result.canonical_bytes).sha256 == result.sha256
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'
    with pytest.raises(TypeError): bool(result)


@pytest.mark.parametrize('raw, value', [(b'null',None),(b'false',False),(b'1',1),
    (b'"text"','text'),(b'[null,1]',[None,1]),(b'{"nested":{"x":1}}',{'nested':{'x':1}})])
def test_strict_json_value_reader_preserves_native_value_domains(raw, value):
    assert parse_resolution_value(raw) == value
