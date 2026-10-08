"""Recovery retries retain proof; independent normal calls reread their basis."""
import json
import os

import pytest

from specroad.changes import (PublicationAuthority, PublicationCheckError, RecoveryAuthority,
    begin_building_journal, prepare_publication_check, project_lock, request_receipt_path)
from specroad.cli.contracts import CommandClass
from support.automatic_recovery import pending, writer, current_model, fresh_process
from support.folds import edit
from support.publication import TRANSACTION, ALLOW as WRITE, files
from support.read_only import inventory, no_write_attempts
from support.targets import POLICY, plan
from test_transaction_preflight import automatic, NEW_REQUEST


RECOVER_PROCESS = '''
from test_transaction_preflight import automatic
print(json.dumps(automatic(root).data))
'''


@pytest.mark.parametrize('state', ['prepared', 'partial', 'complete', 'committed'])
def test_new_process_rechecks_basis_then_publishes_only_the_new_request(tmp_path, state):
    source, old, expected = pending(tmp_path, state)
    recovered = fresh_process(tmp_path, RECOVER_PROCESS)
    assert recovered['exit_code'] == 5 and recovered['requires_new_invocation']
    assert recovered['recovery_completed'] and not recovered['normal_operation_started']
    assert not recovered['request_consumed']
    assert files(tmp_path) == expected
    receipt = tmp_path / request_receipt_path(NEW_REQUEST)
    assert not receipt.exists()
    observed = fresh_process(tmp_path, '''
from support.automatic_recovery import current_model
from test_transaction_preflight import automatic, NEW_REQUEST
from support.targets import plan, POLICY
from support.folds import edit
from support.publication import ALLOW, files
from specroad.changes import (project_lock, prepare_publication_check, begin_building_journal,
    stage_building_journal, publish_prepared_journal, finalize_committing_journal,
    cleanup_completed_transaction, CommittingJournal)
gate = automatic(root).data
assert gate['exit_code'] == 0 and not gate['write_authorized']
model = current_model(root)
change = plan(model, [edit(model.artifacts[0], 'Fresh separate invocation')], request_id=NEW_REQUEST)
check = prepare_publication_check(change, model, policy=POLICY)
tx = 'separate-new-transaction'
with project_lock(root, kind='writer', command='change apply', project_id='sample',
                  request_id=NEW_REQUEST, transaction_id=tx) as held:
    journal = begin_building_journal(check, held_lock=held, transaction_id=tx, authority=ALLOW)
    journal = stage_building_journal(check, journal, held_lock=held, authority=ALLOW)
    publish_prepared_journal(check, journal, held_lock=held, authority=ALLOW)
    journal = CommittingJournal((root / journal.path).read_bytes())
    finalize_committing_journal(check, journal, held_lock=held, authority=ALLOW)
    result = cleanup_completed_transaction(check, tx, held_lock=held, authority=ALLOW).data
print(json.dumps({'gate': gate, 'result': result, 'new_request': NEW_REQUEST,
    'basis': change.data['base']['model_root_sha256'], 'target': change.data['expected_result']['model_root_sha256']}))
''')
    assert observed['result']['commit_completed'] and observed['result']['cleanup_completed']
    assert observed['basis'] != observed['target']
    assert observed['basis'] == (old.data['expected_result']['model_root_sha256']
        if state in ('complete', 'committed') else old.data['base']['model_root_sha256'])
    assert receipt.exists()
    after = files(tmp_path)
    changed = [p for p in after if after[p] != expected[p]]
    assert changed == [source.documents[0].path]
    value = json.loads(after[changed[0]])
    assert value['statement'] == 'Fresh separate invocation'
    assert value['title'] == json.loads(expected[changed[0]])['title']
    assert value['revision'] == json.loads(expected[changed[0]])['revision'] + 1


@pytest.mark.parametrize('state', ['partial', 'complete', 'committed'])
def test_old_publication_observation_cannot_survive_recovery_without_live_recheck(tmp_path, state):
    checks = []

    def capture(model):
        change = plan(model, [edit(model.artifacts[0], 'Unstarted stale request')], request_id=NEW_REQUEST)
        checks.append(prepare_publication_check(change, model, policy=POLICY))

    with writer(tmp_path, state, on_basis=capture):
        pass
    assert fresh_process(tmp_path, RECOVER_PROCESS)['recovery_completed']
    assert automatic(tmp_path).exit_code == 0
    before = inventory(tmp_path)
    with project_lock(tmp_path, kind='writer', command='change apply', project_id='sample',
                      request_id=NEW_REQUEST, transaction_id='next-transaction') as held:
        with no_write_attempts(), pytest.raises(PublicationCheckError) as error:
            begin_building_journal(checks[0], held_lock=held,
                transaction_id='next-transaction', authority=WRITE)
    assert error.value.exit_code == 6
    assert inventory(tmp_path) == before
    assert not (tmp_path / request_receipt_path(NEW_REQUEST)).exists()


def test_fresh_clear_gate_and_prior_recovery_do_not_replace_current_write_authority(tmp_path):
    pending(tmp_path)
    assert fresh_process(tmp_path, RECOVER_PROCESS)['recovery_completed']
    assert automatic(tmp_path).exit_code == 0
    model = current_model(tmp_path)
    check = prepare_publication_check(plan(model, [edit(model.artifacts[0], 'Denied')],
                                          request_id=NEW_REQUEST), model, policy=POLICY)
    before = inventory(tmp_path)
    denied = PublicationAuthority('new-write-denied', '1', lambda request: False)
    with project_lock(tmp_path, kind='writer', command='change apply', project_id='sample',
                      request_id=NEW_REQUEST, transaction_id='next-transaction') as held:
        with no_write_attempts(), pytest.raises(PublicationCheckError) as error:
            begin_building_journal(check, held_lock=held, transaction_id='next-transaction', authority=denied)
    assert error.value.exit_code == 7 and inventory(tmp_path) == before


@pytest.mark.parametrize('state', ['prepared', 'partial', 'complete'])
def test_normal_request_cannot_alias_the_recovered_transaction_request(tmp_path, state):
    source, change, expected = pending(tmp_path, state)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = automatic(tmp_path, request_id=change.data['request_id']).data
    assert result['exit_code'] == 6 and result['reason'] == 'preflight_request_id_conflicts_with_recovery'
    assert not result['recovery_attempted'] and not result['request_consumed']
    assert inventory(tmp_path) == before


def interrupted_archive(root, state, monkeypatch, *, after):
    values = pending(root, state)
    native, fired = os.rename, []

    def interrupt(src, dst, **kwargs):
        if src == TRANSACTION and dst == 'work' and not fired:
            fired.append(True)
            if after:
                native(src, dst, **kwargs)
            raise OSError(5, 'Interrupted terminal archival')
        return native(src, dst, **kwargs)

    with monkeypatch.context() as faults:
        faults.setattr(os, 'rename', interrupt)
        first = automatic(root).data
    assert fired and first['exit_code'] == 5 and first['mutation_possible'], first
    assert not first['recovery_completed'] and not first['normal_operation_started']
    return values


@pytest.mark.parametrize('state', ['prepared', 'partial', 'complete'])
@pytest.mark.parametrize('after', [False, True])
def test_interrupted_archive_reuses_exact_proof_and_requires_another_normal_invocation(tmp_path, monkeypatch, state, after):
    source, change, expected = interrupted_archive(tmp_path, state, monkeypatch, after=after)
    assert files(tmp_path) == expected
    before = inventory(tmp_path)
    intents = {p: (p.read_bytes(), p.stat().st_ino) for p in
               (tmp_path / '.specroad/recovery/transaction-audit').rglob('intent.json')}
    with no_write_attempts():
        read = automatic(tmp_path, command_class=CommandClass.READ_ONLY).data
    assert read['exit_code'] == 5 and inventory(tmp_path) == before
    recovered = fresh_process(tmp_path, RECOVER_PROCESS)
    assert recovered['exit_code'] == 5 and recovered['recovery_completed'], recovered
    assert recovered['requires_new_invocation'] and not recovered['request_consumed']
    assert files(tmp_path) == expected
    assert all((p.read_bytes(), p.stat().st_ino) == value for p, value in intents.items())
    assert not list((tmp_path / '.specroad/recovery').glob('pending-*'))
    assert not (tmp_path / request_receipt_path(NEW_REQUEST)).exists()
    assert automatic(tmp_path).exit_code == 0


@pytest.mark.parametrize('state', ['prepared', 'complete'])
@pytest.mark.parametrize('field', ['project_id', 'transaction_id', 'journal_sha256', 'intent', 'unknown'])
def test_corrupt_pending_selection_never_repairs_or_follows_untrusted_references(tmp_path, monkeypatch, state, field):
    interrupted_archive(tmp_path, state, monkeypatch, after=True)
    barrier, = (tmp_path / '.specroad/recovery').glob('pending-*')
    value = json.loads(barrier.read_bytes())
    value[field] = ({'path': '../../foreign.json', 'sha256': '0' * 64} if field == 'intent'
                    else '0' * 64 if field == 'journal_sha256' else 'foreign')
    barrier.write_text(json.dumps(value))
    before = inventory(tmp_path)
    with no_write_attempts():
        result = automatic(tmp_path).data
    assert result['exit_code'] == 6 and not result['recovery_attempted'], result
    assert not result['normal_operation_started'] and inventory(tmp_path) == before


def test_foreign_active_transaction_prevents_automatic_pending_cleanup(tmp_path, monkeypatch):
    interrupted_archive(tmp_path, 'complete', monkeypatch, after=False)
    foreign = tmp_path / '.specroad/transactions/foreign'
    foreign.mkdir()
    (foreign / 'journal.json').write_bytes(b'unproved foreign work')
    before = inventory(tmp_path)
    with no_write_attempts():
        result = automatic(tmp_path).data
    assert result['exit_code'] == 5 and result['reason'] == 'explicit_recovery_selection_required'
    assert not result['recovery_attempted'] and inventory(tmp_path) == before


@pytest.mark.parametrize('change', ['configuration', 'active_transaction'])
def test_recovery_authorization_cannot_replace_the_selected_context(tmp_path, change):
    pending(tmp_path)
    old = tmp_path / '.specroad/transactions' / TRANSACTION / 'journal.json'
    original = old.read_bytes()

    def authorize(request):
        if change == 'configuration':
            path = tmp_path / 'specroad.json'
            value = json.loads(path.read_bytes())
            value['project_id'] = 'changed-project'
            path.write_text(json.dumps(value))
        else:
            (tmp_path / '.specroad/transactions/other').mkdir()
        return True

    result = automatic(tmp_path, authority=RecoveryAuthority('changing-host', '1', authorize)).data
    assert result['exit_code'] == 6 and not result['recovery_attempted']
    assert result['reason'] == ('preflight_configuration_changed' if change == 'configuration'
                                else 'preflight_operational_metadata_changed')
    assert old.read_bytes() == original
    assert not (tmp_path / request_receipt_path(NEW_REQUEST)).exists()


@pytest.mark.parametrize('owner_state', ['foreign', 'unverifiable', 'pid_reused'])
def test_unproven_owner_record_cannot_enable_automatic_takeover(tmp_path, owner_state):
    lock = tmp_path / '.specroad/locks/project.json'
    with writer(tmp_path):
        record = json.loads(lock.read_bytes())
    if owner_state == 'foreign':
        record['host_id'] = 'definitely-another-test-host'
    elif owner_state == 'unverifiable':
        record['host_id'] = None
    else:
        record['process_start_id'] = 'a-different-process-start'
    lock.write_text(json.dumps(record))
    before = inventory(tmp_path)
    with no_write_attempts():
        result = automatic(tmp_path).data
    assert result['exit_code'] == 5 and result['owner_state'] == owner_state
    assert not result['recovery_attempted'] and inventory(tmp_path) == before
