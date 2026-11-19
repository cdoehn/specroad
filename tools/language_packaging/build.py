"""Language add-on composition reuses the unchanged Core build identity."""
import ast
from hashlib import sha256
from pathlib import Path, PurePosixPath
import tempfile
from build_core import build_core
from .inventory import NUMPY, MODEL_PATH, MODEL_SHA256
from .wheels import read_wheels as read_wheels, regular_bytes as regular_bytes, wheel_files as wheel_files
from .archive import encoded as encoded, publish_archive as publish_archive

__all__ = ('read_wheels','regular_bytes','wheel_files','encoded','publish_archive','package_contents','build_language')

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


def build_language(source_root, wheelhouse, python_minor, output):
    return publish_archive(package_contents(source_root, wheelhouse, python_minor), output)
