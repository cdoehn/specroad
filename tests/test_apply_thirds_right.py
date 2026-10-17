"""Exact partial-run receipts and stable third selection across failures."""
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from verification_support import apply_rotation as rotation
from test_apply_rotation import ANCHOR, NEXT, PAIRS
from test_apply_thirds import thirds


def gate_inputs(tmp_path, monkeypatch, *, sequence=2):
    root=tmp_path/'repo'; (root/'verification').mkdir(parents=True)
    value=thirds(); raw=(json.dumps(value,indent=2)+'\n').encode(); (root/rotation.REGISTRY).write_bytes(raw)
    catalog={'source_sha256':'bound','collected_tests':6,'nodeid_to_test_id':PAIRS}
    monkeypatch.setattr(rotation,'run_catalog_preflight',lambda root,path:path.write_text(json.dumps(catalog)) or True)
    monkeypatch.setattr(rotation,'commit_context',lambda *a:(NEXT,sequence,value))
    monkeypatch.setattr(rotation,'source_identity',lambda root:'bound')
    selected={n:i for n,i in PAIRS.items() if int(i[-1]) % 3 == sequence % 3}
    return root,value,raw,selected


def observation(selected):
    return {'observation_format_version':1,'engine':'pytest','nodeids':list(selected),
        'nodeid_to_test_id':selected,'test_outcomes':{i:'passed' for i in selected.values()},
        'suite_passed':True,'errors':[],'tests_run':len(selected),'pytest_exit_code':0,
        'worker_test_counts':{'gw0':1,'gw1':len(selected)-1}}


@pytest.mark.parametrize('sequence', [0,1,2,3,4,5])
def test_receipt_binds_exact_original_registry_numbers_group_head_and_observed_ids(tmp_path,monkeypatch,sequence):
    root,value,raw,selected=gate_inputs(tmp_path,monkeypatch,sequence=sequence); out=tmp_path/'reports'
    def execute(*a,**k):
        (out/'observations.json').write_text(json.dumps(observation(selected)))
        return SimpleNamespace(returncode=0)
    result=rotation.run_apply_partition(root,out,runner=execute)
    expected={'format_version':1,'kind':'apply-selection-binding-v1','base_commit':NEXT,
        'numbering_anchor_commit':ANCHOR,'rotation_anchor_commit':NEXT,'registry_sha256':sha256(raw).hexdigest(),
        'commit_sequence':sequence,'partition_count':3,'partition_index':sequence % 3,
        'tests':[{'nodeid':node,'test_id':identity,'test_number':int(identity[-1])} for node,identity in sorted(selected.items())]}
    assert result['selection_binding']==expected
    encoded=json.dumps(expected,sort_keys=True,ensure_ascii=True,allow_nan=False,separators=(',',':')).encode()
    assert result['selection_sha256']==sha256(encoded).hexdigest()
    assert result['selected_passed'] and result['full_suite_passed'] is None
    assert json.loads((out/'selection.json').read_text())==result
    assert (root/rotation.REGISTRY).read_bytes()==raw


@pytest.mark.parametrize('fault', ['other_group','missing_test','skip','process','source','head',
    'registry_bytes','registry_numbers','missing_observation','nonparallel_observation'])
def test_failed_or_changed_run_preserves_its_numbered_selection_without_advancing(fault,tmp_path,monkeypatch):
    root,value,raw,selected=gate_inputs(tmp_path,monkeypatch); out=tmp_path/'failed'; calls=[]
    expected=deepcopy(selected)
    def execute(command,**kwargs):
        calls.append(command); observed=observation(selected)
        if fault=='other_group': observed=observation({n:i for n,i in PAIRS.items() if int(i[-1]) % 3 == 1})
        elif fault=='missing_test': observed=observation(dict(list(selected.items())[:1]))
        elif fault=='skip': observed['test_outcomes'][next(iter(selected.values()))]='skipped'
        elif fault=='source': monkeypatch.setattr(rotation,'source_identity',lambda root:'changed')
        elif fault=='head': monkeypatch.setattr(rotation,'commit_context',lambda *a:('c'*40,3,value))
        elif fault=='registry_bytes': (root/rotation.REGISTRY).write_bytes(raw+b'\n')
        elif fault=='registry_numbers':
            changed=deepcopy(value); changed['test_ids'].reverse(); (root/rotation.REGISTRY).write_text(json.dumps(changed))
        elif fault=='nonparallel_observation': observed['worker_test_counts']={'master':2}
        if fault!='missing_observation': (out/'observations.json').write_text(json.dumps(observed))
        return SimpleNamespace(returncode=1 if fault=='process' else 0)
    result=rotation.run_apply_partition(root,out,runner=execute)
    assert len(calls)==1 and not result['selected_passed'] and result['full_suite_passed'] is None
    assert result['exit_code']==1 and result['errors']==['nonpassing_or_unbound_partition']
    assert result['commit_sequence']==2 and result['partition_index']==2 and result['nodeid_to_test_id']==expected
    assert result['selection_binding']['registry_sha256']==sha256(raw).hexdigest()
    assert json.loads((out/'selection.json').read_text())==result
    if fault not in ('registry_bytes','registry_numbers'): assert (root/rotation.REGISTRY).read_bytes()==raw
    assert set(rotation.select_partition(PAIRS,value,2,value).values())==set(expected.values())


@pytest.mark.parametrize('fault', ['source','head','registry'])
def test_changed_preflight_inputs_do_not_start_any_test_body(tmp_path,monkeypatch,fault):
    root,value,raw,selected=gate_inputs(tmp_path,monkeypatch); calls=[]
    if fault=='source': monkeypatch.setattr(rotation,'source_identity',lambda root:'changed')
    elif fault=='head':
        def context(*args):
            calls.append(args); return (NEXT,2,value) if len(calls)==1 else ('c'*40,3,value)
        monkeypatch.setattr(rotation,'commit_context',context)
    else:
        def changed(root):
            (root/rotation.REGISTRY).write_bytes(raw+b'\n'); return 'bound'
        monkeypatch.setattr(rotation,'source_identity',changed)
    with pytest.raises(ValueError):
        rotation.run_apply_partition(root,tmp_path/'preflight',runner=lambda *a,**k:pytest.fail('test body must not start'))
    assert not (tmp_path/'preflight/selection.json').exists()


@pytest.mark.parametrize('added', [1,2,3,4,5])
def test_additions_and_retirements_keep_stable_modulo_membership(added):
    previous=thirds(); ids=[f'new.{n}' for n in range(added)]
    current={n:i for n,i in PAIRS.items() if i!='case.2'}
    current.update({f'tests/test_new.py::test_{n}':identity for n,identity in enumerate(ids)})
    value=thirds(previous['test_ids']+ids)
    parts=[rotation.select_partition(current,value,group,previous) for group in range(3)]
    assert parts[0] | parts[1] | parts[2]==current
    for group,part in enumerate(parts):
        expected={i for i in current.values() if (int(i[-1])+(6 if i.startswith('new.') else 0)) % 3 == group}
        assert set(part.values())==expected
    assert value['test_ids'][2]=='case.2'


def test_receipt_is_order_independent_but_binds_original_registry_bytes():
    value=thirds(); raw=json.dumps(value).encode(); selected=rotation.select_partition(PAIRS,value,0,value)
    first=rotation.selection_receipt(value,raw,selected,NEXT,0)
    assert rotation.selection_receipt(value,raw,dict(reversed(list(selected.items()))),NEXT,0)==first
    changed=rotation.selection_receipt(value,raw+b'\n',selected,NEXT,0)
    assert first['selection_binding']['tests']==changed['selection_binding']['tests']
    assert first['selection_sha256']!=changed['selection_sha256']


def test_retry_uses_a_fresh_report_directory_and_preserves_prior_failure_evidence(tmp_path,monkeypatch):
    root,value,raw,selected=gate_inputs(tmp_path,monkeypatch); out=tmp_path/'reports'
    def fail(*a,**k): return SimpleNamespace(returncode=1)
    first=rotation.run_apply_partition(root,out,runner=fail); saved=(out/'selection.json').read_bytes()
    assert not first['selected_passed']
    with pytest.raises(FileExistsError):
        rotation.run_apply_partition(root,out,runner=lambda *a,**k:pytest.fail('existing evidence must remain'))
    assert (out/'selection.json').read_bytes()==saved
    second_out=tmp_path/'retry'
    def passed(*a,**k):
        (second_out/'observations.json').write_text(json.dumps(observation(selected))); return SimpleNamespace(returncode=0)
    second=rotation.run_apply_partition(root,second_out,runner=passed)
    assert second['selected_passed'] and second['selection_binding']==first['selection_binding']
    assert second['partition_index']==first['partition_index']==2
    assert (out/'selection.json').read_bytes()==saved
