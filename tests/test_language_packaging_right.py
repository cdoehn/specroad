"""Real package probe, closed inventory and independent ABI verification."""
import io
import json
import platform
import sys
from zipfile import ZipFile
import pytest

from language_packaging.build import encoded, publish_archive
from language_packaging.verify import verify_package, probe_package, probe_matrix
from support.portable import build_distribution
from support.processes import run_python
from test_language_packaging import offline_package as _offline_package

offline_package = _offline_package


@pytest.fixture
def package_path(tmp_path,offline_package):
    path=tmp_path/'package.zip';path.write_bytes(offline_package);return path


def test_original_package_runs_only_on_its_actual_abi(package_path):
    manifest,_,_=verify_package(package_path)
    core_hash=manifest['core_build']['build_sha256']
    if sys.version_info[:2] != (3,14) or sys.platform!='linux' or platform.machine()!='x86_64':
        with pytest.raises(ValueError,match='did not pass'):
            probe_package(package_path,sys.executable,expected_core_sha256=core_hash)
        return  # An incompatible runtime is tested as rejection, never as compatibility evidence.
    result=probe_package(package_path,sys.executable,expected_core_sha256=core_hash)
    assert result['observation']['python_minor']=='3.14'
    assert result['observation']['numpy_version']=='2.3.5'
    assert result['observation']['py3langid_version']=='0.4.0'
    assert result['observation']['numpy_check']==6
    assert result['release_approved'] is False and result['language_classification_verified'] is False


@pytest.mark.parametrize('minor',['3.10','3.11','3.12','3.13','3.14'])
def test_each_missing_runtime_prevents_an_all_abi_claim(package_path,minor):
    interpreters={m:sys.executable for m in ('3.10','3.11','3.12','3.13','3.14')}
    packages={m:package_path for m in interpreters}
    del interpreters[minor]
    with pytest.raises(ValueError,match='Incomplete'):
        probe_matrix(packages,interpreters,expected_core_sha256='a'*64)


def test_reusing_cp314_as_cp310_is_not_a_matrix(package_path):
    manifest,_,_=verify_package(package_path)
    rows={m:package_path for m in ('3.10','3.11','3.12','3.13','3.14')}
    with pytest.raises(ValueError,match='substituted ABI'):
        probe_matrix(rows,{m:sys.executable for m in rows},
                     expected_core_sha256=manifest['core_build']['build_sha256'])


@pytest.mark.parametrize('change',['model','license','wheel','core','extra','abi','approved'])
def test_manifest_rehash_does_not_authorize_different_content(tmp_path,offline_package,change):
    from hashlib import sha256
    with ZipFile(io.BytesIO(offline_package)) as archive:
        files={n:archive.read(n) for n in archive.namelist()}
    manifest=json.loads(files.pop('manifest.json'))
    if change=='model':files['model/model.npz.xz']=b'foreign model'
    elif change=='license':files[manifest['dependencies'][0]['licenses'][0]]=b'foreign license'
    elif change=='wheel':files[manifest['dependencies'][0]['wheel']]=b'foreign wheel'
    elif change=='core':files['adapter/specroad/__init__.py']=b'raise RuntimeError()\n'
    elif change=='extra':files['start.sh']=b'foreign command'
    elif change=='abi':manifest['abi']='cp310'
    elif change=='approved':manifest['release_approved']=True
    manifest['files']={n:dict(sha256=sha256(b).hexdigest(),size=len(b)) for n,b in files.items()}
    files['manifest.json']=encoded(manifest)
    path=publish_archive(files,tmp_path/'tampered.zip')
    with pytest.raises(ValueError):verify_package(path)


def test_independent_core_identity_is_required_before_execution(package_path):
    with pytest.raises(ValueError,match='Unexpected Core'):
        probe_package(package_path,sys.executable,expected_core_sha256='a'*64)


def test_core_module_and_zipapp_remain_independent_of_binary_addon(tmp_path):
    module,archive=build_distribution(tmp_path/'core')
    for path in module.rglob('*'):
        assert not path.name.endswith(('.so','.whl','.npz','.xz'))
        assert path.name not in ('numpy','numpy.libs','py3langid')
    for entry in (module,archive):
        result=run_python(['-I','-S','-B',str(entry),'version','--format','json'],tmp_path,capture=True)
        assert result.returncode==0,result.stderr
        data=json.loads(result.stdout)['result']
        assert data['release_approved'] is False


def test_special_package_input_is_rejected_without_waiting_for_a_writer(tmp_path):
    import os
    from language_packaging.build import regular_bytes
    path=tmp_path/'wheel.whl';os.mkfifo(path)
    with pytest.raises(ValueError,match='Invalid package input'):
        regular_bytes(path)
