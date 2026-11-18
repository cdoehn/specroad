"""Independent copy groups, canonical reads and immutable failed measurements."""
from copy import deepcopy
import json
import sqlite3

import pytest

from dev.test_hosts.speculative_choice import choose
from dev.status.monitor_data import run_tests, history as monitor_history
from dev.status.test_time import ranking
from verification_support.runtime_history import RuntimeHistory
from test_speculative_tests import rows, start, phases, confirmation


def test_balanced_rounds_reserve_before_next_worker_and_use_stable_identity():
    active = rows(('z','one'), ('a','two'))
    identities = {'z':'first','a':'second'}
    for host in ['three','one','two','three']:
        node = choose(host, {'one','two','three'}, active, identities=identities)
        assert node is not None
        active.append(dict(nodeid=node,host=host))
        sizes = [sum(r['nodeid']==n for r in active) for n in identities]
        assert max(sizes)-min(sizes) <= 1
    assert all(choose(host, {'one','two','three'}, active) is None for host in ('one','two','three'))
    assert choose('three', {'one','two','three'}, rows(('z','one'),('a','one')), identities=identities) == 'z'


@pytest.mark.parametrize('fault', ['failed','subtest','duplicate','unresolved'])
def test_passing_winner_cannot_validate_failed_or_unknown_copy(tmp_path, fault):
    with RuntimeHistory(tmp_path) as h:
        old = h.begin('a'*64,1)
        h.start(old,'node','identity','gw0'); phases(h,old,'gw0',99)
        run = h.begin('b'*64,2); h.enable_copies(run)
        start(h,run,'gw0','a'*32); start(h,run,'gw1','b'*32)
        if fault == 'failed':
            h.observe(run,'node','identity','gw0','setup',1,'failed')
        elif fault == 'subtest':
            h.observe(run,'node','identity','gw0','call',1,'failed',subtest=True)
        elif fault == 'duplicate':
            for _ in range(2): h.observe(run,'node','identity','gw0','setup',1,'passed')
        phases(h,run,'gw1',2); assert h.complete_copy(run,'node','gw1','b'*32)
        if fault != 'unresolved':
            h.cancel_copy(run,'node','identity','gw0','a'*32,confirmation('a'*32))
        with pytest.raises(ValueError): h.verify_run(run,{'node':'identity'},{'identity':'passed'})
        assert h.snapshot(['identity'])['tests'][0]['duration_ns'] is None
        assert ranking(h.path)['valid_measurements']==0
        assert not monitor_history(h.path)[0]['valid_measurement']


def test_first_completed_not_newest_started_supplies_measurement_and_monitor(tmp_path):
    with RuntimeHistory(tmp_path) as h:
        run=h.begin('a'*64,2); h.enable_copies(run)
        start(h,run,'gw0','a'*32,host='one'); start(h,run,'gw1','b'*32,host='two')
        phases(h,run,'gw0',2); assert h.complete_copy(run,'node','gw0','a'*32)
        phases(h,run,'gw1',5); assert not h.complete_copy(run,'node','gw1','b'*32)
        h.verify_run(run,{'node':'identity'},{'identity':'passed'})
        assert h.snapshot(['identity'])['tests'][0]['duration_ns']==6_000_000_000
        assert ranking(h.path)['tests'][0]['duration_ns']==6_000_000_000
        current=monitor_history(h.path)
        assert len(current)==1 and current[0]['host']=='one' and current[0]['total_seconds']==6
        h.db.row_factory=sqlite3.Row
        bound=dict(h.db.execute('SELECT * FROM runs WHERE id=?',(run,)).fetchone())
        values,_=run_tests(h.path,bound)
        assert len(values)==2
        assert [(v['host'],v['copy_role'],v['copy_state']) for v in values]==[('one','winner','complete'),('two','copy','complete')]


def test_migration_retains_original_values_and_does_not_allow_unbound_duplicates(tmp_path):
    with RuntimeHistory(tmp_path) as h:
        old=h.begin('a'*64,1); h.start(old,'node','identity','gw0'); phases(h,old,'gw0')
        original={t:h.db.execute('SELECT * FROM '+t).fetchall() for t in ('runs','attempts','phases')}
        run=h.begin('b'*64,2); h.enable_copies(run)
        for table, values in original.items():
            assert h.db.execute('SELECT * FROM '+table).fetchall()[:len(values)]==values
        assert h.db.execute('PRAGMA foreign_key_check').fetchall()==[]
        start(h,run,'gw0','a'*32)
        with pytest.raises(sqlite3.IntegrityError): h.authorize_copy(run,'node','gw1','a'*32)
        with pytest.raises(ValueError): h.authorize_copy(run,'node','foreign','b'*32)
        phases(h,run,'gw0'); h.complete_copy(run,'node','gw0','a'*32)
        with pytest.raises(ValueError): h.authorize_copy(run,'node','gw1','b'*32)


def test_manual_move_in_copy_enabled_run_retains_successor_proof(tmp_path):
    with RuntimeHistory(tmp_path) as h:
        run=h.begin('a'*64,2); h.enable_copies(run)
        start(h,run,'gw0','a'*32)
        h.cancel(run,'node','identity','gw0','gw1','a'*32,confirmation('a'*32))
        start(h,run,'gw1','b'*32); phases(h,run,'gw1')
        h.complete_copy(run,'node','gw1','b'*32)
        h.verify_run(run,{'node':'identity'},{'identity':'passed'})
        h.db.execute('UPDATE attempt_moves SET successor=NULL'); h.db.commit()
        with pytest.raises(ValueError): h.verify_run(run,{'node':'identity'},{'identity':'passed'})


def test_latest_new_run_hides_older_copy_group_even_if_older_finishes_late(tmp_path):
    with RuntimeHistory(tmp_path) as h:
        old=h.begin('a'*64,2); h.enable_copies(old); start(h,old,'gw0','a'*32)
        new=h.begin('b'*64,1); h.start(new,'node','identity','gw0')
        phases(h,old,'gw0'); h.complete_copy(old,'node','gw0','a'*32)
        assert h.snapshot(['identity'])['tests'][0]['duration_ns'] is None


def test_live_status_retains_full_identifiers_for_multiple_copies(tmp_path):
    from dev.test_control.store import Owner
    from dev.test_control.view import read_status
    owner=Owner(tmp_path/'apply', {'one':4}, {'one':4}, home=tmp_path/'private')
    try:
        node='tests/test_subject.py::test_one['+'q'*280000+']'
        attempts={str(i):dict(nodeid=node,worker='gw'+str(i),host='one',state='running') for i in range(4)}
        owner.publish({},attempts=attempts)
        observed=read_status(tmp_path/'apply',home=tmp_path/'private')
        assert observed['attempts']==attempts and observed['active']
    finally:
        owner.close()
