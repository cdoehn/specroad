"""Real process termination and fresh recovery at every observed writer boundary."""
import json
import pytest
from specroad.changes import transaction_preflight
from specroad.cli.contracts import CommandClass
from support.writer_boundaries import (PHASES, CRASH_EXIT, SENTINEL,
    SENTINEL_BYTES, child)


@pytest.mark.parametrize('phase', PHASES)
def test_every_native_writer_boundary_recovers_exact_basis_or_complete_target(tmp_path, phase):
    control_root = tmp_path / 'uninterrupted'
    control, trace = child(control_root, 'writer')
    assert control['base_root'] != control['target_root']
    assert trace['completed']['commit_completed'] and trace['completed']['cleanup_completed']
    assert transaction_preflight(control_root, command_class=CommandClass.READ_ONLY).exit_code == 0
    events = [event for event in trace['events'] if event['phase'] == phase]
    assert events and any(e['operation'] == 'fsync' for e in events)
    outcomes = []
    # Discover all actual successful native boundaries; do not silently cap a
    # phase at a fixed number when a new durable operation is introduced.
    for event in events:
        root = tmp_path / ('cut-' + str(event['ordinal']))
        bound, stopped = child(root, 'writer', phase, event['ordinal'], exit_code=CRASH_EXIT)
        assert stopped['cut'] == event
        recovered, = child(root, 'recover')
        assert recovered['pid'] != stopped['pid']
        outcome = recovered['outcome']
        if outcome == 'blocked_before_journal':
            assert phase == 'building', event
            outcome = 'base'
        assert recovered['files'] == bound['before' if outcome == 'base' else 'after'], event
        assert recovered['model_root'] == bound[outcome + '_root'], event
        assert bytes.fromhex(recovered['files'][SENTINEL]) == SENTINEL_BYTES
        outcomes.append({**event, 'outcome': recovered['outcome'],
                         'model_root': recovered['model_root']})
    (tmp_path / 'writer-boundaries.json').write_text(json.dumps(outcomes, indent=2) + '\n')
