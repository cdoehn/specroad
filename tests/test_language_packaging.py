"""Offline packaging behavior against the original CPython 3.14 wheels.

Other ABI entries are declarations, never runtime evidence for those versions.
"""
from hashlib import sha256
import json
from zipfile import ZipFile
import pytest

from language_packaging.build import build_language, read_wheels
from language_packaging.inventory import LANGID, NUMPY, MODEL_SHA256
from support.portable import ROOT

WHEELS = ROOT / 'tests/data/language_wheels'


@pytest.fixture(scope='module')
def offline_package(tmp_path_factory):
    root = tmp_path_factory.mktemp('language-package')
    output = root / 'cp314.zip'
    build_language(ROOT / 'src', WHEELS, '3.14', output)
    return output.read_bytes()


def test_original_wheels_bind_adapter_model_licenses_and_inventory(offline_package):
    import io
    with ZipFile(io.BytesIO(offline_package)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['abi'] == 'cp314' and manifest['platform'] == 'linux-x86_64'
        assert manifest['runtime_verification'] == 'not_run'
        assert manifest['release_approved'] is False
        assert set(archive.namelist()) == set(manifest['files']) | {'manifest.json'}
        for name, expected in manifest['files'].items():
            raw = archive.read(name)
            assert len(raw) == expected['size'] and sha256(raw).hexdigest() == expected['sha256']
        assert sha256(archive.read('model/model.npz.xz')).hexdigest() == MODEL_SHA256
        assert archive.read('adapter/specroad/analyzers/file_adapter.py')
        assert {d['name']:d['version'] for d in manifest['dependencies']} == {
            'numpy':'2.3.5', 'py3langid':'0.4.0'}
        for item in manifest['dependencies']:
            assert item['licenses'] and all(archive.read(p) for p in item['licenses'])
            assert sha256(archive.read(item['wheel'])).hexdigest() == item['sha256']


@pytest.mark.parametrize('minor', ['3.10','3.11','3.12','3.13','3.14'])
def test_missing_exact_wheel_is_explicit_and_does_not_use_another_abi(tmp_path, minor):
    with pytest.raises(ValueError, match='Missing offline wheel'):
        build_language(ROOT / 'src', tmp_path, minor, tmp_path/'out.zip')
    assert not (tmp_path/'out.zip').exists()
    assert NUMPY[minor]['abi'] == 'cp'+minor.replace('.','')


def test_unsupported_python_is_not_a_universal_numpy_fallback(tmp_path):
    with pytest.raises(ValueError, match='No matching'):
        read_wheels(tmp_path, '3.15')


def test_upstream_wheel_replacement_is_rejected_before_publication(tmp_path):
    (tmp_path/NUMPY['3.14']['filename']).write_bytes(b'not the original numpy')
    with pytest.raises(ValueError, match='Wheel hash mismatch'):
        build_language(ROOT/'src', tmp_path, '3.14', tmp_path/'out.zip')
    assert not (tmp_path/'out.zip').exists()


def test_wheel_symlink_is_not_followed(tmp_path):
    (tmp_path/NUMPY['3.14']['filename']).symlink_to(WHEELS/NUMPY['3.14']['filename'])
    with pytest.raises(ValueError, match='Linked'):
        read_wheels(tmp_path, '3.14')


def test_existing_destination_preserves_original_bytes(tmp_path):
    from language_packaging.build import publish_archive
    output = tmp_path/'existing.zip'; output.write_bytes(b'original')
    with pytest.raises(FileExistsError):
        publish_archive({'example': b'new'}, output)
    assert output.read_bytes() == b'original'


def test_extra_is_optional_and_pins_the_reference_backend():
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    project = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']
    assert project['dependencies'] == []
    assert project['optional-dependencies']['language'] == [
        'py3langid==0.4.0', "numpy==2.2.6; python_version == '3.10'",
        "numpy==2.3.5; python_version >= '3.11' and python_version < '3.15'"]
    assert LANGID['version'] == '0.4.0'
