"""Verified archived sources use exactly the shared semantic field comparison."""
from dataclasses import FrozenInstanceError
from hashlib import sha256
import shutil

import pytest

from specroad.archive import build_baseline_manifest, compare_baselines
from specroad.graph.comparison import ComparisonInputs
from specroad.graph.relations import SourceRelations
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.model.paths import artifact_path
from specroad.query import ComparisonSourceSnapshot, compare_sources, compare_semantic
from support.domain import domain_value
from support.model import put
from support.portable import build_distribution
from support.processes import run_core, run_python
from support.read_only import inventory, no_write_attempts
from support.records import record_value, ref
from support.relations import aid
from support.scopes import descriptor
from test_baseline_manifest import baseline_inputs
from test_baseline_materialization import restore
from test_baseline_verification import row_for


def stored_comparison(root, *, values=None, number='0', attachment=b'\x00\xff', rule_value=True):
    root.mkdir()
    if values is None: values = [domain_value('requirement', id=aid(), statement='Original', timing='PT2S')]
    inputs = baseline_inputs(values=values, scope=descriptor('project'),
                             attachment=attachment, rule_value=rule_value)
    snapshot = build_baseline_manifest(**inputs, baseline_id=ref('BASE', number))
    record = record_value('baseline', id=ref('BASE', number), **{k:snapshot.data[k] for k in (
        'scope_descriptor', 'manifest', 'model_root_sha256', 'configuration_hash', 'profiles', 'tool_version')})
    for item in snapshot.objects: put(root, item.reference.path, item.content)
    put(root, artifact_path('baseline', record['id'], 'SR'), canonical_json_bytes(record))
    return record, snapshot, values


def capture(root, record, *, form='bytes'):
    reference = canonical_json_bytes(record) if form == 'bytes' else record['id']
    return ComparisonSourceSnapshot(root, kind='baseline', reference=reference)


@pytest.mark.parametrize('left_form,right_form', [('bytes','bytes'), ('bytes','id'), ('id','bytes'), ('id','id')])
def test_baseline_registry_pairings_equal_direct_semantic_comparison(tmp_path, left_form, right_form):
    left = tmp_path / 'left'; a, snapshot, old = stored_comparison(left)
    new = [domain_value('requirement', id=aid(), statement='Changed', timing='PT1S'),
           domain_value('goal', id=aid('goal'))]
    right = tmp_path / 'right'; b, _, _ = stored_comparison(right, values=new, number='1')
    before = inventory(tmp_path)
    with no_write_attempts():
        first, second = capture(left,a,form=left_form), capture(right,b,form=right_form)
        result = compare_sources(first,second,timing_bounds={aid():'maximum'})
        direct = compare_semantic(ComparisonInputs('sample',[SourceRelations(canonical_json_bytes(v)) for v in old]),
            ComparisonInputs('sample',[SourceRelations(canonical_json_bytes(v)) for v in new]),
            before_configuration=first.configuration,after_configuration=second.configuration,
            timing_bounds={aid():'maximum'})
    assert result.data == direct.data and result.sha256 == direct.sha256
    assert {'text_changed','timing_tightened'} <= set(result.data['categories'])
    assert result.data['inventory_delta']['added_ids'] == [aid('goal')]
    evidence = first.binding['baseline']
    assert evidence['model_root_sha256'] == snapshot.model_root_sha256
    assert evidence['record_sha256'] == sha256(canonical_json_bytes(a)).hexdigest()
    assert evidence['snapshot_integrity_verified'] and first.commit_id is None
    assert not evidence['historical_full_validation_verified'] and not evidence['release_authorized']
    assert inventory(tmp_path) == before


def test_baseline_compare_and_independently_materialized_projects_have_the_same_diff(tmp_path):
    left = tmp_path / 'left'; a, _, _ = stored_comparison(left)
    right = tmp_path / 'right'; b, _, _ = stored_comparison(right, number='1',
        values=[domain_value('requirement', id=aid(), statement='Changed', timing='PT1S')])
    first, second = capture(left,a), capture(right,b)
    local_left, local_right = tmp_path / 'local-left', tmp_path / 'local-right'
    for root, record, target, source in ((left,a,local_left,first),(right,b,local_right,second)):
        restore(root,record,target,default_locale=source.configuration.data['default_locale'],
                generated_path=source.configuration.generated_path)
    before = inventory(tmp_path)
    with no_write_attempts():
        actual = compare_baselines(left,a['id'],right,canonical_json_bytes(b),timing_bounds={aid():'maximum'})
        expected = compare_sources(ComparisonSourceSnapshot(local_left), ComparisonSourceSnapshot(local_right),
                                   timing_bounds={aid():'maximum'})
    assert actual.data == expected.data and actual.sha256 == expected.sha256
    assert inventory(tmp_path) == before


def test_owned_baseline_source_survives_removal_without_live_fallback_or_mutable_evidence(tmp_path):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    source = capture(root,record); digest = source.sha256
    source.binding['baseline']['objects'].clear()
    source.inputs.records[0].data['statement'] = 'Caller mutation'
    source.configuration.data['project_id'] = 'Caller mutation'
    shutil.rmtree(root)
    with no_write_attempts(): assert not compare_sources(source,source).data['changed']
    assert source.sha256 == digest
    with pytest.raises(FrozenInstanceError): source.kind = 'local'


def test_baseline_id_reads_only_its_record_and_archive_despite_invalid_current_files(tmp_path):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    put(root,'specroad.json',b'invalid current configuration')
    put(root,artifact_path('requirement',aid(),'SR'),b'invalid current artifact')
    put(root,'.specroad/transactions/current/journal.json',b'current blocker')
    before = inventory(root)
    with no_write_attempts(): source = capture(root,record,form='id')
    assert source.inputs.records[0].data['statement'] == 'Original'
    assert inventory(root) == before


@pytest.mark.parametrize('role', ['artifact','profile','rule','mapping','attachment',
                                  'semantic_configuration','effective_profile','model_manifest'])
def test_missing_baseline_object_never_uses_current_counterpart(tmp_path, role):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    row = row_for(record,role); path = root / row['object_path']; raw = path.read_bytes(); path.unlink()
    if 'source_path' in row: put(root,row['source_path'],raw)
    before = inventory(root)
    with no_write_attempts(), pytest.raises(ModelError) as error: capture(root,record)
    assert error.value.reason == 'snapshot_referenced_object_missing'
    assert inventory(root) == before


@pytest.mark.parametrize('resource', ['rule','attachment'])
def test_changed_uninterpreted_resources_cannot_be_reported_as_an_unchanged_project(tmp_path, resource):
    left = tmp_path / 'left'; a, _, _ = stored_comparison(left)
    right = tmp_path / 'right'; b, _, _ = stored_comparison(right,number='1',
        **({'rule_value':False} if resource == 'rule' else {'attachment':b'changed bytes'}))
    with no_write_attempts(), pytest.raises(ModelError) as error:
        compare_baselines(left,canonical_json_bytes(a),right,canonical_json_bytes(b))
    assert error.value.reason == 'comparison_resource_semantics_unavailable'


def test_baseline_and_local_sources_share_the_registry_when_resource_inventories_match(tmp_path):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root,attachment=None)
    baseline = capture(root,record); target = tmp_path / 'local'
    restore(root,record,target,default_locale=baseline.configuration.data['default_locale'],
            generated_path=baseline.configuration.generated_path)
    with no_write_attempts():
        local = ComparisonSourceSnapshot(target)
        assert not compare_sources(baseline,local).data['changed']
        assert not compare_sources(local,baseline).data['changed']


def test_unobserved_local_payload_bytes_cannot_replace_a_verified_baseline_payload_inventory(tmp_path):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    target = tmp_path / 'local'; restore(root,record,target)
    with no_write_attempts(), pytest.raises(ModelError) as error:
        compare_sources(capture(root,record),ComparisonSourceSnapshot(target))
    assert error.value.reason == 'comparison_resource_semantics_unavailable'


def test_baseline_record_path_identity_cannot_select_a_different_record(tmp_path):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    alias = ref('BASE','1'); put(root,artifact_path('baseline',alias,'SR'),canonical_json_bytes(record))
    with no_write_attempts(), pytest.raises(ModelError) as error:
        ComparisonSourceSnapshot(root,kind='baseline',reference=alias)
    assert error.value.reason == 'comparison_baseline_identity_mismatch'


def test_declared_baseline_root_is_not_a_comparison_integrity_proof(tmp_path):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    record['model_root_sha256'] = '0' * 64
    with no_write_attempts(), pytest.raises(ModelError) as error: capture(root,record)
    assert error.value.reason == 'baseline_model_root_mismatch'


def test_successive_native_baselines_compare_stored_records_and_their_archived_history(tmp_path):
    from base64 import b64decode
    from test_baseline_creation import project, ACTOR, TIME
    from test_baseline_verification_right import document
    from specroad.changes.baselines import prepare_baseline_operation, object_documents
    from specroad.changes._target_materialization import materialize_target
    from specroad.validation import ModelDocument

    model = project(tmp_path / 'original')
    first = prepare_baseline_operation(model,baseline_id=ref('BASE'),name='First',actor=ACTOR,planned_at=TIME)
    goal = model.artifacts[0]; goal['statement'] = 'Changed goal'
    target_model = materialize_target(model,(ModelDocument(artifact_path('goal',goal['id'],'SR'),canonical_json_bytes(goal)),
                                             document(first['record']),*object_documents(first)))
    second = prepare_baseline_operation(target_model,baseline_id=ref('BASE','1'),name='Second',actor=ACTOR,planned_at=TIME)
    roots = [tmp_path / 'first', tmp_path / 'second']
    for root,operation in zip(roots,(first,second)):
        root.mkdir()
        for item in operation['objects']: put(root,item['path'],b64decode(item['bytes_base64']))
    shutil.rmtree(tmp_path / 'original')
    with no_write_attempts():
        result = compare_baselines(roots[0],canonical_json_bytes(first['record']),
                                   roots[1],canonical_json_bytes(second['record'])).data
    assert result['inventory_delta']['added_ids'] == [first['record']['id']]
    assert 'text_changed' in result['categories']
    assert next(r for r in result['changes'] if r['artifact_id']==goal['id'])['fields'][0]['after']=='Changed goal'
    assert not result['full_semantic_validation'] and not result['write_authorized']


@pytest.mark.parametrize('identity', ['',None,42])
def test_expected_project_identity_is_checked_for_baseline_sources(tmp_path, identity):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    # None is explicitly optional; use a foreign valid identity for that case.
    expected = 'foreign' if identity is None else identity
    with no_write_attempts(), pytest.raises(ModelError) as error:
        ComparisonSourceSnapshot(root,kind='baseline',reference=canonical_json_bytes(record),
                                 expected_project_id=expected)
    assert error.value.reason in ('comparison_project_required','project_identity_mismatch')


@pytest.mark.parametrize('mode', ['core','pyz'])
def test_baseline_comparison_runs_without_git_shell_network_or_installation(tmp_path, mode):
    root = tmp_path / 'archive'; record, _, _ = stored_comparison(root)
    code = 'from specroad.archive import compare_baselines\n'
    code += 'result=compare_baselines(' + ','.join((repr(str(root)),repr(record['id']),repr(str(root)),repr(canonical_json_bytes(record)))) + ')\n'
    code += 'assert not result.data["changed"] and not result.data["write_authorized"]\n'
    if mode == 'core': result = run_core(code,tmp_path,capture=True)
    else:
        _, package = build_distribution(tmp_path / 'distribution')
        result = run_python(['-I','-S','-B','-c','import sys;sys.path.insert(0,'+repr(str(package))+')\n'+code],
                            tmp_path,capture=True)
    assert result.returncode == 0,result.stderr
