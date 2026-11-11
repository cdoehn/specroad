"""Lossless bounded-memory storage of raw profiles, events and per-process traces."""
from hashlib import sha256
import os
from pathlib import Path
import stat
import tempfile
import zlib

from .common import test_key

CHUNK_SIZE = 1024 * 1024


def signature(info):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('A private regular artifact with one link is required')
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def capture(store, run, directory, path, *, kind, nodeid=None, pid=None):
    directory, path = Path(directory).resolve(), Path(path)
    name = path.relative_to(directory).as_posix()
    initial = signature(path.lstat())
    if path.resolve() != path.absolute():
        raise ValueError('Only regular artifacts inside the run directory are admitted')
    previous = store.db.execute('SELECT id,state,byte_count,sha256 FROM artifacts WHERE run_id=? AND path=?', (run, name)).fetchone()
    if previous:
        if previous[1] != 'complete':
            raise ValueError('Preserve and inspect incomplete artifact import: ' + name)
        identifier = previous[0]
    else:
        with store.db:
            identifier = store.db.execute('INSERT INTO artifacts(run_id,path,kind,nodeid,pid,state) VALUES(?,?,?,?,?,?)',
                                          (run, name, kind, nodeid, pid, 'writing')).lastrowid
    digest, size = sha256(), 0
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if signature(os.fstat(stream.fileno())) != initial:
            raise ValueError('Artifact changed before it was opened')
        for ordinal, raw in enumerate(iter(lambda: stream.read(CHUNK_SIZE), b'')):
            digest.update(raw)
            size += len(raw)
            if previous is None:
                with store.db:
                    store.db.execute('INSERT INTO artifact_chunks VALUES(?,?,?,?)',
                                     (identifier, ordinal, len(raw), zlib.compress(raw)))
        if signature(os.fstat(stream.fileno())) != initial:
            raise ValueError('Artifact changed while being read')
    if signature(path.lstat()) != initial or size != initial[2]:
        raise ValueError('Artifact changed while being captured')
    if previous:
        if (size, digest.hexdigest()) != tuple(previous[2:]):
            raise ValueError('Previously captured artifact has different bytes')
        return identifier
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


def archive(store, run, directory, pairs):
    nodes = {test_key(node): node for node in pairs}
    files = sorted(p for p in directory.iterdir() if p.is_file())
    files.extend(sorted(p for p in (directory / 'raw').rglob('*') if p.is_file()))
    for path in files:
        node, pid = None, None
        if path.parent.name in nodes:
            node = nodes[path.parent.name]
        if path.name.startswith('strace.') and path.suffix[1:].isdigit():
            kind, pid = 'strace', int(path.suffix[1:])
        else:
            kind = 'cprofile' if path.suffix == '.pstats' else 'resources' if path.name == 'resources.jsonl' else 'metadata'
        capture(store, run, directory, path, kind=kind, nodeid=node, pid=pid)
