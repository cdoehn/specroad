"""Explicit public source snapshot, excluding local configuration and credentials."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import stat

ROOTS = ('src', 'tests', 'tools', 'verification', 'docs', '.github')
FILES = ('pyproject.toml', 'conftest.py', 'DEVELOPMENT.md', 'README.md', 'LICENSE', '.python-versions', '.gitignore')
EXCLUDE = {'.git', '.venv', '__pycache__', '.pytest_cache', '.mypy_cache', '.patchharbor',
           'CURRENT_WORK.txt', '.env', '.ssh'}


def inventory(root):
    root = Path(root).resolve()
    paths = []
    for directory in ROOTS:
        start = root / directory
        if start.is_symlink():
            raise ValueError('Linked snapshot root')
        if start.is_dir():
            for current, directories, files in os.walk(start, followlinks=False):
                directories[:] = sorted(d for d in directories if d not in EXCLUDE)
                if any((Path(current) / d).is_symlink() for d in directories):
                    raise ValueError('Linked snapshot directory')
                paths.extend(Path(current) / n for n in sorted(files) if n not in EXCLUDE and not n.endswith(('.pyc', '.pyo')))
    paths.extend(root / n for n in FILES if (root / n).exists())
    result = {}
    for path in sorted(paths):
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode):
            raise ValueError('Snapshot only accepts regular source files')
        raw = path.read_bytes()
        result[path.relative_to(root).as_posix()] = {'sha256': sha256(raw).hexdigest(), 'mode': stat.S_IMODE(mode), 'size': len(raw)}
    return result


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def copy_snapshot(root, target):
    root, target = Path(root), Path(target)
    manifest = inventory(root)
    target.mkdir(mode=0o700)
    for name, value in manifest.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (root / name).read_bytes()
        if sha256(raw).hexdigest() != value['sha256']:
            raise ValueError('Source changed while creating snapshot')
        path.write_bytes(raw)
        path.chmod(value['mode'])
    if inventory(target) != manifest or inventory(root) != manifest:
        raise ValueError('Source changed while creating snapshot')
    return manifest


def remote_verify(root, manifest):
    """Program runs with stdlib only, before importing any transferred code."""
    return '''import hashlib,json,stat,os
from pathlib import Path
root=Path(%r)
expected=json.loads(%r)
seen=set()
for current,dirs,files in os.walk(root,followlinks=False):
    if any((Path(current)/n).is_symlink() for n in dirs): raise ValueError('linked snapshot directory')
    for n in files:
        p=Path(current)/n
        name=p.relative_to(root).as_posix()
        m=p.lstat()
        if not stat.S_ISREG(m.st_mode) or name not in expected: raise ValueError('unexpected snapshot entry')
        v=expected[name]
        if hashlib.sha256(p.read_bytes()).hexdigest()!=v['sha256'] or m.st_size!=v['size'] or stat.S_IMODE(m.st_mode)!=v['mode']: raise ValueError('snapshot bytes or mode changed')
        seen.add(name)
if seen!=set(expected): raise ValueError('incomplete snapshot')
print(json.dumps(True))
''' % (str(root), json.dumps(manifest, sort_keys=True))
