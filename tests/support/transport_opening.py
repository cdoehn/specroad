"""Real outbound packages and Python-only opening subprocesses for Apply tests."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

from specroad.bundles import prepare_project_bundle
from support.transport_outbound import register, request, run_request
from test_bundle_receipts import completed
from test_project_bundle import project


def make_handoff(root, distribution, *, subproject=False, history=False):
    repository = root / 'repository'; repository.mkdir()
    origin = repository / 'model' if subproject else repository
    selected = completed(origin)[0] if history else None
    if not history:
        project(origin)
    expected = prepare_project_bundle(origin)
    register(root, repository)
    outbound = request(root, origin, distribution[1])
    result = run_request(root, outbound, source=distribution[0])
    assert result['code'] == 0, result
    return {'source': root / 'output/handoff.zip',
        'runtime': Path(outbound['options']['--patchharbor-pyz']), 'origin': origin,
        'expected': expected, 'selected': selected}


def opening_request(root, package, *, extract=False, expected=True):
    options = {'--profile': ['ai-runtime'], '--patchharbor-pyz': str(package['runtime']),
        '--patchharbor-pyz-sha256': sha256(package['runtime'].read_bytes()).hexdigest(),
        '--runtime-workspace': str(root / 'verification'), '--format': 'json'}
    if extract:
        options['--output'] = str(root / 'sandbox')
    if expected:
        options['--expected-sha256'] = sha256(package['source'].read_bytes()).hexdigest()
    return {'command_id': 'bundle.extract' if extract else 'bundle.verify',
        'arguments': {'file': str(package['source'])}, 'options': options}


def offline(root, source, request, *, before='', after='', expected_process_code=0, argv=False):
    # No inherited site packages or PATH, and real audit denials for shell,
    # Git/other subprocesses and network. This child itself is started by the
    # test harness; the product cannot spawn anything inside this boundary.
    environment = {k: os.environ[k] for k in ('LD_LIBRARY_PATH', 'SystemRoot', 'WINDIR') if k in os.environ}
    environment.update(PATH=str(root / 'no-executables'), HOME=str(root / 'home'),
        LANG='C.UTF-8', LC_ALL='C.UTF-8')
    arguments = request['command_id'].split('.') + [request['arguments']['file']]
    for key, value in request['options'].items():
        for item in value if isinstance(value, list) else [value]:
            arguments.extend((key, item))
    invocation = ('dispatch_result(' + repr(arguments) + ')' if argv else
                  'execute_request(' + repr(request) + ').result')
    body = '''import sys, json, os
from pathlib import Path
def audit(event, args):
    if event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'socket.__new__', 'socket.connect'):
        raise AssertionError('Offline opening attempted external execution/network: ' + event)
sys.addaudithook(audit)
sys.path.insert(0, ''' + repr(str(source)) + ''')
''' + before + '''
from specroad.cli.application import execute_request, dispatch_result
result = ''' + invocation + '''
value = {'code': result.exit_code, 'outcome': result.as_dict()}
''' + after + '''
print(json.dumps(value))
'''
    process = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', body], cwd=root,
        env=environment, stdin=subprocess.DEVNULL, capture_output=True)
    assert process.returncode == expected_process_code, process.stderr.decode(errors='replace')
    if expected_process_code:
        return process
    return json.loads(process.stdout)
