"""Separate package integrity and actual per-interpreter runtime observations."""
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import tempfile
from zipfile import ZipFile

from core_build_metadata import build_record_source
from build_core import ARCHIVE_MAIN
from .build import encoded, regular_bytes, wheel_files
from .inventory import NUMPY, LANGID, MODEL_PATH, MODEL_SHA256


def verify_package(path, *, expected_core_sha256=None):
    raw = regular_bytes(path)
    with ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        if (len(names) != len(set(names)) or len(names) > 10000
                or sum(i.file_size for i in infos) > 256*1024*1024):
            raise ValueError('Invalid package inventory')
        files = {}
        for info in infos:
            name = PurePosixPath(info.filename)
            if (name.is_absolute() or '..' in name.parts or str(name) != info.filename
                    or '\\' in info.filename or info.is_dir()
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError('Unsafe package member')
            files[info.filename] = archive.read(info)
    manifest = json.loads(files.pop('manifest.json'))
    if encoded(manifest) != archive_manifest(raw):
        raise ValueError('Noncanonical manifest')
    keys = {'format_version','kind','python_implementation','python_minor','abi','platform',
            'glibc_min','core_build','dependencies','model','runtime_verification','release_approved','files'}
    if (set(manifest) != keys or type(manifest['format_version']) is not int
            or manifest['format_version'] != 1 or manifest['kind'] != 'specroad-language-offline'
            or manifest['python_implementation'] != 'cpython'
            or manifest['platform'] != 'linux-x86_64'
            or manifest['runtime_verification'] != 'not_run' or manifest['release_approved'] is not False):
        raise ValueError('Unsupported package manifest')
    minor = manifest['python_minor']
    if minor not in NUMPY or any(manifest[k] != NUMPY[minor][k] for k in ('abi','glibc_min')):
        raise ValueError('Unsupported package ABI')
    actual = {name:dict(sha256=sha256(data).hexdigest(),size=len(data)) for name,data in files.items()}
    if manifest['files'] != actual:
        raise ValueError('Package hash inventory differs')
    core = {Path(name[len('adapter/'):]):data for name,data in files.items() if name.startswith('adapter/')}
    if (core.get(Path('__main__.py')) != ARCHIVE_MAIN.encode()
            or core.get(Path('specroad/_build.py')) != build_record_source(core, ARCHIVE_MAIN)
            or not {Path('specroad/__init__.py'),Path('specroad/__main__.py')} <= core.keys()):
        raise ValueError('Core identity differs')
    import ast
    record = ast.literal_eval(next(n.value for n in ast.parse(core[Path('specroad/_build.py')]).body
                                  if isinstance(n,ast.Assign)))
    if manifest['core_build'] != record or (expected_core_sha256 is not None
            and record['build_sha256'] != expected_core_sha256):
        raise ValueError('Unexpected Core identity')
    expected = set('adapter/'+str(p) for p in core)
    dependencies=[]
    for name,row in {'numpy':NUMPY[minor],'py3langid':LANGID}.items():
        wheel='wheels/'+row['filename']; parts=wheel_files(files[wheel],name,row)
        licenses=[]
        for member,data in sorted(parts.items()):
            if PurePosixPath(member).name.lower().startswith(('license','copying','notice')):
                target='licenses/'+name+'/'+member
                if files.get(target) != data: raise ValueError('License bytes differ')
                licenses.append(target)
        if not licenses: raise ValueError('Missing license')
        expected.update([wheel,*licenses])
        dependencies.append(dict(name=name,version=row['version'],wheel=wheel,
                                 sha256=row['sha256'],licenses=licenses))
    model='model/model.npz.xz';expected.add(model)
    if (set(files) != expected or manifest['dependencies'] != dependencies
            or manifest['model'] != dict(path=model,sha256=MODEL_SHA256,upstream_path=MODEL_PATH)
            or sha256(files[model]).hexdigest() != MODEL_SHA256):
        raise ValueError('Package content binding differs')
    return manifest, files, sha256(raw).hexdigest()


def archive_manifest(raw):
    with ZipFile(io.BytesIO(raw)) as archive:
        return archive.read('manifest.json')


PROBE = '''import sys, sysconfig, platform, json
minor = str(sys.version_info[0])+'.'+str(sys.version_info[1])
if (sys.implementation.name != 'cpython' or minor != sys.argv[2]
        or sys.platform != 'linux' or platform.machine() != 'x86_64'
        or sysconfig.get_config_var('Py_GIL_DISABLED')):
    raise SystemExit(2)
sys.path.insert(0, sys.argv[1])
import numpy
import py3langid
from importlib.metadata import version
from specroad.runtime.identity import version_info
print(json.dumps(dict(python_minor=minor, python_version=platform.python_version(),
    implementation=sys.implementation.name, platform='linux-x86_64',
    numpy_version=numpy.__version__, py3langid_version=version('py3langid'),
    numpy_check=int(numpy.array([1,2,3]).sum()),
    core_build_sha256=version_info()['build_sha256'])))
'''


def probe_package(path, interpreter, *, expected_core_sha256):
    """Execute only an explicitly selected interpreter and independently trusted Core."""
    if not isinstance(expected_core_sha256,str) or len(expected_core_sha256)!=64:
        raise ValueError('An independent expected Core hash is required')
    interpreter=Path(interpreter)
    if not interpreter.is_absolute() or not interpreter.is_file():
        raise ValueError('Explicit installed interpreter required')
    manifest,files,package_hash=verify_package(path,expected_core_sha256=expected_core_sha256)
    with tempfile.TemporaryDirectory(prefix='specroad-language-probe-') as temp:
        root=Path(temp); site=root/'site';site.mkdir()
        payload={name[len('adapter/'):]:data for name,data in files.items() if name.startswith('adapter/')}
        for name,row in {'numpy':NUMPY[manifest['python_minor']],'py3langid':LANGID}.items():
            parts=wheel_files(files['wheels/'+row['filename']],name,row)
            if payload.keys() & parts.keys(): raise ValueError('Overlapping wheel files')
            payload.update(parts)
        for name,data in payload.items():
            dest=site/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        # No installer, PATH discovery, inherited Python settings or project CWD.
        completed=subprocess.run([str(interpreter),'-I','-S','-B','-c',PROBE,str(site),manifest['python_minor']],
            cwd=root,input=b'',capture_output=True,check=False,
            env={'PATH':os.defpath,'LANG':'C.UTF-8','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
    if completed.returncode:
        raise ValueError('The selected ABI runtime did not pass the package probe')
    try:
        observation=json.loads(completed.stdout)
    except (ValueError,UnicodeError) as error:
        raise ValueError('Invalid runtime observation') from error
    expected=dict(python_minor=manifest['python_minor'],implementation='cpython',platform='linux-x86_64',
        numpy_version=NUMPY[manifest['python_minor']]['version'],py3langid_version=LANGID['version'],
        numpy_check=6,core_build_sha256=expected_core_sha256)
    if (type(observation) is not dict or set(observation) != set(expected)|{'python_version'}
            or any(observation[k]!=v for k,v in expected.items())
            or not observation['python_version'].startswith(manifest['python_minor']+'.')):
        raise ValueError('Runtime identity differs from the separate package')
    return dict(format_version=1,package_sha256=package_hash,observation=observation,
                language_classification_verified=False,release_approved=False)


def probe_matrix(packages, interpreters, *, expected_core_sha256):
    """All five separately selected, executed ABIs or an explicit incomplete matrix."""
    if set(packages)!=set(NUMPY) or set(interpreters)!=set(NUMPY):
        raise ValueError('Incomplete CPython 3.10–3.14 package/interpreter matrix')
    rows={}
    for minor in NUMPY:
        manifest,_,_=verify_package(packages[minor],expected_core_sha256=expected_core_sha256)
        if manifest['python_minor']!=minor: raise ValueError('Duplicate or substituted ABI package')
        rows[minor]=probe_package(packages[minor],interpreters[minor],expected_core_sha256=expected_core_sha256)
    return dict(format_version=1,packages=rows,release_approved=False)
