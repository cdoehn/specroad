"""Public failure boundaries, native historical closure and durable recovery."""
from hashlib import sha256
import io
import json
from pathlib import Path
import pytest
from specroad.cli import main
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.changes.publication_values import PublicationAuthority
from specroad.model.canonical import canonical_json_bytes as jcs
from support.migration_cli import case, invoke, success, planned, verified, restore, argv, REQUIREMENT
from support.migration_transaction import normative
from support.migration_history import evidence_source, historical_contract_host, EVIDENCE, BASELINE
from support.read_only import inventory, no_write_attempts


def test_public_nested_history_roundtrip_preserves_original_bytes_and_old_hashes(tmp_path):
    data=case(tmp_path,files=evidence_source(nested=True));root,source,_,output,_=data
    planning,options=planned(data)
    observations=[];gate=historical_contract_host(observations)
    applied=success(invoke('migrate.apply',options,gates=(gate,)))
    checked=verified(options,applied,gates=(gate,))
    assert observations and checked['verification']['historical']['historical_integrity_verified']
    assert not checked['verification']['historical']['current_context_verified']
    target=normative(root)
    from specroad.migration.legacy_manifest import validate_legacy_manifest
    legacy=validate_legacy_manifest(target,project_id=json.loads(source['specroad.json'])['project_id'])
    originals={p:target[p] for p in legacy.protected_paths}
    _,result=restore(root,output)
    assert result['execution']['result']=='restored'
    historical=result['execution']['historical_findings']
    assert any(item.get('freshness')=='stale' and 'migration_context_unverified' in item.get('reasons',[]) for item in historical)
    assert all((root/p).read_bytes()==raw for p,raw in originals.items())
    assert (root/EVIDENCE).read_bytes()==source[EVIDENCE]
    assert (root/BASELINE).read_bytes()==source[BASELINE]
    from specroad.migration.history import verify_migrated_history
    history=verify_migrated_history(normative(root),project_id=legacy.data['source']['project_id']).data
    assert history['historical_integrity_verified'] and not history['current_context_verified']


@pytest.mark.parametrize('binding',['--expected-plan-sha256','--expected-inputs-sha256','--expected-report-sha256'])
def test_public_apply_rejects_wrong_explicit_bindings_before_backup_or_writer(tmp_path,binding):
    data=case(tmp_path);_,options=planned(data);options[binding]='0'*64
    before=inventory(data[0])
    with no_write_attempts():result=invoke('migrate.apply',options)
    assert result.exit_code==6
    assert inventory(data[0])==before and not list(data[-1].iterdir())


@pytest.mark.parametrize('field',['write_authorized','expected_target_model_root_sha256','loss_report'])
def test_rehashed_planning_report_is_recomputed_before_apply(tmp_path,field):
    data=case(tmp_path);_,options=planned(data);file=data[3]/'migration.json'
    report=json.loads(file.read_bytes());report[field]=True if field=='write_authorized' else {}
    raw=jcs(report);file.write_bytes(raw);options['--expected-report-sha256']=sha256(raw).hexdigest()
    before=inventory(data[0])
    with no_write_attempts():result=invoke('migrate.apply',options)
    assert result.exit_code==6 and result.details['reason']=='migration_report_recomputation_mismatch'
    assert inventory(data[0])==before and not list(data[-1].iterdir())


def test_public_apply_requires_fresh_host_authority_not_flags_or_plan_success(tmp_path):
    data=case(tmp_path);_,options=planned(data);before=inventory(data[0])
    with no_write_attempts(): result=invoke('migrate.apply',options,authorize=False)
    assert result.exit_code==2 and result.details['reason']=='migration_authority_required'
    assert inventory(data[0])==before and not list(data[-1].iterdir())


def test_public_writer_asks_real_host_and_rejection_leaves_original_source(tmp_path):
    data=case(tmp_path);_,options=planned(data);calls=[]
    host=PublicationAuthority('synthetic-denial','1',lambda request:calls.append(request) or False)
    result=invoke('migrate.apply',options,authority=host)
    assert result.exit_code!=0 and calls and normative(data[0])==data[1]
    assert (data[-1]/'source.zip').is_file()


@pytest.mark.parametrize('damage',['changed','missing','new-file'])
def test_source_changed_since_plan_is_not_overwritten(tmp_path,damage):
    data=case(tmp_path);_,options=planned(data);root=data[0]
    if damage=='changed':(root/REQUIREMENT).write_bytes(data[1][REQUIREMENT]+b' ')
    elif damage=='missing':(root/REQUIREMENT).unlink()
    else:(root/'unexpected.json').write_bytes(b'{}')
    before=inventory(root)
    with no_write_attempts():result=invoke('migrate.apply',options)
    assert result.exit_code in (3,6) and inventory(root)==before
    assert not list(data[-1].iterdir())


def test_existing_different_backup_is_never_overwritten(tmp_path):
    data=case(tmp_path);_,options=planned(data);path=data[-1]/'source.zip';path.write_bytes(b'original existing file')
    before=inventory(data[0])
    with no_write_attempts():result=invoke('migrate.apply',options)
    assert result.exit_code==6 and result.details['reason']=='migration_backup_existing_changed'
    assert path.read_bytes()==b'original existing file' and inventory(data[0])==before


@pytest.mark.parametrize('which',['output','backup'])
def test_public_outputs_must_be_outside_project(tmp_path,which):
    data=case(tmp_path);root,source,planning,_,_=data
    target=root/'outside-looking';target.mkdir()
    if which=='output':command='migrate.plan';options={**planning,'--output-root':str(target)}
    else:
        _,options=planned(data);command='migrate.apply';options['--backup-root']=str(target)
    before=inventory(root)
    with no_write_attempts():result=invoke(command,options)
    assert result.exit_code==7 and inventory(root)==before


@pytest.mark.parametrize('kind',['source_version','target_version','from_spec','input_modes'])
def test_unknown_or_ambiguous_inputs_never_become_a_legacy_compatibility_path(tmp_path,kind):
    data=case(tmp_path);root,source,options,_,_=data
    if kind=='source_version':
        value=json.loads(source['specroad.json']);value['schema_version']='0.2.3';(root/'specroad.json').write_bytes(jcs(value))
    elif kind=='target_version':options['--to']='0.2.1'
    elif kind=='from_spec':options['--from-spec']='0.2.5'
    else:
        _,apply=planned(data);options={**apply,**{k:v for k,v in options.items() if k.startswith('--inputs')}}
    before=inventory(root)
    with no_write_attempts():result=invoke('migrate.apply' if kind=='input_modes' else 'migrate.plan',options)
    assert result.exit_code in (2,3,6) and inventory(root)==before


@pytest.mark.parametrize('damage',['target','receipt','backup','archive','extra'])
def test_public_verify_rejects_damaged_actual_state_without_writes(tmp_path,damage):
    data=case(tmp_path);_,options=planned(data);applied=success(invoke('migrate.apply',options));root=data[0]
    verify={**options,'--expected-backup-sha256':applied['backup']['file']['sha256']}
    if damage=='target':(root/REQUIREMENT).write_bytes((root/REQUIREMENT).read_bytes()+b' ')
    elif damage=='receipt':(root/applied['execution']['receipts']['transaction']['path']).write_bytes(b'{}')
    elif damage=='backup':(data[-1]/'source.zip').write_bytes(b'changed')
    elif damage=='archive':
        path=next(p for p in (root/'archive/objects').rglob('*') if p.is_file());path.write_bytes(b'changed')
    else:(root/'unplanned.json').write_bytes(b'{}')
    before=inventory(root)
    with no_write_attempts():result=invoke('migrate.verify',verify)
    assert result.exit_code in (3,6,7) and inventory(root)==before


@pytest.mark.parametrize('damage',['legacy','archive','journal','receipt'])
def test_bundle_creation_cannot_export_damaged_migration_history(tmp_path,damage):
    data=case(tmp_path);_,options=planned(data);applied=success(invoke('migrate.apply',options));root=data[0]
    receipt=root/applied['execution']['receipts']['transaction']['path']
    if damage=='receipt':path=receipt
    elif damage=='journal':path=receipt.with_name('journal.json')
    elif damage=='legacy':path=root/'mappings/legacy-manifest.json'
    else:path=next(p for p in (root/'archive/objects').rglob('*') if p.is_file())
    path.write_bytes(path.read_bytes()+b'changed');before=inventory(root)
    with no_write_attempts():result=invoke('bundle.create',{'--project':str(root),'--scope':'project','--output-root':str(data[3]),'--output':'invalid.zip'})
    assert result.exit_code in (3,6) and inventory(root)==before and not (data[3]/'invalid.zip').exists()


@pytest.mark.parametrize('point',['prepared','effect','committed'])
def test_public_writer_reports_interruption_and_only_explicit_native_recovery_finishes(tmp_path,monkeypatch,point):
    data=case(tmp_path);planning,options=planned(data);root=data[0]
    total=len(planning['planning']['change_plan']['operations'][0]['changes'])
    event={'prepared':'journal:prepared:0','effect':'effect:0','committed':'journal:committed:'+str(total)}[point]
    from specroad.changes import schema_transition as writer
    seen=[]
    def fail(name):
        if name==event:seen.append(name);raise OSError('Synthetic public migration interruption')
    with monkeypatch.context() as patch:
        patch.setattr(writer,'_checkpoint',fail);failed=invoke('migrate.apply',options)
    assert seen==[event] and failed.exit_code!=0 and failed.details['write_state']=='unknown'
    before=inventory(root)
    with no_write_attempts():retry=invoke('migrate.apply',options)
    assert retry.exit_code==5 and retry.details['reason']=='migration_recovery_required' and inventory(root)==before
    from test_migration_transaction_right import recover
    recovered=recover(root,{'transaction_id':options['--transaction-id']})
    assert recovered['cleanup_completed']
    if point=='committed':
        replay=success(invoke('migrate.apply',options));assert replay['execution']['replayed']
    else:assert normative(root)==data[1]


def test_console_json_entrypoint_uses_explicit_project_and_real_plan_file(tmp_path):
    data=case(tmp_path);options={**data[2],'--format':'json'};output=io.StringIO()
    code=main(argv('migrate.plan',options),stdout=output,context_builder=InvocationContextBuilder())
    document=json.loads(output.getvalue())
    assert code==0 and document['result']['planning']['ready']
    assert document['result']['planning']==json.loads((data[3]/'migration.json').read_bytes())
    assert normative(data[0])==data[1]
