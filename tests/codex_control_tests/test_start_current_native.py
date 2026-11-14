"""The pinned native Core captures real Git trees through an installed adapter."""
import shutil
from pathlib import Path

import pytest

from support.transport_outbound import child, register, FIXTURE, ROOT


@pytest.mark.parametrize('case', ['clean', 'dirty', 'locked', 'foreign'])
def test_installed_checkpoint_adapter_uses_native_identity_snapshot_and_lock(tmp_path, case):
    repository = tmp_path / 'apply'
    repository.mkdir()
    (repository / 'tracked.txt').write_bytes(b'committed\n')
    initial = register(tmp_path, repository)
    installed = tmp_path / 'installed'
    installed.mkdir()
    shutil.copy2(ROOT / 'tools/dev/codex/control/specroad_control/ph_checkpoint.py', installed / 'ph_checkpoint.py')
    if case == 'dirty':
        (repository / 'tracked.txt').write_bytes(b'uncommitted\x00bytes')
        (repository / 'new.txt').write_bytes(b'untracked\n')
    result = child(tmp_path, '''
import contextlib, importlib.util, io, json, subprocess
from pathlib import Path
sys.path.insert(0, ''' + repr(str(FIXTURE / 'patchharbor-1.8.0.pyz')) + ''')
from patchharbor import api
from patchharbor.repository_state import locked_repository_context_for_id
from patchharbor.models import RepositoryId
spec = importlib.util.spec_from_file_location('installed_checkpoint', 'installed/ph_checkpoint.py')
adapter = importlib.util.module_from_spec(spec); spec.loader.exec_module(adapter)
repo = Path(''' + repr(str(repository)) + ''')
repo_id = ''' + repr(initial['repo_id']) + '''
case = ''' + repr(case) + '''
identity = '00000000-0000-4000-8000-000000000001' if case == 'foreign' else repo_id
guard = locked_repository_context_for_id(RepositoryId(repo_id)) if case == 'locked' else contextlib.nullcontext()
with guard, contextlib.redirect_stdout(io.StringIO()) as output:
    code = adapter.main([str(repo), identity, str(Path.cwd() / 'exchange')])
reply = json.loads(output.getvalue())
data = {'code': code, 'reply': reply,
        'head': subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip(),
        'tracked': (repo / 'tracked.txt').read_bytes().hex()}
if code == 0:
    snapshot = api.read_result_snapshot(reply['path'])
    data.update(dirty=snapshot.context.dirty,
                captured=snapshot.effective.files['tracked.txt'].content.hex(),
                untracked='new.txt' in snapshot.effective.files)
print(json.dumps(data))
''')
    assert result['head'] == initial['base_commit']
    assert bytes.fromhex(result['tracked']) == (repository / 'tracked.txt').read_bytes()
    if case in ('clean', 'dirty'):
        assert result['code'] == 0 and result['reply']['ok'] is True
        assert result['dirty'] is (case == 'dirty')
        assert result['untracked'] is (case == 'dirty')
        assert result['captured'] == result['tracked']
    else:
        assert result['code'] == 1 and result['reply']['ok'] is False
        assert result['reply']['error'] == ('repository_busy' if case == 'locked' else 'checkpoint_failed')
        assert not list((tmp_path / 'exchange').glob('*.zip'))
