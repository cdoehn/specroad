"""Recovery retries retain proof; independent normal calls reread their basis."""
from contextlib import ExitStack
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
    pending(tmp_path, state)
    before = inventory(tmp_path)
    observed = fresh_process(tmp_path, RECOVER_PROCESS)
    assert observed['exit_code'] == 5 and observed['project_corrupted']
    assert not observed['recovery_completed'] and not observed['normal_operation_started']
    assert not observed['request_consumed'] and inventory(tmp_path) == before
    assert not (tmp_path / request_receipt_path(NEW_REQUEST)).exists()


@pytest.mark.parametrize('state', ['partial', 'complete', 'committed'])
def test_old_publication_observation_cannot_survive_recovery_without_live_recheck(tmp_path, state):
    checks = []
    def capture(model):
        change = plan(model, [edit(model.artifacts[0], 'Unstarted stale request')], request_id=NEW_REQUEST)
        checks.append(prepare_publication_check(change, model, policy=POLICY))
    with writer(tmp_path, state, on_basis=capture): pass
    before = inventory(tmp_path)
    assert fresh_process(tmp_path, RECOVER_PROCESS)['project_corrupted']
    from specroad.model.errors import ModelError
    with no_write_attempts(), pytest.raises(ModelError):
        with project_lock(tmp_path, kind='writer', command='change apply', project_id='sample',
                          request_id=NEW_REQUEST, transaction_id='next-transaction') as held:
            begin_building_journal(checks[0], held_lock=held, transaction_id='next-transaction', authority=WRITE)
    assert inventory(tmp_path) == before and not (tmp_path / request_receipt_path(NEW_REQUEST)).exists()


def test_fresh_clear_gate_and_prior_recovery_do_not_replace_current_write_authority(tmp_path):
    from support.publication import prepared
    model, _, _ = prepared(tmp_path)
    assert automatic(tmp_path).exit_code == 0
    (tmp_path / '.specroad/locks').mkdir(parents=True, exist_ok=True)
    check = prepare_publication_check(plan(model, [edit(model.artifacts[0], 'Denied')],
                                          request_id=NEW_REQUEST), model, policy=POLICY)
    before = inventory(tmp_path)
    denied = PublicationAuthority('new-write-denied', '1', lambda request: False)
    with project_lock(tmp_path, kind='writer', command='change apply', project_id='sample',
                      request_id=NEW_REQUEST, transaction_id='next-transaction') as held:
        with no_write_attempts(), pytest.raises(PublicationCheckError) as error:
            from specroad.changes.guarded_write import publish_guarded_change
            publish_guarded_change(check, held_lock=held, authority=denied)
    assert error.value.exit_code == 7 and inventory(tmp_path) == before


@pytest.mark.parametrize('state', ['prepared', 'partial', 'complete'])
def test_normal_request_cannot_alias_the_recovered_transaction_request(tmp_path, state):
    source, change, expected = pending(tmp_path, state)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = automatic(tmp_path, request_id=change.data['request_id']).data
    assert result['exit_code'] == 5 and result['reason'] == 'project_corrupted'
    assert not result['recovery_attempted'] and not result['request_consumed']
    assert inventory(tmp_path) == before


def interrupted_archive(root, state, monkeypatch, *, after):
    # Explicit damaged legacy metadata is an input, never a fabricated success.
    values = pending(root, state)
    folder = root / '.specroad/recovery'; folder.mkdir(exist_ok=True, parents=True)
    (folder / 'pending-test.json').write_text(json.dumps({'state':state,'after':after}))
    return values


@pytest.mark.parametrize('state', ['prepared', 'partial', 'complete'])
@pytest.mark.parametrize('after', [False, True])
def test_interrupted_archive_reuses_exact_proof_and_requires_another_normal_invocation(tmp_path, monkeypatch, state, after):
    interrupted_archive(tmp_path, state, monkeypatch, after=after)
    before = inventory(tmp_path)
    with no_write_attempts(): read = automatic(tmp_path, command_class=CommandClass.READ_ONLY).data
    observed = fresh_process(tmp_path, RECOVER_PROCESS)
    assert read['exit_code'] == observed['exit_code'] == 5
    assert observed['project_corrupted'] and not observed['recovery_attempted']
    assert not observed['request_consumed'] and inventory(tmp_path) == before
    assert (tmp_path / '.specroad/recovery/pending-test.json').exists()


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
    assert result['exit_code'] == 5 and not result['recovery_attempted'], result
    assert not result['normal_operation_started'] and inventory(tmp_path) == before


def test_foreign_active_transaction_prevents_automatic_pending_cleanup(tmp_path, monkeypatch):
    interrupted_archive(tmp_path, 'complete', monkeypatch, after=False)
    foreign = tmp_path / '.specroad/transactions/foreign'
    foreign.mkdir()
    (foreign / 'journal.json').write_bytes(b'unproved foreign work')
    before = inventory(tmp_path)
    with no_write_attempts():
        result = automatic(tmp_path).data
    assert result['exit_code'] == 5 and result['reason'] == 'project_corrupted'
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

    before = inventory(tmp_path)
    result = automatic(tmp_path, authority=RecoveryAuthority('changing-host', '1', authorize)).data
    assert result['exit_code'] == 5 and not result['recovery_attempted']
    assert result['reason'] == 'project_corrupted' and inventory(tmp_path) == before
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
