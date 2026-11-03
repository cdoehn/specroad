"""Workspace contracts against isolated Codex transports, never a live model."""
from dataclasses import replace
import json
from pathlib import Path
from uuid import uuid4

from specroad_control.codex import Codex
from specroad_control.config import render
from specroad_control.job_contract import SCHEMA, prompt_for, scope
from specroad_control.local import json_read, private_dir
from codex_control_tests.automation_support import AutomationCase


class ThreadWorkspaceTests(AutomationCase):
    def invoke(self, transport, root, *, readonly=False, observed=None):
        self.config = replace(self.config, transport=transport, thread_cwd=root)
        self.settings(cwd=str(observed or root or self.dev), mode='no_work')
        directory = self.paths.state / ('workspace-' + str(uuid4()))
        private_dir(directory)
        result = Codex(self.config).run(prompt_for(self.seed), SCHEMA, directory,
                                        readonly=readonly)
        self.assertEqual(result['status'], 'no_work')
        return directory

    def request(self):
        return json.loads((self.codex_home / 'request.json').read_text())

    def last_exec(self):
        return json.loads((self.codex_home / 'calls.jsonl').read_text().splitlines()[-1])

    def test_proxy_keeps_parent_after_previous_dev_turn(self):
        self.invoke('app-server-proxy', self.dev.parent, observed=self.dev)
        request = self.request()
        self.assertEqual(request['cwd'], str(self.dev.parent))
        self.assertEqual(request['threadId'], self.thread)
        self.assertEqual(request['sandboxPolicy'], {
            'type': 'workspaceWrite',
            'writableRoots': [str(self.dev.parent), str(self.exchange)],
            'networkAccess': False})
        self.assertEqual(request['approvalPolicy'], 'never')
        self.assertTrue({'model', 'effort', 'permissions'}.isdisjoint(request))

    def test_parent_policy_covers_apply_control_and_other_workspace_content(self):
        self.invoke('app-server-proxy', self.dev.parent)
        roots = [Path(value) for value in self.request()['sandboxPolicy']['writableRoots']]
        for name in ('specroad-apply', 'specroad-control', 'patch-harbor', 'workspace-file'):
            target = self.dev.parent / name
            self.assertTrue(any(target.is_relative_to(root) for root in roots), name)
        self.assertFalse(any(self.dev.parent.parent.is_relative_to(root) for root in roots))

    def test_proxy_explicit_dev_preserves_narrow_scope(self):
        self.invoke('app-server-proxy', self.dev)
        request = self.request()
        self.assertEqual(request['cwd'], str(self.dev))
        self.assertEqual(request['sandboxPolicy']['writableRoots'], [str(self.dev), str(self.exchange)])

    def test_proxy_legacy_configuration_keeps_dev_scope(self):
        self.invoke('app-server-proxy', None)
        self.assertEqual(self.request()['cwd'], str(self.dev))
        self.assertEqual(self.request()['sandboxPolicy']['writableRoots'], [str(self.dev), str(self.exchange)])

    def test_exec_pins_parent_in_arguments_process_and_permissions(self):
        self.invoke('exec', self.dev.parent, observed=self.dev)
        args = self.last_exec()
        self.assertEqual(args[:4], ['exec', '--cd', str(self.dev.parent), 'resume'])
        self.assertEqual((self.codex_home / 'process-cwd').read_text(), str(self.dev.parent))
        self.assertIn('sandbox_workspace_write.writable_roots=' + json.dumps(
            [str(self.dev.parent), str(self.exchange)]), args)
        self.assertIn('sandbox_workspace_write.network_access=false', args)
        self.assertIn('approval_policy="never"', args)
        self.assertIn('sandbox_mode="workspace-write"', args)
        self.assertEqual(args[-2:], [self.thread, '-'])
        self.assertTrue({'--last', '--worktree', '--model', '--dangerously-bypass-approvals-and-sandbox'}.isdisjoint(args))

    def test_exec_legacy_configuration_explicitly_pins_dev(self):
        self.invoke('exec', None)
        self.assertEqual(self.last_exec()[:4], ['exec', '--cd', str(self.dev), 'resume'])
        self.assertEqual((self.codex_home / 'process-cwd').read_text(), str(self.dev))

    def test_parent_probe_remains_readonly_for_proxy(self):
        directory = self.invoke('app-server-proxy', self.dev.parent, readonly=True)
        self.assertEqual(self.request()['cwd'], str(self.dev.parent))
        self.assertEqual(self.request()['sandboxPolicy'], {'type': 'readOnly'})
        self.assertFalse((directory / 'dispatch.json').exists())

    def test_parent_probe_remains_readonly_for_exec(self):
        self.invoke('exec', self.dev.parent, readonly=True)
        args = self.last_exec()
        self.assertEqual(args[:4], ['exec', '--cd', str(self.dev.parent), 'resume'])
        self.assertIn('sandbox_mode="read-only"', args)
        self.assertFalse(any(value.startswith('sandbox_workspace_write.writable_roots=') for value in args))

    def test_normal_turn_reasserts_writes_after_readonly_probe(self):
        self.invoke('app-server-proxy', self.dev.parent, readonly=True)
        self.invoke('app-server-proxy', self.dev.parent)
        self.assertEqual(self.request()['cwd'], str(self.dev.parent))
        self.assertEqual(self.request()['sandboxPolicy']['type'], 'workspaceWrite')
        starts = [r for r in self.codex_daemon.server.requests if r.get('method') == 'turn/start']
        self.assertEqual(len(starts), 2)
        self.assertTrue(all(r['params']['threadId'] == self.thread for r in starts))

    def test_dispatch_receipt_binds_actual_cwd_and_policy(self):
        directory = self.invoke('app-server-proxy', self.dev.parent)
        receipt = json_read(directory / 'dispatch.json')
        request = self.request()
        self.assertEqual(receipt['cwd'], request['cwd'])
        self.assertEqual(receipt['sandboxPolicy'], request['sandboxPolicy'])
        self.assertEqual(receipt['approvalPolicy'], request['approvalPolicy'])
        self.assertEqual(receipt['thread_id'], self.thread)
        self.assertTrue(receipt['turn_id'])

    def test_dispatch_does_not_rewrite_configuration_or_ledger(self):
        before = self.paths.config.read_bytes()
        ledger = (self.paths.state / 'automation.sqlite3').read_bytes()
        self.config = replace(self.config, thread_cwd=self.dev.parent, transport='app-server-proxy')
        identity, encoded = scope(self.config), render(self.config)
        self.invoke('app-server-proxy', self.dev.parent)
        self.assertEqual(self.paths.config.read_bytes(), before)
        self.assertEqual((self.paths.state / 'automation.sqlite3').read_bytes(), ledger)
        self.assertEqual(scope(self.config), identity)
        self.assertEqual(render(self.config), encoded)
