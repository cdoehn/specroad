"""Read-only cancellation annotations; never create or migrate a database."""


def annotate(db, values, run_id):
    if db.execute("SELECT 1 FROM sqlite_master WHERE name='attempt_moves'").fetchone():
        moves = {r['attempt']: dict(r) for r in db.execute('SELECT m.* FROM attempt_moves m JOIN attempts a ON a.id=m.attempt WHERE a.run=?', (run_id,))}
        for value in values:
            if value['attempt_id'] in moves:
                value.update(status='cancelled', phase=None, elapsed_seconds=None, valid_measurement=False,
                             move=moves[value['attempt_id']], completed=True)
    return values
