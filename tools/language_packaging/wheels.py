"""Pinned offline wheel acquisition; never import upstream package code."""
from email.parser import BytesParser
from hashlib import sha256
import io
import os
from pathlib import Path, PurePosixPath
import stat
from zipfile import ZipFile
from .inventory import NUMPY, LANGID, MODEL_PATH, MODEL_SHA256

def regular_bytes(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Linked package input')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 32 * 1024 * 1024:
            raise ValueError('Invalid package input')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            raw = stream.read(32 * 1024 * 1024 + 1)
        fields = ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')
        if len(raw) != info.st_size or any(getattr(info,k)!=getattr(after,k)
                for after in (os.fstat(descriptor),path.lstat()) for k in fields):
            raise ValueError('Package input changed')
        return raw
    finally:
        os.close(descriptor)


def wheel_files(raw, package, row):
    if len(raw) != row['size'] or sha256(raw).hexdigest() != row['sha256']:
        raise ValueError('Wheel hash mismatch: ' + package)
    with ZipFile(io.BytesIO(raw)) as archive:
        files = {}
        infos = archive.infolist()
        if len(infos) > 10000 or sum(i.file_size for i in infos) > 256 * 1024 * 1024:
            raise ValueError('Oversized wheel')
        for info in infos:
            path = PurePosixPath(info.filename)
            if (path.is_absolute() or '..' in path.parts or '\\' in info.filename
                    or str(path) != info.filename.rstrip('/') or info.filename in files
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError('Unsafe wheel path')
            if not info.is_dir():
                files[info.filename] = archive.read(info)
    prefix = package + '-' + row['version'] + '.dist-info/'
    metadata = BytesParser().parsebytes(files[prefix + 'METADATA'])
    if metadata['Name'] != package or metadata['Version'] != row['version']:
        raise ValueError('Wheel metadata mismatch')
    tags = BytesParser().parsebytes(files[prefix + 'WHEEL']).get_all('Tag', [])
    expected = (['py3-none-any'] if package == 'py3langid' else
                [row['abi'] + '-' + row['abi'] + '-' + p
                 for p in row['filename'][:-4].split('-')[-1].split('.')])
    if sorted(tags) != sorted(expected):
        raise ValueError('Wheel ABI mismatch')
    return files


def read_wheels(wheelhouse, python_minor):
    if python_minor not in NUMPY:
        raise ValueError('No matching Linux x86-64 CPython package: ' + str(python_minor))
    rows = {'numpy': NUMPY[python_minor], 'py3langid': LANGID}
    result = {}
    for name, row in rows.items():
        try:
            raw = regular_bytes(Path(wheelhouse) / row['filename'])
        except FileNotFoundError as error:
            raise ValueError('Missing offline wheel: ' + row['filename']) from error
        result[name] = (raw, wheel_files(raw, name, row))
    if sha256(result['py3langid'][1][MODEL_PATH]).hexdigest() != MODEL_SHA256:
        raise ValueError('Reference model hash mismatch')
    return rows, result
