"""18.q.R: real negative exports, original boundaries and explicit native deltas."""
from hashlib import sha256
from pathlib import Path

import pytest

from specroad.model.canonical import canonical_json_bytes
from specroad.proposals.content import content_sha256
from support.transport_outbound import tree
from support.transport_return import sandbox, offline_export
from test_transport_return import distribution as _distribution, handoff as _handoff

distribution = _distribution
handoff = _handoff


@pytest.mark.parametrize('change,code', [('hash',6),('project-delta',6),('project-id',6),('rename-source',6),('deleted-source',6),
    ('proposal-target',3),('reference-runtime',7),('proposal-link',7),('no-request',2)])
def test_invalid_return_refuses_package_and_preserves_inputs(tmp_path,distribution,handoff,change,code):
    value, proposal = sandbox(tmp_path,distribution,handoff)
    o = value['options']; root = Path(o['--project'])
    if change == 'hash': o['--expected-sha256'] = '0'*64
    if change == 'project-delta':
        p = next((root/'spec/goals').glob('*.json'));p.write_bytes(p.read_bytes()+b' ')
    if change == 'project-id':
        p=root/'specroad.json';data=__import__('json').loads(p.read_bytes());data['project_id']='other-project'
        p.write_bytes(canonical_json_bytes(data))
    if change == 'rename-source':
        p=next((root/'spec/goals').glob('*.json'));p.rename(root/'unmanaged-goal.json')
    if change == 'deleted-source': next((root/'spec/goals').glob('*.json')).unlink()
    if change in ('proposal-target','no-request'):
        data = proposal.data; plan = data['change_plan']
        if change == 'proposal-target': plan['expected_result']['model_root_sha256'] = '0'*64
        else: plan['request_id'] = None
        from specroad.changes.core import prepare_change_plan
        data['change_plan'] = prepare_change_plan({k:v for k,v in plan.items() if k != 'change_plan_sha256'}).data
        data['content_sha256'] = content_sha256(data)
        Path(o['--proposal']).write_bytes(canonical_json_bytes(data))
    if change == 'reference-runtime':
        p = Path(o['--patchharbor-pyz']); p.write_bytes(p.read_bytes()+b'foreign')
        o['--patchharbor-pyz-sha256'] = sha256(p.read_bytes()).hexdigest()
    if change == 'proposal-link':
        p=Path(o['--proposal']); moved=p.with_name('actual.json');p.rename(moved);p.symlink_to(moved)
    before = tree(root), tree(handoff['repository'])
    answer = offline_export(tmp_path,distribution[1],value)
    assert answer['code'] == code, answer
    assert not list((tmp_path/'output').glob('*.zip'))
    assert (tree(root),tree(handoff['repository'])) == before


@pytest.mark.parametrize('fault', ('extra','missing','entrypoint','delete','rename','mode','link'))
def test_prepared_inventory_cannot_smuggle_extra_delete_rename_or_code(tmp_path,distribution,handoff,fault):
    value,_ = sandbox(tmp_path,distribution,handoff)
    before = tree(Path(value['options']['--project']))
    script = '''
import specroad.transport.return_export as target
original=target._write_contents
def corrupt(root, contents, entrypoint):
    original(root,contents,entrypoint)
    prefix=root/entrypoint.rsplit('/',1)[0]
    fault=''' + repr(fault) + '''
    data=next((prefix/'data').iterdir())
    if fault=='extra':(prefix/'extra.bin').write_bytes(b'foreign')
    if fault=='missing':data.unlink()
    if fault=='entrypoint':(root/entrypoint).write_bytes(b'#!/bin/bash\\necho foreign\\n')
    if fault in ('delete','rename'):
        import json
        p=prefix/'return.json';v=json.loads(p.read_bytes());v['delta'][0]['after_sha256']=None
        if fault=='rename':v['delta'][0]['path']='spec/goals/foreign.json'
        p.write_text(json.dumps(v))
    if fault=='mode':data.chmod(0o755)
    if fault=='link':
        data.unlink();data.symlink_to(prefix/'proposal.json')
target._write_contents=corrupt
'''
    answer = offline_export(tmp_path,distribution[0],value,before=script)
    assert answer['code'] == 7, answer
    assert not list((tmp_path/'output').glob('*.zip'))
    assert tree(Path(value['options']['--project'])) == before


@pytest.mark.parametrize('phase', ('prepare','pack'))
def test_source_change_at_final_boundary_never_returns_created(tmp_path,distribution,handoff,phase):
    value,_=sandbox(tmp_path,distribution,handoff)
    script='''
from specroad.transport.return_export import ReturnExport
import specroad.transport.return_export as target
root=Path(''' + repr(value['options']['--project']) + ''')
def change():
    p=next((root/'spec/goals').glob('*.json'));p.write_bytes(p.read_bytes()+b' ')
''' + ('''
original=ReturnExport.prepare
def modified(self):
    value=original(self);change();return value
ReturnExport.prepare=modified
''' if phase=='prepare' else '''
original=target._api_call
def modified(api,call,*args,**kwargs):
    value=original(api,call,*args,**kwargs)
    if call is api.pack_patch:change()
    return value
target._api_call=modified
''')
    result=offline_export(tmp_path,distribution[1],value,before=script)
    assert result['code']==6,result


def test_return_manifest_is_owned_and_inputs_are_not_new_review_authority(tmp_path,distribution,handoff):
    value,proposal=sandbox(tmp_path,distribution,handoff)
    assert proposal.data['reviews']==[] and proposal.data['control_history']==[]
    script='''
from specroad.transport.return_export import ReturnExport
original=ReturnExport.prepare
def owned(self):
    data=original(self)
    borrowed=data.manifest;borrowed['delta'].clear();borrowed['proposal']['sha256']='0'*64
    assert data.manifest['delta'] and data.manifest['proposal']['sha256']!='0'*64
    try:data.contents['foreign']=b'foreign'
    except TypeError:pass
    else:raise AssertionError('mutable return payload')
    return data
ReturnExport.prepare=owned
'''
    result=offline_export(tmp_path,distribution[0],value,before=script)
    assert result['code']==0,result
