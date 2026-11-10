"""Actual latest attempts only; stable identities mapped to a fresh collection."""
from pathlib import Path

from dev.status.cli import Target
from dev.status.runtime_read import connection


def history_path(root, explicit=None):
    if explicit is not None:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise ValueError('The requested runtime history does not exist')
        return path
    target = Target.from_repository(root)
    ready, reason = target.runtime_ready()
    if not ready:
        raise ValueError(reason)
    return target.database


def slowest(pairs, path, count=10):
    """Do not fall back to older successes, retired IDs or baseline seeds."""
    with connection(path, timeout=30) as db:
        rows = [dict(row) for row in db.execute('''
            WITH latest AS (SELECT MAX(id) AS id FROM attempts GROUP BY test)
            SELECT a.id AS attempt,a.test,a.run,r.source,r.started,r.workers,
                   SUM(p.duration) AS duration_ns
            FROM latest l JOIN attempts a ON a.id=l.id JOIN runs r ON r.id=a.run
            JOIN phases p ON p.attempt=a.id WHERE a.complete=1 AND a.invalid=0
            GROUP BY a.id HAVING COUNT(DISTINCT p.phase)=3 AND
            MIN(p.phase IN ('setup','call','teardown') AND p.outcome='passed'
                AND typeof(p.duration)='integer' AND p.duration>=0)=1
            ORDER BY duration_ns DESC,a.test
        ''')]
    nodes = {identity: node for node, identity in pairs.items()}
    selected = [row for row in rows if row['test'] in nodes][:count]
    if not selected:
        raise ValueError('No current tests have complete valid actual measurements')
    return ({nodes[row['test']]: row['test'] for row in selected},
            {row['test']: row for row in selected})
