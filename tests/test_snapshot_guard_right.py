"""Exact backup/currentness/receipt bindings and no recovery authority."""
from pathlib import Path
import json
import pytest
from specroad.changes import schema_transition
from specroad.changes.write_guard_values import validate_transaction,transaction_document
from specroad.changes.receipt_values import transaction_receipt_path
from specroad.model.canonical import canonical_json_bytes as jcs
from support.read_only import inventory,no_write_attempts
from test_snapshot_guard import scenario,FAILURES


@pytest.mark.parametrize('kind',['migration','merge'])
@pytest.mark.parametrize('damage',['backup','source','foreign','marker','owner'])
def test_changed_live_inputs_cannot_finish_a_protected_snapshot(tmp_path,monkeypatch,kind,damage):
    root,source,plan,args,target,apply=scenario(tmp_path,kind);seen=[]
    def alter(point):
        if point!='marker_synced':return
        path=(Path(args['backup_path'] if kind=='migration' else args['backup_descriptor']['path'])
              if damage=='backup' else root/next(p for p in source if p.startswith('spec/'))
              if damage=='source' else root/'foreign.bin' if damage=='foreign'
              else root/'.specroad/write-state/pending.json' if damage=='marker'
              else root/'.specroad/locks/project.json')
        path.write_bytes(b'foreign changed bytes');seen.append(path)
    with monkeypatch.context() as patch:
        patch.setattr(schema_transition,'_checkpoint',alter)
        with pytest.raises(FAILURES):apply(root,plan,args)
    assert len(seen)==1 and seen[0].read_bytes()==b'foreign changed bytes'
    before=inventory(root)
    with no_write_attempts(),pytest.raises(FAILURES):apply(root,plan,args)
    assert inventory(root)==before


@pytest.mark.parametrize('field',['plan','command','project','target','backup','native','operations'])
def test_rehashed_receipt_does_not_replace_full_native_plan_binding(tmp_path,field):
    root,source,plan,args,target,apply=scenario(tmp_path,'migration');apply(root,plan,args)
    write=json.loads((root/transaction_receipt_path(args['transaction_id'])).read_bytes())['write']
    if field=='plan':write['marker']['plan_sha256']='0'*64
    elif field=='command':write['marker']['command_id']='change apply'
    elif field=='project':write['marker']['project_id']='another-project'
    elif field=='target':write['target_inventory'][0]['sha256']='0'*64
    elif field=='backup':write['validation']['backup']['source_files_sha256']='0'*64
    elif field=='native':write['validation']['native']['model_valid']=False
    else:write['operations']=[]
    raw=jcs(transaction_document(write))
    before=inventory(root)
    with no_write_attempts(),pytest.raises(FAILURES):validate_transaction(raw)
    assert inventory(root)==before


@pytest.mark.parametrize('action',['complete','rollback','discard'])
def test_legacy_special_recovery_entrypoint_has_no_write_capability(tmp_path,action):
    sentinel=tmp_path/'original';sentinel.write_bytes(b'unchanged');before=inventory(tmp_path)
    import importlib
    with no_write_attempts(),pytest.raises(ModuleNotFoundError) as caught:
        importlib.import_module('specroad.changes.schema_transition_recovery')
    assert caught.value.name=='specroad.changes.schema_transition_recovery'
    assert inventory(tmp_path)==before
