"""Owned roots and explicit child-process protocols for native lock behavior."""
import json
from pathlib import Path
import subprocess
import sys
from specroad.changes import project_lock
from .read_only import make_project

ROOT = Path(__file__).resolve().parents[2]


def options(kind='writer'):
    command = {'writer': 'change apply', 'recovery': 'recover run', 'operational': 'lock recover'}[kind]
    return {'kind': kind, 'command': command, 'project_id': 'sample',
            'transaction_id': None if kind == 'operational' else 'txn-test', 'request_id': 'Req.Test:1'}


def child_program(code, *args):
    # No inherited pytest plugins or hidden credentials are used by the child.
    setup = 'import sys; sys.path.insert(0, ' + repr(str(ROOT / 'src')) + '); '
    return [sys.executable, '-I', '-B', '-c', setup + code, *map(str, args)]


def attempt(root, kind='writer'):
    code = '''
import json
from specroad.changes import project_lock, ProjectLockError
options = json.loads(sys.argv[2])
try:
    with project_lock(sys.argv[1], **options) as held:
        result = {"acquired": held.check()}
except ProjectLockError as error:
    result = {"acquired": False, "reason": error.reason}
print(json.dumps(result))
'''
    completed = subprocess.run(child_program(code, root, json.dumps(options(kind))),
                               check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def orphan(root):
    """The child exits without Python finalizers after acquiring the real lock."""
    code = '''
import os, json
from specroad.changes import project_lock
ctx = project_lock(sys.argv[1], **json.loads(sys.argv[2]))
held = ctx.__enter__()
print(json.dumps(held.record.data), flush=True)
os._exit(0)
'''
    done = subprocess.run(child_program(code, root, json.dumps(options())),
                          check=True, capture_output=True, text=True)
    return json.loads(done.stdout)


class Probe:
    def __init__(self, host=None, state='unknown', start=None):
        self.host, self.state, self.start = host, state, start
    def host_id(self):
        return self.host
    def process(self, pid):
        return self.state, self.start
