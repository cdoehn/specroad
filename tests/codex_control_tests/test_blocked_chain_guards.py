"""Fail-closed boundaries around a deferred blocked correction chain."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import zipfile

from specroad_control.apply_reconcile import enqueue, validate_history
from specroad_control.apply_reconcile_proof import canonical, hashed
from specroad_control.errors import ControlError
from specroad_control.local import json_write, lock
from codex_control_tests.blocked_chain_support import BlockedChainCase, log_for
import codex_control_tests.test_blocked_chain as behavior
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.automation_support import read_package, FakeCodex
from codex_control_tests.test_recovery import LedgerContext


class BlockedChainGuardTests(BlockedChainCase):
    queue = behavior.BlockedChainTests.queue
    engine = behavior.BlockedChainTests.engine
    preserved = behavior.BlockedChainTests.preserved
    rejected = behavior.BlockedChainTests.rejected

    def test_queue_requires_stopped_worker(self):
        with lock(self.paths.state / 'worker.lock'): self.rejected()

    def test_same_source_cannot_be_reclassified_through_old_command(self):
        self.queue()
        with self.assertRaises(ControlError): enqueue(self.paths, self.final['path'])
        self.preserved()

    def test_second_correction_patch_blocks(self):
        other = deepcopy(self.resumed_data); other['bundle_number'] = '003'
        patch_package(self.exchange / 'other.zip', other); self.rejected()

    def test_second_corrective_result_blocks(self):
        self.result('other.zip', previous=self.checkpoint, patch_sha=self.resumed['sha256'], success=False)
        self.rejected()

    def test_changed_message_cannot_hide_a_different_commit(self):
        self.resumed_data['stages'][0]['message'] = 'Other work'; self.create_output(); self.rejected()

    def test_repeated_successful_prefix_is_rejected(self):
        self.resumed_data['stages'].insert(0, deepcopy(self.original_data['stages'][0]))
        self.create_output(); self.rejected()

    def test_zero_tests_on_corrected_commits_blocks(self):
        log = log_for(self.resumed_data, ['e' * 40, 'f' * 40, 'c' * 40]).replace(b'"tests":10', b'"tests":0')
        self.create_output(log=log); self.rejected()

    def test_unknown_progress_field_does_not_extend_the_contract(self):
        log = log_for(self.resumed_data, ['e' * 40, 'f' * 40, 'c' * 40]).replace(b'"phase":"completed"', b'"phase":"completed","extra":true')
        self.create_output(log=log); self.rejected()

    def test_noninteger_progress_version_blocks(self):
        log = log_for(self.resumed_data, ['e' * 40, 'f' * 40, 'c' * 40])
        lines = log.splitlines(); lines[-1] = lines[-1].replace(b'"format_version":1', b'"format_version":true')
        self.create_output(log=b'\n'.join(lines) + b'\n'); self.rejected()

    def test_dirty_or_uncommitted_success_is_rejected(self):
        self.create_output(dirty=True, completed_commit=None); self.rejected()

    def test_mismatched_checkpoint_bytes_block_even_when_rebound(self):
        path = Path(self.checkpoint['path'])
        with zipfile.ZipFile(path) as archive: members = {n: archive.read(n) for n in archive.namelist()}
        members['changes/unstaged.patch'] = members['changes/unstaged.patch'].replace(b'-value = 0', b'-value = 9')
        with zipfile.ZipFile(path, 'w') as archive:
            for name, value in members.items(): archive.writestr(name, value)
        self.checkpoint = read_package(path); self.create_output(); self.rejected()

    def test_changed_original_protocol_after_queue_blocks(self):
        self.queue(); json_write(self.directory / 'protocol-completion.json', {'completed': False})
        with self.engine() as engine:
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(engine.codex.calls, 0)
        self.preserved()

    def test_missing_evidence_after_adoption_blocks_first_new_model(self):
        self.queue()
        with self.engine() as engine:
            self.assertTrue(engine.tick()['again'])
            Path(self.checkpoint['path']).unlink()
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(engine.codex.calls, 0)

    def test_activity_during_final_metadata_observation_prevents_adoption(self):
        self.queue(); codex = FakeCodex(self); observations = iter(('idle', 'active'))
        codex.activity = lambda: next(observations)
        with self.engine(codex=codex) as engine:
            self.assertEqual(engine.tick()['retry_after'], 2); self.assertEqual(codex.calls, 0)
        self.preserved()

    def test_pause_during_final_metadata_observation_prevents_adoption(self):
        from specroad_control.automation import Gate
        self.queue(); gate = Gate(); codex = FakeCodex(self); checks = []
        def activity():
            checks.append(True)
            if len(checks) == 2: gate.set(False)
            return 'idle'
        codex.activity = activity
        with self.engine(codex=codex, gate=gate) as engine:
            self.assertFalse(engine.tick()['again']); self.assertEqual(codex.calls, 0)
        self.preserved()

    def test_restart_retains_one_claim_and_original_budget(self):
        self.queue()
        with self.engine() as engine: self.assertTrue(engine.tick()['again'])
        with self.engine() as engine: self.assertTrue(engine.tick()['halted'])
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 2)
            self.assertEqual(ledger.request_contract()['clarifications_remaining'], 2)

    def test_recomputed_proof_hash_cannot_override_checkpoint_binding(self):
        self.queue()
        with LedgerContext(self.paths, self.config) as ledger:
            doc = validate_history(ledger); doc['artifacts']['checkpoint']['patch_sha256'] = '0' * 64
            ledger.db.execute('UPDATE apply_reconciliations SET proof=?, proof_sha=?', (canonical(doc).decode(), hashed(doc)))
        with self.assertRaises(ControlError) as caught:
            with LedgerContext(self.paths, self.config): pass
        self.assertEqual(caught.exception.code, 'invalid_apply_reconciliation')

    def test_native_archive_swap_to_symlink_blocks_adoption(self):
        self.queue(); path = Path(self.resumed['path']); moved = path.with_suffix('.original'); path.rename(moved); path.symlink_to(moved)
        with self.engine() as engine:
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(engine.codex.calls, 0)
        self.preserved()

    def test_cli_routes_the_explicit_blocked_command(self):
        from specroad_control.cli import main
        with patch('specroad_control.apply_reconcile.enqueue', return_value={'queued': True}) as action:
            self.assertEqual(main(['reconcile-blocked', '--result', self.final['path']]), 0)
        self.assertTrue(action.call_args.kwargs['blocked'])
        self.assertEqual(action.call_args.args[1], self.final['path'])
