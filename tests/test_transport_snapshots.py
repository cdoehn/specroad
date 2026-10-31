"""Real producer Results, independent inventories and public API failure facts."""

from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from support.portable import build_distribution, files_under
from support.transport_runtime import FIXTURE, adapter_source, probe


def ready(root):
    provider = FIXTURE / 'result-clean.zip'
    return adapter_source(provider, sha256(provider.read_bytes()).hexdigest(), root / 'runtime') + '''
api = runtime.load_api(required=('PH-API-RESULT',))
from specroad.transport import TransportFailure
'''


def read_code(path, digest=None):
    return ('runtime.read_snapshot(' + repr(str(path)) + ', expected_sha256=' +
            repr(digest or sha256(path.read_bytes()).hexdigest()) + ')')


@pytest.mark.parametrize('distribution_kind', ['module', 'zipapp'])
def test_complete_native_dirty_snapshot_matches_independent_git_and_disk(tmp_path, distribution_kind):
    module, archive = build_distribution(tmp_path / 'core')
    source = FIXTURE / 'result-dirty.zip'
    reference = tmp_path / 'reference.zip'; reference.write_bytes(source.read_bytes())
    expected = json.loads((FIXTURE / 'expected.json').read_bytes())
    body = ready(tmp_path) + 'snapshot = ' + read_code(reference) + '''
# Read-only snapshot consumption: no shell, Git, network or project extraction.
inventories = {}
for name in ('base', 'index', 'worktree', 'untracked', 'effective'):
    layer = getattr(snapshot, name)
    inventories[name] = {p: dict(mode=f.mode, content_hex=f.content.hex(),
        size=f.size, sha256=f.sha256, object_id=f.object_id.value) for p,f in layer.files.items()}
    try:
        layer.files['invented'] = None
    except TypeError:
        pass
    else:
        raise AssertionError('mutable snapshot mapping')
Path(''' + repr(str(reference)) + ''').write_bytes(b'replaced after capture')
assert snapshot.effective.files['text.txt'].content == b'first\\nworktree\\nlast'
print(json.dumps(dict(inventories=inventories, dirty=snapshot.context.dirty,
    digest=snapshot.sha256, success=snapshot.primary_result.success,
    contract=api.integration_capabilities().snapshot_contract_version)))
'''
    result = probe(tmp_path, body, distribution=module if distribution_kind == 'module' else archive)
    assert result['inventories'] == expected
    assert result['dirty'] and result['contract'] == 1
    assert result['digest'] == sha256(source.read_bytes()).hexdigest()
    assert not (tmp_path / 'text.txt').exists()


@pytest.mark.parametrize('name', ['result-clean.zip', 'result-dirty.zip',
                                 'result-partial-failure.zip', 'result-unavailable.zip',
                                 'result-dry-run.zip'])
def test_historical_result_facts_are_passive_and_not_rewritten(tmp_path, name):
    reference = FIXTURE / 'historical' / name
    with ZipFile(reference) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        context = json.loads(archive.read('context.json'))
        run = json.loads(archive.read('logs/run.json'))
    before = reference.read_bytes()
    body = ready(tmp_path) + 'snapshot = ' + read_code(reference) + '''
print(json.dumps(dict(digest=snapshot.sha256, runtime=snapshot.runtime.version,
    runtime_status=snapshot.runtime.status, dry_run=snapshot.dry_run,
    dirty=snapshot.context.dirty, success=snapshot.primary_result.success,
    exit=snapshot.primary_result.entrypoint_exit_code,
    repo_id=snapshot.context.repo_id.value, commit=snapshot.context.base_commit.value,
    fingerprint=snapshot.context.state_fingerprint,
    algorithm=snapshot.context.fingerprint_algorithm)))
'''
    result = probe(tmp_path, body)
    assert result['digest'] == sha256(before).hexdigest()
    assert result['dirty'] == context['dirty']
    assert result['dry_run'] == manifest['dry_run']
    assert result['success'] == run['primary_result']['success']
    assert result['exit'] == run['primary_result']['entrypoint_exit_code']
    assert result['runtime_status'] == manifest['runtime']['status']
    assert result['commit'] == context['base_commit']
    assert result['repo_id'] == context['repo_id']
    assert result['fingerprint'] == context['state_fingerprint']
    assert result['algorithm'] == context['fingerprint_algorithm']
    assert reference.read_bytes() == before


def damaged_result(root, fault):
    with ZipFile(FIXTURE / 'result-dirty.zip') as archive:
        members = [(i, archive.read(i)) for i in archive.infolist()]
    target = root / 'bad-result.zip'
    with ZipFile(target, 'w') as archive:
        for info, raw in members:
            if fault == info.filename:
                continue
            if fault == 'base_hash' and info.filename == 'base/text.txt':
                raw = b'wrong base bytes'
            if fault == 'untracked_hash' and info.filename == 'untracked/loose.bin':
                raw = b'wrong untracked bytes'
            if fault == 'runtime_hash' and info.filename == 'runtime/patchharbor-1.6.0.pyz':
                raw = b'code must never be loaded'
            if fault == 'invalid_patch' and info.filename == 'changes/staged.patch':
                raw = raw.replace(b'-base\n', b'-wrong context\n')
            archive.writestr(info, raw)
    return target


@pytest.mark.parametrize('fault', ['context.json', 'base/text.txt',
    'changes/staged.patch', 'changes/unstaged.patch', 'untracked/loose.bin',
    'base_hash', 'untracked_hash', 'runtime_hash', 'invalid_patch'])
def test_invalid_layers_never_load_input_code_or_materialize_project(tmp_path, fault):
    reference = damaged_result(tmp_path, fault)
    before = reference.read_bytes()
    body = ready(tmp_path) + '''
def no_input_writes(event, args):
    if event in {'os.mkdir', 'os.rename', 'os.remove', 'os.rmdir', 'os.chmod'}:
        raise AssertionError('snapshot side effect: ' + event)
    if event == 'open' and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
        raise AssertionError('snapshot write')
sys.addaudithook(no_input_writes)
origin = api.__file__
try:
    ''' + read_code(reference) + '''
except TransportFailure as error:
    assert api.__file__ == origin
    print(json.dumps(error.as_dict()))
else:
    raise AssertionError('invalid Result accepted')
'''
    result = probe(tmp_path, body)
    assert result['status'] == 'failed' and result['full_reference_valid'] is False
    assert result['exit_code'] == 3
    assert result['patchharbor']['reason'] == 'source_error'
    assert result['patchharbor']['code'] in ('invalid_result', 'invalid_patch')
    assert reference.read_bytes() == before
    assert set(p.name for p in tmp_path.iterdir()) == {'bad-result.zip', 'runtime'}


def test_snapshot_does_not_implicitly_bootstrap_from_its_input(tmp_path):
    reference = FIXTURE / 'result-dirty.zip'
    body = adapter_source(tmp_path / 'absent', '0' * 64, tmp_path / 'runtime') + '''
try:
    ''' + read_code(reference) + '''
except TransportUnavailable as error:
    print(json.dumps(dict(error=error.as_dict(),
        loaded=[n for n in sys.modules if n.startswith('patchharbor')])))
else:
    raise AssertionError('implicit bootstrap')
'''
    result = probe(tmp_path, body)
    assert result['error']['reason'] == 'explicit_runtime_load_required'
    assert result['loaded'] == [] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('case', ['digest', 'missing', 'relative', 'bad_digest'])
def test_snapshot_input_errors_preserve_upstream_facts(tmp_path, case):
    reference = FIXTURE / 'result-dirty.zip'
    expression = read_code(reference, '0' * 64) if case == 'digest' else read_code(reference)
    if case == 'missing': expression = read_code(tmp_path / 'missing', '0' * 64)
    if case == 'relative': expression = "runtime.read_snapshot('relative', expected_sha256='0' * 64)"
    if case == 'bad_digest': expression = "runtime.read_snapshot('relative', expected_sha256=None)"
    body = ready(tmp_path) + 'try:\n    ' + expression + '''
except TransportFailure as error:
    print(json.dumps(error.as_dict()))
else:
    raise AssertionError('bad input accepted')
'''
    result = probe(tmp_path, body)
    assert result['exit_code'] == {'digest': 6, 'missing': 5, 'relative': 2, 'bad_digest': 2}[case]
    if case == 'digest':
        assert result['patchharbor'] == {'reason': 'source_error', 'kind': 'tool_error', 'code': 'digest_mismatch'}
    assert result['full_reference_valid'] is False


@pytest.mark.parametrize('system,machine,implementation,version', [
    ('win32', 'x86_64', 'cpython', (3,14)), ('linux', 'aarch64', 'cpython', (3,14)),
    ('linux', 'x86_64', 'pypy', (3,14)), ('linux', 'x86_64', 'cpython', (3,9)),
])
def test_platform_refusal_happens_before_source_access(tmp_path, system, machine, implementation, version):
    body = adapter_source(tmp_path / 'absent', '0' * 64, tmp_path / 'runtime') + '''
import specroad.transport.runtime as adapter
from types import SimpleNamespace
adapter.sys = SimpleNamespace(implementation=SimpleNamespace(name=''' + repr(implementation) + '''),
    version_info=''' + repr(version) + ''', platform=''' + repr(system) + ''')
adapter.platform.machine = lambda: ''' + repr(machine) + '''
try:
    runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps(dict(code=error.exit_code, loaded=[n for n in sys.modules if n.startswith('patchharbor')])))
else:
    raise AssertionError('unsupported interpreter/platform accepted')
'''
    result = probe(tmp_path, body)
    assert result == {'code': 2, 'loaded': []}
    assert list(tmp_path.iterdir()) == []


def test_old_distribution_cannot_supply_the_new_api(tmp_path):
    reference = FIXTURE / 'historical/result-clean.zip'
    body = adapter_source(reference, sha256(reference.read_bytes()).hexdigest(), tmp_path / 'runtime') + '''
try:
    runtime.load_api(required=('PH-API-RESULT',))
except TransportUnavailable as error:
    print(json.dumps(dict(error=error.as_dict(), loaded=[n for n in sys.modules if n.startswith('patchharbor')])))
else:
    raise AssertionError('old runtime accepted')
'''
    result = probe(tmp_path, body)
    assert result['error']['exit_code'] == 7 and result['loaded'] == []
    assert list(tmp_path.iterdir()) == []


def test_corrupted_runtime_is_rejected_before_import_or_workspace_creation(tmp_path):
    reference = damaged_result(tmp_path, 'runtime_hash')
    before = files_under(tmp_path)
    body = adapter_source(reference, sha256(reference.read_bytes()).hexdigest(), tmp_path / 'runtime') + '''
try:
    runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps(dict(code=error.exit_code,
        loaded=[n for n in sys.modules if n.startswith('patchharbor')])))
else:
    raise AssertionError('modified runtime executed')
'''
    assert probe(tmp_path, body) == {'code': 7, 'loaded': []}
    assert files_under(tmp_path) == before


@pytest.mark.parametrize('change', ['capability', 'contract', 'origin'])
def test_runtime_reuse_rejects_changed_api_contract_and_origin(tmp_path, change):
    body = ready(tmp_path)
    if change == 'capability':
        body += 'api.read_result_snapshot = None\n'
    elif change == 'contract':
        body += 'api.integration_capabilities = lambda: api.IntegrationCapabilities(2, 1, 1)\n'
    else:
        body += "api.__spec__.origin = '/foreign/patchharbor/api.py'\n"
    body += '''
try:
    runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps(dict(error=error.as_dict(), retained=api is sys.modules['patchharbor.api'])))
else:
    raise AssertionError('changed API accepted')
'''
    result = probe(tmp_path, body)
    assert result['error']['exit_code'] == (7 if change == 'origin' else 2)
    assert result['retained'] is True


@pytest.mark.parametrize('code,expected', [('path_collision', 7), ('resource_limit', 3),
                                         ('unsupported_patch', 2)])
def test_public_snapshot_error_codes_remain_separate_from_exit_numbers(tmp_path, code, expected):
    body = ready(tmp_path) + '''
from specroad.transport.snapshots import api_failure
error = api.ResultSnapshotError(api.SnapshotErrorCode(''' + repr(code) + '''), 'fixture')
print(json.dumps(api_failure(api, error).as_dict()))
'''
    result = probe(tmp_path, body)
    assert result['exit_code'] == expected
    assert result['patchharbor'] == {'reason': 'source_error', 'kind': 'tool_error', 'code': code}


@pytest.mark.parametrize('reason,expected', [('usage_error', 2), ('source_error', 3),
    ('execution_error', 5), ('timeout', 5), ('interrupted', 5), ('result_bundle_error', 5),
    ('state_mismatch', 6), ('repository_busy', 6), ('unsupported_repository_state', 7)])
def test_api_failure_classification_preserves_semantic_reason(tmp_path, reason, expected):
    body = ready(tmp_path) + '''
from specroad.transport.snapshots import api_failure
error = api.PatchHarborError('fixture message', api.FailureReason(''' + repr(reason) + '''))
print(json.dumps(api_failure(api, error).as_dict()))
'''
    result = probe(tmp_path, body)
    assert result['exit_code'] == expected
    assert result['patchharbor'] == {'reason': reason, 'kind': 'tool_error', 'code': None}
