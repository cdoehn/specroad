"""Test incomplete observations and isolated publication, not terminal output."""
from pathlib import Path
from types import SimpleNamespace
import json
import pytest
from verification_support.selected import run_selected, selected_files, verify_observation
from test_selected_gate import fixture, observation, fake


@pytest.mark.parametrize('key,value', [('errors',['worker_crash']),('suite_passed',False),
 ('tests_run',0),('tests_run',True),('pytest_exit_code',False),('worker_test_counts',{'gw0':0}),
 ('worker_test_counts',{'gw0':True}),('nodeids',[]),('engine','other'),('observation_format_version',2),
 ('nodeid_to_test_id',{}),('test_outcomes',{}),('nodeid_to_test_id',None),
 ('nodeid_to_test_id',{'tests/test_one.py::test_one':[]})])
def test_invalid_observations_are_not_passes(key,value):
    data=observation();data[key]=value
    with pytest.raises(ValueError):verify_observation(data,['tests/test_one.py'],1)


def test_wrong_test_file_cannot_substitute_for_selected_file():
    with pytest.raises(ValueError):verify_observation(observation(),['tests/test_two.py'],1)


def test_missing_observations_fail_even_if_process_success(tmp_path):
    names=fixture(tmp_path)
    result=run_selected(tmp_path,names,tmp_path/'build/run',expected=1,runner=lambda *a,**k:SimpleNamespace(returncode=0))
    assert result['exit_code']==1 and result['full_suite_passed'] is None


def test_spawn_failure_is_not_retried(tmp_path):
    names=fixture(tmp_path); calls=[]
    def runner(*a,**k):calls.append(a);raise OSError('start failed')
    result=run_selected(tmp_path,names,tmp_path/'build/run',expected=1,runner=runner)
    assert len(calls)==1 and result['process_exit_code']==4 and not result['selected_passed']


def test_killed_process_cannot_be_green(tmp_path):
    names=fixture(tmp_path)
    assert not run_selected(tmp_path,names,tmp_path/'build/run',expected=1,runner=fake([],code=-9))['selected_passed']


def test_symlinked_test_rejected(tmp_path):
    fixture(tmp_path);(tmp_path/'tests/test_link.py').symlink_to('test_one.py')
    with pytest.raises(ValueError):selected_files(tmp_path,['tests/test_link.py'])


def test_symlinked_report_parent_rejected(tmp_path):
    names=fixture(tmp_path);(tmp_path/'elsewhere').mkdir();(tmp_path/'build').symlink_to('elsewhere',target_is_directory=True)
    with pytest.raises(ValueError):run_selected(tmp_path,names,tmp_path/'build/run',expected=1)
    assert not (tmp_path/'elsewhere/run').exists()


def test_source_report_destination_rejected(tmp_path):
    names=fixture(tmp_path)
    with pytest.raises(ValueError):run_selected(tmp_path,names,tmp_path/'tests/run',expected=1)


def test_empty_collection_and_string_list_refused(tmp_path):
    fixture(tmp_path)
    for names in ([], 'tests/test_one.py'):
        with pytest.raises(ValueError):selected_files(tmp_path,names)


def test_environment_is_not_mutated_and_overrides_are_stripped(tmp_path):
    names=fixture(tmp_path);env={'PYTEST_ADDOPTS':'-n 0','PYTEST_XDIST_WORKER':'gw99'};calls=[]
    run_selected(tmp_path,names,tmp_path/'build/run',expected=1,runner=fake(calls),environment=env)
    assert env=={'PYTEST_ADDOPTS':'-n 0','PYTEST_XDIST_WORKER':'gw99'}
    assert all(k not in calls[0][1]['env'] for k in env)
