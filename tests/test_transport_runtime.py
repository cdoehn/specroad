"""Public lazy integration with the original shipped 1.4.0 runtime, offline."""

from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

from support.portable import build_distribution, files_under
from support.transport_runtime import (
    ARTIFACT_SHA256, adapter_source, envelope, native_patch, probe,
)


@pytest.mark.parametrize('distribution_kind', ['module', 'zipapp'])
def test_real_public_import_and_native_inspection_from_delivered_artifacts(tmp_path, distribution_kind):
    reference, digest = envelope(tmp_path)
    patch = native_patch(tmp_path)
    module, archive = build_distribution(tmp_path / 'core')
    workspace = tmp_path / 'runtime'
    before = reference.read_bytes()
    body = adapter_source(reference, digest, workspace) + '''
assert not any(n == 'patchharbor' or n.startswith('patchharbor.') for n in sys.modules)
before = runtime.describe()
api = runtime.load_api(required=('inspect_patch', 'validate_patch', 'pack_patch'))
assert api is runtime.load_api(required=('bundle', 'apply'))
result = api.inspect_patch(''' + repr(str(patch)) + ''')
print(json.dumps({'before': before, 'after': runtime.describe(),
 'api_name': api.__name__, 'api_origin': api.__file__,
 'inspection_sha256': result.package_sha256,
 'python': list(sys.version_info[:2]),
 'full_reference_valid': runtime.describe()['full_reference_valid']}))
'''
    result = probe(tmp_path, body, distribution=module if distribution_kind == 'module' else archive)
    assert result['api_name'] == 'patchharbor.api'
    assert result['api_origin'].startswith(str(workspace / 'patchharbor-1.4.0.pyz'))
    assert result['inspection_sha256'] == sha256(patch.read_bytes()).hexdigest()
    assert result['python'] == list(sys.version_info[:2])
    assert result['before']['runtime_loaded'] is False
    assert result['after']['runtime_loaded'] is True
    assert result['after']['artifact_sha256'] == ARTIFACT_SHA256
    assert result['after']['version'] == '1.4.0'
    assert result['after']['source_result_sha256'] == digest
    assert result['after']['supported_cpython'] == ['3.10', '3.11', '3.12', '3.13', '3.14']
    assert result['after']['unavailable_capabilities'] == ['PH-API-RESULT']
    assert all(result['after']['api_capabilities'].values())
    assert result['full_reference_valid'] is False
    assert reference.read_bytes() == before
    assert list(workspace.iterdir()) == [workspace / 'patchharbor-1.4.0.pyz']
    assert sha256((workspace / 'patchharbor-1.4.0.pyz').read_bytes()).hexdigest() == ARTIFACT_SHA256


@pytest.mark.parametrize('distribution_kind', ['module', 'zipapp'])
def test_core_commands_and_adapter_description_need_no_transport(tmp_path, distribution_kind):
    module, archive = build_distribution(tmp_path / 'core')
    project = tmp_path / 'project'; project.mkdir()
    (project / 'kept.bin').write_bytes(b'unchanged\x00')
    before = files_under(project)
    body = '''
class NoTransport:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('patchharbor') or fullname.endswith('_pyz_bootstrap'):
            raise AssertionError('lazy boundary violated')
sys.meta_path.insert(0, NoTransport())
import io
from specroad.cli import main
from specroad.transport import PatchHarborRuntime
runtime = PatchHarborRuntime(str(Path.cwd() / 'absent-result'),
    trusted_source_sha256='0' * 64, workspace=str(Path.cwd() / 'absent-workspace'))
print(json.dumps({'exit': main(['--help'], stdout=io.StringIO()),
    'loaded': runtime.describe()['runtime_loaded'],
    'modules': [n for n in sys.modules if n.startswith('patchharbor')]}))
'''
    result = probe(project, body, distribution=module if distribution_kind == 'module' else archive)
    assert result == {'exit': 0, 'loaded': False, 'modules': []}
    assert files_under(project) == before


@pytest.mark.parametrize('capability', ['PH-API-RESULT', 'not_a_public_operation'])
def test_missing_capability_refuses_without_reading_or_loading(tmp_path, capability):
    body = adapter_source(tmp_path / 'absent-result', '0' * 64, tmp_path / 'runtime') + '''
try:
    runtime.load_api(required=(''' + repr(capability) + ''',))
except TransportUnavailable as error:
    print(json.dumps({'error': error.as_dict(),
        'modules': [n for n in sys.modules if n.startswith('patchharbor')]}))
else:
    raise AssertionError('missing capability accepted')
'''
    result = probe(tmp_path, body)
    assert result['error'] == {
        'status': 'unavailable', 'reason': 'api_capability_unavailable',
        'exit_code': 2, 'capability': capability, 'cause_type': None,
        'full_reference_valid': False,
    }
    assert result['modules'] == []
    assert list(tmp_path.iterdir()) == []


def test_declared_unavailable_runtime_is_not_replaced_or_installed(tmp_path):
    reference, digest = envelope(tmp_path, unavailable=True)
    before = files_under(tmp_path)
    body = adapter_source(reference, digest, tmp_path / 'runtime') + '''
try:
    runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps({'error': error.as_dict(),
        'modules': [n for n in sys.modules if n.startswith('patchharbor')]}))
else:
    raise AssertionError('unavailable runtime accepted')
'''
    result = probe(tmp_path, body)
    assert result['error']['reason'] == 'runtime_bootstrap_unavailable'
    assert result['error']['exit_code'] == 2
    assert result['error']['full_reference_valid'] is False
    assert result['modules'] == []
    assert files_under(tmp_path) == before


def test_wrong_trusted_digest_preserves_inputs_and_loads_no_code(tmp_path):
    reference, _ = envelope(tmp_path)
    before = files_under(tmp_path)
    body = adapter_source(reference, '0' * 64, tmp_path / 'runtime') + '''
try:
    runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps({'error': error.as_dict(),
        'modules': [n for n in sys.modules if n.startswith('patchharbor')]}))
else:
    raise AssertionError('untrusted bytes accepted')
'''
    result = probe(tmp_path, body)
    assert result['error']['exit_code'] == 7
    assert result['error']['reason'] == 'runtime_validation_failed'
    assert result['modules'] == []
    assert files_under(tmp_path) == before


def test_existing_runtime_destination_is_preserved(tmp_path):
    reference, digest = envelope(tmp_path)
    workspace = tmp_path / 'runtime'; workspace.mkdir()
    (workspace / 'kept').write_bytes(b'original')
    before = files_under(tmp_path)
    body = adapter_source(reference, digest, workspace) + '''
try:
    runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps({'error': error.as_dict(),
        'modules': [n for n in sys.modules if n.startswith('patchharbor')]}))
else:
    raise AssertionError('existing target replaced')
'''
    result = probe(tmp_path, body)
    assert result['error']['exit_code'] == 5
    assert result['error']['reason'] == 'runtime_io_error'
    assert result['modules'] == []
    assert files_under(tmp_path) == before


def test_project_module_cannot_shadow_the_verified_runtime(tmp_path):
    reference, digest = envelope(tmp_path)
    (tmp_path / 'patchharbor.py').write_text("raise AssertionError('foreign code executed')\n")
    body = adapter_source(reference, digest, tmp_path / 'runtime') + '''
sys.path.append(str(Path.cwd()))
api = runtime.load_api()
print(json.dumps({'api': api.__name__, 'origin': api.__file__}))
'''
    result = probe(tmp_path, body)
    assert result['api'] == 'patchharbor.api'
    assert result['origin'].startswith(str(tmp_path / 'runtime' / 'patchharbor-1.4.0.pyz'))


def test_loaded_foreign_origin_is_not_evicted_or_overwritten(tmp_path):
    reference, digest = envelope(tmp_path)
    before = files_under(tmp_path)
    body = adapter_source(reference, digest, tmp_path / 'runtime') + '''
from types import ModuleType
foreign = ModuleType('patchharbor')
sys.modules['patchharbor'] = foreign
try:
    runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps({'error': error.as_dict(),
        'original_retained': sys.modules['patchharbor'] is foreign}))
else:
    raise AssertionError('foreign origin accepted')
'''
    result = probe(tmp_path, body)
    assert result['error']['exit_code'] == 7
    assert result['error']['reason'] == 'runtime_origin_conflict'
    assert result['original_retained'] is True
    assert files_under(tmp_path) == before


@pytest.mark.parametrize('changed', ['reference', 'runtime'])
def test_reuse_rechecks_both_reference_and_prepared_bytes(tmp_path, changed):
    reference, digest = envelope(tmp_path)
    target = reference if changed == 'reference' else tmp_path / 'runtime' / 'patchharbor-1.4.0.pyz'
    body = adapter_source(reference, digest, tmp_path / 'runtime') + '''
api = runtime.load_api()
path = Path(''' + repr(str(target)) + ''')
path.write_bytes(b'changed')
try:
    runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps({'error': error.as_dict(), 'api_retained': api is sys.modules['patchharbor.api'],
        'observed_bytes': path.read_bytes().decode()}))
else:
    raise AssertionError('changed prepared artifact accepted')
'''
    result = probe(tmp_path, body)
    assert result['error']['exit_code'] == 7
    assert result['api_retained'] is True
    assert result['observed_bytes'] == 'changed'


@pytest.mark.parametrize('digest', [None, '', '0' * 63, 'G' * 64])
def test_trusted_digest_is_mandatory(tmp_path, digest):
    from specroad.transport import PatchHarborRuntime, TransportUnavailable
    with pytest.raises(TransportUnavailable) as caught:
        PatchHarborRuntime(tmp_path / 'reference', trusted_source_sha256=digest,
                          workspace=tmp_path / 'runtime')
    assert caught.value.as_dict()['exit_code'] == 7
    assert list(tmp_path.iterdir()) == []
