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


class CurrentCore(ReconcileCore):
    def __init__(self):
        self.error = None
        self.override = {}

    def call(self, operation, path):
        assert operation == 'current'
        if self.error:
            raise ControlError(self.error, 'Isolated current-state refusal.')
        source = self.result(path)
        return {'kind': 'current', **{k: source[k] for k in
            ('sha256', 'binding', 'repository_path', 'dirty')}, **self.override}


class RebaseCase(MixedCase):
    def result(self, name, *, base=None, work=None, **kwargs):
        if base is None:
            self.files[CAPABILITY_PATH] = canonical(CAPABILITY)
        return super().result(name, base=base, work=work, **kwargs)

    def setUp(self):
        super().setUp()
        self.core = CurrentCore()
        self.engine.core = self.core
        self.engine.exchange.core = self.core

    def refusal(self, *, busy=False, name='refused.zip', previous=None, **changes):
        source = previous or self.ledger().current()['source']
        _, work = snapshot(source)
        files = {name: raw for name, (mode, raw) in work.items()}
        binding = dict(source['binding'])
        if not busy:
            binding['base_commit'] = 'f' * 40 if binding['base_commit'] != 'f' * 40 else 'e' * 40
            files['src/other.py'] = b'preserved = True\n'
        kwargs = {'previous': source, 'patch_sha': self.latest_patch['sha256'],
                  'base': files, 'work': files, 'binding': binding, 'success': False,
                  'primary_kind': 'repository_busy' if busy else 'state_mismatch',
                  'entrypoint_started': False, 'completed_commit': None,
                  'captured_at': '2026-01-02T00:00:00Z'}
        kwargs.update(changes)
        result = self.result(name, **kwargs)
        self.engine.gate.set(False)
        return result

    def rebase(self, result):
        data = deepcopy(self.latest_data)
        previous, progress = original(self.engine, result)
        data.update(binding=result['binding'], source_result_sha256=result['sha256'],
                    initial_dirty=result['dirty'], bundle_number='556',
                    correction_of={'plan_sha256': hashed(previous),
                                   'remaining_commit_ids': progress['remaining_commit_ids']})
        _, files = snapshot(result)
        for stage in data['stages']:
            stage['before'] = {name: sha256(files[name][1]).hexdigest()
                               for name in stage['after'] if name in files}
            files.update({name: ('100644', base64.b64decode(raw))
                          for name, raw in stage['payloads'].items()})
        return data


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
