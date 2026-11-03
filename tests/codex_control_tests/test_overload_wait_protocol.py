"""Read-only modern waiting observations over an independent Unix WebSocket."""
from contextlib import contextmanager
from unittest.mock import patch
from specroad_control.codex import Codex
from specroad_control.codex_proxy import Proxy
from specroad_control.errors import ControlError
from codex_control_tests.automation_support import AutomationCase


class WaitProtocolTests(AutomationCase):
    def setUp(self):
        super().setUp()
        self.settings(thread_status='systemError')
        self.server = self.codex_daemon.server
        self.server.history['failed'] = {'id': 'failed', 'status': 'failed',
            'error': {'codexErrorInfo': 'serverOverloaded'}, 'items': [
                {'id': 'item', 'type': 'commandExecution', 'status': 'inProgress'}]}

    def terminal(self, number=0):
        return {'processId': f'process-{number}', 'itemId': f'item-{number}',
                'command': 'python3 test.py', 'cwd': str(self.dev)}

    def observe(self):
        return Codex(self.config).inspect_overload_wait('failed')

    @contextmanager
    def mutate(self, fn):
        original = Proxy.call
        def call(proxy, method, params):
            return fn(method, params, original(proxy, method, params))
        with patch.object(Proxy, 'call', call):
            yield

    def test_complete_paginated_background_inventory_is_observed(self):
        terminals = [self.terminal(i) for i in range(17)]
        self.settings(thread_status='systemError', background_terminals=terminals)
        result = self.observe()
        self.assertEqual(result['background_terminals'], terminals)
        self.assertEqual(result['turn']['items'][0]['status'], 'inProgress')
        self.assertTrue(any(r.get('params', {}).get('cursor') for r in self.server.requests))

    def test_background_metrics_may_change_between_reads(self):
        self.settings(thread_status='systemError', background_terminals=[{**self.terminal(), 'cpuPercent': 10}])
        def mutate(method, params, result):
            if method == 'thread/items/list':
                self.settings(thread_status='systemError', background_terminals=[{**self.terminal(), 'cpuPercent': 20}])
            return result
        with self.mutate(mutate):
            self.assertEqual(self.observe()['background_terminals'], [self.terminal()])

    def test_new_background_process_between_reads_blocks(self):
        def mutate(method, params, result):
            if method == 'thread/items/list':
                self.settings(thread_status='systemError', background_terminals=[self.terminal()])
            return result
        with self.mutate(mutate), self.assertRaises(ControlError) as caught:
            self.observe()
        self.assertEqual(caught.exception.code, 'overload_background_changed')

    def test_latest_turn_change_between_pages_blocks(self):
        def mutate(method, params, result):
            if method == 'thread/items/list':
                self.server.history['manual'] = {'id': 'manual', 'status': 'completed', 'items': []}
            return result
        with self.mutate(mutate), self.assertRaises(ControlError):
            self.observe()

    def test_incomplete_inventory_is_not_an_empty_terminal_proof(self):
        def mutate(method, params, result):
            if method == 'thread/backgroundTerminals/list':
                result.pop('nextCursor')
            return result
        with self.mutate(mutate), self.assertRaises(ControlError):
            self.observe()

    def test_missing_api_never_triggers_fallback_or_model(self):
        self.settings(thread_status='systemError', no_background_api=True)
        with self.assertRaises(ControlError):
            self.observe()
        self.assertFalse(any(r.get('method') in ('turn/start', 'thread/resume', 'thread/start')
                             for r in self.server.requests))
        self.assertFalse(any(r.get('params', {}).get('includeTurns') for r in self.server.requests))

    def test_duplicate_background_process_is_unproven(self):
        self.settings(thread_status='systemError', background_terminals=[self.terminal(), self.terminal()])
        with self.assertRaises(ControlError):
            self.observe()

    def test_active_turn_never_calls_termination(self):
        self.server.history['failed']['status'] = 'inProgress'
        with self.assertRaises(ControlError):
            self.observe()
        self.assertFalse(any(r.get('method') in ('turn/start', 'thread/resume', 'turn/interrupt',
            'thread/backgroundTerminals/clean', 'thread/backgroundTerminals/terminate') for r in self.server.requests))

    def test_background_byte_budget_applies_across_pages(self):
        self.settings(thread_status='systemError', background_terminals=[self.terminal()])
        with patch('specroad_control.continuation_history.MAX_HISTORY_BYTES', 1), self.assertRaises(ControlError) as caught:
            self.observe()
        self.assertEqual(caught.exception.code, 'overload_background_unproven')

    def test_same_process_cannot_appear_with_two_item_identities(self):
        self.settings(thread_status='systemError', background_terminals=[
            self.terminal(), {**self.terminal(), 'itemId': 'different-item'}])
        with self.assertRaises(ControlError):
            self.observe()
