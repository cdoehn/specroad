"""Complete Release obligations and variant failures over native source bytes."""
from hashlib import sha256
import json

import pytest

from specroad.graph.closure_inputs import ClosureBindings, artifact_node, resource_node
from specroad.model.attachments import AttachmentDescriptor
from specroad.model.canonical import canonical_json_bytes
from specroad.model.domain_schemas import DOMAIN_TYPES
from specroad.model.errors import ModelError
from specroad.planning import resolve_release_scope
from specroad.storage.domain_artifact import DomainArtifact
from specroad.storage.record_artifact import RecordArtifact
from specroad.validation import ModelDocument
from support.closure import observe, slot, subject
from support.domain import domain_value
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import no_write_attempts
from support.records import record_value
from support.relations import aid, edge
from support.targets import model
from test_release_scope import bindings_for, release_values, resolve
from test_verification_required_checks import condition


def value(kind, number=1, **changes):
    factory = domain_value if kind in DOMAIN_TYPES else record_value
    if kind == 'configuration': changes.setdefault('name', 'Configuration ' + str(number))
    return factory(kind, id=aid(kind, number), **changes)


def release_bridge(first):
    return [value('release', relations=[edge('derived_from', aid('source', 9), number=90)]),
            value('source', 9, relations=[edge('references', first['id'], number=91)])]


def rich_project():
    values = release_values()
    values[0]['relations'] = [edge('derived_from', aid('source', 1), number=12)]
    values[7]['relations'].extend([
        edge('verified_by', aid('verification', 1), number=13),
        edge('derived_from', aid('source', 1), number=14)])
    raw = b'owned synthetic verification attachment\n'
    attachment = AttachmentDescriptor(path='attachments/release.txt', media_type='text/plain',
                                      size=len(raw), sha256=sha256(raw).hexdigest())
    additions = [
        value('document', relations=[dict(edge('contains', aid('section', 1), number=15), position=0)]),
        value('section', relations=[dict(edge('contains', aid('content_block', 1), number=16), position=0)]),
        value('content_block', block_kind='artifact_ref', payload={'render_mode': 'summary'},
              relations=[edge('references', aid('requirement', 4), number=17)]),
        value('source', relations=[edge('references', aid('document', 1), number=26)]),
        value('verification', subjects=[aid('requirement', 1)], evidence_slots=[slot(aid('test', 1))]),
        value('test', relations=[edge('produces', aid('evidence', 1), number=18),
                                edge('references', aid('issue', 1), number=25)]),
        value('evidence', subjects=[subject(aid('requirement', 3))], attachments=[attachment.data]),
        value('requirement', 3, relations=[
            edge('depends_on', aid('component', 3), number=19),
            edge('mitigates', aid('risk', 1), number=20),
            edge('allocated_to', aid('interface', 1), number=21),
            edge('addresses', aid('goal', 1), number=22),
            edge('implemented_by', aid('task', 4), number=23),
            edge('duplicates', aid('requirement', 4), number=24)]),
        value('requirement', 4), value('component', 3, maturity='retired'),
        value('risk'), value('goal'),
        value('interface', source_component=aid('component', 1), target_component=aid('component', 2)),
        value('task', 4),
        value('relation_review', relation_id=edge(number=7)['relation_id']),
        value('issue')]
    files = [ModelDocument(attachment.path, raw)]
    for kind in ('rule', 'mapping'):
        files.append(ModelDocument(kind + 's/release.json', canonical_json_bytes({
            'schema_version': '0.2.0', kind + '_id': 'release', kind + '_version': '1'})))
    supplied = model([*values, *additions], attachments=[attachment], resource_files=files)
    bound = bindings_for(supplied)
    resources = {r.kind: r.resource_id for r in bound.inventory.resources}
    bound = observe(bound.inventory, uses={
        artifact_node(aid('component', 1)): (resource_node(resources['profile']),),
        resource_node(resources['profile']): (resource_node(resources['rule']),),
        resource_node(resources['rule']): (resource_node(resources['mapping']),)},
        reviews={edge(number=7)['relation_id']: (aid('relation_review', 1),)},
        attachments={resources['attachment']: attachment})
    return supplied, bound


def test_release_closure_includes_indirect_subjects_slots_reviews_and_resource_chains():
    supplied, bound = rich_project()
    with no_write_attempts():
        data = resolve_release_scope(supplied, aid('release', 1), scope_bindings=bound).data
    seeds = {aid('release', 1), aid('milestone', 1), aid('requirement', 1),
             aid('capability', 1), *(aid('task', n) for n in (1, 2, 3))}
    indirect = {aid(kind, 1) for kind in ('document', 'section', 'content_block', 'source',
        'verification', 'test', 'evidence', 'risk', 'goal', 'interface', 'relation_review', 'issue')}
    indirect.update({aid('requirement', 3), aid('requirement', 4), aid('task', 4),
                     *(aid('component', n) for n in (1, 2, 3))})
    assert data['seed_artifact_ids'] == sorted(seeds)
    assert data['artifact_ids'] == sorted(seeds | indirect)
    assert data['resource_ids'] == sorted(r.resource_id for r in bound.inventory.resources)
    assert {(r['source_id'], r['target_id']) for r in data['external_required_dependencies']} == {
        (aid('requirement', 1), aid('component', 1)),
        (aid('component', 1), aid('component', 2)),
        (aid('requirement', 3), aid('component', 3))}
    assert data['scope_resolution']['boundary_references'] == []
    assert data['scope_applicability_complete'] and data['unresolved_applicability'] == []
    assert {r['artifact_id'] for r in data['applicability']} == seeds | indirect
    assert all(r['status'] == 'applicable' for r in data['applicability'])
    assert not data['release_readiness_evaluated'] and not data['verification_evaluated']
    assert not data['approval_granted'] and not data['full_validation_passed']


STRONG_EDGES = [('addresses', 'requirement', 'goal'), ('refines', 'requirement', 'requirement'),
    ('derived_from', 'requirement', 'source'), ('depends_on', 'requirement', 'requirement'),
    ('constrains', 'requirement', 'component'), ('allocated_to', 'requirement', 'interface'),
    ('implemented_by', 'requirement', 'task'), ('verified_by', 'requirement', 'test'),
    ('produces', 'test', 'evidence'), ('mitigates', 'requirement', 'risk'),
    ('scheduled_for', 'requirement', 'release'), ('part_of', 'task', 'release'),
    ('supersedes', 'requirement', 'requirement'), ('contains', 'document', 'section'),
    ('references', 'source', 'requirement')]


@pytest.mark.parametrize('kind,source_type,target_type', STRONG_EDGES, ids=[e[0] for e in STRONG_EDGES])
@pytest.mark.parametrize('excluded', [False, True], ids=['included', 'variant-conflict'])
def test_every_strong_edge_is_mandatory_beyond_release_seeds(kind, source_type, target_type, excluded):
    link = edge(kind, aid(target_type, 2), number=2)
    if kind == 'contains': link['position'] = 0
    first = value(source_type, relations=[link])
    target = value(target_type, 2)
    if target_type == 'evidence': target['subjects'] = [subject(first['id'])]
    if excluded: target['applicability'] = condition('windows')
    supplied = model([*release_bridge(first), first, target, value('configuration')])
    with no_write_attempts():
        if excluded:
            with pytest.raises(ModelError) as caught:
                resolve(supplied, configuration_id=aid('configuration', 1))
            d = caught.value.diagnostic()
            assert d['code'] == 'SRV141' and d['exit_code'] == 3
            assert (d['source_id'], d['target_id'], d['relation_id'], d['pointer']) == (
                first['id'], target['id'], link['relation_id'], '/relations/0/target')
            assert d['configuration_id'] == aid('configuration', 1)
        else:
            data = resolve(supplied, configuration_id=aid('configuration', 1)).data
            assert data['seed_artifact_ids'] == [aid('release', 1)]
            assert data['artifact_ids'] == sorted([aid('release', 1), aid('source', 9), first['id'], target['id']])
            assert data['scope_applicability_complete'] and data['unresolved_applicability'] == []


@pytest.mark.parametrize('dependency', ['subject', 'slot', 'current-review', 'closed-weak'])
def test_variant_conflicts_on_non_strong_obligations_retain_exact_diagnostics(dependency):
    relation_id = None
    if dependency == 'subject':
        first = value('evidence', subjects=[subject(aid('requirement', 2))])
        target = value('requirement', 2); pointer = '/subjects/0/artifact_id'
    elif dependency == 'slot':
        first = value('verification', subjects=[aid('release', 1)], evidence_slots=[slot(aid('test', 2))])
        target = value('test', 2); pointer = '/evidence_slots/0/test_id'
    elif dependency == 'current-review':
        relation_id = edge(number=2)['relation_id']
        first = value('requirement', relations=[edge('depends_on', aid('release', 1), number=2)])
        target = value('relation_review', 2, relation_id=relation_id)
        pointer = '/current_reviews/' + relation_id + '/0'
    else:
        relation_id = edge(number=2)['relation_id']
        first = value('requirement', relations=[edge('conflicts_with', aid('requirement', 2), number=2)])
        target = value('requirement', 2); pointer = '/relations/0/target'
    target['applicability'] = condition('windows')
    supplied = model([*release_bridge(first), first, target, value('configuration')])
    bound = bindings_for(supplied)
    if dependency == 'current-review':
        bound = observe(bound.inventory, reviews={relation_id: (target['id'],)})
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_release_scope(supplied, aid('release', 1), scope_bindings=bound,
                              configuration_id=aid('configuration', 1))
    d = caught.value.diagnostic()
    assert d['code'] == 'SRV141' and d['severity'] == 'error' and d['exit_code'] == 3
    assert (d['source_id'], d['target_id'], d['relation_id'], d['pointer']) == (
        first['id'], target['id'], relation_id, pointer)
    assert d['configuration_id'] == aid('configuration', 1)


@pytest.mark.parametrize('kind', ['release', 'requirement', 'component'])
@pytest.mark.parametrize('expression', [condition('windows'),
    {'language': 'srx', 'version': '1.0', 'expression': {'op': 'literal', 'value': True}},
    {'language': 'srx', 'version': '1.0', 'expression': {'op': 'literal', 'value': False}}],
    ids=['configuration-dependent', 'constant-true', 'constant-false'])
def test_unselected_configuration_never_turns_conditional_members_into_unconditional_ones(kind, expression):
    values = release_values()
    next(v for v in values if v['id'] == aid(kind, 1))['applicability'] = expression
    supplied = model(values)
    with no_write_attempts(): data = resolve(supplied).data
    assert aid(kind, 1) in data['artifact_ids']
    assert data['unresolved_applicability'] == [aid(kind, 1)]
    row, = [r for r in data['applicability'] if r['artifact_id'] == aid(kind, 1)]
    assert row['status'] == 'potentially_applicable' and row['reason'] == 'no_configuration'
    assert row['configuration_id'] is None and row['configuration_sha256'] is None
    assert row['source_sha256'] == next(r['source_sha256'] for r in data['artifacts'] if r['artifact_id'] == aid(kind, 1))
    assert not data['scope_applicability_complete'] and not data['applicability_evaluated']
    assert not data['release_readiness_evaluated'] and not data['approval_granted']


def test_inherited_configuration_binds_parent_bytes_and_filters_before_closure():
    values = release_values(); values[4]['applicability'] = condition('windows')
    values.extend([value('configuration'), value('configuration', 2,
        parent=aid('configuration', 1), dimensions=[], selection={})])
    linux = resolve(model(values), configuration_id=aid('configuration', 2))
    values[-2]['selection']['platform'] = 'windows'
    windows = resolve(model(values), configuration_id=aid('configuration', 2))
    assert aid('task', 1) not in linux.data['artifact_ids']
    assert aid('task', 1) in windows.data['seed_artifact_ids']
    assert linux.data['configuration_hash'] != windows.data['configuration_hash']
    assert linux.sha256 != windows.sha256
    row, = [r for r in windows.data['applicability'] if r['artifact_id'] == aid('task', 1)]
    assert row['status'] == 'applicable' and row['reason'] == 'condition_true'
    assert row['configuration_id'] == aid('configuration', 2) and row['configuration_sha256']
    values[-2]['title'] = 'Revised configuration context with identical selection'
    changed = resolve(model(values), configuration_id=aid('configuration', 2))
    assert changed.data['artifact_ids'] == windows.data['artifact_ids']
    assert changed.data['configuration_hash'] != windows.data['configuration_hash']


@pytest.mark.parametrize('kind,field', [('component', 'responsibility'), ('test', 'oracle'),
    ('source', 'source_kind'), ('document', 'purpose'), ('risk', 'probability')])
def test_reached_non_planning_members_are_validated_by_their_native_schemas(kind, field):
    bad = value(kind); del bad[field]
    supplied = model([*release_bridge(bad), bad])
    document = next(d for d in supplied.documents if json.loads(d.content)['id'] == bad['id'])
    native = DomainArtifact if kind in DOMAIN_TYPES else RecordArtifact
    with pytest.raises(ModelError) as expected:
        native(document.content, path=document.path)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve(supplied)
    assert caught.value.diagnostic() == expected.value.diagnostic()
    assert caught.value.path == document.path


def test_unreached_non_planning_member_does_not_turn_scope_validation_into_full_validation():
    other = value('component', 9); del other['responsibility']
    with no_write_attempts(): data = resolve(model([value('release'), other])).data
    assert data['artifact_ids'] == [aid('release', 1)] and not data['full_validation_passed']


@pytest.mark.parametrize('configured', [False, True])
def test_invalid_applicability_is_rejected_even_without_configuration(configured):
    bad = value('component', applicability={'language': 'srx', 'version': '1.0',
        'expression': {'op': 'has_relation', 'direction': 'outgoing', 'types': '*'}})
    supplied = model([*release_bridge(bad), bad, value('configuration')])
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve(supplied, configuration_id=aid('configuration', 1) if configured else None)
    assert caught.value.reason == 'invalid_applicability'
    assert caught.value.__cause__.reason == 'applicability_graph_forbidden'
    assert caught.value.pointer.startswith('/applicability')


@pytest.mark.parametrize('missing', ['resource-use', 'attachment'])
def test_incomplete_indirect_resource_observations_are_not_successful_shorter_scopes(missing):
    supplied, bound = rich_project()
    uses = dict(bound.uses); attachments = dict(bound.attachments)
    if missing == 'resource-use':
        identity = next(r.resource_id for r in bound.inventory.resources if r.kind == 'rule')
        uses.pop(resource_node(identity))
    else: attachments.clear()
    incomplete = ClosureBindings(bound.inventory, uses=uses,
        current_reviews=dict(bound.current_reviews), attachments=attachments)
    with no_write_attempts(), pytest.raises(ModelError) as caught:
        resolve_release_scope(supplied, aid('release', 1), scope_bindings=incomplete)
    assert caught.value.reason == {'resource-use': 'closure_usage_observation_missing',
                                  'attachment': 'closure_attachment_observation_missing'}[missing]


def test_applicability_report_is_sorted_owned_and_rebound_to_changed_member_bytes():
    values = release_values()
    for index in (0, 7, 10): values[index]['applicability'] = condition('linux')
    report = resolve(model(values))
    assert report.data['unresolved_applicability'] == sorted([
        aid('release', 1), aid('requirement', 1), aid('component', 2)])
    assert resolve(model(list(reversed(values)))).data == report.data
    detached = report.data; detached['applicability'].clear(); detached['unresolved_applicability'].clear()
    assert len(report.data['applicability']) == 9 and len(report.data['unresolved_applicability']) == 3
    values[10]['description'] = 'Changed external dependency'
    revised = resolve(model(values))
    assert report.sha256 != revised.sha256
    first = next(r for r in report.data['applicability'] if r['artifact_id'] == aid('component', 2))
    second = next(r for r in revised.data['applicability'] if r['artifact_id'] == aid('component', 2))
    assert first['source_sha256'] != second['source_sha256']


@pytest.mark.parametrize('mode', ['core', 'pyz'])
def test_unresolved_and_invalid_members_have_identical_isolated_runtime_contracts(tmp_path, mode):
    values = release_values(); values[10]['applicability'] = condition('windows')
    supplied = model(values); expected = resolve(supplied).data
    body = '''import json, os, sys
from specroad.changes import TargetModel
from specroad.graph.closure_inputs import ClosureBindings, artifact_node, resource_node
from specroad.graph.relations import SourceRelations
from specroad.graph.scope_inputs import ScopeResource, ScopeSeedInputs
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.errors import ModelError
from specroad.planning import resolve_release_scope
from specroad.profiles import ProfileResource, compose_profiles
from specroad.validation import ModelDocument
'''
    body += 'configuration=' + repr(supplied.configuration_bytes) + '\n'
    body += 'documents=' + repr([(d.path, d.content) for d in supplied.documents]) + '\n'
    body += 'resources=' + repr([(d.path, d.content) for d in supplied.resource_files]) + '\n'
    body += 'release_id=' + repr(aid('release', 1)) + '\n'
    body += '''profile=ProfileResource(dict(resources)['profiles/core.json'])
def resolve(documents):
 supplied=TargetModel(configuration,ProjectReadBinding('sample','/explicit/provider',(1,2)),
  [ModelDocument(p,b) for p,b in documents],profile=compose_profiles([profile],core_key=profile.key),
  resource_files=[ModelDocument(p,b) for p,b in resources])
 observed=[ScopeResource('fixture-resource:'+str(i),r.data['kind'],r.data['sha256'],
  r.data.get('version') if r.data['kind'] in ('profile','rule','mapping') else None,
  active=r.data['kind']=='profile') for i,r in enumerate(supplied.resources)]
 inputs=ScopeSeedInputs(supplied.configuration,
  [SourceRelations(d.content,path=d.path) for d in supplied.documents],observed)
 uses={artifact_node(r.identity.id):() for r in inputs.records}
 uses.update({resource_node(r.resource_id):() for r in inputs.resources})
 reviews={r.relation.identity.id:() for r in inputs.references.relations}
 return resolve_release_scope(supplied,release_id,
  scope_bindings=ClosureBindings(inputs,uses=uses,current_reviews=reviews)).data
blocked=[]
def audit(event,args):
 if event.startswith(('socket.','subprocess.')) or event in ('os.system','os.remove','os.rename','os.mkdir'):
  blocked.append(event);raise AssertionError(event)
 if event=='open' and isinstance(args[2],int) and args[2]&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND):
  blocked.append(event);raise AssertionError(event)
sys.addaudithook(audit)
report=resolve(documents)
changed=[]
for path,raw in documents:
 v=json.loads(raw)
 if v['artifact_type']=='component': v.pop('responsibility')
 changed.append((path,json.dumps(v).encode()))
try: resolve(changed)
except ModelError as exc: failure=exc.diagnostic()
else: raise AssertionError('Invalid member accepted')
assert not blocked
print(json.dumps({'report':report,'failure':failure},sort_keys=True))
'''
    if mode == 'core': result = run_core(body, tmp_path, capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I', '-S', '-B', '-c',
            'import sys;sys.path.insert(0,' + repr(str(package)) + ')\n' + body], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    result_data = json.loads(result.stdout)
    assert result_data['report'] == expected
    for v in values:
        if v['artifact_type'] == 'component': v.pop('responsibility')
    with pytest.raises(ModelError) as caught: resolve(model(values))
    assert result_data['failure'] == caught.value.diagnostic()
