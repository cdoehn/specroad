"""Real native migration writes, immutable history and refusal boundaries."""
import json
from hashlib import sha256
import pytest
from tests.support.migration_transaction import setup, apply, normative, journal_path
from tests.support.migration_plans import planned_files, vector_source
from tests.support.reference01 import minimal, artifact, put
from specroad.model.errors import ModelError
from specroad.changes.execution_values import ChangeExecutionError
from specroad.security import SafetyViolation
from specroad.changes.schema_transition_values import TransitionJournal
from specroad.changes.receipt_values import transaction_receipt_path
from tests.support.transition_journal import assert_owned_plan

FAILURES = (ModelError, ChangeExecutionError, SafetyViolation, OSError)


def test_native_complete_target_and_exact_revisions(tmp_path):
    root, source, plan, args = setup(tmp_path)
    expected = planned_files(source, plan)
    result = apply(root, plan, args)
    assert result['write_state'] == 'committed' and result['current_target_verified']
    assert result['target_model_root_sha256'] == plan.data['expected_result']['model_root_sha256']
    assert normative(root) == expected
    for path, raw in source.items():
        if path.startswith('spec/'):
            old, new = json.loads(raw), json.loads((root/path).read_bytes())
            assert new['revision'] == old['revision'] + 1
            assert new['created_at'] == old['created_at'] and new['created_by'] == old['created_by']
            assert new['updated_by'] == plan.data['actor']
    assert json.loads((root/'mappings/legacy-manifest.json').read_bytes())['mapping_version'] == '1.0.0'
    assert not journal_path(root,args).exists()
    assert result['backup']['sha256'] == args['backup_sha256']
    assert not result['approval_granted']
    archived = (root/transaction_receipt_path(args['transaction_id'])).with_name('journal.json')
    assert_owned_plan(TransitionJournal(archived.read_bytes()), plan.source_bytes)


def test_every_source_original_archived_exactly(tmp_path):
    root, source, plan, args = setup(tmp_path)
    apply(root, plan, args)
    for path, raw in source.items():
        digest = sha256(raw).hexdigest()
        assert (root/f'archive/objects/{digest[:2]}/{digest}').read_bytes() == raw


def test_staging_never_installs_final_state_early(tmp_path, monkeypatch):
    from specroad.changes import schema_transition as writer
    root, source, plan, args = setup(tmp_path)
    observations=[]
    def checkpoint(event):
        if event in ('journal:building:0','journal:prepared:0','journal:committing:0'):
            observations.append((event,normative(root)))
    monkeypatch.setattr(writer,'_checkpoint',checkpoint)
    apply(root,plan,args)
    assert len(observations)==3 and all(actual==source for _,actual in observations)


@pytest.mark.parametrize('field,value',[
    ('expected_plan_sha256','0'*64),('expected_inputs_sha256','1'*64),
    ('expected_target_version','0.1.0'),('backup_source_files_sha256','2'*64),
    ('backup_sha256','3'*64),('backup_size',1),('transaction_id','../escape')])
def test_explicit_input_binding_refuses_before_normative_change(tmp_path,field,value):
    root,source,plan,args=setup(tmp_path);args[field]=value
    with pytest.raises(FAILURES):apply(root,plan,args)
    assert normative(root)==source


@pytest.mark.parametrize('mode',['changed','missing','extra','permission','symlink'])
def test_changed_real_source_is_never_rebased(tmp_path,mode):
    root,source,plan,args=setup(tmp_path)
    p=root/'spec/requirements/SR-REQ-0001.json'
    if mode=='changed':p.write_bytes(p.read_bytes()+b' ')
    elif mode=='missing':p.unlink()
    elif mode=='extra':(root/'unexpected.bin').write_bytes(b'extra')
    elif mode=='permission':p.chmod(0o4600)
    else:
        p.unlink(); p.symlink_to(tmp_path/'outside')
    before=normative(root) if mode!='symlink' else None
    with pytest.raises(FAILURES):apply(root,plan,args)
    if before is not None:assert normative(root)==before
    else:assert p.is_symlink()


@pytest.mark.parametrize('mode',['bytes','missing','link','inside'])
def test_actual_backup_is_required_not_report_claim(tmp_path,mode):
    from pathlib import Path
    root,source,plan,args=setup(tmp_path);p=Path(args['backup_path'])
    if mode=='bytes':p.write_bytes(b'not a verified backup')
    elif mode=='missing':p.unlink()
    elif mode=='link':
        raw=p.read_bytes();p.unlink();other=tmp_path/'other.zip';other.write_bytes(raw);p.symlink_to(other)
    else:args['backup_root']=str(root)
    with pytest.raises(FAILURES):apply(root,plan,args)
    assert normative(root)==source


@pytest.mark.parametrize('allowed',[False,1,None,'yes'])
def test_real_boolean_host_authority_required(tmp_path,allowed):
    from specroad.changes.publication_values import PublicationAuthority
    root,source,plan,args=setup(tmp_path)
    args['authority']=PublicationAuthority('synthetic-denied','1',lambda request:allowed)
    with pytest.raises(FAILURES):apply(root,plan,args)
    assert normative(root)==source


def test_authority_cannot_change_source_behind_gate(tmp_path):
    from specroad.changes.publication_values import PublicationAuthority
    root,source,plan,args=setup(tmp_path)
    def mutate(request):
        (root/'unplanned.txt').write_bytes(b'host mutation')
        return True
    args['authority']=PublicationAuthority('synthetic-race','1',mutate)
    with pytest.raises(FAILURES):apply(root,plan,args)
    assert all((root/p).read_bytes()==raw for p,raw in source.items())
    assert not journal_path(root,args).exists()


def test_required_semantic_gate_is_not_skipped(tmp_path):
    from specroad.validation import ModelGate
    root,source,plan,args=setup(tmp_path)
    args['gates']=(ModelGate('document_model','synthetic-deny',
        lambda c:c.dependency_result({i:[] for i in c.subjects}),
        lambda c:c.result([{'reason':'synthetic_document_invalid','severity':'error'}]),None),)
    with pytest.raises(FAILURES):apply(root,plan,args)
    assert normative(root)==source


def test_ai_actor_cannot_bypass_proposal_policy(tmp_path):
    root,source,plan,args=setup(tmp_path,fields={'actor':{'actor_type':'ai','actor_id':'synthetic-ai'}})
    with pytest.raises(FAILURES):apply(root,plan,args)
    assert normative(root)==source


def test_current_validation_does_not_accept_raw_legacy_without_manifest(tmp_path):
    from specroad.validation import ModelDocument, validate_model
    files=minimal();old=artifact('evidence')
    report=validate_model((ModelDocument('spec/evidence/SR-EVD-0001.json',json.dumps(old).encode()),))
    assert not report.passed


def test_passive_operational_source_bytes_remain_bound_and_unchanged(tmp_path):
    files=vector_source();files['.specroad/cache/passive.bin']=b'preserved opaque cache'
    root,source,plan,args=setup(tmp_path,files=files)
    assert '.specroad/cache/passive.bin' in plan.data['operations'][0]['protected_paths']
    apply(root,plan,args)
    assert (root/'.specroad/cache/passive.bin').read_bytes()==b'preserved opaque cache'


def test_active_operational_source_is_never_migration_input(tmp_path):
    from specroad.migration.planning import plan_migration
    from tests.support.migration_plans import FIELDS,target_inputs
    files=vector_source();files['.specroad/transactions/unknown/journal.json']=b'{}'
    with pytest.raises(FAILURES):plan_migration(files,inputs=target_inputs(files),**FIELDS)


def test_historical_baseline_and_source_closure_survive_real_write(tmp_path):
    from tests.support.reference01 import seal
    files=vector_source(); old=seal(files)
    root,source,plan,args=setup(tmp_path,files=files)
    original=source['spec/baselines/'+old['id']+'.json']
    apply(root,plan,args)
    assert (root/'spec/baselines'/ (old['id']+'.json')).read_bytes()==original
    observed=json.loads(original)
    assert observed['model_root_sha256']==old['model_root_sha256']
    assert observed['revision']==old['revision']


def test_full_backup_preserves_unreferenced_binary_and_empty_files(tmp_path):
    files=vector_source();files.update({'notes/opaque.bin':b'\x00\xff\r\n','notes/empty':b''})
    root,source,plan,args=setup(tmp_path,files=files)
    apply(root,plan,args)
    assert (root/'notes/opaque.bin').read_bytes()==b'\x00\xff\r\n'
    assert (root/'notes/empty').read_bytes()==b''


def test_shared_kernel_mutex_excludes_migration_writer(tmp_path):
    from specroad.changes._lock_files import LockFiles
    root,source,plan,args=setup(tmp_path)
    with LockFiles(root) as files:
        files.acquire()
        with pytest.raises(FAILURES) as seen: apply(root,plan,args)
    assert seen.value.reason=='project_lock_busy'
    assert normative(root)==source


def test_missing_language_service_cannot_be_a_successful_stub(tmp_path):
    from tests.support.migration_plans import target_inputs
    files=vector_source()
    root,source,plan,args=setup(tmp_path,files=files,inputs=target_inputs(files))
    with pytest.raises(FAILURES): apply(root,plan,args)
    assert normative(root)==source
