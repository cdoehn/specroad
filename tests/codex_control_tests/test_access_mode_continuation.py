"""Permission continuity never substitutes for original overload evidence."""
from dataclasses import replace

from specroad_control import continuation
from specroad_control.errors import ControlError
from specroad_control.local import json_read, json_write
from codex_control_tests.test_continuation import PartialCodex
from codex_control_tests.test_overload_retry import RetryCase


class FullAccessContinuationTests(RetryCase):
    def setUp(self):
        super().setUp()
        self.config = replace(self.config, access_mode='full-access')
        self.engine.config = self.config
        self.codex = PartialCodex(self)
        self.engine.codex = self.codex
        self.codex.observe = self.engine.observe
        self.codex.after_failure = self.modern_receipt

    def directory(self):
        return self.paths.state / 'jobs' / self.seed['sha256']

    def modern_receipt(self, directory):
        receipt = json_read(directory / 'dispatch.json')
        receipt['cwd'] = str(self.dev)
        json_write(directory / 'dispatch.json', receipt)

    def test_full_access_continues_proven_work_without_replaying_original_actions(self):
        self.assertEqual(self.engine.tick()['retry_after'], 60)
        saved = (self.dev / 'partial.txt').read_bytes()
        self.assertEqual(json_read(self.directory() / 'dispatch.json')['sandboxPolicy'],
                         {'type': 'dangerFullAccess'})
        self.now += 60
        self.engine.tick()
        self.assertEqual(self.codex.calls, 2)
        self.assertEqual((self.dev / 'partial.txt').read_bytes(), saved)
        self.assertIsNotNone(self.codex.continuations[1])
        self.assertEqual(self.ledger().current()['stage'], 'no_work')

    def test_mode_change_rejects_old_receipt_without_rewriting_it(self):
        self.engine.tick()
        path = self.directory() / 'dispatch.json'
        original = path.read_bytes()
        restricted = replace(self.config, access_mode='workspace-write')
        with self.assertRaises(ControlError) as caught:
            continuation.receipts(restricted, self.directory(), self.seed)
        self.assertEqual(caught.exception.code, 'continuation_dispatch_unproven')
        self.assertEqual(path.read_bytes(), original)
        # The reverse mismatch cannot turn a workspace receipt into authority.
        receipt = json_read(path)
        receipt.update(continuation.policy(restricted))
        json_write(path, receipt)
        with self.assertRaises(ControlError) as caught:
            continuation.receipts(self.config, self.directory(), self.seed)
        self.assertEqual(caught.exception.code, 'continuation_dispatch_unproven')
        self.assertEqual(self.codex.calls, 1)

    def test_full_access_cannot_borrow_legacy_receipt_without_cwd(self):
        self.codex.after_failure = lambda _: None
        self.assertTrue(self.engine.tick()['halted'])
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))
        self.assertEqual(self.codex.calls, 1)

    def test_full_access_does_not_allow_external_tools_or_pending_background_work(self):
        for kind in ('mcpToolCall', 'collabAgentToolCall', 'unknown'):
            with self.subTest(kind=kind):
                turn = {'itemsView': 'full', 'items': [
                    {'id': 'u', 'type': 'userMessage', 'content': [{'type': 'text', 'text': 'request'}]},
                    {'id': 'external', 'type': kind}]}
                with self.assertRaises(ControlError):
                    continuation.prove_items(turn, 'request', self.config)
        self.codex.background = [{'processId': 'running'}]
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 1)
