"""Real delivered PYZ in explicitly synthetic runtime-descriptor envelopes.

These envelopes are not full Results or snapshot-validation fixtures. No claim
about a repository, Apply, a proposal or the missing PH-API-RESULT is made.
"""

from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from support.processes import run_python


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/patchharbor140'
ARTIFACT_SHA256 = '4e0d26997bffe9476e79d98211cef2d93be7899063a0eb3480bea2ffa3d8f594'


def envelope(root, *, unavailable=False):
    artifact = (FIXTURE / 'patchharbor-1.4.0.pyz').read_bytes()
    assert sha256(artifact).hexdigest() == ARTIFACT_SHA256
    metadata = json.loads((FIXTURE / 'runtime.json').read_bytes())
    if unavailable:
        metadata.update(status='unavailable', reason='artifact_missing')
        for key in ('artifact', 'profile', 'content_id', 'content_id_algorithm',
                    'runtime_dependencies', 'provenance', 'capabilities'):
            metadata[key] = None
    raw = json.dumps(metadata, sort_keys=True, separators=(',', ':')).encode()
    runtime = {key: metadata[key] for key in ('status', 'reason', 'artifact')}
    runtime['metadata'] = {'path': 'runtime/runtime.json', 'size': len(raw),
                           'sha256': sha256(raw).hexdigest()}
    manifest = {'marker': 'patch-harbor-result-bundle', 'format_version': 3,
                'runtime': runtime}
    target = root / 'runtime-envelope.zip'
    with ZipFile(target, 'w') as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        archive.writestr('runtime/runtime.json', raw)
        if not unavailable:
            archive.writestr(metadata['artifact']['path'], artifact)
    return target, sha256(target.read_bytes()).hexdigest()


def native_patch(root):
    # An inspect-only native patch. The entrypoint is data and never executed.
    patch = root / 'inspect-only.zip'
    with ZipFile(patch, 'w') as archive:
        archive.writestr('patch.json', json.dumps({
            'marker': 'patch-harbor', 'format_version': 1, 'entrypoint': 'run.sh',
            'repo_id': '00000000-0000-4000-8000-000000000001',
            'base_commit': '1' * 40, 'state_fingerprint': '2' * 16,
            'fingerprint_algorithm': 'patchharbor-state-v1',
        }))
        archive.writestr('run.sh', '#!/usr/bin/env bash\n# PATCHHARBOR\nexit 0\n')
    return patch


def probe(root, body, *, distribution=None):
    distribution = distribution or ROOT / 'src'
    prefix = 'import sys; sys.path.insert(0,' + repr(str(distribution)) + ');\n'
    prefix += '''
import json, os
from pathlib import Path
def deny_external(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn',
                 'socket.connect', 'socket.getaddrinfo'}:
        raise AssertionError('unexpected external effect: ' + event)
sys.addaudithook(deny_external)
'''
    result = run_python(['-I', '-S', '-B', '-c', prefix + body], root, capture=True)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    return json.loads(result.stdout)


def adapter_source(reference, digest, workspace):
    return ('from specroad.transport import PatchHarborRuntime, TransportUnavailable\n'
            'runtime = PatchHarborRuntime(' + repr(str(reference)) +
            ', trusted_source_sha256=' + repr(digest) +
            ', workspace=' + repr(str(workspace)) + ')\n')
