"""Lossless bounded-memory storage of raw profiles, events and per-process traces."""
from hashlib import sha256
import os
from pathlib import Path
import stat
import tempfile
import zlib

CHUNK_SIZE = 1024 * 1024


def capture(store, run, directory, path, *, kind, nodeid=None, pid=None):
    directory, path = Path(directory).resolve(), Path(path)
    name = path.relative_to(directory).as_posix()
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or path.resolve() != path.absolute():
        raise ValueError('Only regular artifacts inside the run directory are admitted')
    previous = store.db.execute('SELECT id,state FROM artifacts WHERE run_id=? AND path=?', (run, name)).fetchone()
    if previous:
        if previous[1] != 'complete':
            raise ValueError('Preserve and inspect incomplete artifact import: ' + name)
        return previous[0]
    with store.db:
        identifier = store.db.execute('INSERT INTO artifacts(run_id,path,kind,nodeid,pid,state) VALUES(?,?,?,?,?,?)',
                                      (run, name, kind, nodeid, pid, 'writing')).lastrowid
    digest, size = sha256(), 0
    with path.open('rb') as stream:
        for ordinal, raw in enumerate(iter(lambda: stream.read(CHUNK_SIZE), b'')):
            digest.update(raw)
            size += len(raw)
            with store.db:
                store.db.execute('INSERT INTO artifact_chunks VALUES(?,?,?,?)',
                                 (identifier, ordinal, len(raw), zlib.compress(raw)))
    after = path.stat()
    if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or size != after.st_size:
        raise ValueError('Artifact changed while being captured')
    with store.db:
        store.db.execute('UPDATE artifacts SET state=?,byte_count=?,sha256=? WHERE id=?',
                         ('complete', size, digest.hexdigest(), identifier))
    return identifier


def export(db, identifier, output):
    row = db.execute('SELECT state,byte_count,sha256,codec FROM artifacts WHERE id=?', (identifier,)).fetchone()
    if row is None or row[0] != 'complete' or row[3] != 'zlib-chunks-v1':
        raise ValueError('A complete stored artifact is required')
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    digest, size, expected = sha256(), 0, 0
    fd, temporary = tempfile.mkstemp(prefix='.profile-export-', dir=output.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            for ordinal, raw_size, data in db.execute('SELECT ordinal,raw_size,data FROM artifact_chunks WHERE artifact_id=? ORDER BY ordinal', (identifier,)):
                if ordinal != expected or not 0 < raw_size <= CHUNK_SIZE:
                    raise ValueError('Artifact chunk sequence or size is damaged')
                decoder = zlib.decompressobj()
                try:
                    raw = decoder.decompress(data, raw_size + 1)
                except zlib.error as exc:
                    raise ValueError('Artifact compression stream is damaged') from exc
                if len(raw) != raw_size or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                    raise ValueError('Artifact chunk content differs')
                digest.update(raw)
                size += len(raw)
                stream.write(raw)
                expected += 1
            if (size, digest.hexdigest()) != (row[1], row[2]):
                raise ValueError('Exported artifact failed its size/hash check')
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)  # Publish only verified bytes, never replace.
    finally:
        Path(temporary).unlink()
