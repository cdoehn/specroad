"""Real isolated Git/PH fixtures; setup mutations precede the source witness."""
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from support.transport_runtime import runtime_artifact


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/fixtures/patchharbor180'


def child(root, body, *, source=None):
    environment = {k: os.environ[k] for k in ('LD_LIBRARY_PATH', 'SystemRoot', 'WINDIR') if k in os.environ}
    environment.update(HOME=str(root/'home'), XDG_CONFIG_HOME=str(root/'config'),
        XDG_STATE_HOME=str(root/'state'), GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
        PATH=str(Path(shutil.which('git')).parent), LANG='C.UTF-8', LC_ALL='C.UTF-8')
    prefix = 'import sys; sys.path.insert(0, ' + repr(str(source or ROOT/'src')) + ');\n'
    result = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', prefix + body],
        cwd=root, env=environment, stdin=subprocess.DEVNULL, capture_output=True)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    return json.loads(result.stdout)


def register(root, repository):
    (root/'home').mkdir(); (root/'exchange').mkdir()
    return child(root, '''
import json, subprocess
from pathlib import Path
sys.path.insert(0, ''' + repr(str(FIXTURE/'patchharbor-1.8.0.pyz')) + ''')
from patchharbor import api
repo = Path(''' + repr(str(repository)) + ''')
def git(*args):
    return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.PIPE)
git('init', '-q'); git('config', 'user.name', 'Synthetic transport fixture')
git('config', 'user.email', 'fixture@example.invalid'); git('config', 'core.autocrlf', 'false')
git('add', '--all'); git('commit', '-qm', 'Independent input fixture')
context=api.register(repo)
api.configure_exchange_directory(Path.cwd()/'exchange', repository=repo)
print(json.dumps({'repo_id':str(context.repo_id),'base_commit':str(context.base_commit)}))
''')


def request(root, project, artifact):
    reference, digest = runtime_artifact(root)
    output = root/'output'; output.mkdir()
    return {'command_id':'bundle.create', 'options':{
        '--project':str(project), '--profile':['ai-runtime'], '--direction':'outbound',
        '--patchharbor-pyz':str(reference), '--patchharbor-pyz-sha256':digest,
        '--specroad-pyz':str(artifact), '--specroad-pyz-sha256':sha256(artifact.read_bytes()).hexdigest(),
        '--output-root':str(output), '--output':'handoff.zip', '--format':'json'}}


def run_request(root, value, *, source=None, before=''):
    return child(root, before + '\nfrom specroad.cli.application import execute_request\nimport json\n'
        + 'result=execute_request(' + repr(value) + ').result\n'
        + 'print(json.dumps({"code":result.exit_code,"outcome":result.as_dict()}))', source=source)


def tree(root):
    return {p.relative_to(root).as_posix():(p.read_bytes(),p.stat().st_mode)
            for p in root.rglob('*') if p.is_file()}
