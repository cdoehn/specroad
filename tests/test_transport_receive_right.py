"""18.r.R: actual rejection before payload, exact replay and partial outcomes."""
from hashlib import sha256
import json
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.model.canonical import canonical_json_bytes
from support.transport_outbound import tree
from support.transport_receive import returned, receive
from test_transport_receive import distribution as _distribution

distribution = _distribution


def repack(path, change):
    with ZipFile(path) as archive:
        items=[(entry,archive.read(entry.filename)) for entry in archive.infolist()]
    path.unlink()
    with ZipFile(path,'w',ZIP_DEFLATED) as archive:
        for entry,raw in items:
            replacement=change(entry,raw)
            if replacement is not None:archive.writestr(entry,replacement)


@pytest.mark.parametrize('fault', ('entrypoint','data','extra','missing','normative','review','delete','rename',
                                   'handoff-extra','handoff-format'))
def test_host_rejects_untrusted_inventory_before_any_payload(tmp_path,distribution,fault):
    handoff,package,_=returned(tmp_path,distribution)
    with ZipFile(package) as z:
        key=next(n.rsplit('/',1)[0] for n in z.namelist() if n.endswith('/return.json'))
    def change(entry,raw):
        if fault=='handoff-format' and entry.filename=='PATCHHARBOR_META/environment.json':return b'{}'
        if fault=='entrypoint' and entry.filename.endswith('/receive.sh'):return b'#!/bin/bash\nexit 0\n'
        if fault=='data' and '/data/' in entry.filename:return b'foreign data'
        if fault=='missing' and '/data/' in entry.filename:return None
        if fault=='normative' and '/data/' in entry.filename:entry.filename='specroad.json'
        if fault=='review' and entry.filename.endswith('/proposal.json'):
            v=json.loads(raw);v['proposal_status']='approved';v['reviews']=[{'actor_type':'human','decision':'approved'}]
            return canonical_json_bytes(v)
        if fault in ('delete','rename') and entry.filename.endswith('/return.json'):
            v=json.loads(raw)
            if fault=='delete':v['delta'][0]['after_sha256']=None
            else:v['delta'][0]['path']='spec/goals/foreign.json'
            return canonical_json_bytes(v)
        return raw
    repack(package,change)
    if fault=='extra':
        with ZipFile(package,'a') as z:z.writestr(key+'/extra.txt',b'foreign')
    if fault=='handoff-extra':
        with ZipFile(package,'a') as z:z.writestr('PATCHHARBOR_META/foreign.txt',b'foreign')
    before=tree(handoff['repository'])
    result=receive(handoff,package,distribution[1])
    assert result['status']=='refused',result
    assert tree(handoff['repository'])==before
    assert not (handoff['repository']/'.specroad-return').exists()


def test_same_patch_replay_requires_actual_native_completion_and_writes_nothing(tmp_path,distribution):
    handoff,package,_=returned(tmp_path,distribution)
    first=receive(handoff,package,distribution[0])
    assert first['status']=='proposal_received' and first['patchharbor']['success'],first
    before=tree(handoff['repository'])
    second=receive(handoff,package,distribution[0],name='again',prior_result=first['patchharbor']['result_path'])
    assert second['status']=='proposal_received' and second['replayed'],second
    from specroad.changes import read_transaction_completion
    from specroad.storage.project import ProjectSource
    live=first['draft_completion']['completion']
    historical=read_transaction_completion(ProjectSource(handoff['origin']),live['transaction_id']).data
    assert live['current_target_verified'] and not live['replayed']
    assert not historical['current_target_verified'] and historical['replayed']
    assert historical=={**live,'current_target_verified':False,'replayed':True}
    receipt=next((handoff['repository']/'.specroad-return').glob('*/received.json'))
    assert json.loads(receipt.read_bytes())['completion']==historical
    assert second['draft_completion']['completion']==historical
    assert second['patchharbor']['result_status']=='not_reapplied'
    assert tree(handoff['repository'])==before


@pytest.mark.parametrize('fault', ('missing-receipt','forged-receipt','changed-proposal','extra-stage','symlink-stage'))
def test_unknown_or_changed_completed_state_is_not_automatically_reapplied(tmp_path,distribution,fault):
    handoff,package,proposal=returned(tmp_path,distribution)
    first=receive(handoff,package,distribution[1]);assert first['status']=='proposal_received',first
    stage=next((handoff['repository']/'.specroad-return').iterdir())
    if fault=='missing-receipt':(stage/'received.json').unlink()
    if fault=='forged-receipt':(stage/'received.json').write_bytes(b'{}')
    if fault=='changed-proposal':
        p=handoff['origin']/proposal.original.path;p.write_bytes(p.read_bytes()+b' ')
    if fault=='extra-stage':(stage/'foreign').write_bytes(b'foreign')
    if fault=='symlink-stage':
        p=stage/'received.json';p.rename(stage/'saved');p.symlink_to(stage/'saved')
    before=tree(handoff['repository'])
    result=receive(handoff,package,distribution[0],name='rejected-replay')
    assert result['status']=='refused',result
    assert tree(handoff['repository'])==before


@pytest.mark.parametrize('fault', ('target','package','stage','workspace'))
def test_admission_rechecks_toctou_under_native_repository_lock(tmp_path,distribution,fault):
    handoff,package,_=returned(tmp_path,distribution)
    project=handoff['origin'];before=InspectionSnapshot(project,None).model.source_files
    script='''
original=ReturnReceiver._admit
def raced(self,facts):
    fault='''+repr(fault)+'''
    if fault=='target':
        p=next((self.project.root/'spec/goals').glob('*.json'));p.write_bytes(p.read_bytes()+b' ')
    if fault=='package':self.source.path.write_bytes(self.source.raw+b'foreign')
    if fault=='stage':self.stage.mkdir(parents=True);(self.stage/'foreign').write_bytes(b'untouched')
    if fault=='workspace':self.workspace.chmod(0o755)
    return original(self,facts)
ReturnReceiver._admit=raced
'''
    result=receive(handoff,package,distribution[1],before=script)
    assert result['status']=='failed' and not result['patchharbor']['success'],result
    after=InspectionSnapshot(project,None).model.source_files
    if fault=='target':
        changed={k for k in before if before[k]!=after[k]}
        assert len(changed)==1 and after[next(iter(changed))]==before[next(iter(changed))]+b' '
    else:assert after==before
    assert not list(project.glob('spec/proposals/*.json'))


def test_result_publication_failure_does_not_erase_real_draft_completion(tmp_path,distribution):
    handoff,package,proposal=returned(tmp_path,distribution)
    script='''
import sys,os
finished=[False]
original=ReturnReceiver._receive
def finished_receive(self):
    value=original(self);finished[0]=True;return value
ReturnReceiver._receive=finished_receive
def audit(event,args):
    if finished[0] and event in ('open','os.rename','os.link','os.mkdir'):
        for item in args[:2]:
            if isinstance(item,(str,bytes)) and str(Path(os.fsdecode(item)).absolute()).startswith(options['workspace']):
                raise PermissionError('Synthetic Result publication failure after native draft commit')
sys.addaudithook(audit)
'''
    result=receive(handoff,package,distribution[0],before=script)
    assert result['status']=='proposal_received',result
    assert result['draft_completion']['write_state']=='committed'
    assert (handoff['origin']/proposal.original.path).exists()
    assert result['patchharbor'].get('success') is not True,result


@pytest.mark.parametrize('boundary', ('before-draft','after-draft'))
def test_real_receiver_process_loss_keeps_unknown_state_closed(tmp_path,distribution,boundary):
    from support.transport_outbound import child
    handoff,package,proposal=returned(tmp_path,distribution)
    root=handoff['repository'].parent
    options=dict(expected_sha256=sha256(package.read_bytes()).hexdigest(),
        reference=str(handoff['source']),reference_sha256=sha256(handoff['source'].read_bytes()).hexdigest(),
        repository=str(handoff['repository']),workspace=str(root/'interrupted'),
        patchharbor_pyz=str(handoff['runtime']),patchharbor_pyz_sha256=sha256(handoff['runtime'].read_bytes()).hexdigest(),timeout=30)
    inner='''import sys,os
sys.path.insert(0,'''+repr(str(distribution[0]))+''')
from specroad.changes import PublicationAuthority
import specroad.transport.return_receive as receive
'''+('receive.ReturnReceiver._receive=lambda self:os._exit(91)\n' if boundary=='before-draft'
    else 'receive.record=lambda self:os._exit(91)\n')+'''
receive.ReturnReceiver('''+repr(str(package))+''',authority=PublicationAuthority('synthetic-crash-host','1',lambda request:True),authorize_transport=lambda request:True,
    **'''+repr(options)+''').receive()
'''
    result=child(root,'''import subprocess,json
r=subprocess.run([sys.executable,'-I','-S','-B','-c','''+repr(inner)+'''],capture_output=True,timeout=120)
print(json.dumps({'code':r.returncode}))''',source=distribution[0])
    assert result['code']==91,result
    assert (handoff['origin']/proposal.original.path).exists()==(boundary=='after-draft')
    before=tree(handoff['repository'])
    refused=receive(handoff,package,distribution[0],name='after-interruption')
    assert refused['status']=='refused',refused
    assert refused['reason']=='return_stage_without_complete_receipt'
    assert tree(handoff['repository'])==before


@pytest.mark.parametrize('kind', ('id','request'))
def test_local_identity_and_request_conflicts_never_overwrite_originals(tmp_path,distribution,kind):
    handoff,package,proposal=returned(tmp_path,distribution)
    if kind=='id':
        p=handoff['origin']/proposal.original.path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(proposal.source_bytes)
    else:
        # A prior native receipt consumed this request; missing transport proof cannot authorize another write.
        first=receive(handoff,package,distribution[0]);assert first['status']=='proposal_received',first
        stage=next((handoff['repository']/'.specroad-return').iterdir());(stage/'received.json').unlink()
    before=tree(handoff['repository'])
    result=receive(handoff,package,distribution[0],name='conflict')
    assert result['status']=='refused',result
    assert tree(handoff['repository'])==before


def test_genuine_foreign_reviews_are_passive_and_local_draft_requires_new_review(tmp_path,distribution):
    from pathlib import Path
    from specroad.proposals import ProposalContext, ProposalOriginal
    from specroad.proposals.review_start import review_start_project
    from specroad.changes import PublicationAuthority
    from support.proposal_decisions import ReviewCase
    from support.transport_return import origin, sandbox, offline_export
    host=tmp_path/'host';host.mkdir()
    handoff=origin(host,distribution)
    remote=tmp_path/'remote';remote.mkdir()
    value,proposal=sandbox(remote,distribution,handoff)
    root=Path(value['options']['--project'])
    path=root/proposal.original.path;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(proposal.source_bytes)
    case=ReviewCase.__new__(ReviewCase)
    case.root=root;case.originals=[proposal.original]
    case.contexts=[ProposalContext(proposal.original,InspectionSnapshot(root,None).model)]
    case.reviews=[];case.controls=[];case.current_decisions=True
    case.authority=PublicationAuthority('synthetic-foreign-review-host','1',lambda request:True)
    review_start_project(root,proposal.data['id'],expected_revision=1,
        actor={'actor_type':'human','actor_id':'synthetic-author'},planned_at='2026-11-18T01:00:00Z',
        change_plan_id='foreign-start',transaction_id='foreign-start',authority=case.authority)
    case.capture(start=True);case.decide(planned_at='2026-11-18T01:30:00Z')
    assert case.original.data['proposal_status']=='approved' and case.original.data['reviews']
    foreign=path.read_bytes()
    value['options']['--proposal']=str(path)
    exported=offline_export(remote,distribution[1],value)
    assert exported['code']==0,exported
    package=Path(exported['outcome']['result']['file']['path'])
    outcome=receive(handoff,package,distribution[1])
    assert outcome['status']=='proposal_received' and outcome['patchharbor']['success'],outcome
    local=ProposalOriginal((handoff['origin']/proposal.original.path).read_bytes(),path=proposal.original.path)
    assert local.data['proposal_status']==local.data['maturity']=='draft'
    assert local.data['revision']==local.data['content_revision']==1
    assert local.data['reviews']==local.data['control_history']==[]
    assert local.binding.content_sha256==case.original.binding.content_sha256
    with ZipFile(package) as archive:
        assert archive.read(next(n for n in archive.namelist() if n.endswith('/proposal.json')))==foreign
    assert path.read_bytes()==foreign


@pytest.mark.parametrize('fault', ('absent','wrong-hash','changed-result'))
def test_replay_requires_original_successful_ph_result_as_well_as_native_receipt(tmp_path,distribution,fault):
    from pathlib import Path
    handoff,package,_=returned(tmp_path,distribution)
    first=receive(handoff,package,distribution[0])
    assert first['status']=='proposal_received' and first['patchharbor']['success'],first
    before=tree(handoff['repository'])
    prior=Path(first['patchharbor']['result_path'])
    script=''
    if fault=='wrong-hash':script="options['prior_result_sha256']='0'*64"
    if fault=='changed-result':
        script="p=Path(options['prior_result']);p.write_bytes(p.read_bytes()+b'changed')"
    answer=receive(handoff,package,distribution[0],name='retry-proof',before=script,
        prior_result=None if fault=='absent' else prior)
    assert answer['status']=='refused',answer
    expected='return_prior_native_result_required' if fault=='absent' else 'transport_input_hash_mismatch'
    assert answer['reason']==expected and answer['exit_code']==6,answer
    assert tree(handoff['repository'])==before



def test_replay_in_subproject_preserves_native_history_across_distributions(tmp_path,distribution):
    from pathlib import Path
    handoff,package,_=returned(tmp_path,distribution,subproject=True)
    first=receive(handoff,package,distribution[1])
    assert first['status']=='proposal_received' and first['patchharbor']['success'],first
    receipt=next((handoff['repository']/'.specroad-return').glob('*/received.json'))
    raw=receipt.read_bytes(); record=json.loads(raw)
    before=tree(handoff['repository'])
    for index,route in enumerate((1,0)):
        repeated=receive(handoff,package,distribution[route],name='again-'+str(index),
                         prior_result=Path(first['patchharbor']['result_path']))
        assert repeated['status']=='proposal_received' and repeated['replayed'],repeated
        assert repeated['patchharbor']['result_status']=='not_reapplied'
        assert repeated['draft_completion']['completion']==record['completion']
        assert not repeated['draft_completion']['completion']['current_target_verified']
        assert repeated['draft_completion']['completion']['replayed']
        assert receipt.read_bytes()==raw and tree(handoff['repository'])==before


@pytest.mark.parametrize('field', ('transaction_id','target_model_root_sha256','current_target_verified','replayed'))
def test_replay_rejects_changed_historical_completion_without_rewriting_receipt(tmp_path,distribution,field):
    handoff,package,_=returned(tmp_path,distribution)
    first=receive(handoff,package,distribution[0])
    assert first['status']=='proposal_received' and first['patchharbor']['success'],first
    receipt=next((handoff['repository']/'.specroad-return').glob('*/received.json'))
    value=json.loads(receipt.read_bytes())
    if field in ('current_target_verified','replayed'):
        value['completion'][field]=not value['completion'][field]
    elif field=='transaction_id':value['completion'][field]='foreign-transaction'
    else:value['completion'][field]='0'*64
    receipt.write_bytes(canonical_json_bytes(value))
    before=tree(handoff['repository'])
    refused=receive(handoff,package,distribution[1],name='forged-history',
                    prior_result=first['patchharbor']['result_path'])
    assert refused=={'status':'refused','reason':'return_receipt_mismatch','exit_code':6},refused
    assert tree(handoff['repository'])==before
