"""Load the actual pinned model in its supported, isolated add-on runtime."""
import io
import platform
import sys
import sysconfig
from zipfile import ZipFile

import pytest

from language_packaging.build import wheel_files
from language_packaging.inventory import LANGID, NUMPY
from language_packaging.verify import verify_package
from support.processes import run_python
from test_language_packaging import offline_package as _offline_package

offline_package = _offline_package


@pytest.fixture(scope='module')
def model_installation(tmp_path_factory, offline_package):
    root = tmp_path_factory.mktemp('model-runtime')
    archive = root / 'addon.zip'; archive.write_bytes(offline_package)
    manifest, files, _ = verify_package(archive)
    site = root / 'site'; site.mkdir()
    payload = {n[len('adapter/'):]: raw for n, raw in files.items() if n.startswith('adapter/')}
    for name, row in {'numpy':NUMPY['3.14'], 'py3langid':LANGID}.items():
        payload.update(wheel_files(files['wheels/' + row['filename']], name, row))
    for name, raw in payload.items():
        path = site / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    return site, manifest


def test_real_model_is_loaded_once_per_session_without_global_identifier(model_installation, tmp_path):
    site, manifest = model_installation
    # The fixture contains cp314 binaries. Another ABI must be rejected, never
    # reported as a successful model-load observation for that ABI.
    compatible = (sys.version_info[:2] == (3, 14) and sys.platform == 'linux'
                  and platform.machine() == 'x86_64' and not sysconfig.get_config_var('Py_GIL_DISABLED'))
    body = '''
import sys, os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
sys.path.insert(0, sys.argv[1])
from specroad.analyzers._model_session import ModelSession
from specroad.analyzers._values import AnalyzerError
if sys.argv[2] == 'no':
    try:
        with ModelSession() as session: session.model()
    except AnalyzerError as error:
        assert error.exit_code == 5
    else:
        raise AssertionError('foreign ABI accepted')
else:
    import py3langid.langid as library
    import py3langid.modelio as storage
    count = []
    original = storage.load_model
    def observe(raw):
        count.append(1)
        return original(raw)
    storage.load_model = observe
    assert library.IDENTIFIER is None
    with ModelSession() as session:
        assert not count
        model = session.model()
        assert session.model() is model
        assert model.nb_ptc.size > 0 and len(model.labels) > 50
        assert count == [1]
    assert session._model is None and library.IDENTIFIER is None
    del model
    with ModelSession() as second:
        second.model()
    assert count == [1, 1] and library.IDENTIFIER is None
'''
    result = run_python(['-I', '-S', '-B', '-c', body, str(site), 'yes' if compatible else 'no'],
                        tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    assert manifest['runtime_verification'] == 'not_run' and manifest['release_approved'] is False


def test_model_fixture_contains_exact_upstream_bytes(offline_package):
    from hashlib import sha256
    from specroad.analyzers._model_session import MODEL_SHA256
    with ZipFile(io.BytesIO(offline_package)) as archive:
        model = archive.read('model/model.npz.xz')
    assert sha256(model).hexdigest() == MODEL_SHA256
