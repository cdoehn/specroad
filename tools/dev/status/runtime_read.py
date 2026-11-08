"""Short, bounded, read-only runtime transactions; never initialize a database."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import stat
import time


@contextmanager
def connection(path, timeout=5):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError('Laufzeitdatenbank fehlt: ' + str(path))
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Keine reguläre Laufzeitdatenbank')
    deadline = time.monotonic() + timeout
    db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=min(timeout, 1))
    try:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        db.execute('BEGIN')
        if [tuple(row) for row in db.execute('SELECT id,version FROM metadata')] != [(1, 1)]:
            raise ValueError('Unbekanntes Format der Laufzeitdatenbank')
        yield db
        after = path.stat()
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise ValueError('Laufzeitdatenbank wurde während der Abfrage ersetzt.')
    finally:
        db.close()
