"""Read-only cancellation annotations; never create or migrate a database."""


def annotate(db, values, run_id):
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='attempt_moves'").fetchone():
        moves = {r['attempt']: dict(r) for r in db.execute('SELECT m.* FROM attempt_moves m JOIN attempts a ON a.id=m.attempt WHERE a.run=?', (run_id,))}
        for value in values:
            if value['attempt_id'] in moves:
                value.update(status='cancelled', phase=None, elapsed_seconds=None, valid_measurement=False,
                             move=moves[value['attempt_id']], completed=True)
    from verification_support.runtime_copies import enabled
    if enabled(db, run_id):
        copies = {r['attempt']:dict(r) for r in db.execute(
            'SELECT * FROM speculative_attempts WHERE run=?', (run_id,))}
        winners = {r['node']:r['worker'] for r in db.execute(
            'SELECT node,worker FROM speculative_winners WHERE run=?', (run_id,))}
        for value in values:
            row = copies.get(value['attempt_id'])
            if row is None:
                raise ValueError('Attempt lacks its copy reservation')
            value.update(attempt_token=row['token'], copy_role='winner' if winners.get(row['node']) == row['worker'] else 'copy',
                         copy_state=row['state'])
            if row['state'] in ('cancelled', 'moved'):
                value.update(status='failed' if row['failed'] else 'cancelled', phase=None,
                             elapsed_seconds=None, valid_measurement=False, completed=True)
    return values
