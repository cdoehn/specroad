"""Small complete native-container doubles with explicit deletion diffs."""
from hashlib import sha256
import json
import zipfile

from specroad_control.apply_snapshot import blob
from codex_control_tests.blocked_chain_support import snapshot_members
from specroad_control.mixed_contract import CAPABILITY


def deletion_diff(name, raw):
    prefix = ('diff --git a/{0} b/{0}\ndeleted file mode 100644\nindex {1}..{2}\n'.format(
        name, blob(raw, 40), '0'*40)).encode()
    if not raw:
        return prefix
    if b'\0' in raw:
        return prefix + ('Binary files a/' + name + ' and /dev/null differ\n').encode()
    lines = raw.splitlines(keepends=True)
    size = '' if len(lines) == 1 else ',' + str(len(lines))
    text = ('--- a/' + name + '\n+++ /dev/null\n@@ -1' + size + ' +0,0 @@\n').encode()
    for line in lines:
        text += b'-' + line
        if not line.endswith(b'\n'):
            text += b'\n\\ No newline at end of file\n'
    return prefix + text


def result_snapshot(path, base, work, *, staged=False, log=b'', **values):
    tracked, untracked, members = snapshot_members(base, work)
    deleted = b''.join(deletion_diff(n, base[n]) for n in sorted(set(base) - set(work)))
    members['changes/unstaged.patch'] += deleted
    if staged:
        members['changes/staged.patch'] = members['changes/unstaged.patch']
        members['changes/unstaged.patch'] = b''
    members['manifest.json'] = json.dumps({'base_entries':tracked, 'untracked_entries':untracked}).encode()
    members['logs/execution.log'] = log
    with zipfile.ZipFile(path, 'w') as archive:
        for name, raw in members.items(): archive.writestr(name, raw)
    return {'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest(), 'dirty':base != work,
            'success':True, 'development_contract':CAPABILITY, **values}
