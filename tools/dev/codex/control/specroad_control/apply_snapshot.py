"""Bounded passive file-map reconstruction; no repository code or patch execution."""
import base64
from hashlib import sha1, sha256
import io
from pathlib import Path
import re
import zipfile
import zlib

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
        if name in changed:
            fail('Diff repeats a path.')
        index += 1
        end = index
        while end < len(lines) and not lines[end].startswith(b'diff --git '):
            end += 1
        if lines[index:index + 1] in ([b'deleted file mode 100644\n'], [b'new file mode 100644\n']):
            changed[name] = created_or_deleted(base, name, lines[index:end])
            index = end
            continue
        if name not in base:
            fail('Diff path is not a tracked file.')
        mode, original = base[name]
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
    return {name: value for name, value in {**base, **changed}.items() if value is not None}


def created_or_deleted(base, name, lines):
    """Exact full-file addition/deletion only; modes, blob IDs and all bytes bound."""
    removed = lines[0] == b'deleted file mode 100644\n'
    if (name in base) != removed or removed and base[name][0] != '100644':
        fail('Addition/deletion inventory or mode differs.')
    identity = re.fullmatch(rb'index ([0-9a-f]{40}|[0-9a-f]{64})\.\.([0-9a-f]{40}|[0-9a-f]{64})\n',
                            lines[1] if len(lines) > 1 else b'')
    if identity is None or len(identity[1]) != len(identity[2]):
        fail('Addition/deletion lacks full Git identities.')
    old, new = identity[1].decode(), identity[2].decode()
    if (new if removed else old) != '0' * len(old):
        fail('Addition/deletion has a nonzero absent identity.')
    body = lines[2:]
    if removed:
        raw = base[name][1]
        if blob(raw, len(old)) != old:
            fail('Deleted file preimage differs from the native base.')
        expected = []
        if raw:
            content = lf_lines(raw)
            count = b'' if len(content) == 1 else b',' + str(len(content)).encode()
            expected = [b'--- a/' + name.encode() + b'\n', b'+++ /dev/null\n',
                        b'@@ -1' + count + b' +0,0 @@\n']
            for line in content:
                expected.append(b'-' + line + (b'' if line.endswith(b'\n') else b'\n'))
                if not line.endswith(b'\n'):
                    expected.append(b'\\ No newline at end of file\n')
        binary = [b'Binary files a/' + name.encode() + b' and /dev/null differ\n']
        if body[:1] == [b'GIT binary patch\n']:
            binary_deletion(body[1:], raw)
            return None
        if body != expected and not (b'\0' in raw and body == binary):
            fail('Deleted file diff does not account for every original byte.')
        return None
    if not body:
        raw = b''
    else:
        if body[:2] != [b'--- /dev/null\n', b'+++ b/' + name.encode() + b'\n'] or len(body) < 4:
            fail('Only complete text additions are reconstructible.')
        hunk = re.fullmatch(rb'@@ -0,0 \+1(?:,(\d+))? @@\n', body[2])
        if hunk is None:
            fail('New file must be one complete hunk.')
        content = []
        for line in body[3:]:
            if line == b'\\ No newline at end of file\n':
                if not content or not content[-1].endswith(b'\n') or line != body[-1]:
                    fail('Invalid new-file newline marker.')
                content[-1] = content[-1][:-1]
            elif line.startswith(b'+') and line.endswith(b'\n'):
                content.append(line[1:])
            else:
                fail('Invalid new-file content.')
        if len(content) != int(hunk[1] or b'1'):
            fail('New-file line count differs.')
        raw = b''.join(content)
    if blob(raw, len(new)) != new:
        fail('New file bytes differ from the native Git identity.')
    return ('100644', raw)


def binary_deletion(lines, original):
    """Git --binary deletion: exact zero-byte forward and full literal inverse."""
    position = 0
    for expected in (b'', original):
        if position >= len(lines) or lines[position] != ('literal ' + str(len(expected)) + '\n').encode():
            fail('Binary deletion needs exact bounded literal images.')
        position += 1
        encoded = bytearray()
        while position < len(lines) and lines[position] != b'\n':
            line = lines[position]; position += 1
            prefix = line[0] if line else 0
            count = prefix - 64 if 65 <= prefix <= 90 else prefix - 70 if 97 <= prefix <= 122 else 0
            if not count or not line.endswith(b'\n') or len(line) != 2 + ((count + 3) // 4) * 5:
                fail('Invalid binary deletion line.')
            decoded = base64.b85decode(line[1:-1])
            if any(decoded[count:]) or len(encoded) + count > LIMIT:
                fail('Binary deletion padding or size differs.')
            encoded.extend(decoded[:count])
        if position >= len(lines):
            fail('Unterminated binary deletion.')
        position += 1
        decoder = zlib.decompressobj()
        raw = decoder.decompress(encoded, len(expected) + 1)
        if raw != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            fail('Binary deletion literal differs from the complete native bytes.')
    if position != len(lines):
        fail('Trailing binary deletion data.')

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
        indexed = modified_files(base, read('changes/staged.patch'))
        work = modified_files(indexed, read('changes/unstaged.patch'))
        staged = {n for n in set(base) | set(indexed) if base.get(n) != indexed.get(n)}
        if any(work.get(n) != indexed.get(n) for n in staged):
            fail('Divergent index/worktree changes require separate recovery evidence.')
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
    scope = set(stage['payloads']) | set(stage.get('deletions', {}))
    if set(stage['before']) != scope.intersection(files):
        fail('Stage preimage inventory is incomplete.')
    for name, expected in stage['before'].items():
        mode, raw = files[name]
        if mode != '100644' or sha256(raw).hexdigest() != expected:
            fail('Stage preimage bytes or mode differ from the proven snapshot.')
    result = dict(files)
    for name, digest in stage.get('deletions', {}).items():
        raw = base64.b64decode(stage['delete_preimages'][name], validate=True)
        if len(raw) > LIMIT or sha256(raw).hexdigest() != digest:
            fail('Deletion full preimage differs from its promise.')
        if name in files and (files[name] != ('100644', raw) or stage['before'].get(name) != digest):
            fail('Deletion differs from the complete native preimage.')
        result.pop(name, None)
    for name, encoded in stage['payloads'].items():
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > LIMIT or sha256(raw).hexdigest() != stage['after'][name]:
            fail('Stage file exceeds the passive proof limit or differs from its hash.')
        result[name] = ('100644', raw)
    no_collisions(result)
    if sum(len(raw) for mode, raw in result.values()) > SNAPSHOT_LIMIT:
        fail('Stage snapshot exceeds the passive proof limit.')
    return result
