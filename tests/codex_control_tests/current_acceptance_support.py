"""Complete synthetic Apply snapshots, isolated SQLite and an idle fake thread."""
import base64
from hashlib import sha256
from unittest.mock import Mock, patch

from specroad_control.apply_reconcile_proof import canonical, hashed, public_plan
from specroad_control.apply_snapshot import snapshot
from specroad_control.current_acceptance import enqueue
from specroad_control.current_acceptance_proof import PATH, CAPABILITY
from specroad_control.job_contract import new_contract
from specroad_control.local import json_write
from codex_control_tests.authorization_support import AuthorizationCase
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.blocked_chain_support import stage, log_for
from codex_control_tests.mixed_support import postimage


class AcceptanceCase(AuthorizationCase):
    def setUp(self):
        super().setUp()
        installed = patch('specroad_control.current_acceptance.require_release')
        installed.start(); self.addCleanup(installed.stop)
        self.engine.core.current = Mock(return_value=None)

    def manual(self, remaining=2, *, mixed=False, completed=None, mutate_base=None,
               mutate_log=None, capability=CAPABILITY, reset_capability=None):
        self.ledger().bind_contract(new_contract(remaining, allowed=False, version=4))
        self.latest_data = self.data(mixed=mixed)
        first = self.latest_data['stages'][1 if mixed else 0]
        raw = canonical(capability)
        first['after'][PATH] = sha256(raw).hexdigest()
        first['payloads'][PATH] = base64.b64encode(raw).decode()
        if reset_capability is not None:
            from specroad_control.current_acceptance_proof import RESET_PATH
            raw = canonical(reset_capability)
            first['after'][RESET_PATH] = sha256(raw).hexdigest()
            first['payloads'][RESET_PATH] = base64.b64encode(raw).decode()
        self.latest_patch = patch_package(self.exchange / 'manual.zip', self.latest_data)
        self.engine.gate.set(False)
        self.engine.tick()
        return self.outcome(completed=completed, mutate_base=mutate_base, mutate_log=mutate_log)

    def accept_current(self, **changes):
        values = {'result': self.following['path'], 'clarification': True,
                  'reason': 'Accept the verified tested state after manual work'}
        values.update(changes)
        return enqueue(self.paths, **values)

    def adopt(self, **changes):
        self.accept_current(**changes)
        self.engine.gate.set(True)
        self.assertTrue(self.engine.tick()['again'])
        _, files = snapshot(self.following)
        self.files = {name: raw for name, (mode, raw) in files.items()}

    def external_correction(self):
        """Finish the failed R/C without advancing the old automation ledger."""
        parent, original = self.following, self.latest_data
        _, work = snapshot(parent)
        files = {name: raw for name, (mode, raw) in work.items()}
        right = stage('feature.R', files, {'src/example.py': b'value = 12\n'}) | {'role': 'implementation'}
        final = postimage(files, [right])
        clean = stage('feature.C', final, {'src/example.py': b'value = (12)\n'}) | {'role': 'implementation'}
        data = {**original, 'source_result_sha256': parent['sha256'], 'binding': parent['binding'],
            'bundle_number': '556', 'initial_dirty': True, 'handoff_kind': 'patch_ready',
            'correction_of': {'plan_sha256': hashed(public_plan(original)),
                              'remaining_commit_ids': ['feature.R', 'feature.C']},
            'stages': [right, clean]}
        package = patch_package(self.exchange / 'correction.zip', data)
        self.following = self.result('corrected.zip', previous=parent, patch_sha=package['sha256'],
            base=postimage(files, data['stages']), log=log_for(data, ['d'*40, 'e'*40]),
            binding={**self.binding, 'base_commit': 'e'*40}, completed_commit='e'*40,
            captured_at='2026-01-01T02:00:00Z')
        self.latest_data, self.latest_patch = data, package
        return parent

    def block_current(self):
        """A real Engine boundary with a synthetic terminal blocked response."""
        source = self.ledger().current()['source']
        original = self.codex.run
        def block(prompt, schema, directory, *, authorize, **kwargs):
            assert authorize()
            answer = {'source_result_sha256': source['sha256'], 'status': 'blocked',
                      'patch_sha256': '', 'message': 'Optional detail decision requires authorization'}
            json_write(directory / 'protocol-completion.json', {'completed': True,
                'thread_id': self.thread, 'transport': self.config.transport, 'answer': answer})
            return answer
        self.codex.run = block
        self.engine.gate.set(True)
        try:
            self.assertTrue(self.engine.tick()['halted'])
        finally:
            self.codex.run = original
