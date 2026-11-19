"""Build separate, hash-bound offline add-ons from explicitly supplied wheels.

No resolver, installer, network access, source execution or release approval.
"""
import ast
from email.parser import BytesParser
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from build_core import build_core
from .inventory import NUMPY, LANGID, MODEL_PATH, MODEL_SHA256


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('utf-8')


def regular_bytes(path):
    path = Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Linked package input')
    with path.open('rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 32 * 1024 * 1024:
            raise ValueError('Invalid package input')
        raw = stream.read(32 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    if (len(raw) != info.st_size or (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_ctime_ns)
            != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns)):
        raise ValueError('Package input changed')
    return raw


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


def package_contents(source_root, wheelhouse, python_minor):
    rows, wheels = read_wheels(wheelhouse, python_minor)
    with tempfile.TemporaryDirectory(prefix='specroad-language-build-') as temp:
        module, _ = build_core(source_root, Path(temp) / 'core')
        payload = {'adapter/' + p.relative_to(module).as_posix(): p.read_bytes()
                   for p in module.rglob('*') if p.is_file()}
    # Generated build metadata is a literal, never execute a supplied source tree.
    tree = ast.parse(payload['adapter/specroad/_build.py'].decode('utf-8'))
    record = ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.Assign)))
    dependencies = []
    for name, row in rows.items():
        raw, files = wheels[name]
        target = 'wheels/' + row['filename']
        payload[target] = raw
        licenses = []
        for path, data in sorted(files.items()):
            if PurePosixPath(path).name.lower().startswith(('license', 'copying', 'notice')):
                license_path = 'licenses/' + name + '/' + path
                payload[license_path] = data
                licenses.append(license_path)
        if not licenses:
            raise ValueError('Missing upstream licenses: ' + name)
        dependencies.append(dict(name=name, version=row['version'], wheel=target,
            sha256=row['sha256'], licenses=licenses))
    model = 'model/model.npz.xz'
    payload[model] = wheels['py3langid'][1][MODEL_PATH]
    manifest = dict(format_version=1, kind='specroad-language-offline',
        python_implementation='cpython', python_minor=python_minor, abi=NUMPY[python_minor]['abi'],
        platform='linux-x86_64', glibc_min=NUMPY[python_minor]['glibc_min'],
        core_build=record, dependencies=dependencies,
        model=dict(path=model, sha256=MODEL_SHA256, upstream_path=MODEL_PATH),
        runtime_verification='not_run', release_approved=False,
        files={name:dict(sha256=sha256(data).hexdigest(), size=len(data))
               for name, data in sorted(payload.items())})
    payload['manifest.json'] = encoded(manifest)
    return payload


def publish_archive(payload, output):
    output = Path(output).absolute()
    if os.path.lexists(output):
        raise FileExistsError(output)
    parent = output.parent.resolve(strict=True)
    output = parent / output.name
    descriptor, name = tempfile.mkstemp(prefix='.language-package-', dir=parent)
    temp = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            with ZipFile(stream, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
                for path, raw in sorted(payload.items()):
                    info = ZipInfo(path, (1980, 1, 1, 0, 0, 0))
                    info.compress_type = ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, output)  # Exclusive atomic publication, never replace.
        directory = os.open(parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temp.unlink(missing_ok=True)
    return output


def build_language(source_root, wheelhouse, python_minor, output):
    return publish_archive(package_contents(source_root, wheelhouse, python_minor), output)
