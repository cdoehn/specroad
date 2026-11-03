"""Dispatch and receipt contracts without sockets or a real Codex/model process."""
from collections import deque
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
from codex_control_tests.external_temp import temporary_directory
import unittest
from unittest.mock import patch
from uuid import uuid4

from specroad_control.codex import Codex
from specroad_control.config import Config, execution_directory
from specroad_control.continuation import receipts
from specroad_control.continuation_evidence import policy, prove_items, request_prompt, sha
from specroad_control.errors import ControlError
from specroad_control.local import json_read, json_write, private_dir


EXEC_DOUBLE = '''import json, os, pathlib, sys
home = pathlib.Path(os.environ['CODEX_HOME'])
(home/'execution.json').write_text(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd()}))
sys.stdin.read()
output = pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1])
output.write_text(json.dumps({'status': 'no_work'}))
for event in ({'type': 'thread.started', 'thread_id': sys.argv[-2]},
              {'type': 'turn.started'}, {'type': 'turn.completed'}):
    print(json.dumps(event), flush=True)
'''


class LocalProxy:
    """Only the dispatch protocol is doubled; exec still runs its isolated child."""
    def __init__(self, config):
        self.config = config
        self.requests = []
        self.pending = deque()
        self.checks = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def thread(self):
        self.checks += 1

    def call(self, method, params):
        self.requests.append((method, deepcopy(params)))
        if method == 'thread/resume':
            return {'thread': {'id': self.config.session_id}}
        if method != 'turn/start':
            raise AssertionError(method)
        turn = 'isolated-turn'
        self.pending.extend([
            {'method': 'item/completed', 'params': {'threadId': self.config.session_id,
                'turnId': turn, 'item': {'type': 'agentMessage',
                                       'text': json.dumps({'status': 'no_work'})}}},
            {'method': 'turn/completed', 'params': {'threadId': self.config.session_id,
                'turn': {'id': turn, 'status': 'completed'}}}])
        return {'turn': {'id': turn, 'status': 'inProgress'}}


class WorkspaceUnitTests(unittest.TestCase):
    def setUp(self):
        temporary = temporary_directory(prefix='cw-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / 'Workspace mit Leerzeichen Ä'
        self.dev = self.workspace / 'specroad-codex'
        self.dev.mkdir(parents=True)
        self.exchange = self.workspace / 'exchange'
        self.exchange.mkdir()
        self.codex_home = self.root / 'codex-double'
        self.codex_home.mkdir(mode=0o700)
        binary = self.root / 'codex-double.py'
        binary.write_text('#!' + sys.executable + '\n' + EXEC_DOUBLE)
        binary.chmod(0o700)
        self.config = Config(self.dev, self.exchange, str(uuid4()),
                             codex_executable=binary, codex_home=self.codex_home,
                             thread_cwd=self.workspace, transport='app-server-proxy')
        self.directory = self.root / 'evidence'
        private_dir(self.directory)
        self.proxy = LocalProxy(self.config)
        for name in ('specroad_control.codex.Proxy', 'specroad_control.proxy_turn.Proxy'):
            mock = patch(name, return_value=self.proxy)
            mock.start()
            self.addCleanup(mock.stop)

    def run_turn(self, *, readonly=False, authorize=lambda: True):
        return Codex(self.config).run('isolated request', {}, self.directory,
                                     readonly=readonly, authorize=authorize)

    def started(self):
        return [params for method, params in self.proxy.requests if method == 'turn/start']

    def failure_receipts(self, *, with_cwd=True):
        source = {'path': str(self.exchange / 'source.zip'), 'sha256': 'a' * 64,
                  'run_id': str(uuid4()), 'binding': {'base_commit': 'b' * 40,
                    'repo_id': str(uuid4()), 'fingerprint_algorithm': 'patchharbor-state-v1',
                    'state_fingerprint': 'c' * 16}}
        attempt = {'thread_id': self.config.session_id, 'source_sha256': source['sha256'],
                   'number': 0, 'workspace_sha256': 'd' * 64, 'request_source': source}
        turn = {'thread_id': self.config.session_id, 'turn_id': 'failed-turn'}
        dispatch = {**turn, 'prompt_sha256': sha(request_prompt(attempt, source)),
                    **policy(self.config)}
        if with_cwd:
            dispatch['cwd'] = str(execution_directory(self.config))
        for name, document in (
                ('attempt', attempt), ('turn', turn), ('dispatch', dispatch),
                ('failure', {**turn, 'turn_status': 'failed', 'codex_error': 'serverOverloaded',
                             'codex_will_retry': False})):
            json_write(self.directory / (name + '.json'), document)
        return source

    def test_proxy_parent_dispatch_binds_directory_and_full_workspace_policy(self):
        self.assertEqual(self.run_turn(), {'status': 'no_work'})
        request, = self.started()
        self.assertEqual(request['cwd'], str(self.workspace))
        self.assertEqual(request['threadId'], self.config.session_id)
        self.assertEqual(request['sandboxPolicy'], {
            'type': 'workspaceWrite', 'writableRoots': [str(self.workspace), str(self.exchange)],
            'networkAccess': False})
        self.assertEqual(request['approvalPolicy'], 'never')
        self.assertTrue({'permissions', 'model', 'effort'}.isdisjoint(request))
        dispatch = json_read(self.directory / 'dispatch.json')
        self.assertEqual(dispatch['cwd'], request['cwd'])
        self.assertEqual(dispatch['sandboxPolicy'], request['sandboxPolicy'])
        self.assertEqual(self.proxy.checks, 2)

    def test_exec_parent_directory_survives_spaces_and_unicode(self):
        self.config = replace(self.config, transport='exec')
        self.run_turn()
        execution = json.loads((self.codex_home / 'execution.json').read_text())
        self.assertEqual(execution['cwd'], str(self.workspace))
        self.assertEqual(execution['args'][:4], ['exec', '--cd', str(self.workspace), 'resume'])
        self.assertIn('sandbox_workspace_write.writable_roots=' + json.dumps(
            [str(self.workspace), str(self.exchange)]), execution['args'])
        self.assertIn('sandbox_workspace_write.network_access=false', execution['args'])
        self.assertIn('approval_policy="never"', execution['args'])
        self.assertEqual(execution['args'][-2:], [self.config.session_id, '-'])

    def test_proxy_probe_keeps_workspace_but_is_readonly(self):
        self.run_turn(readonly=True)
        request, = self.started()
        self.assertEqual(request['cwd'], str(self.workspace))
        self.assertEqual(request['sandboxPolicy'], {'type': 'readOnly'})
        self.assertFalse((self.directory / 'dispatch.json').exists())

    def test_exec_probe_keeps_workspace_but_is_readonly(self):
        self.config = replace(self.config, transport='exec')
        self.run_turn(readonly=True)
        execution = json.loads((self.codex_home / 'execution.json').read_text())
        self.assertEqual(execution['cwd'], str(self.workspace))
        self.assertIn('sandbox_mode="read-only"', execution['args'])
        self.assertFalse(any(arg.startswith('sandbox_workspace_write.writable_roots=')
                             for arg in execution['args']))

    def test_legacy_configuration_stays_in_dev(self):
        self.config = replace(self.config, thread_cwd=None)
        self.run_turn()
        request, = self.started()
        self.assertEqual(request['cwd'], str(self.dev))
        self.assertEqual(request['sandboxPolicy']['writableRoots'], [str(self.dev), str(self.exchange)])

    def test_modern_parent_receipt_is_accepted_without_rewriting(self):
        source = self.failure_receipts()
        before = (self.directory / 'dispatch.json').read_bytes()
        self.assertEqual(receipts(self.config, self.directory, source)[2]['cwd'], str(self.workspace))
        self.assertEqual((self.directory / 'dispatch.json').read_bytes(), before)

    def test_legacy_dev_receipt_remains_valid_without_rewriting(self):
        self.config = replace(self.config, thread_cwd=None)
        source = self.failure_receipts(with_cwd=False)
        before = (self.directory / 'dispatch.json').read_bytes()
        self.assertNotIn('cwd', receipts(self.config, self.directory, source)[2])
        self.assertEqual((self.directory / 'dispatch.json').read_bytes(), before)

    def test_parent_receipt_without_cwd_never_infers_permission_upgrade(self):
        source = self.failure_receipts(with_cwd=False)
        before = (self.directory / 'dispatch.json').read_bytes()
        with self.assertRaises(ControlError) as caught:
            receipts(self.config, self.directory, source)
        self.assertEqual(caught.exception.code, 'continuation_dispatch_unproven')
        self.assertEqual((self.directory / 'dispatch.json').read_bytes(), before)

    def test_foreign_workspace_blocks_both_transports_before_attachment(self):
        foreign = self.root / 'foreign'
        foreign.mkdir()
        for transport in ('exec', 'app-server-proxy'):
            with self.subTest(transport=transport):
                self.config = replace(self.config, thread_cwd=foreign, transport=transport)
                with self.assertRaises(ControlError) as caught:
                    self.run_turn()
                self.assertEqual(caught.exception.code, 'invalid_thread_workspace')
        self.assertEqual(self.proxy.checks, 0)
        self.assertEqual(self.proxy.requests, [])
        self.assertFalse((self.codex_home / 'execution.json').exists())
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_late_workspace_symlink_blocks_both_transports_before_start(self):
        foreign = self.root / 'foreign'
        foreign.mkdir()
        saved = self.root / 'saved-workspace'
        def replace_workspace():
            self.workspace.rename(saved)
            self.workspace.symlink_to(foreign, target_is_directory=True)
            return True
        for transport in ('exec', 'app-server-proxy'):
            with self.subTest(transport=transport):
                self.config = replace(self.config, transport=transport)
                try:
                    with self.assertRaises(ControlError) as caught:
                        self.run_turn(authorize=replace_workspace)
                    self.assertEqual(caught.exception.code, 'invalid_thread_workspace')
                    self.assertEqual(self.started(), [])
                    self.assertFalse((self.codex_home / 'execution.json').exists())
                    self.assertEqual(list(self.directory.iterdir()), [])
                finally:
                    if saved.exists():
                        self.workspace.unlink()
                        saved.rename(self.workspace)

    def test_pause_wins_before_workspace_dispatch(self):
        for transport in ('exec', 'app-server-proxy'):
            with self.subTest(transport=transport):
                self.config = replace(self.config, transport=transport)
                with self.assertRaises(ControlError) as caught:
                    self.run_turn(authorize=lambda: False)
                self.assertEqual(caught.exception.code, 'dispatch_paused')
        self.assertEqual(self.started(), [])
        self.assertFalse((self.codex_home / 'execution.json').exists())
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_mutated_dispatch_directory_or_policy_cannot_authorize_continuation(self):
        source = self.failure_receipts()
        original = json_read(self.directory / 'dispatch.json')
        variants = []
        for cwd in (str(self.dev), str(self.root), None):
            variants.append({**original, 'cwd': cwd})
        for field, value in (('networkAccess', True), ('type', 'dangerFullAccess'),
                             ('writableRoots', [str(self.root)])):
            variants.append({**original, 'sandboxPolicy': {**original['sandboxPolicy'], field: value}})
        variants.append({**original, 'approvalPolicy': 'on-request'})
        for document in variants:
            with self.subTest(document=document):
                json_write(self.directory / 'dispatch.json', document)
                before = (self.directory / 'dispatch.json').read_bytes()
                with self.assertRaises(ControlError) as caught:
                    receipts(self.config, self.directory, source)
                self.assertEqual(caught.exception.code, 'continuation_dispatch_unproven')
                self.assertEqual((self.directory / 'dispatch.json').read_bytes(), before)

    def test_historical_narrow_receipt_is_not_upgraded_for_parent_workspace(self):
        self.config = replace(self.config, thread_cwd=None)
        source = self.failure_receipts(with_cwd=False)
        before = (self.directory / 'dispatch.json').read_bytes()
        self.config = replace(self.config, thread_cwd=self.workspace)
        with self.assertRaises(ControlError) as caught:
            receipts(self.config, self.directory, source)
        self.assertEqual(caught.exception.code, 'continuation_dispatch_unproven')
        self.assertEqual((self.directory / 'dispatch.json').read_bytes(), before)

    def test_explicit_dev_can_read_historical_narrow_receipt(self):
        self.config = replace(self.config, thread_cwd=self.dev)
        source = self.failure_receipts(with_cwd=False)
        self.assertNotIn('cwd', receipts(self.config, self.directory, source)[2])

    def test_workspace_writes_do_not_expand_automatic_recovery_action_proof(self):
        turn = {'itemsView': 'full', 'items': [
            {'id': 'user', 'type': 'userMessage', 'content': [{'type': 'text', 'text': 'request'}]},
            {'id': 'change', 'type': 'fileChange', 'status': 'completed',
             'changes': [{'path': str(self.workspace / 'specroad-control' / 'control.py')}]}]}
        with self.assertRaises(ControlError):
            prove_items(turn, 'request', self.config)
