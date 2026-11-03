"""Bounded passive file-map reconstruction; no repository code or patch execution."""
import base64
from hashlib import sha1, sha256
import io
from pathlib import Path
import re
import zipfile

from .apply_reconcile_proof import LIMIT, archive_bytes, hashed, fail
from .local import decode_object

SNAPSHOT_LIMIT = 256 * 1024 * 1024
FILE_LIMIT = 100000


def safe_path(name):
    if (not isinstance(name, str) or name in ('.', '..') or not re.fullmatch('[A-Za-z0-9_./-]+', name)
            or str(Path(name)) != name or Path(name).is_absolute()
            or any(part.lower() in ('.', '..', '.git', '.patchharbor') for part in Path(name).parts)):
        fail('Unsupported snapshot path.')
    return name

def no_collisions(files):
    if len(files) > FILE_LIMIT:
        fail('Snapshot file count exceeds the passive proof limit.')
    for name in files:
        safe_path(name)
        if any(str(parent) in files for parent in Path(name).parents if str(parent) != '.'):
            fail('A file masks a snapshot directory.')

def blob(raw, length):
    if length not in (40, 64):
        fail('Unsupported Git blob identifier.')
    content = b'blob ' + str(len(raw)).encode() + b'\0' + raw
    return (sha1(content) if length == 40 else sha256(content)).hexdigest()

def lf_lines(raw):
    parts = raw.split(b'\n')
    return [part + b'\n' for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])

def modified_files(base, diff):
    """Apply only exact ordinary text hunks to owned in-memory bytes, without Git."""
    lines, index, changed = lf_lines(diff), 0, {}
    while index < len(lines):
        header = re.fullmatch(rb'diff --git a/([A-Za-z0-9_./-]+) b/\1\n', lines[index])
        if header is None:
            fail('Unsupported diff header; no rename, binary or mode fallback.')
        name = safe_path(header[1].decode())
        if name not in base or name in changed:
            fail('Diff path is not one unique tracked file.')
        mode, original = base[name]
        index += 1
        old_new = re.fullmatch(rb'index ([0-9a-f]{40}|[0-9a-f]{64})\.\.([0-9a-f]{40}|[0-9a-f]{64}) (100644|100755)\n', lines[index])
        if (old_new is None or old_new[3].decode() != mode
                or old_new[1].decode() != blob(original, len(old_new[1]))):
            fail('Diff preimage or mode differs from the native base.')
        index += 1
        if lines[index:index + 2] != [b'--- a/' + name.encode() + b'\n', b'+++ b/' + name.encode() + b'\n']:
            fail('Only tracked text modifications are supported.')
        index += 2
        before, after, cursor, hunks = lf_lines(original), [], 0, 0
        while index < len(lines) and not lines[index].startswith(b'diff --git '):
            hunk = re.fullmatch(rb'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n', lines[index])
            if hunk is None:
                fail('Unsupported diff hunk.')
            old_start, old_count, new_start, new_count = (int(hunk[1]), int(hunk[2] or b'1'),
                                                         int(hunk[3]), int(hunk[4] or b'1'))
            position = old_start - (old_count != 0)
            if position < cursor or position > len(before):
                fail('Overlapping or displaced diff hunk.')
            after.extend(before[cursor:position]); cursor = position
            if new_start - (new_count != 0) != len(after):
                fail('Diff destination position is inconsistent.')
            index += 1
            old_seen = new_seen = 0
            while old_seen < old_count or new_seen < new_count:
                line = lines[index]; index += 1
                mark, content = line[:1], line[1:]
                if mark not in (b' ', b'-', b'+') or not line.endswith(b'\n'):
                    fail('Invalid text hunk line.')
                if index < len(lines) and lines[index] == b'\\ No newline at end of file\n':
                    content = content[:-1]; index += 1
                if mark != b'+':
                    if cursor >= len(before) or before[cursor] != content:
                        fail('Diff context differs; no offset or fuzz is allowed.')
                    cursor += 1; old_seen += 1
                if mark != b'-':
                    after.append(content); new_seen += 1
                if old_seen > old_count or new_seen > new_count:
                    fail('Diff hunk count overflow.')
            hunks += 1
        after.extend(before[cursor:])
        result = b''.join(after)
        if not hunks or blob(result, len(old_new[2])) != old_new[2].decode():
            fail('Diff postimage is not the promised Git blob.')
        changed[name] = (mode, result)
    return {**base, **changed}

def snapshot(fact):
    raw = archive_bytes(fact)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) > FILE_LIMIT + 64 or len({entry.filename for entry in entries}) != len(entries):
            fail('Duplicate snapshot member.')
        sizes = {entry.filename: entry.file_size for entry in entries}
        def read(name):
            if name not in sizes or sizes[name] > LIMIT:
                fail('Missing or oversized snapshot member.')
            return archive.read(name)
        manifest = decode_object(read('manifest.json'))
        inventory = manifest['base_entries']
        untracked = manifest['untracked_entries']
        if (not isinstance(inventory, list) or not isinstance(untracked, list)
                or len(inventory) + len(untracked) > FILE_LIMIT
                or sum(size for name, size in sizes.items() if name.startswith(('base/', 'untracked/'))) > SNAPSHOT_LIMIT):
            fail('Snapshot inventory exceeds the passive proof limits.')
        base, expected = {}, set()
        for entry in inventory:
            name = safe_path(entry['path']); mode = entry['git_mode']
            raw = read('base/' + name)
            if (name in base or mode not in ('100644', '100755') or type(entry['size']) is not int
                    or len(raw) != entry['size'] or blob(raw, len(entry['object_id'])) != entry['object_id']):
                fail('Native base inventory and bytes disagree.')
            base[name] = (mode, raw); expected.add('base/' + name)
        if read('changes/staged.patch'):
            fail('Staged changes require a separately reviewed recovery contract.')
        work = modified_files(base, read('changes/unstaged.patch'))
        for entry in untracked:
            name = safe_path(entry['path']); raw = read('untracked/' + name)
            if (name in work or entry['mode'] != '100644' or type(entry['size']) is not int
                    or len(raw) != entry['size'] or sha256(raw).hexdigest() != entry['sha256']):
                fail('Untracked snapshot inventory and bytes disagree.')
            work[name] = ('100644', raw); expected.add('untracked/' + name)
        if {name for name in sizes if name.startswith(('base/', 'untracked/'))} != expected:
            fail('Snapshot members and inventory differ.')
        no_collisions(base); no_collisions(work)
        if fact['dirty'] != (base != work):
            fail('Dirty state is inconsistent with complete file maps.')
        return base, work

def inventory_hash(files):
    return hashed({name: [mode, sha256(raw).hexdigest()] for name, (mode, raw) in files.items()})

def apply_stage(files, stage):
    scope = set(stage['payloads'])
    if set(stage['before']) != scope.intersection(files):
        fail('Stage preimage inventory is incomplete.')
    for name, expected in stage['before'].items():
        mode, raw = files[name]
        if mode != '100644' or sha256(raw).hexdigest() != expected:
            fail('Stage preimage bytes or mode differ from the proven snapshot.')
    result = dict(files)
    for name, encoded in stage['payloads'].items():
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > LIMIT:
            fail('Stage file exceeds the passive proof limit.')
        result[name] = ('100644', raw)
    no_collisions(result)
    if sum(len(raw) for mode, raw in result.values()) > SNAPSHOT_LIMIT:
        fail('Stage snapshot exceeds the passive proof limit.')
    return result
