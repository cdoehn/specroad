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






@pytest.fixture(scope='module')
def writer_control_events(tmp_path_factory):
    """Discover native multi-file boundaries once per worker in this run.

    Only immutable JSON of normalized event descriptions is retained. Live
    projects, process identities, plans and completion proofs are not shared
    with any crash case. Each consumer decodes its own event dictionaries.
    """
    _, trace = control(tmp_path_factory.mktemp('multi-writer-control'))
    return json.dumps(trace['events'])


@pytest.fixture
def writer_control(writer_control_events):
    return {'events': json.loads(writer_control_events)}








@pytest.mark.parametrize('receipt', ['transaction', 'request'])
@pytest.mark.parametrize('change', ['missing', 'foreign'])
def test_damaged_receipt_after_committed_marker_keeps_target_blocked_and_evidence(
        tmp_path, receipt, change, writer_control):
    trace = writer_control
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
