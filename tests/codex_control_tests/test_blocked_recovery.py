"""Explicit recovery of completed blocked turns with a later proven Apply."""
import json
import hashlib
from pathlib import Path
from unittest.mock import patch as mock_patch

from specroad_control.automation import Engine, Gate
from specroad_control.commands import recover
from specroad_control.codex import Codex
from specroad_control.errors import ControlError
from specroad_control.local import json_write, private_dir
from codex_control_tests.automation_support import AutomationCase, FakeCodex, FakeCore, package
from codex_control_tests.test_recovery import LedgerContext


class BlockedRecoveryTests(AutomationCase):
    def setUp(self):
        super().setUp()
        with LedgerContext(self.paths, self.config) as ledger:
            ledger.change('running')
            ledger.change('uncertain', error='dev_blocked')
        self.directory = self.paths.state / 'jobs' / self.seed['sha256']
        private_dir(self.directory)
        self.protocol = self.directory / 'protocol-completion.json'
        self.answer = {'source_result_sha256': self.seed['sha256'], 'status': 'blocked',
                       'patch_sha256': '', 'message': 'Needs a product decision.'}
        json_write(self.protocol, {'completed': True, 'thread_id': self.thread,
                                  'transport': 'exec', 'answer': self.answer})
        json_write(self.directory / 'completion.json', self.answer)
        json_write(self.paths.state_file, {'desired': 'paused', 'active_job': False})

    def output(self, **result_changes):
        patch = package(self.exchange / 'manual.zip', {'kind': 'patch', 'binding': self.binding})
        result = self.result('manual-result.zip', previous=self.seed, patch_sha=patch['sha256'],
                             **({'completed_commit': 'c' * 40} | result_changes))
        return patch, result

    def assert_blocked(self, code='recovery_unproven'):
        before = self.protocol.read_bytes()
        with self.assertRaises(ControlError) as caught:
            recover(self.paths)
        self.assertEqual(caught.exception.code, code)
        with LedgerContext(self.paths, self.config) as ledger:
            row = ledger.current()
            self.assertEqual((row['stage'], row['error'], row['patch_sha']),
                             ('uncertain', 'dev_blocked', None))
        self.assertEqual(self.protocol.read_bytes(), before)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_bound_success_recovers_without_model_or_overwriting_old_evidence(self):
        patch, result = self.output()
        preserved = {p: p.read_bytes() for p in (self.protocol, self.directory / 'completion.json',
                                                self.paths.config, self.paths.state_file)}
        answer = recover(self.paths)
        self.assertEqual(answer, {'recovered': True, 'stage': 'waiting_result',
                                  'model_called': False, 'service_started': False})
        with LedgerContext(self.paths, self.config) as ledger:
            row = ledger.current()
            self.assertEqual(row['patch_sha'], patch['sha256'])
            self.assertEqual(row['run_id'], self.seed['run_id'])
            self.assertEqual(ledger.seed_sha, self.seed['sha256'])
        self.assertEqual({p: p.read_bytes() for p in preserved}, preserved)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())
        self.assertEqual(recover(self.paths)['reason'], 'no_uncertain_job')

    def test_worker_does_not_automatically_release_blocked_job(self):
        self.output()
        codex = FakeCodex(self)
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=codex) as engine:
            self.assertTrue(engine.tick()['halted'])
        self.assertEqual(codex.calls, 0)

    def test_human_receipt_without_patch_and_result_stays_blocked(self):
        self.assert_blocked()

    def test_patch_without_apply_result_stays_blocked(self):
        package(self.exchange / 'manual.zip', {'kind': 'patch', 'binding': self.binding})
        self.assert_blocked()

    def test_result_without_patch_stays_blocked(self):
        patch, _ = self.output()
        Path(patch['path']).unlink()
        self.assert_blocked()

    def test_unbound_result_does_not_release(self):
        self.output(expected={**self.binding, 'base_commit': 'd' * 40})
        self.assert_blocked()

    def test_two_bound_patches_stay_ambiguous(self):
        self.output()
        package(self.exchange / 'other.zip', {'kind': 'patch', 'binding': self.binding, 'other': True})
        self.assert_blocked()

    def test_failed_apply_is_not_a_recovery_success(self):
        self.output(success=False, primary_kind='entrypoint_exit')
        self.assert_blocked()

    def test_dry_run_is_not_a_recovery_success(self):
        self.output(dry_run=True)
        self.assert_blocked()

    def test_dirty_apply_is_not_a_recovery_success(self):
        self.output(dirty=True)
        self.assert_blocked()

    def test_uncommitted_apply_is_not_a_recovery_success(self):
        self.output(completed_commit=None)
        self.assert_blocked()

    def test_two_results_including_failed_attempt_do_not_choose_success(self):
        patch, _ = self.output()
        self.result('second-result.zip', previous=self.seed, patch_sha=patch['sha256'],
                    success=False, primary_kind='entrypoint_exit')
        self.assert_blocked()

    def test_commit_must_match_result_snapshot(self):
        self.output(completed_commit='d' * 40)
        self.assert_blocked()

    def test_apply_without_started_entrypoint_is_rejected(self):
        self.output(entrypoint_started=False)
        self.assert_blocked()

    def test_wrong_thread_completion_is_preserved(self):
        self.output()
        protocol = json.loads(self.protocol.read_text())
        protocol['thread_id'] = 'another-thread'
        json_write(self.protocol, protocol)
        self.assert_blocked('recovery_evidence_invalid')

    def test_uncompleted_protocol_is_not_adopted(self):
        self.output()
        protocol = json.loads(self.protocol.read_text())
        protocol['completed'] = False
        json_write(self.protocol, protocol)
        self.assert_blocked('recovery_evidence_invalid')

    def test_receipt_for_another_source_is_not_adopted(self):
        self.output()
        protocol = json.loads(self.protocol.read_text())
        protocol['answer']['source_result_sha256'] = 'f' * 64
        json_write(self.protocol, protocol)
        self.assert_blocked('recovery_evidence_invalid')

    def test_nonblocked_receipt_cannot_clear_a_blocked_claim(self):
        self.output()
        protocol = json.loads(self.protocol.read_text())
        protocol['answer']['status'] = 'no_work'
        json_write(self.protocol, protocol)
        self.assert_blocked('recovery_evidence_invalid')

    def test_malformed_blocked_answer_is_not_adopted(self):
        self.output()
        protocol = json.loads(self.protocol.read_text())
        protocol['answer']['unexpected'] = True
        json_write(self.protocol, protocol)
        self.assert_blocked('recovery_evidence_invalid')

    def test_busy_thread_cannot_be_recovered(self):
        self.output()
        self.settings(thread_status='active')
        self.assert_blocked('dev_thread_busy')

    def during_second_check(self, action):
        original = Codex.check
        checks = []
        def check(codex):
            checks.append(True)
            if len(checks) == 2:
                action()
            return original(codex)
        return mock_patch.object(Codex, 'check', check)

    def test_thread_becoming_active_during_validation_blocks_adoption(self):
        self.output()
        with self.during_second_check(lambda: self.settings(thread_status='active')):
            self.assert_blocked('dev_thread_busy')

    def test_changed_protocol_during_validation_blocks_adoption(self):
        self.output()
        before = self.protocol.read_bytes()
        def changed():
            protocol = json.loads(before)
            protocol['answer']['message'] = 'Changed external evidence.'
            json_write(self.protocol, protocol)
        with self.during_second_check(changed):
            with self.assertRaises(ControlError) as caught:
                recover(self.paths)
        self.assertEqual(caught.exception.code, 'recovery_evidence_changed')
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.current()['stage'], 'uncertain')
        self.assertNotEqual(self.protocol.read_bytes(), before)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_result_change_during_validation_blocks_adoption(self):
        _, result = self.output()
        with self.during_second_check(lambda: package(Path(result['path']), {**result, 'changed': True})):
            self.assert_blocked('recovery_evidence_changed')

    def test_new_ambiguous_patch_during_validation_blocks_adoption(self):
        self.output()
        def changed():
            package(self.exchange / 'extra.zip', {'kind': 'patch', 'binding': self.binding, 'extra': True})
        with self.during_second_check(changed):
            self.assert_blocked()

    def test_recovery_pins_result_and_original_completion_hash(self):
        patch, result = self.output()
        completion_sha = hashlib.sha256(self.protocol.read_bytes()).hexdigest()
        recover(self.paths)
        with LedgerContext(self.paths, self.config) as ledger:
            proof = ledger.blocked_recovery()
            self.assertEqual(proof['sha256'], result['sha256'])
            row = ledger.db.execute('SELECT * FROM blocked_recoveries').fetchone()
            self.assertEqual((row['source_sha'], row['patch_sha'], row['completion_sha']),
                             (self.seed['sha256'], patch['sha256'], completion_sha))

    def test_restart_follows_only_pinned_result_and_never_repeats_original_job(self):
        _, result = self.output()
        recover(self.paths)
        codex = FakeCodex(self, 'no_work')
        original_run = codex.run
        seen = []
        def run(prompt, *args, **kwargs):
            seen.append(json.loads(prompt.split('\n')[1])['sha256'])
            return original_run(prompt, *args, **kwargs)
        codex.run = run
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=codex) as engine:
            engine.tick()
            engine.tick()
        self.assertEqual(seen, [result['sha256']])
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.current()['sha'], result['sha256'])
            self.assertEqual(ledger.db.execute('SELECT stage FROM jobs WHERE sha=?', (self.seed['sha256'],)).fetchone()[0], 'done')
            self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM blocked_recoveries').fetchone()[0], 1)

    def assert_pinned_failure(self, code='recovery_evidence_changed'):
        codex = FakeCodex(self)
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=codex) as engine:
            with self.assertRaises(ControlError) as caught:
                engine.tick()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(codex.calls, 0)
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.current()['sha'], self.seed['sha256'])

    def test_missing_pinned_result_blocks_dispatch_after_restart(self):
        _, result = self.output()
        recover(self.paths)
        Path(result['path']).unlink()
        self.assert_pinned_failure()

    def test_changed_pinned_result_blocks_dispatch_after_restart(self):
        _, result = self.output()
        recover(self.paths)
        package(Path(result['path']), {**result, 'changed': True})
        self.assert_pinned_failure()

    def test_corrupt_recovery_history_blocks_dispatch(self):
        self.output()
        recover(self.paths)
        with LedgerContext(self.paths, self.config) as ledger:
            ledger.db.execute("UPDATE blocked_recoveries SET completion_sha='invalid'")
        self.assert_pinned_failure('invalid_recovery_history')

    def test_archived_packages_and_results_remain_recoverable(self):
        patch, result = self.output()
        archive = self.exchange / 'PatchHarbor-Archive'
        archive.mkdir()
        for item in (self.seed, patch, result):
            Path(item['path']).rename(archive / Path(item['path']).name)
        self.assertTrue(recover(self.paths)['recovered'])

    def test_storage_failure_rolls_back_proof_and_claim_together(self):
        self.output()
        with LedgerContext(self.paths, self.config) as ledger:
            ledger.db.execute('''CREATE TRIGGER fail_adoption BEFORE UPDATE OF stage ON jobs
                WHEN NEW.stage='waiting_result' BEGIN SELECT RAISE(ABORT, 'test storage failure'); END''')
        self.assert_blocked('recovery_persist_failed')
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertIsNone(ledger.blocked_recovery())
