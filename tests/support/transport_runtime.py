"""Pinned standalone runtime; historical descriptor envelopes are negative data."""

from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from support.processes import run_python


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/patchharbor160'
RUNTIME_FIXTURE = ROOT / 'tests/fixtures/patchharbor180'
ARTIFACT_SHA256 = '050cc2d1dc3ecbb1478f6a40c9a5123d1d34d350215d5cc0303025ea08dc4f1e'
LEGACY_SHA256 = '377e715d7cb443eb5e80a3e7f9e8405f36092a0f7c062745b70c8b3a2e3eb055'


def runtime_artifact(root):
    source = RUNTIME_FIXTURE / 'patchharbor-1.8.0.pyz'
    raw = source.read_bytes()
    assert sha256(raw).hexdigest() == ARTIFACT_SHA256
    target = root / source.name
    target.write_bytes(raw)
    return target, ARTIFACT_SHA256


def envelope(root, *, unavailable=False, fixture=FIXTURE):
    metadata = json.loads((fixture / 'runtime.json').read_bytes())
    artifact = (fixture / Path(metadata['artifact']['path']).name).read_bytes()
    assert sha256(artifact).hexdigest() == metadata['artifact']['sha256']
    if fixture == FIXTURE:
        assert sha256(artifact).hexdigest() == LEGACY_SHA256
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
            ', trusted_artifact_sha256=' + repr(digest) +
            ', workspace=' + repr(str(workspace)) + ')\n')
