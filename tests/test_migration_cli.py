"""Public migration and Restore integration, entirely synthetic on real files."""
from hashlib import sha256
import json
import pytest
from specroad.cli.results import thaw
from specroad.cli.result_schemas import validate_result_document
from specroad.bundles.migration_source import verify_source_backup
from support.migration_cli import case, invoke, success, planned, verified, restore, REQUIREMENT
from support.migration_transaction import normative
from support.read_only import inventory, no_write_attempts


@pytest.mark.parametrize('representation',['argv','mapping'])
def test_public_migration_plan_apply_verify_and_restore_roundtrip(tmp_path,representation):
    data=case(tmp_path);root,source,options,output,backup=data
    before=inventory(root)
    planning,apply=planned(data,representation)
    assert inventory(root)==before
    assert planning['planning']['ready'] and planning['planning']['loss_report']['lossless']
    report=json.loads((output/'migration.json').read_bytes())
    assert report==planning['planning']
    applied=success(invoke('migrate.apply',apply,representation))
    assert applied['execution']['write_state']=='committed'
    assert applied['execution']['current_target_verified'] and not applied['execution']['approval_granted']
    actual=verify_source_backup((backup/'source.zip').read_bytes(),
        expected_sha256=applied['backup']['file']['sha256'],
        expected_source_files_sha256=applied['backup']['source_files_sha256'])
    assert actual.files==source
    current=json.loads((root/REQUIREMENT).read_bytes());old=json.loads(source[REQUIREMENT])
    assert current['id']==old['id'] and current['revision']==old['revision']+1
    assert current['statement']==old['statement'] and current['language']=='en' and current['normative_force']=='must'
    assert current['extensions']==old['extensions'] and current['schema_version']=='0.2.0'
    before_verify=inventory(root)
    with no_write_attempts(): checked=verified(apply,applied,representation)
    assert inventory(root)==before_verify and checked['verification']['verified']
    assert checked['verification']['observation']=='stable_live_target'
    assert not checked['verification']['current_readiness_verified']
    target=normative(root)
    bundle,restored=restore(root,output,representation=representation)
    assert normative(root)==target
    assert bundle['manifest']['bundle_model_root_sha256']==checked['verification']['binding']['target_model_root_sha256']
    for path,raw in source.items():
        digest=sha256(raw).hexdigest()
        assert (root/f'archive/objects/{digest[:2]}/{digest}').read_bytes()==raw
    for result in (planning,applied,checked):validate_result_document('migration-command-v1',result)


def test_builtin_provider_executes_independent_full_project_vector():
    from specroad.migration.registry import builtin_registry
    from specroad.migration.execution import verify_vectors,execute_step
    graph=builtin_registry()
    edge=graph.resolve(graph.steps[0].source,graph.steps[0].target)[0]
    vector=edge.transformation.vectors[0]
    original=vector.before
    result=execute_step(edge,original)
    assert result==vector.after, {
        path: (result['files'].get(path), vector.after['files'].get(path))
        for path in set(result['files']) | set(vector.after['files'])
        if result['files'].get(path) != vector.after['files'].get(path)}
    assert original==vector.before
    verify_vectors(graph)
    assert not edge.step.reversible and edge.step.backward is None


def test_public_apply_can_plan_from_explicit_inputs_and_is_idempotent(tmp_path):
    data=case(tmp_path);root,source,options,output,backup=data
    inputs={k:v for k,v in options.items() if k not in ('--output-root','--output')}
    inputs.update({'--backup-root':str(backup),'--backup':'source.zip','--transaction-id':'synthetic-direct'})
    applied=success(invoke('migrate.apply',inputs))
    assert applied['execution']['write_state']=='committed'
    before=inventory(root);backup_before=inventory(backup)
    again=success(invoke('migrate.apply',{'--project':str(root),'--to':'0.2.0'}))
    assert again['execution']['status']=='not_required' and again['execution']['no_change']
    assert inventory(root)==before and inventory(backup)==backup_before


def test_public_request_replay_uses_native_completed_journal(tmp_path):
    data=case(tmp_path);_,options=planned(data)
    first=success(invoke('migrate.apply',options));before=inventory(data[0])
    again=success(invoke('migrate.apply',options))
    assert again['execution']['replayed'] and not again['execution']['current_target_verified']
    assert again['execution']['journal_sha256']==first['execution']['journal_sha256']
    assert inventory(data[0])==before


def test_incomplete_explicit_mapping_yields_an_honest_non_executable_plan(tmp_path):
    data=case(tmp_path);root,source,options,output,backup=data
    path=data[2]['--inputs-root']+'/mapping.json'
    from pathlib import Path
    mapping=json.loads(Path(path).read_bytes());mapping['requirement_mappings']=[]
    Path(path).write_text(json.dumps(mapping))
    before=inventory(root);result=success(invoke('migrate.plan',options))
    assert not result['planning']['ready'] and result['planning']['change_plan'] is None
    assert any(b['reason']=='requirement_mapping_required' for b in result['planning']['blockers'])
    assert inventory(root)==before and not list(backup.iterdir())
