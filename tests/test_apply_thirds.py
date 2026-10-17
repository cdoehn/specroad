"""Stable modulo-three groups bound to actual successful first-parent commits."""
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from verification_support import apply_rotation as rotation
from verification_support.process_environment import test_environment as controlled_environment
from test_apply_rotation import ANCHOR, NEXT, PAIRS, git_reader, registry

AFTER = 'c' * 40


def thirds(ids=None):
    return {**registry(ids), 'format_version': 2, 'partition_count': 3, 'rotation_anchor_commit': NEXT}


def test_three_groups_partition_stable_numbers_and_repeat_only_after_three_commits():
    value = thirds()
    parts = [rotation.select_partition(PAIRS, value, n, value if n else registry()) for n in range(9)]
    for n, part in enumerate(parts):
        assert set(part.values()) == {f'case.{i}' for i in range(6) if i % 3 == n % 3}
    assert parts[0] | parts[1] | parts[2] == PAIRS
    assert not parts[0].keys() & parts[1].keys() and not parts[1].keys() & parts[2].keys()
    assert not parts[0].keys() & parts[2].keys()
    assert parts[0] == parts[3] == parts[6]


def test_migration_preserves_all_existing_numbers_and_appends_new_ids():
    current = {n: i for n, i in PAIRS.items() if i != 'case.2'}
    current['tests/test_added.py::test_added'] = 'case.-1'
    previous = registry(); value = thirds([*previous['test_ids'], 'case.-1'])
    numbers = rotation.validate_registry(value, current.values(), previous)
    assert numbers == {**{f'case.{i}': i for i in range(6)}, 'case.-1': 6}
    assert set(rotation.select_partition(current, value, 0, previous).values()) == {'case.0', 'case.3', 'case.-1'}
    assert value['test_ids'][2] == 'case.2'


def test_same_head_retry_keeps_group_zero_and_successful_commits_advance_from_new_anchor(tmp_path):
    value = thirds(); before = git_reader(tmp_path, [NEXT, ANCHOR], registry())
    for _ in range(2):
        head, sequence, previous = rotation.commit_context(tmp_path, value, runner=before)
        assert (head, sequence, previous) == (NEXT, 0, registry())
        assert set(rotation.select_partition(PAIRS, value, sequence, previous).values()) == {'case.0', 'case.3'}
    head, sequence, previous = rotation.commit_context(tmp_path, value,
        runner=git_reader(tmp_path, [AFTER, NEXT, ANCHOR], value))
    assert head == AFTER and sequence == 1 and previous == value
    assert set(rotation.select_partition(PAIRS, value, sequence, previous).values()) == {'case.1', 'case.4'}


@pytest.mark.parametrize('case', ['count_bool', 'count_two', 'count_four', 'missing_anchor', 'bad_anchor',
    'unknown', 'reorder', 'drop_old', 'duplicate', 'reset_number_anchor'])
def test_invalid_migration_contract_cannot_renumber_or_choose_a_different_fraction(case):
    value = thirds()
    if case == 'count_bool': value['partition_count'] = True
    elif case == 'count_two': value['partition_count'] = 2
    elif case == 'count_four': value['partition_count'] = 4
    elif case == 'missing_anchor': del value['rotation_anchor_commit']
    elif case == 'bad_anchor': value['rotation_anchor_commit'] = 'not-a-commit'
    elif case == 'unknown': value['selection'] = [0]
    elif case == 'reorder': value['test_ids'].reverse()
    elif case == 'drop_old': value['test_ids'].pop(2)
    elif case == 'duplicate': value['test_ids'].append('case.0')
    else: value['anchor_commit'] = NEXT
    with pytest.raises(ValueError): rotation.select_partition(PAIRS, value, 0, registry())


@pytest.mark.parametrize('case', ['old_migration_anchor', 'missing_rotation_anchor', 'earlier_than_number_anchor',
    'restart_committed', 'rollback_to_halves', 'migration_sequence'])
def test_rotation_cannot_restart_or_use_unbound_history(tmp_path, case):
    value = thirds(); previous = registry(); history = [NEXT, ANCHOR]; sequence = 0
    if case == 'old_migration_anchor': value['rotation_anchor_commit'] = ANCHOR
    elif case == 'missing_rotation_anchor': value['rotation_anchor_commit'] = AFTER
    elif case == 'earlier_than_number_anchor': history = [ANCHOR, NEXT]
    elif case == 'restart_committed':
        previous = thirds(); value['rotation_anchor_commit'] = AFTER; history = [AFTER, NEXT, ANCHOR]
    elif case == 'rollback_to_halves': previous = thirds(); value = registry()
    else: sequence = 1
    with pytest.raises(ValueError):
        if case != 'migration_sequence':
            _, sequence, previous = rotation.commit_context(tmp_path, value,
                runner=git_reader(tmp_path, history, previous))
        rotation.select_partition(PAIRS, value, sequence, previous)


@pytest.mark.parametrize('group', [0, 1, 2])
def test_three_group_reports_are_explicit_partial_results_without_even_odd_labels(tmp_path, monkeypatch, group):
    root = tmp_path/'repo'; (root/'verification').mkdir(parents=True)
    value = thirds(); (root/rotation.REGISTRY).write_text(json.dumps(value))
    catalog = {'source_sha256': 'bound', 'collected_tests': 6, 'nodeid_to_test_id': PAIRS}
    monkeypatch.setattr(rotation, 'run_catalog_preflight', lambda root,path:path.write_text(json.dumps(catalog)) or True)
    monkeypatch.setattr(rotation, 'commit_context', lambda *a:(NEXT,group,value))
    monkeypatch.setattr(rotation, 'source_identity', lambda root:'bound')
    outdir=tmp_path/'reports'; calls=[]
    selected={n:i for n,i in PAIRS.items() if int(i[-1]) % 3 == group}
    def execute(command, **kwargs):
        calls.append(command)
        observation={'observation_format_version':1,'engine':'pytest','nodeids':list(selected),
            'nodeid_to_test_id':selected,'test_outcomes':{i:'passed' for i in selected.values()},
            'suite_passed':True,'errors':[],'tests_run':2,'pytest_exit_code':0,
            'worker_test_counts':{'gw0':1,'gw1':1}}
        (outdir/'observations.json').write_text(json.dumps(observation))
        return SimpleNamespace(returncode=0)
    report=rotation.run_apply_partition(root,outdir,runner=execute)
    assert len(calls)==1 and report['selected_passed'] and report['full_suite_passed'] is None
    assert report['format_version']==2 and report['test_scope']=='stable_modulo_partition'
    assert report['partition_count']==3 and report['partition_index']==group
    assert report['rotation_anchor_commit']==NEXT and report['anchor_commit']==ANCHOR
    assert report['expected_tests']==2 and report['collected_tests']==6 and 'parity' not in report
    assert report['nodeid_to_test_id']==selected
    assert (outdir/'nodeids.txt').read_text().splitlines()==list(selected)
    assert json.loads((root/rotation.REGISTRY).read_text())==value


@pytest.mark.parametrize(('group','failing'), [(0,False),(1,False),(2,False),(2,True)])
def test_real_parallel_runner_executes_exactly_one_third_and_retains_failure(tmp_path, group, failing):
    root=Path(__file__).resolve().parents[1]
    (tmp_path/'pytest.ini').write_text('[pytest]\n')
    (tmp_path/'test_sample.py').write_text('\n'.join(
        f'def test_{n}():\n    assert {not (failing and n==2)}\n' for n in range(6)))
    selected=[f'test_sample.py::test_{n}' for n in range(6) if n % 3 == group]
    (tmp_path/'nodeids.txt').write_text('\n'.join(selected)+'\n')
    command=rotation.parallel_command(root,tmp_path,2,2)
    command[-1:-1]=['-c',str(tmp_path/'pytest.ini'),'--confcutdir',str(tmp_path),'-p','verification_support.pytest_backend']
    process=subprocess.run(command,cwd=tmp_path,env=controlled_environment(os.environ),
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    observed=json.loads((tmp_path/'observations.json').read_text())
    assert process.returncode==(1 if failing else 0)
    assert set(observed['nodeids'])==set(selected) and observed['tests_run']==2
    assert observed['suite_passed'] is (not failing)
    assert all(name.startswith('gw') for name in observed['worker_test_counts'])
