"""Real model ranking in the original isolated CPython-3.14 offline package.

The small synthetic examples are integration inputs, not the reviewed release
acceptance corpus. A foreign ABI rejection is not a positive runtime proof.
"""
import ast
from hashlib import sha256
import io
import json
import lzma
import platform
import sys
import sysconfig
from zipfile import ZipFile

from specroad.analyzers._reference_candidates import CANDIDATES, CANDIDATES_SHA256
from support.processes import run_python
from test_analyzer_model_integration import model_installation as _model_installation
from test_analyzer_reference import reference_request
from test_language_packaging import offline_package as _offline_package

model_installation = _model_installation
offline_package = _offline_package


def test_candidates_match_every_original_model_column_with_ordered_alias_deduplication(offline_package):
    with ZipFile(io.BytesIO(offline_package)) as package:
        model = package.read('model/model.npz.xz')
    with ZipFile(io.BytesIO(lzma.decompress(model))) as archive:
        raw = archive.read('classes.npy')
    assert raw[:8] == b'\x93NUMPY\x01\x00'
    header_size = int.from_bytes(raw[8:10], 'little')
    header = ast.literal_eval(raw[10:10 + header_size].decode('ascii'))
    assert header == {'descr': '<U3', 'fortran_order': False, 'shape': (142,)}
    rows = [raw[i:i + 12].decode('utf-32-le').rstrip('\x00')
            for i in range(10 + header_size, len(raw), 12)]
    expected = tuple(dict.fromkeys(rows))
    assert len(rows) == 142 and len(expected) == 140
    assert rows.count('sr') == rows.count('uz') == 2
    assert CANDIDATES == expected
    raw_catalog = json.dumps(list(expected), ensure_ascii=False, separators=(',', ':')).encode()
    assert CANDIDATES_SHA256 == sha256(raw_catalog).hexdigest()


def test_real_library_ranks_complete_texts_with_original_request_and_model_bindings(model_installation, tmp_path):
    site, manifest = model_installation
    texts = [
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
    request = reference_request(texts)
    path = tmp_path / 'request.json'
    path.write_bytes(request.canonical_bytes)
    compatible = (sys.version_info[:2] == (3, 14) and sys.platform == 'linux'
                  and platform.machine() == 'x86_64' and not sysconfig.get_config_var('Py_GIL_DISABLED'))
    body = '''
import sys, os, json, hashlib, math
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
sys.path.insert(0, sys.argv[1])
from specroad.analyzers.reference import rank_request
from specroad.analyzers.requests import AnalyzerRequest
from specroad.analyzers._values import AnalyzerError
raw = Path(sys.argv[2]).read_bytes()
request = AnalyzerRequest(raw)
if sys.argv[3] == 'no':
    try:
        rank_request(request)
    except AnalyzerError as error:
        assert error.exit_code == 5
    else:
        raise AssertionError('foreign ABI accepted')
    print(json.dumps({'compatible': False, 'classification_verified': False}))
else:
    import socket, subprocess, py3langid.langid as library
    import py3langid.modelio as storage
    def forbidden(*args, **kwargs):
        raise AssertionError('network, filter or upstream operational mode exposed')
    socket.socket = subprocess.Popen = library.main = storage.save_model = forbidden
    library.LanguageIdentifier.set_languages = forbidden
    assert library.IDENTIFIER is None
    result = rank_request(request)
    assert request.canonical_bytes == raw and library.IDENTIFIER is None
    assert result.request_id == request.data['request_id']
    assert result.snapshot_sha256 == request.data['snapshot_sha256']
    assert result.descriptor_sha256 == request.data['analyzers'][0]['descriptor_sha256']
    assert result.engine.model_sha256 == 'f4f4a2c3465ca1f081541037f9cac23021d68151c2f709c55ae5eedfca522963'
    assert result.engine.library_versions == (('numpy', '2.3.5'), ('py3langid', '0.4.0'))
    assert result.engine.python_implementation == 'cpython'
    assert result.engine.python_version.startswith('3.14.')
    candidates = result.engine.candidates
    catalog = json.dumps(list(candidates), separators=(',', ':')).encode()
    assert result.engine.candidates_sha256 == hashlib.sha256(catalog).hexdigest()
    assert len(candidates) == len(set(candidates)) == 140
    originals = {item['subject_key']: item for item in request.data['subjects']}
    expected_labels = dict(zip((item['subject_key'] for item in request.data['subjects']), ('de','en','fr','ja')))
    assert [item.subject_key for item in result.subjects] == sorted(originals)
    # An independent original library call checks lossless adapter projection.
    # Both models are real; the first owned model has already been released.
    from specroad.analyzers._model_session import ModelSession
    with ModelSession() as session:
        model = session.model()
        assert tuple(model.labels) == candidates
        for item in result.subjects:
            subject = originals[item.subject_key]
            expected = tuple(sorted(model.rank(subject['value']), key=lambda row: (-row[1], row[0])))
            assert item.scores == expected
            assert item.value_sha256 == subject['value_sha256']
            assert len(item.scores) == 140 and {label for label, _ in item.scores} == set(candidates)
            assert all(math.isfinite(score) and 0 <= score <= 1 for _, score in item.scores)
            assert abs(sum(score for _, score in item.scores) - 1.0) < 0.00001
            assert item.scores[0][0] == expected_labels[item.subject_key]
    assert library.IDENTIFIER is None and Path(sys.argv[2]).read_bytes() == raw
    print(json.dumps({'compatible': True, 'ranked': len(result.subjects),
                      'candidates': len(candidates), 'classification_verified': False}))
'''
    result = run_python(['-I', '-S', '-B', '-c', body, str(site), str(path),
                         'yes' if compatible else 'no'], tmp_path, capture=True)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed == ({'compatible': True, 'ranked': 4, 'candidates': 140,
                         'classification_verified': False} if compatible else
                        {'compatible': False, 'classification_verified': False})
    assert path.read_bytes() == request.canonical_bytes
    assert manifest['runtime_verification'] == 'not_run' and manifest['release_approved'] is False
