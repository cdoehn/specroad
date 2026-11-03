"""No permission from changed proof, ambiguous recovery or partial persistence."""
from copy import deepcopy
from pathlib import Path
import sqlite3
from unittest.mock import patch

from specroad_control.clarification_authorization import verify, enqueue
from specroad_control.clarification_authorization import require_installed
from specroad_control.clarification_authorization_history import validate_history, complete, history_hash
from specroad_control.apply_reconcile_proof import canonical, hashed
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from specroad_control.local import json_write, read_private, write_private
from codex_control_tests.authorization_support import AuthorizationCase


class ClarificationAuthorizationRightTests(AuthorizationCase):
    def grant(self):
        self.manual(); self.authorize()
        self.engine.gate.set(True)
        return validate_history(self.ledger())

    def test_atomic_rollback_after_new_job_but_before_contract(self):
        doc = self.grant(); ledger = self.ledger()
        previous = history_hash(ledger)
        with patch.object(ledger, '_insert_contract', side_effect=sqlite3.OperationalError('injected disk fault')):
            with self.assertRaises(ControlError): complete(ledger, doc, doc['artifacts'])
        self.assertEqual(history_hash(ledger), previous)
        self.assertEqual(validate_history(ledger), doc)
        self.assertEqual(ledger.current()['sha'], self.seed['sha256'])
        complete(ledger, doc, doc['artifacts'])
        self.assertEqual(ledger.request_contract(), new_contract(2, version=4))

    def test_pause_arriving_during_final_proof_prevents_adoption(self):
        self.grant()
        def close_gate(*args):
            value = verify(*args)
            self.engine.gate.set(False)
            return value
        with patch('specroad_control.clarification_authorization.verify', side_effect=close_gate):
            self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.assertIsNotNone(validate_history(self.ledger()))
        self.assertEqual(self.codex.calls, 0)

    def test_thread_becoming_active_after_proof_preserves_intent(self):
        self.grant()
        self.codex.activity.side_effect = ['idle', 'active']
        self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.assertEqual(self.codex.calls, 0)

    def test_config_change_blocks_without_rewriting_intent(self):
        doc = self.grant()
        write_private(self.paths.config, read_private(self.paths.config) + b'\n# changed\n')
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(validate_history(self.ledger()), doc)

    def test_attempt_appearing_after_authorization_cannot_be_ignored(self):
        doc = self.grant()
        path = self.paths.state / 'jobs' / self.seed['sha256'] / 'attempt.json'
        json_write(path, {'source_sha256': self.seed['sha256'], 'thread_id': self.thread,
                         'request_contract': new_contract(2, allowed=False)})
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(validate_history(self.ledger()), doc)

    def test_config_change_during_archive_validation_is_detected(self):
        self.manual()
        from specroad_control.clarification_authorization import prove
        def changing(*args):
            value = prove(*args)
            write_private(self.paths.config, read_private(self.paths.config) + b'\n# race\n')
            return value
        with patch('specroad_control.clarification_authorization.prove', side_effect=changing):
            with self.assertRaises(ControlError): self.authorize()
        self.assertIsNone(validate_history(self.ledger()))

    def test_missing_archived_patch_blocks_first_new_turn(self):
        self.grant(); self.engine.tick()
        Path(self.latest_patch['path']).unlink()
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], self.following['sha256'])
        self.assertEqual(self.ledger().current()['stage'], 'ready')
        self.assertEqual(self.codex.calls, 0)

    def test_completed_authorization_does_not_tolerate_changed_old_budget(self):
        self.grant(); self.engine.tick()
        ledger = self.ledger()
        ledger.db.execute('UPDATE clarification_budgets SET remaining=3 WHERE sha=?', (self.seed['sha256'],))
        with self.assertRaises(ControlError): validate_history(ledger)

    def test_completed_authorization_preserves_unknown_output_classification(self):
        self.grant(); self.engine.tick()
        ledger = self.ledger()
        ledger.db.execute("UPDATE request_contracts SET output_kind='patch_ready' WHERE sha=?", (self.seed['sha256'],))
        with self.assertRaises(ControlError): validate_history(ledger)

    def test_corrupt_intent_never_becomes_new_authority(self):
        doc = self.grant(); ledger = self.ledger()
        ledger.db.execute("UPDATE clarification_authorizations SET proof_sha=?", ('0'*64,))
        with self.assertRaises(ControlError): validate_history(ledger)
        self.assertEqual(ledger.current()['sha'], self.seed['sha256'])

    def test_coherently_rehashed_but_invalid_intents_are_rejected(self):
        original = self.grant(); ledger = self.ledger()
        variants = [deepcopy(original) for _ in range(5)]
        variants[0]['version'] = True
        variants[1]['reason'] = 'contains\nnewline'
        variants[2]['evidence']['unknown.json'] = 'a'*64
        variants[3]['selected_contract'] = new_contract(3, version=4)
        variants[4]['artifacts']['result']['success'] = False
        for doc in variants:
            with self.subTest(doc=variants.index(doc)):
                ledger.db.execute('UPDATE clarification_authorizations SET proof=?,proof_sha=?', (canonical(doc).decode(), hashed(doc)))
                with self.assertRaises(ControlError): validate_history(ledger)
        ledger.db.execute('UPDATE clarification_authorizations SET proof=?,proof_sha=?', (canonical(original).decode(), hashed(original)))
        self.assertEqual(validate_history(ledger), original)

    def test_regular_completed_handoff_cannot_be_reclassified_as_operator_grant(self):
        self.manual()
        ledger = self.ledger()
        ledger.db.execute("UPDATE request_contracts SET output_kind='patch_ready'")
        with self.assertRaises(ControlError): self.authorize()
        self.assertIsNone(validate_history(ledger))

    def test_unresolved_attempt_without_its_request_is_rejected(self):
        self.manual(); ledger = self.ledger()
        ledger.db.execute("UPDATE jobs SET stage='uncertain',patch_sha=NULL,error='dev_blocked'")
        ledger.db.execute('UPDATE request_contracts SET output_kind=NULL')
        with self.assertRaises(ControlError): self.authorize()

    def test_unknown_thread_state_cannot_adopt_a_queued_intent(self):
        self.grant()
        self.codex.activity.side_effect = ControlError('apply_reconciliation_thread_unknown', 'unknown')
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])

    def test_fresh_result_which_is_already_claimed_cannot_be_reissued(self):
        self.manual(); self.engine.tick()
        with self.assertRaises(ControlError): self.authorize()
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False))

    def test_source_file_mutation_invalidates_the_pinned_proof(self):
        self.grant()
        path = Path(self.seed['path']); path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.codex.calls, 0)

    def test_offline_recovery_and_thread_handover_guard_pending_authority(self):
        self.grant()
        from specroad_control.apply_reconcile_history import require_no_pending
        with self.assertRaises(ControlError) as caught: require_no_pending(self.ledger())
        self.assertEqual(caught.exception.code, 'clarification_authorization_pending')

    def test_changed_actual_artifact_rolls_back_before_any_job_update(self):
        doc = self.grant(); ledger = self.ledger()
        actual = deepcopy(doc['artifacts']); actual['completion_sha256'] = 'f'*64
        with self.assertRaises(ControlError): complete(ledger, doc, actual)
        self.assertEqual(validate_history(ledger), doc)

    def test_contract4_without_explicit_project_opt_in_is_insufficient(self):
        from specroad_control.clarification_authorization_contract import PATH
        self.manual(mutate_base=lambda files: {name: raw for name, raw in files.items() if name != PATH})
        with self.assertRaises(ControlError): self.authorize()
        self.assertIsNone(validate_history(self.ledger()))

    def test_old_installed_release_cannot_accept_new_authorization_intents(self):
        paths = self.paths
        with patch('specroad_control.releases.active_entrypoint', return_value=Path('/synthetic/release/control')) as active:
            with patch('specroad_control.local.json_read', return_value={'files': {'control': 'a'*64}}):
                with self.assertRaises(ControlError): require_installed(paths)
            active.assert_called_once_with(paths)
        with patch('specroad_control.releases.active_entrypoint', side_effect=ControlError('invalid_release', 'changed')):
            with self.assertRaises(ControlError): require_installed(paths)
