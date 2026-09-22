"""Selected tests never masquerade as a whole-suite or release verdict."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from verification_support.selected import selected_files, run_selected, verify_observation


def fixture(root):
    for name in ('src/specroad','tests','tools','verification'):
        (root/name).mkdir(parents=True)
    (root/'pyproject.toml').write_text('')
    (root/'tests/test_one.py').write_text('def test_one(): pass\n')
    return ['tests/test_one.py']


def observation():
    return {'observation_format_version':1, 'engine':'pytest', 'nodeids':['tests/test_one.py::test_one'],
            'nodeid_to_test_id':{'tests/test_one.py::test_one':'tests/test_one.py::test_one'},
            'test_outcomes':{'tests/test_one.py::test_one':'passed'},
            'suite_passed':True,'errors':[], 'tests_run':1,'pytest_exit_code':0,
            'worker_test_counts':{'gw0':1}}


def fake(calls, data=None, code=0):
    def start(cmd, **kw):
        calls.append((cmd,kw))
        Path(cmd[cmd.index('--sr-observations')+1]).write_text(json.dumps(observation() if data is None else data))
        return SimpleNamespace(returncode=code)
    return start


def test_explicit_files_only(tmp_path):
    names=fixture(tmp_path)
    assert selected_files(tmp_path,names)==tuple(names)


def test_bad_paths_rejected(tmp_path):
    fixture(tmp_path)
    for name in ('tests','tests/*.py','../tests/test_one.py','tests/test_one.py::test_one', '/tests/test_one.py'):
        with pytest.raises((ValueError,OSError)): selected_files(tmp_path,[name])


def test_duplicates_rejected(tmp_path):
    names=fixture(tmp_path)
    with pytest.raises(ValueError): selected_files(tmp_path,names*2)


def test_selected_success_is_not_a_full_pass(tmp_path):
    names=fixture(tmp_path); calls=[]
    result=run_selected(tmp_path,names,tmp_path/'build/run',expected=1,runner=fake(calls))
    assert result['selected_passed'] and result['full_suite_passed'] is None
    assert result['test_scope']=='selected_files_only'
    assert len(calls)==1 and calls[0][0][-1]=='tests/test_one.py'
    assert '--sr-gate' not in calls[0][0] and '--sr-evidence' not in calls[0][0]
    assert calls[0][0][calls[0][0].index('-n')+1]=='4'
    assert 'timeout' not in calls[0][1]


def test_skip_is_not_accepted(tmp_path):
    names=fixture(tmp_path); data=observation();data['test_outcomes']['tests/test_one.py::test_one']='skipped'
    assert not run_selected(tmp_path,names,tmp_path/'build/run',expected=1,runner=fake([],data))['selected_passed']


def test_nonzero_process_fails_even_with_green_report(tmp_path):
    names=fixture(tmp_path)
    assert run_selected(tmp_path,names,tmp_path/'build/run',expected=1,runner=fake([],code=1))['exit_code']==1


def test_expected_count_is_enforced():
    with pytest.raises(ValueError): verify_observation(observation(),['tests/test_one.py'],2)


def test_source_change_invalidates_observation(tmp_path):
    names=fixture(tmp_path)
    def start(cmd,**kw):
        result=fake([])(cmd,**kw)
        (tmp_path/'tests/test_one.py').write_text('changed')
        return result
    assert not run_selected(tmp_path,names,tmp_path/'build/run',expected=1,runner=start)['selected_passed']


def test_serial_selected_run_disallowed(tmp_path):
    names=fixture(tmp_path)
    with pytest.raises(ValueError): run_selected(tmp_path,names,tmp_path/'build/run',expected=1,workers=0)
    assert not (tmp_path/'build/run').exists()


def test_existing_reports_preserved(tmp_path):
    names=fixture(tmp_path); target=tmp_path/'build/run';target.mkdir(parents=True)
    (target/'selection.json').write_text('preserved')
    with pytest.raises(FileExistsError): run_selected(tmp_path,names,target,expected=1,runner=fake([]))
    assert (target/'selection.json').read_text()=='preserved'
