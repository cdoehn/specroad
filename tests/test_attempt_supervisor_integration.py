"""Native subprocess tree termination, including detached descendants."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from dev.test_hosts.attempt_supervisor import request
from support.live_pool import await_value


@pytest.mark.parametrize('detached', [False, True])
def test_supervisor_reaps_owned_descendants_and_leaves_foreign_process_alive(tmp_path, detached):
    supervisor = Path(__file__).resolve().parents[1]/'tools/dev/test_hosts/attempt_supervisor.py'
    source = '''import json,os,subprocess,sys,time
from pathlib import Path
root=Path(sys.argv[1])
code="import os,time; from pathlib import Path; "
if sys.argv[2]=='1': code += "os.fork() and os._exit(0); os.setsid(); "
code += "Path("+repr(str(root/'child'))+").write_text(str(os.getpid())); time.sleep(60)"
subprocess.Popen([sys.executable,'-c',code])
(root/'ready').write_text(json.dumps([os.environ['SPECROAD_ATTEMPT_SOCKET'],os.environ['SPECROAD_ATTEMPT_SECRET']]))
time.sleep(60)
'''
    log = tmp_path/'worker.log'
    temporary = tmp_path / ('long-worker-temp-' + 'x' * 120)
    temporary.mkdir(mode=0o700)
    env = os.environ | {'TMPDIR': str(temporary)}
    foreign = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    with log.open('w') as output:
        worker = subprocess.Popen([sys.executable, str(supervisor), '-c', source, str(tmp_path), str(int(detached))], stdout=output, stderr=output, env=env)
        try:
            await_value(lambda: (tmp_path/'ready').exists() and (tmp_path/'child').exists(), worker, log)
            endpoint, secret = json.loads((tmp_path/'ready').read_text())
            # Real parametrized identities can be much larger than a socket's
            # buffer. Preserve them in requests and accumulated cancel receipts.
            completed = dict(token='c'*32, index=0, slot=0,
                nodeid='tests/test_native.py::test_completed[' + '\0' * 70000 + ']',
                start=time.monotonic_ns())
            request(endpoint, secret, 'arm', **completed)
            completed['end'] = time.monotonic_ns()
            request(endpoint, secret, 'complete', token=completed['token'], end=completed['end'])
            token = 'a'*32
            active = dict(token=token, index=1, slot=0,
                nodeid='tests/test_native.py::test_one[' + 'q'*280000 + ']',
                start=time.monotonic_ns())
            request(endpoint, secret, 'arm', **active)
            assert request(endpoint, secret, 'status') == dict(active=active, completed=[completed])
            assert request(endpoint, secret, 'cancel', token='b'*32)['cancelled'] is False
            assert worker.poll() is None and foreign.poll() is None
            reply = request(endpoint, secret, 'cancel', token=token)
            assert reply['cancelled'] and reply['children_remaining'] == 0
            assert reply['completed'] == [completed]
            assert {key: reply['attempt'][key] for key in active} == active
            assert reply['attempt']['end'] >= active['start']
            assert worker.wait(timeout=10) == 137
            assert not Path(endpoint).parent.exists()
            assert not Path('/proc', (tmp_path/'child').read_text()).exists()
            assert foreign.poll() is None
        finally:
            if worker.poll() is None:
                worker.terminate(); worker.wait(timeout=5)
            foreign.terminate(); foreign.wait(timeout=5)
