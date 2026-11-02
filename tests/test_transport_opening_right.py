"""15.o.R: adversarial real packages, live boundaries and owned crash recovery."""
from copy import copy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import stat
from zipfile import ZipFile, ZipInfo

import pytest

from specroad.bundles import prepare_project_bundle
from specroad.bundles.container import BundleContainer, encode_bundle
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.cli.result_schemas import validate_result_document
from specroad.storage.archive import encode_zip
from support.transport_opening import make_handoff, opening_request, offline
from support.transport_outbound import tree
from support.folds import goal
from support.model import put
from specroad.model.paths import artifact_path
from test_transport_opening import distribution, handoff


def members(raw):
    with ZipFile(BytesIO(raw)) as archive:
        return {i.filename: archive.read(i) for i in archive.infolist()}


def rebound(files, *, project=None):
    files = dict(files)
    manifest = json.loads(files.pop('handoff.json'))
    if project is not None:
        files['project/project.zip'] = project.source_bytes
        manifest.update(project_id=project.manifest['project_id'],
            scope_descriptor=project.manifest['scope_descriptor'],
            model_root_sha256=project.manifest['bundle_model_root_sha256'])
    manifest['reference']['sha256'] = sha256(files['reference/result.zip']).hexdigest()
    manifest['entries'] = [{'path': n, 'size': len(b), 'sha256': sha256(b).hexdigest()}
                           for n, b in sorted(files.items())]
    manifest.pop('package_id')
    manifest['package_id'] = sha256(b'specroad-ai-handoff-v1\0' + canonical_json_bytes(manifest)).hexdigest()
    return encode_zip({'handoff.json': canonical_json_bytes(manifest), **files},
                      max_uncompressed_bytes=512 * 1024 * 1024)


def own_package(root, handoff, raw=None):
    package = {'source': root / 'input.zip', 'runtime': root / 'trusted.pyz'}
    package['source'].write_bytes(handoff['source'].read_bytes() if raw is None else raw)
    package['runtime'].write_bytes(handoff['runtime'].read_bytes())
    return package


@pytest.mark.parametrize('damage', ('extra', 'unknown-field', 'bool-size', 'noncanonical',
    'truncated', 'duplicate', 'traversal', 'link', 'foreign-core', 'forged-build', 'wrong-hash', 'wrong-runtime'))
def test_passive_rejections_precede_workspace_and_code(tmp_path, distribution, handoff, damage):
    raw = handoff['source'].read_bytes(); files = members(raw)
    if damage == 'extra':
        files['unexpected.py'] = b'raise AssertionError("must not execute")'; raw = rebound(files)
    elif damage in ('unknown-field', 'bool-size', 'noncanonical'):
        manifest = json.loads(files['handoff.json'])
        if damage == 'unknown-field': manifest['approval'] = True
        elif damage == 'bool-size': manifest['entries'][0]['size'] = True
        files['handoff.json'] = (json.dumps(manifest, indent=2).encode() if damage == 'noncanonical'
                               else canonical_json_bytes(manifest))
        raw = encode_zip(files, max_uncompressed_bytes=512 * 1024 * 1024)
    elif damage == 'truncated': raw = raw[:-30]
    elif damage in ('duplicate', 'traversal', 'link'):
        stream = BytesIO()
        with ZipFile(stream, 'w') as archive:
            for name, data in files.items(): archive.writestr(name, data)
            if damage == 'link':
                entry = ZipInfo('linked'); entry.create_system = 3
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(entry, b'outside')
            else:
                archive.writestr('handoff.json' if damage == 'duplicate' else '../escape', b'foreign')
        raw = stream.getvalue()
    elif damage in ('foreign-core', 'forged-build'):
        changed = 'specroad/_build.py' if damage == 'forged-build' else 'specroad/__init__.py'
        stream = BytesIO()
        # A Python zipapp includes directories; the production bundle writer
        # intentionally accepts only file payloads. Preserve the actual PYZ
        # structure here so this case reaches the passive code-trust boundary.
        with ZipFile(BytesIO(files['runtime/specroad.pyz'])) as original, ZipFile(stream, 'w') as modified:
            assert changed in original.namelist()
            for entry in original.infolist():
                content = original.read(entry)
                if entry.filename == changed:
                    content += b'\nraise AssertionError("untrusted code executed")\n'
                modified.writestr(copy(entry), content)
        files['runtime/specroad.pyz'] = stream.getvalue()
        manifest = json.loads(files['handoff.json'])
        manifest['runtimes']['specroad']['artifact_sha256'] = sha256(files['runtime/specroad.pyz']).hexdigest()
        files['handoff.json'] = canonical_json_bytes(manifest)
        raw = rebound(files)
    package = own_package(tmp_path, handoff, raw)
    request = opening_request(tmp_path, package, extract=True)
    if damage == 'wrong-hash': request['options']['--expected-sha256'] = '0' * 64
    elif damage == 'wrong-runtime':
        package['runtime'].write_bytes(b'raise AssertionError("foreign runtime")')
        request['options']['--patchharbor-pyz-sha256'] = sha256(package['runtime'].read_bytes()).hexdigest()
    before = tree(tmp_path)
    result = offline(tmp_path, distribution[1], request)
    assert result['code'] in (3, 6, 7), result
    if damage in ('foreign-core', 'forged-build'):
        assert result['code'] == 7, result
        assert result['outcome']['summary']['transport_failure']['reason'] == {
            'foreign-core': 'core_distribution_mismatch',
            'forged-build': 'invalid_core_build_record',
        }[damage]
    assert result['outcome']['result'] is None and tree(tmp_path) == before
    assert not (tmp_path / 'verification').exists() and not (tmp_path / 'sandbox').exists()


def test_rehashed_outer_cannot_hide_invalid_native_result(tmp_path, distribution, handoff):
    files = members(handoff['source'].read_bytes())
    inner = members(files['reference/result.zip'])
    path = next(n for n in inner if n.startswith('base/') and n.endswith('specroad.json'))
    inner[path] += b'\n'
    files['reference/result.zip'] = encode_zip(inner, max_uncompressed_bytes=512 * 1024 * 1024)
    package = own_package(tmp_path, handoff, rebound(files))
    result = offline(tmp_path, distribution[0], opening_request(tmp_path, package, extract=True))
    assert result['code'] != 0 and result['code'] != 4, result
    facts = result['outcome']['summary']['transport_failure']
    assert facts['patchharbor']['code'] and facts['full_reference_valid'] is False
    assert (tmp_path / 'verification/result.zip').read_bytes() == files['reference/result.zip']
    assert not (tmp_path / 'sandbox').exists()


@pytest.mark.parametrize('field', ('repo_id', 'base_commit', 'state_fingerprint', 'project_path'))
def test_outer_declarations_cannot_rebind_native_state(tmp_path, distribution, handoff, field):
    files = members(handoff['source'].read_bytes())
    manifest = json.loads(files['handoff.json'])
    if field == 'project_path': manifest[field] = 'another-project'
    else:
        manifest['reference'][field] = {'repo_id': 'e26484c0-2522-4f21-bad9-22abc963a209',
            'base_commit': 'a' * 40, 'state_fingerprint': 'b' * 16}[field]
    files['handoff.json'] = canonical_json_bytes(manifest)
    package = own_package(tmp_path, handoff, rebound(files))
    result = offline(tmp_path, distribution[1], opening_request(tmp_path, package, extract=True))
    assert result['code'] == 3, result
    assert not (tmp_path / 'sandbox').exists()


def test_portable_receipt_tampering_fails_before_root_creation(tmp_path, distribution):
    origin = tmp_path / 'fixture'; origin.mkdir()
    handoff = make_handoff(origin, distribution, history=True)
    original = handoff['expected']; files = original.files
    name = next(p for p in files if p.startswith('.specroad/requests/'))
    value = json.loads(files[name]); value['operations_sha256'] = '0' * 64
    files[name] = canonical_json_bytes(value)
    raw = encode_bundle({k: v for k, v in original.manifest.items() if k != 'entries'}, files)
    outer = members(handoff['source'].read_bytes()); outer['project/project.zip'] = raw
    package = own_package(tmp_path, handoff, rebound(outer))
    result = offline(tmp_path, distribution[0], opening_request(tmp_path, package, extract=True))
    assert result['code'] == 3, result
    assert not (tmp_path / 'verification').exists() and not (tmp_path / 'sandbox').exists()


@pytest.mark.parametrize('change', ('missing', 'additional'))
def test_closed_changed_project_cannot_replace_complete_native_projection(tmp_path, distribution, handoff, change):
    copied = tmp_path / 'changed-project'
    shutil.copytree(handoff['origin'], copied, ignore=shutil.ignore_patterns('.git', '.patchharbor'))
    if change == 'missing':
        (copied / 'mappings/export.json').unlink()
    else:
        artifact = goal(77)
        put(copied, artifact_path('goal', artifact['id'], 'SR'), canonical_json_bytes(artifact))
    smaller = prepare_project_bundle(copied)
    package = own_package(tmp_path, handoff, rebound(members(handoff['source'].read_bytes()), project=smaller))
    result = offline(tmp_path, distribution[0], opening_request(tmp_path, package, extract=True))
    assert result['code'] == 3, result
    assert result['outcome']['summary']['transport_failure']['reason'] == 'handoff_effective_project_inventory'
    assert not (tmp_path / 'sandbox').exists()


@pytest.mark.parametrize('scope', ('local_only', 'partial'))
def test_nonportable_or_partial_project_is_not_promoted(tmp_path, distribution, handoff, scope):
    original = handoff['expected']
    metadata = original.manifest
    if scope == 'local_only': metadata['idempotency_scope'] = 'local_only'
    else: metadata['read_only'] = True
    files = members(handoff['source'].read_bytes())
    project_files = members(original.source_bytes)
    project_files['bundle-manifest.json'] = canonical_json_bytes(metadata)
    files['project/project.zip'] = encode_zip(project_files, max_uncompressed_bytes=512 * 1024 * 1024)
    package = own_package(tmp_path, handoff, rebound(files))
    result = offline(tmp_path, distribution[1], opening_request(tmp_path, package, extract=True))
    assert result['code'] in (3, 7), result
    assert not (tmp_path / 'verification').exists() and not (tmp_path / 'sandbox').exists()


@pytest.mark.parametrize('boundary', ('source-link', 'runtime-link', 'source-hardlink', 'runtime-hardlink',
    'parent-link', 'target-link', 'workspace-exists', 'workspace-in-project', 'overlap', 'target-file'))
def test_unsafe_operating_paths_preserve_foreign_bytes(tmp_path, distribution, handoff, boundary):
    package = own_package(tmp_path, handoff)
    request = opening_request(tmp_path, package, extract=True)
    if boundary.startswith(('source-', 'runtime-')):
        key = boundary.split('-')[0]; path = package[key]; saved = path.with_suffix('.saved')
        path.rename(saved)
        if boundary.endswith('hardlink'): os.link(saved, path)
        else: path.symlink_to(saved)
    elif boundary == 'parent-link':
        real = tmp_path / 'real'; real.mkdir(); (tmp_path / 'alias').symlink_to(real, target_is_directory=True)
        request['options']['--runtime-workspace'] = str(tmp_path / 'alias/new')
    elif boundary == 'target-link': (tmp_path / 'sandbox').symlink_to(tmp_path, target_is_directory=True)
    elif boundary == 'workspace-exists': (tmp_path / 'verification').mkdir()
    elif boundary == 'workspace-in-project':
        project = tmp_path / 'existing'; project.mkdir(); (project / 'specroad.json').write_bytes(b'foreign')
        request['options']['--runtime-workspace'] = str(project / 'new')
    elif boundary == 'overlap': request['options']['--runtime-workspace'] = str(tmp_path / 'sandbox')
    elif boundary == 'target-file': (tmp_path / 'sandbox').write_bytes(b'foreign')
    # Symlink cycles are deliberately not traversed by the witness.
    before = {p.name: (p.lstat().st_ino, p.lstat().st_mode) for p in tmp_path.iterdir()}
    result = offline(tmp_path, distribution[0], request)
    assert result['code'] in (6, 7), result
    assert {p.name: (p.lstat().st_ino, p.lstat().st_mode) for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize('change', ('package', 'runtime', 'private-reference', 'private-code',
    'workspace-mode', 'workspace-identity', 'foreign-workspace-file'))
def test_inputs_and_private_bytes_are_rechecked_before_target_writes(tmp_path, distribution, handoff, change):
    package = own_package(tmp_path, handoff)
    body = '''from specroad.transport.opening import SandboxOpening
original = SandboxOpening.extract
def changed(self):
'''
    mutation = {
        'package': "self.source.path.write_bytes(self.source.raw + b'changed')",
        'runtime': "self.pyz.path.write_bytes(self.pyz.raw + b'changed')",
        'private-reference': "self.reference.path.write_bytes(self.reference.raw + b'changed')",
        'private-code': "self.runtime._prepared.path.write_bytes(b'changed')",
        'workspace-mode': "self.workspace.chmod(0o755)",
        'workspace-identity': "self.workspace.rename(self.workspace.with_name('retained')); self.workspace.mkdir(mode=0o700)",
        'foreign-workspace-file': "(self.workspace / 'foreign').write_bytes(b'foreign')",
    }[change]
    body += '    ' + mutation + '\n    return original(self)\nSandboxOpening.extract = changed\n'
    result = offline(tmp_path, distribution[1], opening_request(tmp_path, package, extract=True), before=body)
    assert result['code'] in (6, 7), result
    assert not (tmp_path / 'sandbox').exists()
    assert result['outcome']['summary']['transport']['runtime_workspace'] == str(tmp_path / 'verification')


@pytest.mark.parametrize('change,code', (('foreign-module', 7), ('host', 5), ('io', 5)))
def test_unavailable_runtime_never_becomes_partial_success(tmp_path, distribution, handoff, change, code):
    body = {
        'foreign-module': "import types\nsys.modules['patchharbor'] = types.ModuleType('patchharbor')\n",
        'host': "import platform\nplatform.machine = lambda: 'unsupported'\n",
        'io': "from specroad.transport import opening\ndef failed(self):\n    raise OSError(28, 'No space')\nopening.SandboxOpening._workspace = failed\n",
    }[change]
    result = offline(tmp_path, distribution[0], opening_request(tmp_path, handoff, extract=True), before=body)
    assert result['code'] == code, result
    assert result['outcome']['result'] is None and not (tmp_path / 'sandbox').exists()


def rename_hook(target, code):
    return '''from specroad.authoring import _bootstrap_io
native = _bootstrap_io.rename_new
def intercepted(function, source_fd, source, target_fd, name):
    outer = os.readlink('/proc/self/fd/' + str(target_fd)) == ''' + repr(str(target)) + '''
    native(function, source_fd, source, target_fd, name)
    if outer:
''' + ''.join('        ' + line + '\n' for line in code.splitlines()) + '''
_bootstrap_io.rename_new = intercepted
'''


@pytest.mark.parametrize('stop', ('.specroad', 'reference', 'runtime', 'project'))
def test_process_death_recovers_only_original_owned_inventory(tmp_path, distribution, handoff, stop):
    request = opening_request(tmp_path, handoff, extract=True)
    hook = rename_hook(tmp_path / 'sandbox', "if name == " + repr(stop) + ": os._exit(37)")
    offline(tmp_path, distribution[1], request, before=hook, expected_process_code=37)
    assert (tmp_path / 'sandbox/.specroad-bootstrap/journal.json').is_file()
    request['options']['--runtime-workspace'] = str(tmp_path / 'new-verification')
    result = offline(tmp_path, distribution[0], request)
    assert result['code'] == 0, result
    assert (tmp_path / 'sandbox/reference/outbound.zip').read_bytes() == handoff['source'].read_bytes()
    assert not (tmp_path / 'sandbox/.specroad-bootstrap').exists()
    before = tree(tmp_path / 'sandbox')
    request['options']['--runtime-workspace'] = str(tmp_path / 'third-verification')
    collision = offline(tmp_path, distribution[1], request)
    assert collision['code'] == 6 and tree(tmp_path / 'sandbox') == before


@pytest.mark.parametrize('damage', ('foreign', 'changed-bytes', 'journal', 'identity', 'different-source'))
def test_unowned_or_changed_recovery_never_deletes_foreign_data(tmp_path, distribution, handoff, damage):
    package = own_package(tmp_path, handoff)
    request = opening_request(tmp_path, package, extract=True)
    offline(tmp_path, distribution[0], request,
        before=rename_hook(tmp_path / 'sandbox', 'os._exit(37)'), expected_process_code=37)
    stage = tmp_path / 'sandbox/.specroad-bootstrap'
    if damage == 'foreign': (stage / 'foreign').write_bytes(b'foreign')
    elif damage == 'changed-bytes': (stage / 'runtime/specroad.pyz').write_bytes(b'foreign')
    elif damage == 'journal': (stage / 'journal.json').write_bytes(b'{"entries": []}')
    elif damage == 'identity':
        path = stage / 'reference/outbound.zip'; raw = path.read_bytes(); path.rename(path.with_suffix('.saved')); path.write_bytes(raw)
    elif damage == 'different-source':
        another = tmp_path / 'different-repository'; another.mkdir()
        new_package = make_handoff(another, distribution)
        raw = new_package['source'].read_bytes()
        package['source'].write_bytes(raw)
        request['options']['--expected-sha256'] = sha256(raw).hexdigest()
    before = tree(tmp_path / 'sandbox')
    request['options']['--runtime-workspace'] = str(tmp_path / 'new-verification')
    result = offline(tmp_path, distribution[1], request)
    assert result['code'] in (3, 6, 7), result
    assert result['outcome']['result'] is None and tree(tmp_path / 'sandbox') == before


def test_io_failure_rolls_back_only_owned_sandbox_and_retains_private_workspace(tmp_path, distribution, handoff):
    hook = rename_hook(tmp_path / 'sandbox', "_bootstrap_io.rename_new = native\nraise OSError(28, 'No space')")
    result = offline(tmp_path, distribution[1], opening_request(tmp_path, handoff, extract=True), before=hook)
    assert result['code'] == 5, result
    assert not (tmp_path / 'sandbox').exists() and (tmp_path / 'verification/result.zip').is_file()
    effects = result['outcome']['summary']['transport']
    assert effects['sandbox_root'] is None and effects['bootstrap_state'] == 'rolled_back'


def test_interrupted_inner_extraction_without_outer_proof_is_retained(tmp_path, distribution, handoff):
    hook = '''from specroad.transport import _sandbox_root
native = _sandbox_root.extract_bundle
def interrupted(*args, **kwargs):
    native(*args, **kwargs)
    os._exit(37)
_sandbox_root.extract_bundle = interrupted
'''
    request = opening_request(tmp_path, handoff, extract=True)
    offline(tmp_path, distribution[0], request, before=hook, expected_process_code=37)
    before = tree(tmp_path / 'sandbox')
    assert (tmp_path / 'sandbox/.specroad-bootstrap/project/specroad.json').is_file()
    request['options']['--runtime-workspace'] = str(tmp_path / 'new-verification')
    result = offline(tmp_path, distribution[1], request)
    assert result['code'] in (5, 6), result
    assert tree(tmp_path / 'sandbox') == before
    assert result['outcome']['summary']['transport']['bootstrap_state'] == 'recovery_required'


@pytest.mark.parametrize('damage', ('extra', 'false-gate', 'authority', 'manifest-extra', 'reference-hash', 'runtime-type'))
def test_closed_result_contract_rejects_false_or_unbound_success(tmp_path, distribution, handoff, damage):
    result = offline(tmp_path, distribution[0], opening_request(tmp_path, handoff))
    assert result['code'] == 0, result
    value = result['outcome']['result']
    if damage == 'extra': value['unbound'] = 'extra'
    elif damage == 'false-gate': value['full_reference_valid'] = False
    elif damage == 'authority': value['write_authorized'] = True
    elif damage == 'manifest-extra': value['manifest']['approved'] = True
    elif damage == 'reference-hash': value['manifest']['reference']['sha256'] = 'short'
    elif damage == 'runtime-type': value['manifest']['runtimes']['patchharbor']['snapshot_contract_version'] = True
    with pytest.raises(ModelError):
        validate_result_document('ai-runtime-verify-v1', value)


@pytest.mark.parametrize('change', ('appeared', 'replaced'))
def test_target_identity_is_not_rebound_between_verification_and_publication(tmp_path, distribution, handoff, change):
    target = tmp_path / 'sandbox'
    if change == 'replaced': target.mkdir()
    mutation = "self.output.rename(self.output.with_name('old-target')); " if change == 'replaced' else ''
    hook = ("from specroad.transport.opening import SandboxOpening\noriginal = SandboxOpening.extract\n"
        "def changed(self):\n    " + mutation + "self.output.mkdir()\n"
        "    (self.output / 'foreign').write_bytes(b'preserve')\n"
        "    return original(self)\nSandboxOpening.extract = changed\n")
    result = offline(tmp_path, distribution[0], opening_request(tmp_path, handoff, extract=True), before=hook)
    assert result['code'] in (6, 7), result
    assert tree(target) == {'foreign': (b'preserve', (target / 'foreign').stat().st_mode)}
