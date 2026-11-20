"""Five mandatory real offline backends; no foreign-ABI or skip success path.

Original wheels and interpreters are explicit preinstalled test dependencies.
Synthetic integration texts do not replace the reviewed release corpus.
"""
from hashlib import sha256
import json
from pathlib import Path

import pytest

from language_packaging.build import build_language, wheel_files
from language_packaging.inventory import LANGID, NUMPY
from language_packaging.runtime_matrix import load_runtime_matrix
from language_packaging.verify import verify_package
from support.portable import ROOT
from support.processes import run_python
from test_analyzer_reference import reference_request


TEXTS = [
    'Das System muss alle Änderungen an den gespeicherten Anforderungen vollständig '
    'protokollieren. Benutzer können die ursprünglichen Angaben auch ohne eine '
    'Verbindung zum Internet lesen und auf einem anderen Rechner weiterbearbeiten.',
    'The application must preserve the entire original requirement when a user '
    'exports the project. Every change must remain associated with its author '
    'and the corresponding revision so that another user can inspect the history.',
    'Le système doit conserver toutes les informations du projet pendant son '
    'exportation. Les utilisateurs doivent pouvoir consulter les exigences '
    'enregistrées sans connexion au réseau et retrouver chaque modification.',
    'このシステムは、利用者が入力した要求の全文を保存しなければなりません。'
    'プロジェクトを別のコンピューターへ移す場合にも、変更履歴と元の文章を保持します。'
    '利用者はネットワークに接続していなくても保存した情報を確認できます。',
]

PROBE = r'''
import hashlib, json, math, os, platform, sys, sysconfig, unicodedata
from pathlib import Path
site, request_path, mode, expected_path = sys.argv[1:]
expected = json.loads(Path(expected_path).read_bytes())
assert sys.implementation.name == 'cpython' and sys.platform == 'linux'
assert platform.machine() == 'x86_64' and not sysconfig.get_config_var('Py_GIL_DISABLED')
assert platform.python_version() == expected['version']
assert hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest() == expected['sha256']
assert sysconfig.get_config_var('SOABI').startswith('cpython-' + expected['abi'][2:] + '-')
os.environ['OPENBLAS_NUM_THREADS'] = os.environ['OMP_NUM_THREADS'] = '1'
sys.path.insert(0, site)
if mode.startswith('missing_'):
    missing = mode[len('missing_'):]
    class MissingDependency:
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split('.')[0] == missing:
                raise ModuleNotFoundError(fullname)
    sys.meta_path.insert(0, MissingDependency())
import socket, subprocess
def forbidden(*args, **kwargs):
    raise AssertionError('network, subprocess, model write or candidate filter used')
socket.socket = subprocess.Popen = forbidden
from specroad.analyzers.reference import rank_request
from specroad.analyzers.requests import AnalyzerRequest
from specroad.analyzers._values import AnalyzerError
from specroad import _build
assert _build.BUILD_METADATA == expected['core_build']
raw = Path(request_path).read_bytes()
request = AnalyzerRequest(raw)
if mode != 'positive':
    try:
        rank_request(request)
    except AnalyzerError as error:
        assert error.exit_code == 5
    else:
        raise AssertionError('unavailable backend returned successful rankings')
    assert request.canonical_bytes == raw
    from specroad.analyzers.file_adapter import default_inputs
    from specroad.analyzers.requests import create_request
    from specroad.analyzers.language_text import prepare_request
    unavailable_inputs = {k: request.data[k] for k in ('analyzers', 'subjects', 'context', 'settings', 'extensions')}
    unavailable_inputs['settings'] = default_inputs({})['settings']
    unavailable_request = create_request(**unavailable_inputs, analysis_id=request.data['request_id'])
    unavailable = prepare_request(unavailable_request)
    assert len(unavailable.subjects) == 4 and unavailable.engine is None
    assert all(s.status == 'unavailable' and not s.scores for s in unavailable.subjects)
    assert unavailable.snapshot_sha256 == unavailable_request.data['snapshot_sha256']
    print(json.dumps({'mode': mode, 'version': platform.python_version(), 'exit_code': 5}))
else:
    import py3langid.langid as library
    import py3langid.modelio as storage
    library.main = storage.save_model = library.LanguageIdentifier.set_languages = forbidden
    assert library.IDENTIFIER is None
    result = rank_request(request)
    assert library.IDENTIFIER is None and request.canonical_bytes == raw
    assert result.request_id == request.data['request_id']
    assert result.snapshot_sha256 == request.data['snapshot_sha256']
    assert result.descriptor_sha256 == request.data['analyzers'][0]['descriptor_sha256']
    engine = result.engine
    assert engine.model_sha256 == expected['model_sha256']
    assert engine.library_versions == (('numpy', expected['numpy']), ('py3langid', '0.4.0'))
    assert engine.adapter_version == request.data['analyzers'][0]['descriptor']['adapter_version']
    assert engine.python_implementation == 'cpython' and engine.python_version == expected['version']
    assert engine.unicode_version == unicodedata.unidata_version
    assert len(engine.candidates) == len(set(engine.candidates)) == 140
    assert engine.candidates_sha256 == hashlib.sha256(json.dumps(list(engine.candidates), separators=(',', ':')).encode()).hexdigest()
    originals = {s['subject_key']: s for s in request.data['subjects']}
    labels = dict(zip((s['subject_key'] for s in request.data['subjects']), ('de', 'en', 'fr', 'ja')))
    assert [s.subject_key for s in result.subjects] == sorted(originals)
    from specroad.analyzers._model_session import ModelSession
    with ModelSession() as session:
        model = session.model()
        assert tuple(model.labels) == engine.candidates
        for subject in result.subjects:
            original = originals[subject.subject_key]
            direct = tuple(sorted(model.rank(original['value']), key=lambda row: (-row[1], row[0])))
            assert subject.scores == direct and subject.value_sha256 == original['value_sha256']
            assert len(subject.scores) == 140 and {k for k, v in subject.scores} == set(engine.candidates)
            assert all(math.isfinite(v) and 0 <= v <= 1 for k, v in subject.scores)
            assert abs(sum(v for k, v in subject.scores) - 1) < 0.00001
            assert subject.scores[0][0] == labels[subject.subject_key]
    assert library.IDENTIFIER is None
    from specroad.analyzers.file_adapter import default_inputs
    from specroad.analyzers.requests import create_request
    from specroad.analyzers.language_text import prepare_request
    materialized = {k: request.data[k] for k in ('analyzers', 'subjects', 'context', 'settings', 'extensions')}
    materialized['settings'] = default_inputs({})['settings']
    language_request = create_request(**materialized, analysis_id=request.data['request_id'])
    language_raw = language_request.canonical_bytes
    prepared = prepare_request(language_request)
    assert prepared.engine == result.engine
    assert prepared.preprocessing_version == 'ascii-edge-codepoints-v1'
    assert prepared.min_text_codepoints == 20
    assert prepared.snapshot_sha256 == language_request.data['snapshot_sha256']
    assert [(s.subject_key, s.value_sha256, s.scores) for s in prepared.subjects] == [
        (s.subject_key, s.value_sha256, s.scores) for s in result.subjects]
    assert all(s.status == 'ranked' and s.reason is None for s in prepared.subjects)
    assert language_request.canonical_bytes == language_raw and request.canonical_bytes == raw
    # Negative request settings must fail before another model can be decoded.
    storage.load_model = forbidden
    for name in ('languages', 'candidates', 'model'):
        bad = AnalyzerRequest(Path(request_path).with_name(name + '.json').read_bytes())
        try:
            rank_request(bad)
        except AnalyzerError as error:
            assert error.exit_code == 2
        else:
            raise AssertionError('forbidden reference settings accepted')
    assert Path(request_path).read_bytes() == raw
    print(json.dumps({'mode': mode, 'version': platform.python_version(), 'ranked': 4,
                      'candidates': 140, 'filters_rejected': 3}))
'''


@pytest.mark.parametrize('minor', ['3.10', '3.11', '3.12', '3.13', '3.14'])
def test_original_backend_and_failures_on_each_supported_runtime(tmp_path, minor):
    matrix = load_runtime_matrix()
    row = matrix['interpreters'][minor]
    archive = tmp_path / ('cp' + minor.replace('.', '') + '.zip')
    build_language(ROOT / 'src', matrix['wheelhouse'], minor, archive)
    manifest, files, _ = verify_package(archive)
    assert manifest['python_minor'] == minor and manifest['abi'] == NUMPY[minor]['abi']
    assert manifest['runtime_verification'] == 'not_run' and manifest['release_approved'] is False
    site = tmp_path / 'site'; site.mkdir()
    payload = {n[len('adapter/'):]: raw for n, raw in files.items() if n.startswith('adapter/')}
    for name, wheel in {'numpy': NUMPY[minor], 'py3langid': LANGID}.items():
        payload.update(wheel_files(files['wheels/' + wheel['filename']], name, wheel))
    for name, raw in payload.items():
        path = site / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    del payload, files
    request = reference_request(TEXTS)
    path = tmp_path / 'request.json'; path.write_bytes(request.canonical_bytes)
    for name, value in (('languages', ['de']), ('candidates', ['en']), ('model', '/foreign/model')):
        (tmp_path / (name + '.json')).write_bytes(reference_request(TEXTS, settings={name: value}).canonical_bytes)
    expected = dict(row, abi=NUMPY[minor]['abi'], numpy=NUMPY[minor]['version'],
                    core_build=manifest['core_build'], model_sha256=manifest['model']['sha256'])
    binding = tmp_path / 'expected.json'; binding.write_text(json.dumps(expected), encoding='utf-8')
    for mode in ('positive', 'missing_numpy', 'missing_py3langid', 'model_hash'):
        if mode == 'model_hash':
            model = site / 'py3langid/data/model.npz.xz'
            original = model.read_bytes()
            model.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        result = run_python(['-I', '-S', '-B', '-c', PROBE, str(site), str(path), mode, str(binding)],
                            tmp_path, python=row['executable'], capture=True)
        assert result.returncode == 0, result.stderr
        observed = json.loads(result.stdout)
        assert observed == (dict(mode=mode, version=row['version'], ranked=4, candidates=140, filters_rejected=3)
                            if mode == 'positive' else dict(mode=mode, version=row['version'], exit_code=5))
    assert sha256(Path(row['executable']).read_bytes()).hexdigest() == row['sha256']
    assert path.read_bytes() == request.canonical_bytes
