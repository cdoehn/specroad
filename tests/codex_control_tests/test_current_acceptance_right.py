"""Race, budget, lifecycle and native live-state boundaries for explicit adoption."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from specroad_control.apply_reconcile_proof import canonical, hashed
from specroad_control.current_acceptance_history import validate_history
from specroad_control.current_acceptance_proof import CAPABILITY
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from specroad_control.local import json_write
from codex_control_tests.current_acceptance_support import AcceptanceCase
from codex_control_tests.apply_reconcile_support import patch_package


class CurrentAcceptanceRightTests(AcceptanceCase):
    def test_known_mixed_handoff_consumes_unrecorded_slot_exactly_once(self):
        self.manual(2, mixed=True)
        self.ledger().db.execute("UPDATE request_contracts SET allowed=1,output_kind='patch_ready_with_clarification'")
        self.adopt()
        self.assertEqual(self.ledger().request_contract(), new_contract(1, version=4))
        self.accept_current()
        self.assertEqual(self.ledger().request_contract(), new_contract(1, version=4))
        self.assertEqual(self.ledger().request_contract(self.seed['sha256']), new_contract(2, version=4))

    def test_last_already_published_slot_cannot_be_granted_again(self):
        self.manual(1, mixed=True)
        self.ledger().db.execute("UPDATE request_contracts SET allowed=1,output_kind='patch_ready_with_clarification'")
        with self.assertRaises(ControlError): self.accept_current()
        self.adopt(clarification=False)
        self.assertEqual(self.ledger().request_contract(), new_contract(0, allowed=False, version=4))

    def test_changed_base_budget_is_not_hidden_by_effective_receipt(self):
        self.manual(); self.adopt()
        self.ledger().db.execute('UPDATE clarification_budgets SET remaining=3 WHERE sha=?', (self.following['sha256'],))
        with self.assertRaises(ControlError): self.ledger()

    def test_changed_original_output_classification_invalidates_pending_intent(self):
        self.manual(); self.accept_current()
        ledger = self.ledger()
        ledger.db.execute("UPDATE request_contracts SET output_kind='patch_ready' WHERE sha=?", (self.seed['sha256'],))
        with self.assertRaises(ControlError): self.engine.tick()

    def test_coherent_receipt_cannot_upgrade_the_selected_budget(self):
        self.manual(); self.accept_current()
        ledger = self.ledger(); doc = validate_history(ledger)
        doc['selected_contract']['clarifications_remaining'] = 3
        ledger.db.execute('UPDATE current_acceptances SET proof=?,proof_sha=?', (canonical(doc).decode(), hashed(doc)))
        with self.assertRaises(ControlError): self.ledger()

    def test_same_ready_late_original_attempt_prevents_adoption(self):
        self.manual(); self.engine.tick(); self.accept_current()
        json_write(self.paths.state / 'jobs' / self.following['sha256'] / 'attempt.json', {'late': True})
        self.engine.gate.set(True)
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertIsNotNone(validate_history(self.ledger()))

    def test_same_ready_late_attempt_is_rechecked_inside_commit_gate(self):
        self.manual(); self.engine.tick(); self.accept_current()
        gate = self.engine.gate.enter
        def late(commit):
            json_write(self.paths.state / 'jobs' / self.following['sha256'] / 'attempt.json', {'late': True})
            return gate(commit)
        self.engine.gate.enter = late; self.engine.gate.set(True)
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertIsNotNone(validate_history(self.ledger()))

    def test_configuration_race_during_native_capture_cannot_queue(self):
        self.manual()
        def change(source):
            self.paths.config.write_text(self.paths.config.read_text() + '\n# concurrent edit\n')
        self.engine.core.current.side_effect = change
        with self.assertRaises(ControlError): self.accept_current()
        self.assertIsNone(validate_history(self.ledger()))

    def test_followup_arriving_during_native_capture_prevents_adoption(self):
        self.manual(); self.accept_current()
        def arrive(source):
            patch_package(self.exchange / 'late.zip', self.data(self.following))
        self.engine.core.current.side_effect = arrive
        self.engine.gate.set(True)
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])

    def test_known_later_result_also_vetoes_old_selection(self):
        self.manual()
        later = self.result('later.zip', captured_at='2026-01-01T02:00:00Z')
        ledger = self.ledger()
        ledger.db.execute("INSERT INTO jobs VALUES(?,?,?,'done',NULL,NULL,0)",
            (later['run_id'], later['sha256'], canonical(later).decode()))
        with self.assertRaises(ControlError): self.accept_current()

    def test_duplicate_physical_copy_of_identical_result_is_idempotent(self):
        self.manual(); self.accept_current()
        copy = self.exchange / 'same-result.zip'; copy.write_bytes(Path(self.following['path']).read_bytes())
        self.assertTrue(self.accept_current(result=str(copy))['queued'])

    def test_old_recovery_files_are_not_required_after_explicit_current_acceptance(self):
        self.manual(); self.engine.tick()
        # The selected native final Apply stays intact. Historical verifier is
        # deliberately unavailable; an explicit new current receipt supersedes it.
        self.adopt()
        with patch('specroad_control.apply_reconcile.verify_completed', side_effect=AssertionError('old chain')):
            self.assertFalse(self.dispatch()['halted'])

    def test_completed_blocker_evidence_remains_pinned_after_adoption(self):
        self.manual(); self.engine.tick(); self.block_current(); self.adopt()
        old = self.paths.state / 'jobs' / self.following['sha256'] / 'completion.json'
        doc = json.loads(old.read_bytes()); doc['message'] = 'changed terminal response'
        json_write(old, doc)
        result = self.dispatch(mixed=True)
        self.assertTrue(result['halted'])
        self.assertEqual(self.codex.calls, 0)

    def test_archived_same_source_keeps_its_original_request_path(self):
        self.manual(); self.engine.tick(); self.block_current()
        moved = self.exchange / 'archived-current.zip'
        Path(self.following['path']).rename(moved)
        self.accept_current(result=str(moved))
        self.assertTrue(self.engine.tick()['again'])
        self.assertEqual(self.ledger().request_contract(), new_contract(2, version=4))

    def test_active_thread_after_adoption_waits_without_attempt(self):
        self.manual(); self.adopt()
        self.codex.activity.return_value = 'active'
        self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.codex.calls, 0)
        self.assertFalse(self.ledger().attempt_origin(self.paths, self.following['sha256']).exists())

    def test_transaction_abort_preserves_both_old_job_and_pending_receipt(self):
        self.manual(); self.accept_current()
        ledger = self.ledger(); old = ledger.current()
        ledger.db.execute("CREATE TRIGGER reject_adoption BEFORE INSERT ON jobs BEGIN SELECT RAISE(ABORT,'synthetic interruption'); END")
        # A trigger is a history change. Refresh only that fixture's pinned hash
        # to reach the transactional insertion boundary, not an earlier guard.
        from specroad_control.current_acceptance_history import history_hash
        row = ledger.db.execute('SELECT * FROM current_acceptances').fetchone()
        doc = json.loads(row['proof']); doc['history_sha256'] = history_hash(ledger)
        ledger.db.execute('UPDATE current_acceptances SET proof=?,proof_sha=?', (canonical(doc).decode(), hashed(doc)))
        self.engine.gate.set(True)
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.ledger().current(), old)
        self.assertIsNotNone(validate_history(self.ledger()))

    def test_pending_acceptance_blocks_other_offline_transitions(self):
        self.manual(); self.accept_current()
        from specroad_control.apply_reconcile_history import require_no_pending as recovery
        from specroad_control.clarification_authorization_history import require_no_pending as authorization
        from specroad_control.blocked_authorization import enqueue as blocked
        for call in (lambda: recovery(self.ledger()), lambda: authorization(self.ledger()),
                     lambda: blocked(self.paths, self.following['path'], source_sha256=self.following['sha256'], reason='other')):
            with patch('specroad_control.blocked_authorization.require_release'), self.assertRaises(ControlError): call()

    def test_old_blocked_grant_cannot_stack_with_current_acceptance(self):
        self.manual(); self.adopt(clarification=False); self.block_current()
        from specroad_control.blocked_authorization import enqueue
        with patch('specroad_control.blocked_authorization.require_release'), self.assertRaises(ControlError):
            enqueue(self.paths, self.following['path'], source_sha256=self.following['sha256'], reason='second grant')

    def test_structurally_incomplete_success_log_is_rejected(self):
        def no_gate(raw):
            lines = raw.decode().splitlines()
            progress = json.loads(lines[-1].split(' ', 1)[1])
            del progress['committed'][-1]['gate']
            return lines[0].encode() + b'\nSPECROAD_APPLY_PROGRESS ' + canonical(progress) + b'\n'
        self.manual(mutate_log=no_gate)
        with self.assertRaises(ControlError): self.accept_current()

    def test_marker_boolean_is_not_an_integer_capability(self):
        self.manual(capability={**CAPABILITY, 'format_version': True})
        with self.assertRaises(ControlError): self.accept_current()

    def test_unknown_marker_field_cannot_grant_a_force_mode(self):
        self.manual(capability={**CAPABILITY, 'force': True})
        with self.assertRaises(ControlError): self.accept_current()

    def test_missing_final_bundle_cannot_be_replaced_by_a_git_commit(self):
        self.manual(); Path(self.latest_patch['path']).unlink()
        with self.assertRaises(ControlError): self.accept_current()

    def test_current_state_probe_runs_again_immediately_before_dispatch(self):
        self.manual(); self.adopt()
        self.engine.core.current.side_effect = ControlError('core_rejected', 'Live native lock is now held')
        self.assertTrue(self.dispatch()['halted'])
        self.assertEqual(self.codex.calls, 0)


@pytest.mark.parametrize('change', [dict(dirty=True), dict(sha256='2'*64),
    dict(repository_path='/different/repo'), dict(binding={'repo_id': '33333333-3333-4333-8333-333333333333',
        'base_commit': 'a'*40, 'state_fingerprint': 'b'*16, 'fingerprint_algorithm': 'patchharbor-state-v1'})])
def test_native_current_state_requires_all_four_values_path_sha_and_cleanliness(change):
    from specroad_control.core import Core
    source = {'sha256': '1'*64, 'path': '/exchange/result.zip', 'repository_path': '/apply',
        'binding': {'repo_id': '11111111-1111-4111-8111-111111111111', 'base_commit': 'a'*40,
                    'state_fingerprint': 'b'*16, 'fingerprint_algorithm': 'patchharbor-state-v1'}}
    core = Core(Mock())
    core.call = Mock(return_value={**source, 'kind': 'current', 'dirty': False, **change})
    with pytest.raises(ControlError): core.current(source)


def test_native_bridge_uses_registered_nonmutating_capture_and_never_apply():
    from specroad_control import ph_bridge
    api = Mock()
    context = SimpleNamespace(repo_id='11111111-1111-4111-8111-111111111111', base_commit='a'*40,
        state_fingerprint='b'*16, fingerprint_algorithm='patchharbor-state-v1', repository_path='/apply', dirty=False)
    captured = SimpleNamespace(sha256='1'*64, facts=SimpleNamespace(context=context))
    modules = {name: ModuleType(name) for name in ('patchharbor', 'patchharbor.result_reader',
        'patchharbor.repository_state', 'patchharbor.errors')}
    modules['patchharbor'].api = api
    modules['patchharbor.result_reader'].capture_result_reference = Mock(return_value=captured)
    capture = modules['patchharbor.repository_state'].capture_repository_context = Mock(return_value=context)
    modules['patchharbor.errors'].PatchHarborError = RuntimeError
    modules['patchharbor.errors'].FailureReason = SimpleNamespace(REPOSITORY_BUSY=object())
    stream = io.StringIO()
    with patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['bridge', 'current', '/exchange/result.zip']), redirect_stdout(stream):
        assert ph_bridge.main() == 0
    capture.assert_called_once_with(Path('/apply'), read_only=True)
    assert json.loads(stream.getvalue())['data']['binding']['base_commit'] == 'a'*40
    api.apply.assert_not_called()
