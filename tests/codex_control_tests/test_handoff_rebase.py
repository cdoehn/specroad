"""Bound native rejection successors; isolated protocol/file-map evidence only."""
import base64
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from specroad_control.apply_reconcile_proof import canonical, hashed, public_plan
from specroad_control.apply_snapshot import snapshot
from specroad_control.automation import Engine, Gate
from specroad_control.errors import ControlError
from specroad_control.handoff_rebase import CAPABILITY, CAPABILITY_PATH, original, rejection
from specroad_control.job_contract import new_contract
from specroad_control.mixed_contract import MIXED
from specroad_control.mixed_evidence import verify_handoff
from codex_control_tests.apply_reconcile_support import ReconcileCore, patch_package
from codex_control_tests.mixed_support import MixedCase


from codex_control_tests.handoff_rebase_support import RebaseCase

class HandoffRebaseTests(RebaseCase):
    def test_rejected_regular_handoff_requests_one_new_bound_complete_remainder(self):
        self.dispatch(); refused = self.refusal()
        self.assertFalse(self.engine.tick()['halted'])
        self.assertEqual(self.ledger().current()['sha'], refused['sha256'])
        self.assertEqual(self.ledger().request_contract(), new_contract(3, allowed=False, version=4))
        data = self.rebase(refused)
        self.assertFalse(self.dispatch(data=data)['halted'])
        self.assertEqual(self.codex.calls, 2)
        self.assertEqual([s['commit_id'] for s in self.latest_data['stages']], ['feature.W', 'feature.R', 'feature.C'])
        self.assertEqual(self.ledger().current()['patch_sha'], self.latest_patch['sha256'])
        self.assertTrue(Path(refused['path']).is_file())

    def test_rejected_mixed_handoff_keeps_prefix_and_spends_no_second_slot(self):
        self.dispatch(True); original_patch = self.latest_patch
        first = self.refusal(); self.engine.tick()
        expected = new_contract(2, allowed=False, version=4, continuation=True)
        self.assertEqual(self.ledger().request_contract(), expected)
        self.assertFalse(self.dispatch(True, self.rebase(first))['halted'])
        second = self.refusal(name='refused-again.zip', captured_at='2026-01-03T00:00:00Z')
        self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), expected)
        self.assertEqual(self.codex.calls, 2)
        self.assertEqual(self.ledger().current()['sha'], second['sha256'])
        self.assertTrue(Path(original_patch['path']).is_file())

    def test_busy_unchanged_waits_without_new_job_patch_or_budget_change(self):
        self.dispatch(True); source = self.seed; refused = self.refusal(busy=True)
        for _ in range(2):
            self.assertEqual(self.engine.tick(), {'halted': False, 'again': False})
        self.assertEqual(self.ledger().current()['sha'], source['sha256'])
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))
        self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.engine.summary()['apply_wait_reason'], 'repository_busy')
        self.assertTrue(Path(refused['path']).is_file())

    def test_busy_observation_does_not_conflict_with_later_real_completion(self):
        self.dispatch(); self.refusal(busy=True, captured_at='2026-01-01T00:30:00Z')
        completed = self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], completed['sha256'])
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))
        self.assertEqual(self.codex.calls, 1)

    def test_current_apply_lock_keeps_rejection_waiting_without_replay(self):
        self.dispatch(); self.refusal(); self.core.error = 'repository_busy'
        self.assertEqual(self.engine.tick(), {'halted': False, 'again': False, 'retry_after': 30})
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.assertEqual(self.codex.calls, 1)
        self.core.error = None
        self.assertFalse(self.engine.tick()['halted'])

    def test_rejected_prefix_cannot_turn_into_new_clarification(self):
        self.dispatch(True); refused = self.refusal(); self.engine.tick()
        data = self.rebase(refused); prefix = data['stages'][0]
        name = next(iter(prefix['after'])); raw = b'Unapproved replacement decision\n'
        prefix['after'][name] = sha256(raw).hexdigest()
        prefix['payloads'][name] = base64.b64encode(raw).decode()
        fact = patch_package(self.exchange/'wrong-prefix.zip', data)
        with self.assertRaises((ControlError, ValueError)):
            verify_handoff(self.engine, refused, fact, self.ledger().request_contract(), MIXED)

    def test_live_state_change_blocks_dispatch_without_mutating_history(self):
        self.dispatch(); refused = self.refusal()
        self.core.override = {'binding': {**refused['binding'], 'base_commit': '9'*40}}
        with self.assertRaises(ControlError) as error:
            self.engine.tick()
        self.assertEqual(error.exception.code, 'current_repository_mismatch')
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.assertEqual(self.codex.calls, 1)

    def test_restart_retains_new_result_and_original_handoff(self):
        self.dispatch(True); refused = self.refusal(); self.engine.tick()
        expected = self.ledger().request_contract()
        self.engine.close()
        gate = Gate(); gate.set(False)
        self.engine = Engine(self.config,self.paths,gate,core=self.core,codex=self.codex)
        self.addCleanup(self.engine.close)
        self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['sha'], refused['sha256'])
        self.assertEqual(self.ledger().request_contract(), expected)
        self.assertEqual(self.codex.calls, 1)
