"""Synthetic direct Apply proofs; never use a real service, model or user history."""
import base64
from hashlib import sha256
from contextlib import contextmanager
from unittest.mock import Mock, patch

from specroad_control.clarification_authorization import enqueue
from specroad_control.clarification_authorization_contract import PATH, CAPABILITY
from specroad_control.apply_reconcile_proof import canonical
from specroad_control.config import render
from specroad_control.job_contract import new_contract
from specroad_control.local import write_private, private_dir
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.mixed_support import MixedCase


class AuthorizationCase(MixedCase):
    def setUp(self):
        super().setUp()
        self.codex.activity = Mock(return_value='idle')
        private_dir(self.paths.config.parent)
        write_private(self.paths.config, render(self.config).encode())
        offline = patch('specroad_control.commands.configured_offline', self.offline)
        offline.start()
        self.addCleanup(offline.stop)
        installed = patch('specroad_control.clarification_authorization.require_installed')
        installed.start()
        self.addCleanup(installed.stop)

    @contextmanager
    def offline(self, paths, **kwargs):
        assert paths == self.paths
        yield self.config, self.engine

    def manual(self, remaining=2, *, mixed=False, completed=None, mutate_base=None):
        self.ledger().bind_contract(new_contract(remaining, allowed=False))
        self.latest_data = self.data(mixed=mixed)
        first = self.latest_data['stages'][1 if mixed else 0]
        raw = canonical(CAPABILITY)
        first['after'][PATH] = sha256(raw).hexdigest()
        first['payloads'][PATH] = base64.b64encode(raw).decode()
        self.latest_patch = patch_package(self.exchange / 'manual.zip', self.latest_data)
        self.engine.gate.set(False)
        self.engine.tick()
        return self.outcome(completed=completed, mutate_base=mutate_base)

    def authorize(self, **changes):
        values = {'result': self.following['path'], 'source_sha256': self.seed['sha256'],
                  'reason': 'Explicit optional detail clarification for future work'}
        values.update(changes)
        return enqueue(self.paths, **values)
