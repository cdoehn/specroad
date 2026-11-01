"""Standalone canonical runtime admission; no Result supplies executable code."""
from hashlib import sha256
from pathlib import Path
import stat

import pytest

from support.portable import files_under
from support.transport_runtime import (
    ROOT, ARTIFACT_SHA256, adapter_source, probe, runtime_artifact,
)


def refusal(source, digest, workspace):
    return adapter_source(source, digest, workspace) + '''
try:
    runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps({'error':error.as_dict(),
        'loaded':[n for n in sys.modules if n=='patchharbor' or n.startswith('patchharbor.')]}))
else:
    raise AssertionError('invalid runtime admitted')
'''


def test_direct_runtime_and_public_export_need_no_result_or_bootstrap(tmp_path):
    source, digest = runtime_artifact(tmp_path)
    body = adapter_source(source, digest, tmp_path/'private') + '''
class NoResultBootstrap:
    def find_spec(self, fullname, path=None, target=None):
        if fullname=='specroad.transport._pyz_bootstrap':
            raise AssertionError('Result bootstrap used')
sys.meta_path.insert(0,NoResultBootstrap())
api=runtime.load_api(required=('export_runtime','PH-API-RESULT'))
output=Path.cwd()/'export';output.mkdir()
exported=api.export_runtime(output)
print(json.dumps({'runtime':runtime.describe(),'export_sha256':exported.sha256,
    'equal':exported.path.read_bytes()==Path(''' + repr(str(source)) + ''').read_bytes()}))
'''
    result = probe(tmp_path, body)
    assert result['equal'] and result['export_sha256'] == ARTIFACT_SHA256
    assert result['runtime']['runtime_source'] == 'standalone_pyz'
    assert result['runtime']['source_artifact_sha256'] == digest
    assert 'source_result_sha256' not in result['runtime']
    assert stat.S_IMODE((tmp_path/'private').stat().st_mode) == 0o700
    assert stat.S_IMODE((tmp_path/'private/patchharbor-1.8.0.pyz').stat().st_mode) == 0o600


@pytest.mark.parametrize('version', ('1.4.0','1.6.0','1.7.0'))
def test_older_standalone_pyz_is_rejected_even_with_its_correct_external_hash(tmp_path,version):
    source = ROOT/'tests/fixtures'/('patchharbor'+version.replace('.',''))/('patchharbor-'+version+'.pyz')
    raw = source.read_bytes()
    result = probe(tmp_path,refusal(source,sha256(raw).hexdigest(),tmp_path/'private'))
    assert result['error']['reason'] == 'unsupported_runtime_distribution'
    assert result['error']['exit_code'] == 7 and result['loaded'] == []
    assert source.read_bytes() == raw and list(tmp_path.iterdir()) == []


def test_missing_standalone_runtime_is_not_discovered_or_installed(tmp_path):
    result = probe(tmp_path,refusal(tmp_path/'absent.pyz',ARTIFACT_SHA256,tmp_path/'private'))
    assert result['error']['reason'] == 'runtime_io_error'
    assert result['error']['exit_code'] == 5 and result['loaded'] == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('kind', ('symlink','hardlink','parent_link','directory','fifo','oversize'))
def test_standalone_runtime_rejects_unsafe_inputs_before_import(tmp_path,kind):
    import os
    source,digest=runtime_artifact(tmp_path)
    candidate=tmp_path/'input.pyz'
    if kind=='symlink': candidate.symlink_to(source)
    elif kind=='hardlink': os.link(source,candidate)
    elif kind=='parent_link':
        real=tmp_path/'real';real.mkdir();source.rename(real/source.name)
        linked=tmp_path/'linked';linked.symlink_to(real,target_is_directory=True)
        candidate=linked/source.name
    elif kind=='directory': candidate.mkdir()
    elif kind=='fifo': os.mkfifo(candidate)
    else:
        with candidate.open('wb') as stream: stream.truncate(16*1024*1024+1)
    result=probe(tmp_path,refusal(candidate,digest,tmp_path/'private'))
    assert result['error']['exit_code']==7 and result['loaded']==[]
    assert not (tmp_path/'private').exists()


def test_same_process_requests_reuse_only_the_checked_private_copy(tmp_path):
    source,digest=runtime_artifact(tmp_path)
    body=adapter_source(source,digest,tmp_path/'first')+'''
api=runtime.load_api()
other=PatchHarborRuntime('''+repr(str(source))+''',trusted_artifact_sha256='''+repr(digest)+''',
    workspace='''+repr(str(tmp_path/'unused'))+''',safe_reference=True)
second=other.load_api(required=('prepare_reference_export',))
print(json.dumps({'same':second is api,'loaded':other.describe()['runtime_loaded'],
    'safe_contract':other.describe()['safe_reference_contract_version']}))
'''
    assert probe(tmp_path,body)=={'same':True,'loaded':True,'safe_contract':1}
    assert not (tmp_path/'unused').exists()


def test_new_request_rechecks_its_own_artifact_before_reusing_a_loaded_runtime(tmp_path):
    source,digest=runtime_artifact(tmp_path)
    body=adapter_source(source,digest,tmp_path/'first')+'''
api=runtime.load_api()
other=PatchHarborRuntime(str(Path.cwd()/'missing.pyz'),trusted_artifact_sha256='''+repr(digest)+''',
    workspace=str(Path.cwd()/'second'),safe_reference=True)
try: other.load_api()
except TransportUnavailable as error:
    print(json.dumps({'code':error.exit_code,'retained':api is sys.modules['patchharbor.api']}))
else: raise AssertionError('new request omitted its own runtime binding')
'''
    assert probe(tmp_path,body)=={'code':5,'retained':True}
    assert not (tmp_path/'second').exists()


@pytest.mark.parametrize('target', ('source','private'))
@pytest.mark.parametrize('when', ('reuse','import'))
@pytest.mark.parametrize('same_bytes', (False,True))
def test_atomic_replacement_is_detected_even_with_identical_bytes(tmp_path,target,when,same_bytes):
    source,digest=runtime_artifact(tmp_path)
    changed=source if target=='source' else tmp_path/'private/patchharbor-1.8.0.pyz'
    body=adapter_source(source,digest,tmp_path/'private')+'''
def replace_input():
    path=Path('''+repr(str(changed))+''')
    raw=path.read_bytes() if '''+repr(same_bytes)+''' else b'changed after original capture'
    replacement=path.with_name('replacement.pyz')
    replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
'''
    if when=='reuse':
        body+='api=runtime.load_api()\nreplace_input()\n'
    else:
        body+='''
import specroad.transport.runtime as adapter
from types import SimpleNamespace
original=adapter.importlib.import_module
def changed_import(name):
    api=original(name)
    replace_input()
    return api
adapter.importlib=SimpleNamespace(import_module=changed_import)
'''
    body+='''
try: runtime.load_api()
except TransportUnavailable as error:
    code=error.exit_code
else: raise AssertionError('replacement was adopted')
try: runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps({'code':code,'again':error.reason,
        'retained':'patchharbor.api' in sys.modules}))
else: raise AssertionError('failed import retried')
'''
    assert probe(tmp_path,body)=={'code':7,'again':'fresh_process_required','retained':True}


@pytest.mark.parametrize('target', ('directory','file'))
def test_runtime_copy_must_remain_private_between_calls(tmp_path,target):
    source,digest=runtime_artifact(tmp_path)
    path=tmp_path/'private'
    if target=='file': path=path/'patchharbor-1.8.0.pyz'
    body=adapter_source(source,digest,tmp_path/'private')+'''
api=runtime.load_api()
Path('''+repr(str(path))+''').chmod(0o777)
try: runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps({'code':error.exit_code,'retained':api is sys.modules['patchharbor.api']}))
else: raise AssertionError('publicly writable runtime copy reused')
'''
    assert probe(tmp_path,body)=={'code':7,'retained':True}


@pytest.mark.parametrize('failure', ('RuntimeError','KeyboardInterrupt'))
def test_partial_import_failure_requires_fresh_process_and_preserves_modules(tmp_path,failure):
    source,digest=runtime_artifact(tmp_path)
    body=adapter_source(source,digest,tmp_path/'private')+'''
import specroad.transport.runtime as adapter
from types import SimpleNamespace
original=adapter.importlib.import_module
def interrupted(name):
    original(name)
    raise '''+failure+'''('interrupted after imports')
adapter.importlib=SimpleNamespace(import_module=interrupted)
try: runtime.load_api()
except '''+failure+''': pass
else: raise AssertionError('failure suppressed')
try: runtime.load_api()
except TransportUnavailable as error: first=error.reason
else: raise AssertionError('failed request retried')
other=PatchHarborRuntime('''+repr(str(source))+''',trusted_artifact_sha256='''+repr(digest)+''',
    workspace=str(Path.cwd()/'other'))
try: other.load_api()
except TransportUnavailable as error:
    print(json.dumps({'first':first,'new':error.reason,
        'retained':'patchharbor.api' in sys.modules,'loaded':runtime.describe()['runtime_loaded']}))
else: raise AssertionError('partial import adopted')
'''
    assert probe(tmp_path,body)=={'first':'fresh_process_required','new':'runtime_origin_conflict',
                                  'retained':True,'loaded':False}
    assert not (tmp_path/'other').exists()


@pytest.mark.parametrize('field', ('contract_version','snapshot_contract_version',
                                 'guarded_apply_contract_version','safe_reference_contract_version'))
@pytest.mark.parametrize('value', (None,True,2))
def test_all_required_capability_versions_are_strict_on_reuse(tmp_path,field,value):
    source,digest=runtime_artifact(tmp_path)
    body=adapter_source(source,digest,tmp_path/'private',safe_reference=True)+'''
from dataclasses import replace
api=runtime.load_api()
caps=api.integration_capabilities()
api.integration_capabilities=lambda:replace(caps,**{'''+repr(field)+':'+repr(value)+'''})
try: runtime.load_api()
except TransportUnavailable as error:
    print(json.dumps({'code':error.exit_code,'retained':api is sys.modules['patchharbor.api']}))
else: raise AssertionError('invalid capability version accepted')
'''
    assert probe(tmp_path,body)=={'code':2,'retained':True}
