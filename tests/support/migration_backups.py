"""Independent byte inventories and filesystem fixtures for source backups."""
from hashlib import sha256
import json


def file_hash(files):
    rows = [{'path': p, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
            for p, raw in sorted(files.items(), key=lambda r: r[0].encode('utf-8'))]
    return sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False,
                            separators=(',', ':')).encode()).hexdigest()


def write_project(root, files):
    root.mkdir()
    for path, raw in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return root


def disk_files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}
