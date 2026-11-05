"""Negative proofs, interrupted adoption and races keep original authority intact."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from specroad_control.apply_reconcile_proof import canonical, hashed
from specroad_control.blocked_authorization import verify, require_release
from specroad_control.blocked_authorization_history import complete, validate_history, history_hash
from specroad_control.config import render
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from specroad_control.local import json_read, json_write, read_private, write_private
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.blocked_authorization_support import BlockedAuthorizationCase


class BlockedClarificationRightTests(BlockedAuthorizationCase):
    def pending(self):
        self.blocked(); self.grant()
        return validate_history(self.ledger())

    def test_config_changed_after_intent_is_preserved_and_blocked(self):
        doc = self.pending()
        write_private(self.paths.config, read_private(self.paths.config) + b'\n# changed\n')
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(validate_history(self.ledger()), doc)
        self.assertEqual(self.codex.calls, 0)

    def test_changed_completion_after_adoption_blocks_dispatch(self):
        self.adopted()
        root = self.paths.state / 'jobs' / self.seed['sha256']
        answer = json_read(root / 'completion.json'); answer['message'] += ' changed'
        json_write(root / 'completion.json', answer)
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 0)
        self.assertEqual(self.ledger().current()['stage'], 'ready')

    def test_atomic_failure_after_lifecycle_update_rolls_back_everything(self):
        doc = self.pending(); ledger = self.ledger(); old = ledger.current()
        before = history_hash(ledger)
        with patch('specroad_control.blocked_authorization_history.validate_history',
                   side_effect=[doc, ControlError('injected_fault', 'after update')]):
            with self.assertRaises(ControlError): complete(ledger, doc)
        self.assertEqual(ledger.current(), old)
        self.assertEqual(history_hash(ledger), before)
        self.assertEqual(validate_history(ledger), doc)
        complete(ledger, doc)
        self.assertEqual(ledger.request_contract(), new_contract(2, version=4))

    def test_pause_arriving_during_final_proof_prevents_adoption(self):
        doc = self.pending()
        def closing(*args, **kwargs):
            verify(*args, **kwargs)
            self.engine.gate.set(False)
        with patch('specroad_control.blocked_authorization.verify', side_effect=closing):
            self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(validate_history(self.ledger()), doc)

    def test_thread_becomes_active_between_observations(self):
        doc = self.pending()
        self.codex.activity.side_effect = ['idle', 'active']
        self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(validate_history(self.ledger()), doc)

    def test_active_thread_after_adoption_waits_without_a_new_attempt(self):
        self.adopted(); self.codex.activity.return_value = 'active'
        answer = self.engine.tick()
        self.assertFalse(answer['halted']); self.assertFalse(answer['again'])
        self.assertEqual(self.codex.calls, 0)
        self.assertFalse((self.paths.state / 'jobs' / self.seed['sha256'] / 'authorized').exists())

    def test_late_output_in_codex_preflight_prevents_dispatch(self):
        self.adopted(); original = self.codex.run
        def late(*args, **kwargs):
            patch_package(self.exchange / 'late.zip', self.data())
            return original(*args, **kwargs)
        self.codex.run = late
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls, 0)

    def test_later_unclaimed_result_prevents_adoption(self):
        self.pending()
        self.result('unclaimed.zip', captured_at='2026-01-02T00:00:00Z')
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.ledger().current()['stage'], 'uncertain')

    def test_archive_move_keeps_hash_identity_and_original_request_bytes(self):
        self.pending()
        original = Path(self.seed['path'])
        archived = original.with_name('moved-source.zip'); original.rename(archived)
        self.assertTrue(self.grant(result=str(archived))['queued'])
        self.assertTrue(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])

    def test_missing_or_changed_original_files_do_not_queue(self):
        self.blocked(); root = self.paths.state / 'jobs' / self.seed['sha256']
        for name in ('attempt.json', 'protocol-completion.json', 'completion.json'):
            p = root / name; old = read_private(p); p.unlink()
            with self.subTest(name=name), self.assertRaises(ControlError): self.grant()
            write_private(p, old)
        self.assertIsNone(validate_history(self.ledger()))

    def test_mismatched_answer_or_source_never_authorizes(self):
        self.blocked(); root = self.paths.state / 'jobs' / self.seed['sha256']
        p = root / 'completion.json'; original = read_private(p)
        for key, value in [('status', 'no_work'), ('patch_sha256', 'f' * 64),
                           ('source_result_sha256', 'a' * 64), ('message', 1)]:
            answer = json_read(p); answer[key] = value; json_write(p, answer)
            with self.subTest(key=key), self.assertRaises(ControlError): self.grant()
            write_private(p, original)

    def test_rehashed_invalid_grants_do_not_create_authority(self):
        original = self.pending(); ledger = self.ledger()
        variants = [deepcopy(original) for _ in range(5)]
        variants[0]['version'] = True
        variants[1]['selected_contract'] = new_contract(3, version=4)
        variants[2]['original_job']['error'] = 'codex_turn_failed'
        variants[3]['attempt_number'] = True
        variants[4]['evidence']['completion.json'] = None
        for doc in variants:
            ledger.db.execute('UPDATE blocked_clarification_authorizations SET proof=?,proof_sha=?',
                              (canonical(doc).decode(), hashed(doc)))
            with self.subTest(doc=variants.index(doc)), self.assertRaises(ControlError): validate_history(ledger)
        ledger.db.execute('UPDATE blocked_clarification_authorizations SET proof=?,proof_sha=?',
                          (canonical(original).decode(), hashed(original)))
        self.assertEqual(validate_history(ledger), original)

    def test_base_budget_change_after_adoption_is_not_accepted(self):
        self.adopted(); ledger = self.ledger()
        ledger.db.execute('UPDATE clarification_budgets SET remaining=3')
        with self.assertRaises(ControlError): validate_history(ledger)

    def test_other_offline_operations_respect_pending_grant(self):
        self.pending()
        from specroad_control.apply_reconcile_history import require_no_pending
        with self.assertRaises(ControlError) as caught: require_no_pending(self.ledger())
        self.assertEqual(caught.exception.code, 'clarification_authorization_pending')

    def test_proxy_original_turn_and_prompt_are_both_required(self):
        self.config = replace(self.config, transport='app-server-proxy')
        self.engine.config = self.config
        write_private(self.paths.config, render(self.config).encode())
        self.blocked()
        p = self.paths.state / 'jobs' / self.seed['sha256'] / 'dispatch.json'
        old = read_private(p)
        for key, value in [('turn_id', 'different-turn'), ('prompt_sha256', '0' * 64)]:
            dispatch = json_read(p); dispatch[key] = value; json_write(p, dispatch)
            with self.subTest(key=key), self.assertRaises(ControlError): self.grant()
            write_private(p, old)
        self.assertTrue(self.grant()['queued'])
        self.assertTrue(self.engine.tick()['again'])

    def test_second_blocked_answer_is_not_replayed_by_repeating_grant(self):
        self.adopted()
        def again(prompt, schema, directory, *, authorize, **kwargs):
            assert authorize()
            return {'source_result_sha256': self.seed['sha256'], 'status': 'blocked',
                    'patch_sha256': '', 'message': 'External fact still unavailable.'}
        self.codex.run = again
        self.assertTrue(self.engine.tick()['halted'])
        old = self.ledger().current()
        self.assertTrue(self.grant()['completed'])
        self.assertEqual(self.ledger().current(), old)
        self.assertTrue(self.engine.tick()['halted'])

    def test_installed_release_must_include_new_capability(self):
        with patch('specroad_control.blocked_authorization.require_installed'):
            with patch('specroad_control.local.json_read', return_value={'files': {}}):
                with self.assertRaises(ControlError): require_release(self.paths)

    def test_retry_attempt_paths_keep_original_failure_budget(self):
        self.adopted(); ledger = self.ledger()
        root = self.paths.state / 'jobs' / self.seed['sha256']
        self.assertEqual(ledger.attempt_origin(self.paths, self.seed['sha256']), root / 'authorized/0000')
        # An actual overload claim appends to the existing retry ledger; the
        # new attempt path never replaces root/attempt.json.
        ledger.change('running')
        failure = {'workspace_sha256': 'a' * 64, 'turn_id': 'synthetic-failed-turn',
                   'turn_status': 'failed', 'codex_error': 'serverOverloaded',
                   'codex_will_retry': False, 'legacy': True}
        row = ledger.schedule_retry(failure, (5,), 100)
        self.assertEqual(row['number'], 1)
        self.assertEqual(ledger.attempt_directory(self.paths, self.seed['sha256'], 1), root / 'authorized/0001')
        self.assertEqual(ledger.request_contract()['clarifications_remaining'], 2)
        self.assertEqual(json_read(root / 'attempt.json')['request_contract']['clarification_allowed'], False)
