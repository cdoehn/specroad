"""Real isolated adapter probes; fault injection belongs only to the test host.

These synthetic integration inputs are not a reviewed language corpus. The
trusted test bootstrap composes the existing complete adapter and transport;
it does not claim the separately planned durable Work dispatcher is integrated.
"""
from hashlib import sha256
from pathlib import Path
import sys

import pytest

from language_packaging.build import build_language, wheel_files
from language_packaging.inventory import LANGID, NUMPY
from language_packaging.runtime_matrix import load_runtime_matrix
from language_packaging.verify import verify_package
from specroad.analyzers.file_adapter import default_inputs
from specroad.analyzers.subjects import request_from_project
from specroad.analyzers.worker_transport import execute
from support.domain import domain_value
from support.portable import ROOT
from support.read_only import make_project
from support.relations import aid


@pytest.fixture(scope='module')
def runtime_factory(tmp_path_factory):
    """Reuse only immutable installations; each case owns its request/project."""
    matrix = load_runtime_matrix()
    installations = {}

    def obtain(minor='3.14'):
        if minor not in installations:
            root = tmp_path_factory.mktemp('acceptance-' + minor)
            archive = root / 'addon.zip'
            build_language(ROOT / 'src', matrix['wheelhouse'], minor, archive)
            manifest, files, _ = verify_package(archive)
            site = root / 'site'
            site.mkdir()
            payload = {n[len('adapter/'):]: raw for n, raw in files.items()
                       if n.startswith('adapter/')}
            for name, wheel in {'numpy': NUMPY[minor], 'py3langid': LANGID}.items():
                payload.update(wheel_files(files['wheels/' + wheel['filename']], name, wheel))
            for name, raw in payload.items():
                target = site / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            installations[minor] = site, matrix['interpreters'][minor], manifest
        return installations[minor]

    return obtain


def native_request(root, cases):
    root.mkdir()
    values = [domain_value('requirement', id=aid(number=i + 1),
                           statement=text, language=language)
              for i, (language, text) in enumerate(cases)]
    make_project(root, *values)
    (root / 'unselected.txt').write_text('PRIVATE: not selected as an analyzer subject')
    return request_from_project(root, **default_inputs({}), analysis_id='acceptance:original')


# Test-owned executable bytes, selected by the test, never by subject content,
# descriptor, model input, environment variable, project path or JSON extension.
WORKER = r'''
import os, socket, subprocess, sys
sys.path.insert(0, sys.argv[1])
from specroad.analyzers._values import encoded, digest
from specroad.analyzers.requests import AnalyzerRequest, create_request
from specroad.analyzers.packages import create_package
from specroad.analyzers._execution import unavailable_package
request = AnalyzerRequest(sys.stdin.buffer.read())
original = request.canonical_bytes
if MODE.startswith('wire:'):
    fault = MODE.split(':', 1)[1]
    package = unavailable_package(request)
    value = package.data
    if fault == 'exit':
        raise SystemExit(17)
    if fault == 'foreign':
        data = request.data
        for subject in data['subjects']:
            subject['value'] += ' Other original value.'
            subject['value_sha256'] = digest(subject['value'])
        other = create_request(**{k: data[k] for k in
            ('analyzers', 'subjects', 'context', 'settings', 'extensions')},
            analysis_id=data['request_id'])
        value['reports'] = unavailable_package(other).data['reports']
    elif fault == 'request':
        value['request']['request_id'] = 'different:request'
    elif fault == 'duplicate':
        value['reports'].append(value['reports'][0])
    elif fault == 'missing_subject':
        value['reports'][0]['subjects'] = []
    elif fault == 'duplicate_subject':
        value['reports'][0]['subjects'].append(value['reports'][0]['subjects'][0])
    elif fault == 'field':
        value['reports'][0]['executable'] = 'sh'
    elif fault == 'stale_snapshot':
        value['reports'][0]['snapshot_sha256'] = '0' * 64
    elif fault == 'score_hash':
        value['reports'][0]['subjects'][0]['payload'] = {
            'specroad.language_detection': {'decision': {'status': 'detected',
                'language': 'en', 'scores': [{'language': 'en', 'score': '1.000000000000'}]}}}
    raw = encoded(value)
    if fault == 'truncated': raw = raw[:-1]
    elif fault == 'empty': raw = b''
    elif fault == 'extra_json': raw += b'\n{}'
    elif fault == 'duplicate_key': raw = b'{"package_version":"1.0.0",' + raw[1:]
    sys.stdout.buffer.write(raw)
    raise SystemExit(0)

# py3langid's pinned modelio.load_model decompresses into an anonymous file.
# Allocate that single test-owned resource before the write guard. The original
# decoder receives this real file only while loading the hash-checked model;
# no pathname or authority is supplied by a subject, and no write guard is relaxed.
import stat, tempfile
from types import SimpleNamespace
scratch = tempfile.TemporaryFile(suffix='.npz')
scratch_info = os.fstat(scratch.fileno())
assert stat.S_ISREG(scratch_info.st_mode) and scratch_info.st_nlink == 0
scratch_claims = []
def load_with_scratch(storage):
    previous_tempfile = storage.tempfile
    def claim_scratch(*args, **kwargs):
        assert not args and kwargs == {'suffix': '.npz'}
        assert not scratch.closed and not scratch_claims
        scratch_claims.append(1)
        return scratch
    storage.tempfile = SimpleNamespace(TemporaryFile=claim_scratch)
    try:
        return load()
    finally:
        storage.tempfile = previous_tempfile
        scratch.close()

violations = []
def forbidden(*args, **kwargs):
    violations.append('capability')
    raise AssertionError('subject obtained a network/process/write capability')
def audit(event, args):
    if event == 'open':
        _, mode, flags = args
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            forbidden()
    elif event in ('os.remove', 'os.rename', 'os.mkdir', 'os.rmdir', 'os.chmod',
                   'os.truncate', 'os.utime', 'os.link', 'os.symlink'):
        forbidden()
sys.addaudithook(audit)
socket.socket = subprocess.Popen = os.system = forbidden
import py3langid.langid as library
import py3langid.modelio as storage
library.main = storage.save_model = library.LanguageIdentifier.set_languages = forbidden
from specroad.analyzers import _model_session
from specroad.analyzers._reference_candidates import CANDIDATES
from specroad.analyzers.reports import create_report
from specroad.analyzers.worker import analyze_language
load = _model_session.load_reference_model
loads, seen = [], []
def observed_load():
    model = load_with_scratch(storage)
    loads.append(1)
    rank = model.rank
    def observed_rank(text):
        seen.append(digest(text))
        if MODE.startswith('score:') and text.startswith('FAULT '):
            fault = MODE.split(':', 1)[1]
            rows = [(label, 1.0 if label == 'en' else 0.0) for label in CANDIDATES]
            if fault == 'missing': return rows[:-1]
            if fault == 'duplicate': return rows[:-1] + [rows[0]]
            if fault == 'shape': return None
            if fault == 'sum': return [(label, 0.5) for label in CANDIDATES]
            rows[0] = (rows[0][0], {'nan': float('nan'), 'infinite': float('inf'),
                'negative': -0.1, 'above_one': 1.1, 'boolean': True}[fault])
            return rows
        return rank(text)
    class ObservedModel:
        # The original upstream object is slotted. Observe through read-only
        # delegation; do not mutate it or replace real positive rankings.
        @property
        def labels(self):
            return model.labels
        @property
        def _norm_probs(self):
            return model._norm_probs
        @property
        def min_confidence(self):
            return model.min_confidence
        def rank(self, text):
            return observed_rank(text)
    return ObservedModel()
_model_session.load_reference_model = observed_load
try:
    assessment = analyze_language(request)
finally:
    scratch.close()
assert not loads or len(scratch_claims) == 1
assert request.canonical_bytes == original and library.IDENTIFIER is None and not violations
report = assessment.report.data
checked = create_report(request, analyzer_id='specroad.py3langid',
    engine=report['engine'], subjects=report['subjects'], findings=report['findings'],
    run_status=report['run_status'], run_id=report['run_id'], extensions=report['extensions'],
    operational={'test_probe': {'model_loads': len(loads), 'ranked_value_hashes': seen}})
sys.stdout.buffer.write(create_package(request, [checked]).canonical_bytes)
'''


def invoke_case(monkeypatch, runtime, request, mode='positive'):
    """Use real pipes/process cleanup and the production response validator."""
    from specroad.analyzers import _worker_process
    site, interpreter, _ = runtime
    assert sha256(Path(interpreter['executable']).read_bytes()).hexdigest() == interpreter['sha256']
    run_process = _worker_process.run_process
    def observed_process(*args, **kwargs):
        completed = run_process(*args, **kwargs)
        if completed.returncode != 0 and mode != 'wire:exit':
            # Preserve the actual process result and production error contract.
            # Bound diagnostics to stderr from this synthetic test worker only.
            print('Analyzer fixture worker failed: ' +
                  completed.stderr[-8192:].decode('utf-8', errors='replace'), file=sys.stderr)
        return completed
    with monkeypatch.context() as context:
        context.setattr(sys, 'executable', interpreter['executable'])
        context.setattr(_worker_process, 'distribution_path', lambda: site)
        context.setattr(_worker_process, 'run_process', observed_process)
        context.setattr(_worker_process, 'BOOTSTRAP', 'MODE = ' + repr(mode) + '\n' + WORKER)
        return execute(request)
