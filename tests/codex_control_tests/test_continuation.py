"""Partial-work continuations use local protocol doubles, never a real model."""
from copy import deepcopy
from specroad_control import continuation as continuation_contract
from specroad_control.codex import Codex
from specroad_control.errors import ControlError
from specroad_control.job_contract import SCHEMA, prompt_for
from specroad_control.local import json_read, json_write, private_dir
from codex_control_tests.automation_support import AutomationCase, package
from codex_control_tests.test_overload_retry import RetryCase, OverloadCodex
from codex_control_tests.retry_support import git


class PartialCodex(OverloadCodex):
    def __init__(self, case):
        super().__init__(case)
        self.status = 'systemError'
        self.prompts = []
        self.continuations = []
        self.background = []
        self.after_failure = lambda directory: None

    def inspect_continuation(self, turn_id):
        if self.background:
            raise ControlError('continuation_background_active', 'Running terminal fixture')
        return {'thread_status': self.status, 'turn': deepcopy(self.turns.get(turn_id)),
                'latest_turn_id': next(reversed(self.turns), None), 'background_terminals': self.background}

    def run(self, prompt, schema, directory, *, readonly=False, authorize=lambda: True, continuation=None):
        before = self.calls
        try:
            return super().run(prompt, schema, directory, readonly=readonly, authorize=authorize)
        finally:
            if self.calls != before:
                self.prompts.append(prompt)
                self.continuations.append(continuation)
                turn_id = f'turn-{self.calls}'
                turn = self.turns[turn_id]
                turn['itemsView'] = 'full'
                turn['items'][2]['cwd'] = str(self.case.dev)
                turn['items'][2]['source'] = 'agent'
                json_write(directory/'dispatch.json', {'thread_id': self.case.thread, 'turn_id': turn_id,
                    'prompt_sha256': continuation_contract.sha(prompt), **continuation_contract.policy(self.case.config)})
                if self.calls <= self.failures:
                    (self.case.dev/'partial.txt').write_text('preserved work ' + str(self.calls))
                    turn['items'].append({'id': 'edit', 'type': 'fileChange', 'status': 'completed',
                                         'changes': [{'path': str(self.case.dev/'partial.txt')}]})
                    self.after_failure(directory)


class ContinuationTests(RetryCase):
    def setUp(self):
        super().setUp()
        self.codex = PartialCodex(self)
        self.engine.codex = self.codex
        self.codex.observe = self.engine.observe

    def test_partial_work_survives_overload_and_continues_same_source(self):
        self.assertEqual(self.engine.tick()['retry_after'], 60)
        content = (self.dev/'partial.txt').read_bytes()
        evidence = self.ledger().retry_info(self.seed['sha256'])['evidence']
        self.assertEqual(evidence['mode'], 'continuation')
        self.assertEqual(self.codex.calls, 1)
        self.now += 60
        self.engine.tick()
        self.assertEqual(self.codex.calls, 2)
        self.assertEqual((self.dev/'partial.txt').read_bytes(), content)
        self.assertEqual(self.codex.continuations[1], evidence)
        self.assertNotEqual(self.codex.prompts[0], self.codex.prompts[1])
        self.assertEqual(self.ledger().current()['stage'], 'no_work')

    def test_committed_partial_work_is_kept(self):
        def commit(_):
            git(self.dev, 'add', '--', 'partial.txt')
            git(self.dev, 'commit', '--quiet', '-m', 'Partial work fixture')
        self.codex.after_failure = commit
        self.engine.tick()
        head = git(self.dev, 'rev-parse', 'HEAD')
        self.now += 60; self.engine.tick()
        self.assertEqual(git(self.dev, 'rev-parse', 'HEAD'), head)
        self.assertEqual(self.codex.calls, 2)

    def test_repeat_overloads_share_the_existing_finite_budget(self):
        self.codex.failures = 20
        for wait in (60, 180, 600, 1800):
            self.assertEqual(self.engine.tick()['retry_after'], wait)
            self.now += wait
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 5)
        self.assertEqual(self.engine.summary()['retry_blocked_reason'], 'retry_exhausted')

    def test_completed_shell_with_nonzero_exit_can_be_inspected_and_continued(self):
        self.codex.effect = {'id': 'test', 'type': 'commandExecution', 'command': 'python3 -B tools/test_parallel.py',
                             'cwd': str(self.dev), 'source':'agent', 'status': 'completed', 'exitCode': 1}
        self.assertFalse(self.engine.tick()['halted'])

    def test_context_compaction_is_a_known_non_tool_item(self):
        self.codex.effect = {'id': 'compact', 'type': 'contextCompaction'}
        self.assertFalse(self.engine.tick()['halted'])

    def test_external_or_delegated_tool_still_blocks(self):
        for kind in ('mcpToolCall', 'collabAgentToolCall', 'unknown'):
            with self.subTest(kind=kind):
                turn = {'itemsView':'full', 'items': [{'id':'u','type':'userMessage',
                      'content':[{'type':'text','text':'request'}]}, {'id':'x','type':kind}]}
                with self.assertRaises(ControlError): continuation_contract.prove_items(turn, 'request', self.config)

    def test_running_command_never_schedules(self):
        self.codex.effect = {'id':'busy','type':'commandExecution','command':'python3 test.py',
                            'cwd':str(self.dev),'status':'inProgress','exitCode':None}
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls, 1)

    def test_missing_original_dispatch_is_not_inferred(self):
        self.codex.after_failure = lambda directory: (directory/'dispatch.json').unlink()
        self.assertTrue(self.engine.tick()['halted'])
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))

    def test_user_interruption_never_schedules_even_with_partial_files(self):
        self.codex.after_failure = lambda directory: json_write(directory/'failure.json', {
            **json_read(directory/'failure.json'), 'turn_status':'interrupted'})
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls, 1)

    def test_external_workspace_edit_during_wait_blocks_continuation(self):
        self.engine.tick(); self.now += 60
        (self.dev/'partial.txt').write_text('changed outside this attempt')
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.ledger().current()['error'], 'continuation_checkpoint_changed')

    def test_changed_history_during_wait_blocks_continuation(self):
        self.engine.tick(); self.now += 60
        self.codex.turns['turn-1']['items'][1]['text'] = 'changed evidence'
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls, 1)

    def test_intervening_manual_turn_blocks_continuation(self):
        self.engine.tick(); self.now += 60
        self.codex.turns['manual'] = {'id':'manual','status':'completed'}
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls, 1)

    def test_active_turn_is_left_running_without_new_turn(self):
        self.engine.tick(); self.now += 60; self.codex.status = 'active'
        self.assertEqual(self.engine.tick()['retry_after'], 30)
        self.assertEqual(self.codex.calls, 1)

    def test_background_terminal_cannot_authorize_replacement(self):
        self.codex.background = [{'processId':'running'}]
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls, 1)

    def test_patch_published_before_failure_is_adopted_without_retry(self):
        self.codex.after_failure = lambda _: package(self.exchange/'published.zip', {'kind':'patch','binding':self.binding})
        self.assertTrue(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['stage'], 'waiting_result')
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))
        self.assertEqual(self.codex.calls, 1)

    def test_pause_preserves_the_scheduled_continuation(self):
        self.engine.tick(); self.now += 60; self.engine.gate.set(False)
        self.engine.tick(); self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.ledger().current()['stage'], 'retry_wait')
        self.engine.gate.set(True); self.engine.tick(); self.assertEqual(self.codex.calls, 2)


class ContinuationHistoryTests(AutomationCase):
    def setUp(self):
        super().setUp()
        self.settings(thread_status='systemError')
        self.codex_daemon.server.history['target'] = {'id':'target','status':'failed',
            'error':{'codexErrorInfo':'serverOverloaded'},'items':[{'id':'r','type':'reasoning'}]}

    def observe(self):
        return Codex(self.config).inspect_continuation('target')

    def test_system_error_is_proven_by_latest_terminal_and_no_background_work(self):
        live = self.observe()
        self.assertEqual(live['thread_status'], 'systemError')
        self.assertEqual(live['turn']['itemsView'], 'full')
        self.assertEqual(live['background_terminals'], [])
        requests = self.codex_daemon.server.requests
        self.assertTrue(any(r.get('method') == 'thread/backgroundTerminals/list' for r in requests))
        self.assertFalse(any(r.get('method') in ('turn/start', 'thread/resume') for r in requests))

    def test_no_background_api_is_not_treated_as_empty(self):
        self.settings(no_background_api=True)
        with self.assertRaises(ControlError): self.observe()

    def test_active_background_terminal_blocks_observation(self):
        self.settings(background_terminals=[{'processId':'p'}])
        with self.assertRaises(ControlError) as caught: self.observe()
        self.assertEqual(caught.exception.code, 'continuation_background_active')

    def test_newer_turn_is_not_skipped_to_find_failed_target(self):
        self.codex_daemon.server.history['newer'] = {'id':'newer','status':'completed','items':[]}
        with self.assertRaises(ControlError) as caught: self.observe()
        self.assertEqual(caught.exception.code, 'continuation_intervening_turn')

    def test_missing_targeted_items_never_uses_legacy_history_for_continuation(self):
        self.settings(no_item_pages=True)
        with self.assertRaises(ControlError): self.observe()
        self.assertFalse(any(r.get('params', {}).get('includeTurns') for r in self.codex_daemon.server.requests))

    def test_proxy_continuation_starts_same_thread_without_model_or_effort_override(self):
        from dataclasses import replace
        self.config = replace(self.config, transport='app-server-proxy')
        live = self.observe()
        evidence = {'turn_id':'target','history_sha256':continuation_contract.sha(live['turn'])}
        directory = self.paths.state/'test-continuation'; private_dir(directory)
        result = Codex(self.config).run(prompt_for(self.seed), SCHEMA, directory, continuation=evidence)
        self.assertEqual(result['status'], 'patch_ready')
        requests = [r['params'] for r in self.codex_daemon.server.requests if r.get('method')=='turn/start']
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]['threadId'], self.thread)
        self.assertNotIn('model', requests[0]); self.assertNotIn('effort', requests[0])
