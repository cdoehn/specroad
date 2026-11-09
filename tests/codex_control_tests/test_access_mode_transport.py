"""Actual CLI argv and local socket requests against isolated protocol doubles."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from io import StringIO
import json
from unittest.mock import patch
from uuid import uuid4

from specroad_control import cli
from specroad_control.codex import Codex
from specroad_control.commands import configure, probe
from specroad_control.config import load, render
from specroad_control.errors import ControlError
from specroad_control.job_contract import SCHEMA, prompt_for
from specroad_control.local import json_read, private_dir, write_private
from codex_control_tests.automation_support import AutomationCase


class AccessModeTransportTests(AutomationCase):
    def select(self, transport, *, parent=False):
        self.config = replace(self.config, transport=transport, access_mode='full-access',
                              thread_cwd=self.dev.parent if parent else None)
        self.settings(cwd=str(self.config.thread_cwd or self.dev), mode='no_work')
        write_private(self.paths.config, render(self.config).encode())

    def invoke(self, **options):
        directory = self.paths.state / ('access-' + str(uuid4()))
        private_dir(directory)
        answer = Codex(self.config).run(prompt_for(self.seed), SCHEMA, directory, **options)
        self.assertEqual(answer['status'], 'no_work')
        return directory

    def assert_full_access(self):
        working = self.config.thread_cwd or self.dev
        if self.config.transport == 'app-server-proxy':
            # The independent daemon double records ordinary JSON, not private
            # Control state. Read it like the other transport contract tests.
            request = json.loads((self.codex_home / 'request.json').read_text())
            self.assertEqual(request['threadId'], self.thread)
            self.assertEqual(request['cwd'], str(working))
            self.assertEqual(request['approvalPolicy'], 'never')
            self.assertEqual(request['sandboxPolicy'], {'type': 'dangerFullAccess'})
            self.assertTrue({'permissions', 'model', 'effort'}.isdisjoint(request))
            return request
        args = json.loads((self.codex_home / 'calls.jsonl').read_text().splitlines()[-1])
        self.assertEqual(args[:4], ['exec', '--cd', str(working), 'resume'])
        self.assertEqual((self.codex_home / 'process-cwd').read_text(), str(working))
        self.assertEqual(args[-2:], [self.thread, '-'])
        overrides = [args[i + 1] for i, item in enumerate(args) if item == '-c']
        self.assertEqual(overrides, ['approval_policy="never"', 'sandbox_mode="danger-full-access"'])
        self.assertTrue({'--full-auto', '--last', '--model',
                         '--dangerously-bypass-approvals-and-sandbox'}.isdisjoint(args))

    def test_both_transports_use_full_access_for_repeated_productive_turns(self):
        for transport in ('exec', 'app-server-proxy'):
            with self.subTest(transport=transport):
                self.select(transport, parent=True)
                for _ in range(2):
                    directory = self.invoke()
                    request = self.assert_full_access()
                    if request:
                        receipt = json_read(directory / 'dispatch.json')
                        self.assertEqual(receipt['sandboxPolicy'], request['sandboxPolicy'])
                        self.assertEqual(receipt['approvalPolicy'], request['approvalPolicy'])
                        self.assertEqual(receipt['cwd'], request['cwd'])

    def test_probe_does_not_downgrade_full_access_or_change_its_no_tools_task(self):
        for transport in ('exec', 'app-server-proxy'):
            with self.subTest(transport=transport):
                self.select(transport)
                before = self.paths.config.read_bytes()
                result = probe(self.paths)
                self.assertTrue(result['same_thread_protocol'])
                self.assertFalse(result['service_started'])
                self.assertEqual(result['remote_visibility'], 'not_verified')
                request = self.assert_full_access()
                if request:
                    self.assertIn('Keine Tools', request['input'][0]['text'])
                self.assertEqual(self.paths.config.read_bytes(), before)
                self.invoke()
                self.assert_full_access()

    def test_full_access_preserves_pause_boundary_for_both_transports(self):
        for transport in ('exec', 'app-server-proxy'):
            with self.subTest(transport=transport):
                self.select(transport)
                with self.assertRaises(ControlError) as caught:
                    self.invoke(authorize=lambda: False)
                self.assertEqual(caught.exception.code, 'dispatch_paused')
                self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_proxy_continuation_sends_full_access_and_exact_existing_thread(self):
        from specroad_control.continuation import sha
        self.select('app-server-proxy')
        self.settings(cwd=str(self.dev), thread_status='systemError', mode='no_work')
        self.codex_daemon.server.history['target'] = {
            'id': 'target', 'status': 'failed', 'error': {'codexErrorInfo': 'serverOverloaded'},
            'items': [{'id': 'r', 'type': 'reasoning'}]}
        live = Codex(self.config).inspect_continuation('target')
        evidence = {'turn_id': 'target', 'history_sha256': sha(live['turn'])}
        self.invoke(continuation=evidence)
        self.assert_full_access()
        starts = [r for r in self.codex_daemon.server.requests if r.get('method') == 'turn/start']
        self.assertEqual(len(starts), 1)

    def test_full_access_does_not_start_in_busy_or_foreign_thread(self):
        for transport in ('exec', 'app-server-proxy'):
            for settings, expected in (({'thread_status': 'active'}, 'dev_thread_busy'),
                                       ({'cwd': str(self.home / 'foreign')}, 'wrong_thread_repository')):
                with self.subTest(transport=transport, settings=settings):
                    self.select(transport)
                    self.settings(**settings)
                    with self.assertRaises(ControlError) as caught:
                        self.invoke()
                    self.assertEqual(caught.exception.code, expected)
                    self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_failed_full_access_turn_does_not_fall_back_or_retry(self):
        for transport in ('exec', 'app-server-proxy'):
            with self.subTest(transport=transport):
                self.select(transport)
                self.settings(cwd=str(self.dev), fail=True)
                log = self.codex_home / 'calls.jsonl'
                previous = len(log.read_text().splitlines()) if log.exists() else 0
                with self.assertRaises(ControlError):
                    self.invoke()
                self.assertEqual(len(log.read_text().splitlines()), previous + 1)
                self.assert_full_access()

    def test_configure_persists_explicit_mode_preserves_it_if_omitted_and_can_restrict_again(self):
        original = load(self.paths)
        for selected, expected in (('full-access', 'full-access'), (None, 'full-access'),
                                   ('workspace-write', 'workspace-write')):
            with self.subTest(selected=selected):
                result = configure(self.paths, thread_id=self.thread, access_mode=selected)
                configured = load(self.paths)
                self.assertEqual(configured.access_mode, expected)
                self.assertEqual(replace(configured, access_mode=original.access_mode,
                                         command_path=original.command_path), original)
                self.assertEqual(result['access_mode'], expected)
                self.assertFalse(result['model_called'])
                self.assertFalse(result['service_started'])
                self.assertFalse(result['bootstrap_created'])
                self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_invalid_configuration_preserves_existing_bytes(self):
        before = self.paths.config.read_bytes()
        with self.assertRaises(ControlError) as caught:
            configure(self.paths, thread_id=self.thread, access_mode='full-auto')
        self.assertEqual(caught.exception.code, 'invalid_access_mode')
        self.assertEqual(self.paths.config.read_bytes(), before)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_cli_forwards_explicit_mode_only_to_configure(self):
        with patch.object(cli.commands, 'configure', return_value={'configured': True}) as operation:
            with redirect_stdout(StringIO()):
                self.assertEqual(cli.main(['configure', '--thread-id', self.thread,
                                          '--access-mode', 'full-access']), 0)
            self.assertEqual(operation.call_args.kwargs['access_mode'], 'full-access')
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
                cli.main(['start', '--access-mode', 'full-access'])
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(operation.call_count, 1)
