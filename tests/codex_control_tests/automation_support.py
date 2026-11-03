"""Isolated protocol doubles, not evidence of a live Codex/Remote session."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import uuid4
import zipfile
from specroad_control.config import Config, render
from specroad_control.core import Core
from specroad_control.errors import ControlError
from specroad_control.local import write_private, private_dir
from specroad_control.ledger import Ledger
from specroad_control.job_contract import scope
from codex_control_tests.support import LocalCase
from codex_control_tests.daemon_socket import SocketDaemon


def package(path, facts):
    facts = dict(facts)
    manifest = {**facts['binding'], 'format_version': 1}
    if facts['kind'] == 'result':
        manifest.update(marker='patch-harbor-result-bundle', run_id=facts['run_id'], patch_sha256=facts.get('patch_sha256'))
        manifest['created_at'] = facts.get('captured_at')
        name = 'manifest.json'
    else:
        manifest.update(marker='patch-harbor', entrypoint='run.sh')
        name = 'patch.json'
    temporary = path.with_suffix('.partial')
    with zipfile.ZipFile(temporary, 'w') as z:
        z.writestr(name, json.dumps(manifest))
        z.writestr('test-facts.json', json.dumps(facts))
    temporary.replace(path)
    return read_package(path)


def read_package(path):
    with zipfile.ZipFile(path) as z:
        facts = json.loads(z.read('test-facts.json'))
    return {**facts, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'path': str(path)}


class FakeCore:
    def result(self, path):
        data = read_package(Path(path))
        if data.get('reject') or data['kind'] != 'result':
            raise ControlError('core_rejected', 'rejected by test double')
        return data

    def patch(self, path):
        data = read_package(Path(path))
        if data.get('reject') or data['kind'] != 'patch':
            raise ControlError('core_rejected', 'rejected by test double')
        return data

    def validate(self, path, source):
        data = self.patch(path)
        if data['binding'] != source['binding']:
            raise ControlError('binding_mismatch', 'binding')
        return {**data, 'reference_sha256': source['sha256'], 'binding_matches': True}


class FakeCodex:
    def __init__(self, case, mode='patch'):
        self.case, self.mode, self.calls = case, mode, 0

    def check(self):
        return {'thread_resolved': True, 'model_called': False, 'remote_visibility': 'not_verified'}

    def run(self, prompt, schema, directory, *, readonly=False, authorize=lambda: True):
        if not authorize():
            raise ControlError('dispatch_paused', 'paused')
        self.calls += 1
        if self.mode == 'failure':
            raise ControlError('codex_turn_failed', 'unknown effects')
        source = json.loads(prompt.split('\n')[1])
        if self.mode == 'patch':
            data = package(self.case.exchange / ('patch-' + str(self.calls) + '.zip'), {'kind': 'patch', 'binding': source['binding']})
            return {'source_result_sha256': source['sha256'], 'status': 'patch_ready', 'patch_sha256': data['sha256'], 'message': ''}
        return {'source_result_sha256': source['sha256'], 'status': self.mode, 'patch_sha256': '', 'message': ''}


# This executable is deliberately a TEST DOUBLE. It has no Codex/network imports.
CODEX_SCRIPT = r'''
import hashlib, json, os, pathlib, sys, time, zipfile
home = pathlib.Path(os.environ['CODEX_HOME'])
settings = json.loads((home / 'test.json').read_text())
def emit(d): print(json.dumps(d), flush=True)
def answer(prompt):
    marker = prompt.split('marker=')[-1]
    if 'Sichtbarkeitstest' in prompt: return {'marker': marker}
    src = json.loads(prompt.split('\n')[1])
    if settings.get('mode') == 'patch':
        path = pathlib.Path(settings['exchange']) / ('dev-' + src['run_id'] + '.zip')
        facts = {'kind': 'patch', 'binding': src['binding']}
        tmp = path.with_suffix('.partial')
        with zipfile.ZipFile(tmp, 'w') as z:
            z.writestr('patch.json', json.dumps(dict(src['binding'], marker='patch-harbor',format_version=1, entrypoint='run.sh')))
            z.writestr('test-facts.json', json.dumps(facts))
        tmp.replace(path)
        return {'source_result_sha256': src['sha256'], 'status': 'patch_ready', 'patch_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'message': ''}
    return {'source_result_sha256': src['sha256'], 'status': 'no_work', 'patch_sha256': '', 'message': ''}
def beginning():
    with (home / 'calls.jsonl').open('a') as out: out.write(json.dumps(sys.argv[1:]) + '\n')
    (home / 'process-cwd').write_text(os.getcwd())
    (home / 'started').write_text('yes')
    if settings.get('slow'):
        while not (home / 'release').exists(): time.sleep(.02)
if sys.argv[1:3] == ['app-server', 'proxy']:
    for line in sys.stdin:
        obj = json.loads(line); method=obj.get('method'); ident=obj.get('id')
        if method == 'initialize': emit({'id':ident,'result':{}})
        elif method in ('thread/read', 'thread/resume'):
            if settings.get('missing'): emit({'id':ident,'error':{'code':-1,'message':'missing'}})
            else: emit({'id':ident,'result':{'thread':{'id':settings.get('returned_id',settings['thread']), 'cwd':settings.get('cwd',os.getcwd()), 'status':{'type':settings.get('thread_status','idle')}}}})
        elif method == 'turn/start':
            beginning(); params=obj['params']; turn='test-turn'
            with (home/'request.json').open('w') as out: json.dump(params,out)
            emit({'id':ident,'result':{'turn':{'id':turn,'status':'inProgress'}}})
            result=answer(params['input'][0]['text'])
            emit({'method':'item/completed','params':{'threadId':settings['thread'],'turnId':turn,'item':{'type':'agentMessage','text':json.dumps(result)}}})
            emit({'method':'turn/completed','params':{'threadId':settings['thread'],'turn':{'id':turn,'status': 'failed' if settings.get('fail') else 'completed'}}})
        elif method and ident is not None: emit({'id':ident,'error':{'code':-1}})
else:
    args = sys.argv[1:]
    if args[:2] == ['exec','--cd']:
        assert args[2] == os.getcwd()
        args = [args[0], *args[3:]]
    assert args[:2] == ['exec','resume']
    beginning(); prompt=sys.stdin.read()
    target=settings.get('event_thread',settings['thread'])
    emit({'type':'thread.started','thread_id':target})
    if settings.get('misordered'): emit({'type':'turn.completed'})
    emit({'type':'turn.started'})
    if settings.get('extra_turn'): emit({'type':'turn.started'})
    if settings.get('malformed'): print('broken',flush=True)
    if settings.get('missing_completed'): sys.exit(0)
    result=answer(prompt)
    output=pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1])
    with output.open('w') as out: json.dump(result,out)
    emit({'type':'turn.failed' if settings.get('fail') else 'turn.completed'})
'''

CORE_SCRIPT = r'''
import hashlib,json,pathlib,sys,zipfile
# Protocol double for an already installed interpreter. The product helper is
# tested independently against the actual bundled PH Core, never loaded here.
a=sys.argv[sys.argv.index('ph_bridge.py')+1:] if 'ph_bridge.py' in sys.argv else sys.argv[4:]
try:
    operation,path=a[:2]; path=pathlib.Path(path)
    with zipfile.ZipFile(path) as z: d=json.loads(z.read('test-facts.json'))
    if d.get('reject'): raise ValueError()
    d['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    if operation=='validate':
        ref=pathlib.Path(a[2]); d.update(binding_matches=True, reference_sha256=hashlib.sha256(ref.read_bytes()).hexdigest())
    print(json.dumps({'ok':True,'data':d}))
except Exception:
    print(json.dumps({'ok':False,'error':'core_rejected'})); sys.exit(1)
'''


class AutomationCase(LocalCase):
    def setUp(self):
        super().setUp()
        self.dev = self.home / 'specroad-codex'; self.dev.mkdir(); (self.dev/'.git').mkdir()
        self.exchange = self.home / 'exchange'; self.exchange.mkdir()
        self.codex_home = self.home / 'codex-home'; self.codex_home.mkdir(mode=0o700)
        self.repo_id, self.thread = str(uuid4()), str(uuid4())
        self.binding = {'repo_id': self.repo_id, 'base_commit': 'a'*40, 'state_fingerprint': 'b'*16, 'fingerprint_algorithm': 'patchharbor-state-v1'}
        self.seed = self.result('seed.zip')
        self.binary = self.home / 'fake-codex'
        self.binary.write_text('#!' + sys.executable + '\n' + CODEX_SCRIPT); self.binary.chmod(0o700)
        self.python = self.home / 'fake-core'
        self.python.write_text('#!' + sys.executable + '\n' + CORE_SCRIPT); self.python.chmod(0o700)
        self.config = Config(self.dev, self.exchange, self.thread, True, self.repo_id,
                             self.python, self.binary, self.codex_home, settle_seconds=.05)
        self.settings()
        self.codex_daemon = SocketDaemon(self.codex_home, self.dev)
        self.addCleanup(self.codex_daemon.close)
        write_private(self.paths.config, render(self.config).encode())
        # General worker tests are independent of the host's free disk capacity.
        write_private(self.paths.config.with_suffix('.limits.toml'), b'format_version = 1\nmin_free_gb = 0.001\n')
        private_dir(self.paths.state)
        history = Ledger(self.paths.state / "automation.sqlite3", scope(self.config), initial=self.seed)
        history.close()

    def settings(self, **values):
        current = {'thread': self.thread, 'exchange': str(self.exchange)}
        current.update(values)
        temporary = self.codex_home/'test.json.partial'
        temporary.write_text(json.dumps(current))
        temporary.replace(self.codex_home/'test.json')

    def result(self, name, *, previous=None, patch_sha=None, **changes):
        facts = {'kind':'result','binding':dict(self.binding), 'run_id':str(uuid4()),
                 'repository_path':str(self.home/'specroad-apply'), 'operation':'bundle',
                 'dry_run':False,'success':True,'primary_kind':'success','entrypoint_started':False,
                 'patch_sha256':None,'expected':None,'completed_commit':None,'dirty':False}
        if previous is not None:
            facts.update(binding={**previous['binding'], 'base_commit': 'c'*40}, operation='apply',
                         expected=previous['binding'], patch_sha256=patch_sha, entrypoint_started=True)
        facts.update(changes)
        return package(self.exchange / name, facts)
