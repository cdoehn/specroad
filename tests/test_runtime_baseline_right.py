"""Failures, explicit bypasses and immutable calibration boundaries."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_runtime_baseline import measurement
from verification_support.runtime_baseline import (BASELINE, RuntimeMeasurements, encoded,
    filter_partition, freeze, load_baseline, make_baseline, validate_baseline)


@pytest.mark.parametrize('fault', ['partial','missing_phase','duplicate_id','duplicate_node',
    'negative','bool','wrong_version','serial','bad_hash','bad_timestamp'])
def test_invalid_full_measurement_cannot_hide_any_test(fault):
    value=measurement()
    if fault=='partial': value['full_suite_passed']=False
    elif fault=='missing_phase': value['tests'][0]['phase_ns'].pop('teardown')
    elif fault=='duplicate_id': value['tests'][1]['test_id']=value['tests'][0]['test_id']
    elif fault=='duplicate_node': value['tests'][1]['nodeid']=value['tests'][0]['nodeid']
    elif fault=='negative': value['tests'][0]['phase_ns']['call']=-1
    elif fault=='bool': value['tests'][0]['phase_ns']['call']=True
    elif fault=='wrong_version': value['format_version']=True
    elif fault=='serial': value['workers']=1
    elif fault=='bad_hash': value['source_sha256']='invented'
    else: value['measured_at']='yesterday'
    with pytest.raises(ValueError): make_baseline(value)


@pytest.mark.parametrize('fault', ['extra_exclusion','fast_exclusion','duplicate_exclusion','fraction',
    'duplicate_id','negative','bool','missing','timestamp','digest'])
def test_corrupt_baseline_is_rejected_instead_of_silently_excluding_tests(tmp_path,fault):
    value=make_baseline(measurement())
    if fault=='extra_exclusion': value['excluded_test_ids'].append('case.7')
    elif fault=='fast_exclusion': value['excluded_test_ids']=['case.0','case.1']
    elif fault=='duplicate_exclusion': value['excluded_test_ids']=['case.9','case.9']
    elif fault=='fraction': value['exclude_numerator']=True
    elif fault=='duplicate_id': value['tests'][1]['test_id']=value['tests'][0]['test_id']
    elif fault=='negative': value['tests'][0]['duration_ns']=-1
    elif fault=='bool': value['tests'][0]['duration_ns']=False
    elif fault=='missing': value.pop('tests')
    elif fault=='timestamp': value['measured_at']='2026-10-28T10:00:00'
    else: value['measurement_sha256']='x'*64
    (tmp_path/'verification').mkdir()
    (tmp_path/BASELINE).write_bytes(encoded(value))
    with pytest.raises(ValueError): load_baseline(tmp_path)


@pytest.mark.parametrize('duration', [True,-1,float('nan'),float('inf'),1e308])
def test_invalid_native_duration_cannot_become_a_measurement(duration):
    recorder=RuntimeMeasurements()
    recorder.observe('node','call',duration)
    assert recorder.invalid


def test_linked_baseline_is_rejected_without_replacing_its_target(tmp_path):
    (tmp_path/'verification').mkdir()
    target=tmp_path/'outside.json'; target.write_bytes(encoded(make_baseline(measurement())))
    (tmp_path/BASELINE).symlink_to(target)
    before=target.read_bytes()
    with pytest.raises(ValueError): load_baseline(tmp_path)
    assert target.read_bytes()==before


def test_empty_filtered_group_is_not_a_success_and_retired_entries_never_move_cutoff():
    value=make_baseline(measurement())
    with pytest.raises(ValueError): filter_partition({'node':'case.9'},('a'*64,value))
    keep,record=filter_partition({'node':'new'},('a'*64,value))
    assert keep=={'node':'new'} and not record['excluded_test_ids']


def fixture_with_excluded_native(root):
    from support.catalog_project import make_catalog_project, NATIVE_IDS, LEGACY_ID
    root=make_catalog_project(root)
    value=measurement(5)
    ids=[*NATIVE_IDS,LEGACY_ID,'retired']
    for row,identity in zip(value['tests'],ids):
        row['test_id']=identity
    value['tests'][0]['phase_ns']['call']=10**15
    (root/BASELINE).write_bytes(encoded(make_baseline(value)))
    assert NATIVE_IDS[0] in load_baseline(root)[1]['excluded_test_ids']
    return root


def test_real_explicit_dev_selection_runs_the_excluded_test_and_preserves_baseline(tmp_path):
    from support.catalog_project import execute,NATIVE_IDS
    root=fixture_with_excluded_native(tmp_path)
    before=(root/BASELINE).read_bytes()
    out=root/'build/selected'
    result=execute(root,'run_selected_tests.py',['--test-file','tests/test_subject.py',
        '--expected-tests','4','--workers','2','--outdir',str(out)])
    assert result.returncode==0,result.stderr.decode()
    observed=json.loads((out/'observations.json').read_text())
    assert observed['tests_run']==4 and observed['test_outcomes'][NATIVE_IDS[0]]=='passed'
    assert (root/BASELINE).read_bytes()==before


def test_real_manual_full_suite_is_unfiltered_and_never_recalibrates(tmp_path):
    from support.catalog_project import execute,NATIVE_IDS
    root=fixture_with_excluded_native(tmp_path)
    before=(root/BASELINE).read_bytes()
    output=root/'build/full.json'
    result=execute(root,'run_tests.py',['--workers','2','--observations',str(output)])
    assert result.returncode==0,result.stderr.decode()
    observed=json.loads(output.read_text())
    assert observed['tests_run']==4 and observed['test_outcomes'][NATIVE_IDS[0]]=='passed'
    assert (root/BASELINE).read_bytes()==before


def test_runtime_output_cannot_replace_inputs_or_an_existing_measurement(tmp_path):
    from support.catalog_project import make_catalog_project,execute,effects
    root=make_catalog_project(tmp_path)
    for target in (root/'verification/new.json',root/'build/existing.json'):
        if target.name=='existing.json': target.write_bytes(b'preserved')
        result=execute(root,'run_tests.py',['--workers','2','--runtime-measurement',str(target)])
        assert result.returncode!=0 and not effects(root)
    assert (root/'build/existing.json').read_bytes()==b'preserved'


def test_failed_or_unfinished_collection_is_not_publishable(tmp_path):
    from support.catalog_project import make_catalog_project,execute
    root=make_catalog_project(tmp_path)
    output=root/'build/not-complete.json'
    result=execute(root,'run_tests.py',['--workers','2','--expected-tests','99',
                                     '--runtime-measurement',str(output)])
    assert result.returncode!=0 and not output.exists()


def test_baseline_change_during_apply_invalidates_an_otherwise_passing_observation(tmp_path,monkeypatch):
    from verification_support import apply_rotation as rotation
    from test_apply_thirds import thirds
    from test_apply_rotation import NEXT
    root=tmp_path/'repo';(root/'verification').mkdir(parents=True)
    measured=measurement(12)
    pairs={r['nodeid']:r['test_id'] for r in measured['tests']}
    registry=thirds(sorted(pairs.values()))
    (root/rotation.REGISTRY).write_text(json.dumps(registry))
    baseline=make_baseline(measured)
    (root/BASELINE).write_bytes(encoded(baseline))
    catalog={'source_sha256':'bound','collected_tests':12,'nodeid_to_test_id':pairs}
    monkeypatch.setattr(rotation,'run_catalog_preflight',lambda r,p:p.write_text(json.dumps(catalog)) or True)
    monkeypatch.setattr(rotation,'commit_context',lambda *a:(NEXT,1,registry))
    monkeypatch.setattr(rotation,'source_identity',lambda root:'bound')
    selected,_=filter_partition(rotation.select_partition(pairs,registry,1,registry),load_baseline(root))
    out=tmp_path/'report'
    def execute(*args,**kwargs):
        observed={'observation_format_version':1,'engine':'pytest','nodeids':list(selected),
            'nodeid_to_test_id':selected,'test_outcomes':{i:'passed' for i in selected.values()},
            'suite_passed':True,'errors':[],'tests_run':len(selected),'pytest_exit_code':0,
            'worker_test_counts':{'gw0':len(selected),'gw1':0}}
        (out/'observations.json').write_text(json.dumps(observed))
        (root/BASELINE).write_bytes(encoded(baseline)+b' ')
        return SimpleNamespace(returncode=0)
    result=rotation.run_apply_partition(root,out,runner=execute)
    assert not result['selected_passed'] and result['exit_code']==1
