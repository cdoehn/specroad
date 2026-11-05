"""Isolated real ledger and native-container doubles, no operator data or services."""
from unittest.mock import Mock, patch

from specroad_control.apply_reconcile_proof import canonical
from specroad_control.blocked_authorization import CAPABILITY, PATH, enqueue
from specroad_control.job_contract import new_contract
from specroad_control.local import json_write
from codex_control_tests.authorization_support import AuthorizationCase


class BlockedAuthorizationCase(AuthorizationCase):
    def result(self, name, **kwargs):
        if name == 'seed.zip':
            self.files[PATH] = canonical(CAPABILITY)
        return super().result(name, **kwargs)

    def setUp(self):
        super().setUp()
        installed = patch('specroad_control.blocked_authorization.require_release')
        installed.start(); self.addCleanup(installed.stop)
        self.codex.activity = Mock(return_value='idle')

    def blocked(self, remaining=2, *, allowed=False):
        self.ledger().bind_contract(new_contract(remaining, allowed=allowed, version=4))
        original = self.codex.run
        def block(prompt, schema, directory, *, authorize, **kwargs):
            assert authorize()
            answer = {'source_result_sha256': self.seed['sha256'], 'status': 'blocked',
                      'patch_sha256': '', 'message': 'Detail contract needs operator authorization.'}
            json_write(directory / 'protocol-completion.json', {
                'transport': self.config.transport, 'thread_id': self.thread,
                'completed': True, 'answer': answer})
            return answer
        self.codex.run = block
        try:
            self.assertTrue(self.engine.tick()['halted'])
        finally:
            self.codex.run = original
        self.assertEqual(self.ledger().current()['error'], 'dev_blocked')

    def grant(self, **changes):
        values = {'result': self.seed['path'], 'source_sha256': self.seed['sha256'],
                  'reason': 'Explicit operator grant for this blocked source'}
        values.update(changes)
        return enqueue(self.paths, **values)

    def adopted(self):
        self.blocked(); self.grant()
        self.assertTrue(self.engine.tick()['again'])
