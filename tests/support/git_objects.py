"""Owned Git fixtures built as data, without invoking Git write commands."""
from hashlib import sha1
from pathlib import Path
import stat
import zlib


class GitFixture:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True)
        self.git = self.root / '.git'
        for directory in ('objects', 'refs/heads', 'refs/tags', 'hooks', 'info'):
            (self.git / directory).mkdir(parents=True, exist_ok=True)
        (self.git / 'HEAD').write_bytes(b'ref: refs/heads/main\n')
        (self.git / 'config').write_bytes(b'[core]\nrepositoryformatversion = 0\nbare = false\nlogallrefupdates = false\n')
        (self.git / 'index').write_bytes(b'owned pre-existing index bytes; not an input to object reads')
        (self.root / 'foreign.txt').write_bytes(b'keep exactly')

    def object(self, kind, data):
        raw = kind.encode() + b' ' + str(len(data)).encode() + b'\0' + data
        oid = sha1(raw, usedforsecurity=False).hexdigest()
        target = self.git / 'objects' / oid[:2] / oid[2:]
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(zlib.compress(raw))
        return oid

    def tree(self, files):
        nested = {}
        for path, content in files.items():
            parts = path.split('/')
            current = nested
            for part in parts[:-1]:
                current = current.setdefault(part, {})
            current[parts[-1]] = content

        def build(values):
            rows = []
            for name, value in values.items():
                if type(value) is dict:
                    mode, oid = '40000', build(value)
                else:
                    mode, data = value if type(value) is tuple else ('100644', value)
                    oid = data if mode == '160000' else self.object('blob', data)
                rows.append((name.encode() + (b'/' if mode == '40000' else b''),
                             mode.encode() + b' ' + name.encode() + b'\0' + bytes.fromhex(oid)))
            return self.object('tree', b''.join(raw for _, raw in sorted(rows)))
        return build(nested)

    def commit(self, files, *, parent=None, ref='refs/heads/main', message=b'owned fixture'):
        tree = self.tree(files)
        raw = b'tree ' + tree.encode() + b'\n'
        if parent is not None:
            raw += b'parent ' + parent.encode() + b'\n'
        raw += (b'author Fixture <fixture@example.invalid> 1 +0000\n'
                b'committer Fixture <fixture@example.invalid> 1 +0000\n\n' + message + b'\n')
        oid = self.object('commit', raw)
        if ref is not None:
            self.ref(ref, oid)
        return oid

    def ref(self, name, oid):
        target = self.git / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(oid.encode() + b'\n')

    def capture(self):
        return {str(p.relative_to(self.root)): (stat.S_IMODE(p.stat().st_mode), p.read_bytes())
                for p in self.root.rglob('*') if p.is_file()}
