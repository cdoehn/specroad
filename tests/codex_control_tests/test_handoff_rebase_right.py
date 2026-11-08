"""No invented progress, new authority, discarded scopes or guessed successors."""
import base64
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad_control.apply_reconcile_proof import public_plan, hashed
from specroad_control.automation import Engine, Gate
from specroad_control.errors import ControlError
from specroad_control.handoff_rebase import CAPABILITY_PATH, rejection, require_remaining_scope
from specroad_control.job_contract import new_contract
from specroad_control.mixed_evidence import verify_handoff, verify_followup
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.handoff_rebase_support import RebaseCase


class HandoffRebaseGuardTests(RebaseCase):
    def test_two_meaningful_rejections_remain_ambiguous(self):
        self.dispatch(); self.refusal(name='first.zip'); self.refusal(name='second.zip')
        with self.assertRaises(ControlError) as error:
            self.engine.tick()
        self.assertEqual(error.exception.code, 'ambiguous_result')
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.assertEqual(self.codex.calls, 1)

    def test_later_unrelated_result_prevents_automatic_adoption(self):
        self.dispatch(); self.refusal()
        self.result('unrelated.zip', captured_at='2026-01-03T00:00:00Z')
        with self.assertRaises(ControlError) as error:
            self.engine.tick()
        self.assertEqual(error.exception.code, 'source_superseded')
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])

    def test_no_grant_from_missing_project_opt_in(self):
        self.dispatch()
        files = {n: raw for n, raw in self.files.items() if n != CAPABILITY_PATH}
        self.refusal(base=files, work=files)
        with self.assertRaises(ControlError):
            self.engine.tick()
        self.assertEqual(self.codex.calls, 1)

    def test_snapshot_with_false_dirty_flag_is_rejected(self):
        self.dispatch(); self.refusal(dirty=True)
        with self.assertRaises(ControlError):
            self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])

    def test_failed_behavior_gate_still_uses_original_progress_path(self):
        self.dispatch(True); result = self.outcome(completed=1)
        self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], result['sha256'])
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False, version=4))
        self.assertFalse(self.dispatch(data=self.correction())['halted'])
        self.assertEqual([s['commit_id'] for s in self.latest_data['stages']], ['feature.W', 'feature.R', 'feature.C'])

    def test_consumed_rejection_is_not_claimed_again_on_idle_tick(self):
        self.dispatch(); refused = self.refusal(); self.engine.tick()
        self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.ledger().current()['sha'], refused['sha256'])

    def test_preserved_dirty_snapshot_cannot_be_silently_omitted(self):
        self.dispatch()
        work = {**self.files, 'src/foreign.py': b'preserve = 7\n'}
        refused = self.refusal(base=self.files, work=work, dirty=True)
        self.engine.tick()
        data = self.rebase(refused)
        fact = patch_package(self.exchange/'drops-dirty.zip', data)
        with self.assertRaises(ControlError) as error:
            verify_handoff(self.engine, refused, fact, self.ledger().request_contract(), 'patch_ready')
        self.assertEqual(error.exception.code, 'mixed_handoff_unproven')

    def test_native_unavailable_is_not_misreported_as_busy(self):
        self.dispatch(); self.refusal(); self.core.error = 'core_unavailable'
        with self.assertRaises(ControlError) as error:
            self.engine.tick()
        self.assertEqual(error.exception.code, 'core_unavailable')
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])

    def test_lock_race_at_dispatch_defers_without_a_model_turn(self):
        self.dispatch(); refused = self.refusal(); self.engine.tick()
        data = self.rebase(refused)
        original_call = self.core.call
        count = 0
        def race(operation, path):
            nonlocal count
            count += 1
            if count == 2:
                raise ControlError('repository_busy', 'New lock at final dispatch.')
            return original_call(operation, path)
        with patch.object(self.core, 'call', side_effect=race):
            answer = self.dispatch(data=data)
        self.assertEqual(answer, {'halted': False, 'again': False, 'retry_after': 30})
        self.assertEqual(self.ledger().current()['stage'], 'ready')
        self.assertEqual(self.codex.calls, 1)

    def test_unchanged_busy_snapshot_cannot_hide_other_bytes(self):
        self.dispatch()
        files = {**self.files, 'src/extra.py': b'extra = True\n'}
        self.refusal(busy=True, base=files, work=files)
        with self.assertRaises(ControlError):
            self.engine.tick()

    def test_wrong_patch_hash_does_not_advance_the_pending_handoff(self):
        self.dispatch(); self.refusal(patch_sha='9'*64)
        self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.assertEqual(self.codex.calls, 1)

    def test_native_busy_protocol_is_preserved_by_the_core_bridge_client(self):
        from subprocess import CompletedProcess
        from specroad_control.core import Core
        response = CompletedProcess([], 1, stdout=b'{"ok":false,"error":"repository_busy"}', stderr=b'')
        with patch('specroad_control.core.subprocess.run', return_value=response):
            with self.assertRaises(ControlError) as error:
                Core(self.config).call('current', Path(self.seed['path']))
        self.assertEqual(error.exception.code, 'repository_busy')

    def test_missing_original_archive_cannot_grant_a_rebase(self):
        self.dispatch(); self.refusal()
        Path(self.latest_patch['path']).unlink()
        with self.assertRaises(ControlError):
            self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])


@pytest.mark.parametrize('changed', [
    {'dry_run': True}, {'success': True}, {'entrypoint_started': True},
    {'completed_commit': 'a'*40}, {'operation': 'bundle'},
    {'primary_kind': 'validation_error'}, {'primary_kind': 'execution_error'},
    {'captured_at': '2026-01-01T00:00:00Z'}, {'captured_at': None},
    {'repository_path': '/another/apply'}, {'patch_sha256': '1'*64},
])
def test_rejection_proof_refuses_unproven_native_outcomes(changed):
    case = RebaseCase('runTest'); case.setUp()
    try:
        case.dispatch(); refused = case.refusal()
        value = {**refused, **changed}
        with pytest.raises((ControlError, ValueError)):
            rejection(case.engine, case.seed, case.latest_patch, value)
        assert case.ledger().current()['sha'] == case.seed['sha256']
        assert case.codex.calls == 1
    finally:
        case.doCleanups()


@pytest.mark.parametrize('change', ['id', 'role', 'message', 'path', 'test_file', 'test_id', 'stage'])
def test_rebase_retains_complete_scope_and_required_tests(change):
    old = {'commit_id': 'feature.R', 'role': 'implementation', 'message': 'Complete feature',
           'after': {'src/example.py': 'a'*64},
           'test_plan': {'test_files': ['tests/test_example.py'], 'test_ids': ['exact-regression']}}
    new = deepcopy(old)
    if change == 'id': new['commit_id'] = 'different.R'
    elif change == 'role': new['role'] = 'correction'
    elif change == 'message': new['message'] = 'Other scope'
    elif change == 'path': new['after'] = {}
    elif change == 'test_file': new['test_plan']['test_files'] = []
    elif change == 'test_id': new['test_plan']['test_ids'] = []
    with pytest.raises(ControlError):
        require_remaining_scope([old], [] if change == 'stage' else [new])
