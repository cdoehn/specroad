"""One native crash matrix for multi-file writes, receipts and recovery restarts."""
import json
import pytest

from specroad.changes import (transaction_preflight, transaction_receipt_path,
    request_receipt_path, TransactionReceipt, RequestReceipt)
from specroad.cli.contracts import CommandClass
from support.writer_boundaries import (PHASES, CRASH_EXIT, SENTINEL,
    SENTINEL_BYTES, child, journal_at)
from support.publication import files, TRANSACTION
from support.recovery import RECOVER, tree
from support.targets import ACTOR


def control(root):
    return child(root, 'writer', '', -1, 'multi')


def cut_writer(root, event):
    bound, stopped = child(root, 'writer', event['phase'], event['ordinal'],
                           'multi', exit_code=CRASH_EXIT)
    assert stopped['cut'] == event
    return bound


def assert_result(bound, recovered):
    outcome = recovered['outcome']
    assert outcome in ('base', 'target', 'blocked_before_journal')
    side = 'after' if outcome == 'target' else 'before'
    assert recovered['files'] == bound[side]
    assert recovered['model_root'] == bound['target_root' if side == 'after' else 'base_root']
    assert bytes.fromhex(recovered['files'][SENTINEL]) == SENTINEL_BYTES


def select(trace, scenario):
    events = trace['events']
    if scenario == 'discard':
        return [e for e in events if e['phase'] == 'staging'][-1]
    if scenario == 'receipts':
        return next(e for e in events if e['phase'] == 'receipts' and e['operation'] == 'fsync'
                    and e['paths'][0].endswith('/journal.complete'))
    targets = [e for e in events if e['phase'] == 'publishing' and e['operation'] == 'replace'
               and e['paths'][1].startswith('spec/')]
    assert len(targets) == 3
    return targets[0 if scenario == 'rollback' else -1]


@pytest.mark.parametrize('phase', PHASES)
def test_multi_file_writer_boundaries_never_accept_a_mixed_model(tmp_path, phase):
    _, trace = control(tmp_path / 'control')
    events = [e for e in trace['events'] if e['phase'] == phase]
    assert events
    outcomes, mixed = [], 0
    for event in events:
        root = tmp_path / ('cut-' + str(event['ordinal']))
        bound = cut_writer(root, event)
        live = {p: b.hex() for p, b in files(root).items()}
        if live not in (bound['before'], bound['after']):
            mixed += 1
            before = tree(root)
            blocked = transaction_preflight(root, command_class=CommandClass.READ_ONLY).data
            assert blocked['exit_code'] != 0 and not blocked['transaction_preflight_passed']
            assert tree(root) == before
        recovered, = child(root, 'recover')
        assert_result(bound, recovered)
        if recovered['outcome'] == 'blocked_before_journal':
            assert phase == 'building'
        outcomes.append({**event, 'outcome': recovered['outcome']})
    if phase == 'publishing':
        assert mixed > 0
        assert {row['outcome'] for row in outcomes} == {'base', 'target'}
    (tmp_path / 'multi-writer-boundaries.json').write_text(json.dumps(outcomes, indent=2) + '\n')


@pytest.mark.parametrize('missing', ['transaction', 'request', 'both'])
def test_missing_receipts_before_committed_marker_are_reconstructed_exactly(tmp_path, missing):
    _, trace = control(tmp_path / 'control')
    root = tmp_path / 'project'
    bound = cut_writer(root, select(trace, 'receipts'))
    journal = journal_at(root)
    paths = {'transaction': root / transaction_receipt_path(TRANSACTION),
             'request': root / request_receipt_path(journal.data['request_id'])}
    originals = {name: path.read_bytes() for name, path in paths.items()}
    for name in paths if missing == 'both' else [missing]:
        paths[name].unlink()
    recovered, = child(root, 'recover')
    assert recovered['outcome'] == 'target'
    assert_result(bound, recovered)
    assert {name: path.read_bytes() for name, path in paths.items()} == originals
    transaction = TransactionReceipt(originals['transaction'])
    request = RequestReceipt(originals['request'])
    assert transaction.data['result_object'] == request.data['result_object']
    assert len(transaction.data['result_object']['published_paths']) == 3


@pytest.mark.parametrize('receipt', ['transaction', 'request'])
@pytest.mark.parametrize('change', ['missing', 'foreign'])
def test_damaged_receipt_after_committed_marker_keeps_target_blocked_and_evidence(tmp_path, receipt, change):
    _, trace = control(tmp_path / 'control')
    event = next(e for e in trace['events'] if e['phase'] == 'receipts'
                 and e['operation'] == 'replace' and e['paths'][0].endswith('/journal.complete'))
    root = tmp_path / 'project'
    bound = cut_writer(root, event)
    journal = journal_at(root)
    path = root / (transaction_receipt_path(TRANSACTION) if receipt == 'transaction'
                   else request_receipt_path(journal.data['request_id']))
    if change == 'missing': path.unlink()
    else: path.write_bytes(b'foreign receipt bytes')
    before = tree(root)
    result = transaction_preflight(root, command_class=CommandClass.NORMATIVE_WRITE,
        request_id='following-request', expected_project_id='sample', actor=ACTOR, authority=RECOVER).data
    assert result['exit_code'] != 0 and not result['recovery_completed']
    assert not result['normal_operation_started'] and not result['request_consumed']
    assert tree(root) == before
    assert {p: b.hex() for p, b in files(root).items()} == bound['after']


@pytest.mark.parametrize('scenario', ['discard', 'rollback', 'complete'])
@pytest.mark.parametrize('group', range(4))
def test_every_recovery_boundary_survives_another_interrupted_recovery(tmp_path, scenario, group):
    _, writer_trace = control(tmp_path / 'writer-control')
    start = select(writer_trace, scenario)
    control_root = tmp_path / 'recovery-control'
    expected = cut_writer(control_root, start)
    completed, = child(control_root, 'recover')
    assert_result(expected, completed)
    events = completed['events']
    assert events and any(e['operation'] == 'link' for e in events)
    observed = []
    # All four collected groups cover the complete native trace, without a
    # boundary limit or dependence on another test's execution order.
    for event in events[group::4]:
        root = tmp_path / ('cut-' + str(event['ordinal']))
        bound = cut_writer(root, start)
        stopped, = child(root, 'recover', 'recovery', event['ordinal'], exit_code=CRASH_EXIT)
        assert stopped['cut'] == event
        # A second actual process stop also occurs in the recovery path. Its
        # first native effect is selected from its current persisted state;
        # the first attempt's event order is not presumed to repeat.
        again, = child(root, 'recover', 'recovery', 0, exit_code=CRASH_EXIT)
        assert again['pid'] != stopped['pid'] and again['cut']['ordinal'] == 0
        recovered, = child(root, 'recover')
        assert recovered['pid'] not in (stopped['pid'], again['pid'])
        assert_result(bound, recovered)
        assert recovered['outcome'] == ('target' if scenario == 'complete' else 'base')
        assert transaction_preflight(root, command_class=CommandClass.READ_ONLY).exit_code == 0
        if scenario == 'rollback':
            created = set(bound['after']) - set(bound['before'])
            assert len(created) == 1
            removed = list((root / '.specroad/recovery').rglob('*.removed'))
            assert len(removed) == 1 and removed[0].read_bytes().hex() == bound['after'][created.pop()]
        observed.append({**event, 'outcome': recovered['outcome'], 'process_stops': 3,
                         'scenario': scenario, 'group': group})
    (tmp_path / 'recovery-boundaries.json').write_text(json.dumps(observed, indent=2) + '\n')


@pytest.mark.parametrize('change', ['foreign', 'authority_prefix', 'rollback_binding'])
def test_partial_writer_successor_cannot_be_adopted_after_its_binding_changes(tmp_path, change):
    from specroad.changes import (RecoveryError, RecoveryAuthority, LockRecord,
        RolledBackJournal, transaction_recovery_lock, rollback_interrupted_transaction,
        cleanup_recovered_transaction)
    from specroad.model.canonical import canonical_json_bytes
    _, trace = control(tmp_path / 'control')
    successors = [e for e in trace['events'] if e['phase'] == 'publishing'
                  and e['operation'] == 'fsync' and e['paths'][0].endswith('/journal.next')]
    root = tmp_path / 'project'
    bound = cut_writer(root, successors[1])
    journal = journal_at(root)
    pending = (root / journal.path).with_name('journal.next')
    lock = LockRecord((root / '.specroad/locks/project.json').read_bytes())
    with transaction_recovery_lock(root, TRANSACTION, project_id='sample',
            request_id=journal.data['request_id'], command='recover run',
            expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
            authority=RECOVER, actor=ACTOR, reason='Partial writer binding test', force=True) as held:
        if change == 'rollback_binding':
            done = rollback_interrupted_transaction(TRANSACTION, held_lock=held,
                authority=RECOVER, expected_journal_sha256=journal.sha256)
            assert done.data['rollback_completed']
            terminal = journal_at(root)
            value = terminal.data
            value['rollback']['started_from_sha256'] = '0' * 64
            forged = RolledBackJournal(canonical_json_bytes(value))
            (root / terminal.path).write_bytes(forged.source_bytes)
            before = tree(root)
            with pytest.raises(RecoveryError):
                cleanup_recovered_transaction(TRANSACTION, held_lock=held,
                    authority=RECOVER, expected_journal_sha256=forged.sha256)
            assert tree(root) == before
            assert {p: b.hex() for p, b in files(root).items()} == bound['before']
        else:
            raw = pending.read_bytes()
            authority = RECOVER
            if change == 'foreign':
                pending.write_bytes(b'foreign successor')
            else:
                def interfere(request):
                    pending.write_bytes(raw[:17])
                    return True
                authority = RecoveryAuthority('interfering-test-host', '1', interfere)
            before = tree(root)
            with pytest.raises(RecoveryError):
                rollback_interrupted_transaction(TRANSACTION, held_lock=held,
                    authority=authority, expected_journal_sha256=journal.sha256)
            if change == 'authority_prefix':
                before[pending.relative_to(root).as_posix()] = raw[:17]
            assert tree(root) == before
