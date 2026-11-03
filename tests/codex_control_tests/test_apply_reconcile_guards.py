"""Changed bytes, ambiguous status and crash boundaries cannot release new work."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import zipfile
from unittest.mock import patch

from specroad_control.apply_reconcile import enqueue, validate_history
from specroad_control.apply_reconcile_proof import canonical, hashed, plan
from specroad_control.automation import Engine, Gate
from specroad_control.cli import main
from specroad_control.errors import ControlError
from specroad_control.local import json_write, write_private
from codex_control_tests.apply_reconcile_support import ReconcileCase, ReconcileCore, patch_package
from codex_control_tests.automation_support import FakeCodex, read_package
from codex_control_tests.test_recovery import LedgerContext


class ReconciliationGuardTests(ReconcileCase):
    def queue(self):
        return enqueue(self.paths, self.final['path'])

    def engine(self, *, codex=None):
        codex = codex or FakeCodex(self, 'no_work')
        if not hasattr(codex, 'activity'):
            codex.activity = lambda: 'idle'
        return Engine(self.config, self.paths, Gate(), core=ReconcileCore(), codex=codex)

    def test_unknown_thread_status_is_not_queued(self):
        self.settings(thread_status='systemError')
        with self.assertRaises(ControlError) as caught: self.queue()
        self.assertEqual(caught.exception.code, 'apply_reconciliation_thread_unknown')
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertIsNone(validate_history(ledger))

    def test_unknown_worker_thread_status_blocks_instead_of_waiting(self):
        self.queue()
        codex = FakeCodex(self)
        codex.activity = lambda: (_ for _ in ()).throw(ControlError('apply_reconciliation_thread_unknown', 'unknown'))
        with self.engine(codex=codex) as engine:
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(codex.calls, 0)

    def test_wrong_thread_identity_blocks_queue(self):
        self.settings(returned_id='not-the-configured-thread')
        with self.assertRaises(ControlError): self.queue()

    def test_second_check_detects_active_chat_and_preserves_request(self):
        self.queue()
        codex = FakeCodex(self)
        statuses = iter(['idle', 'active']); codex.activity = lambda: next(statuses)
        with self.engine(codex=codex) as engine:
            self.assertEqual(engine.tick()['retry_after'], 2)
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertIsNotNone(validate_history(ledger))

    def test_changed_result_during_last_metadata_check_cannot_advance(self):
        self.queue()
        codex = FakeCodex(self)
        observations = []
        def activity():
            observations.append(True)
            if len(observations) == 2:
                Path(self.final['path']).unlink()
            return 'idle'
        codex.activity = activity
        with self.engine(codex=codex) as engine:
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(codex.calls, 0)
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertEqual(ledger.current()['sha'], self.seed['sha256'])

    def test_changed_config_does_not_use_stale_intent(self):
        self.queue()
        write_private(self.paths.config, self.paths.config.read_bytes() + b'\n# changed\n')
        with self.engine() as engine:
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(engine.codex.calls, 0)

    def test_missing_completed_recovery_artifact_blocks_first_model_call(self):
        self.queue()
        with self.engine() as engine:
            engine.tick()
        Path(self.original['path']).unlink()
        with self.engine() as engine:
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(engine.codex.calls, 0)

    def test_changed_receipt_after_adoption_blocks_first_model_call(self):
        self.queue()
        with self.engine() as engine: engine.tick()
        json_write(self.directory / 'completion.json', {**self.answer, 'message': 'replacement'})
        with self.engine() as engine:
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(engine.codex.calls, 0)

    def test_original_clarification_classification_cannot_be_relabelled(self):
        with LedgerContext(self.paths, self.config) as ledger:
            ledger.db.execute("UPDATE request_contracts SET output_kind='unknown'")
        with self.assertRaises(ControlError): self.queue()

    def test_malformed_original_attempt_fails_closed(self):
        write_private(self.directory / 'attempt.json', b'{not-json')
        with self.assertRaises(ControlError): self.queue()

    def test_changed_request_contract_blocks_queue(self):
        path = self.directory / 'attempt.json'
        doc = json.loads(path.read_text()); doc['request_contract']['clarifications_remaining'] = 1
        json_write(path, doc)
        with self.assertRaises(ControlError): self.queue()

    def test_corrupt_proof_is_rejected_on_ledger_reopen(self):
        self.queue()
        with LedgerContext(self.paths, self.config) as ledger:
            ledger.db.execute("UPDATE apply_reconciliations SET proof_sha=?", ('0' * 64,))
        with self.assertRaises(ControlError) as caught:
            with LedgerContext(self.paths, self.config): pass
        self.assertEqual(caught.exception.code, 'invalid_apply_reconciliation')

    def test_rehashed_unknown_proof_field_is_rejected(self):
        self.queue()
        with LedgerContext(self.paths, self.config) as ledger:
            doc = validate_history(ledger); doc['allow_unverified'] = True
            ledger.db.execute('UPDATE apply_reconciliations SET proof=?, proof_sha=?',
                              (canonical(doc).decode(), hashed(doc)))
        with self.assertRaises(ControlError):
            with LedgerContext(self.paths, self.config): pass

    def test_coherent_old_patch_replacement_is_not_recovery(self):
        self.queue()
        with LedgerContext(self.paths, self.config) as ledger:
            ledger.db.execute('UPDATE jobs SET patch_sha=?', (self.resumed['sha256'],))
        with self.assertRaises(ControlError):
            with LedgerContext(self.paths, self.config): pass

    def test_additional_payload_file_is_rejected(self):
        path = Path(self.resumed['path'])
        with zipfile.ZipFile(path, 'a') as archive: archive.writestr('unexpected.py', 'raise RuntimeError()')
        fact = ReconcileCore().patch(path)
        with self.assertRaises(ControlError): plan(fact)

    def test_code_on_data_statement_line_cannot_be_hidden_by_normalization(self):
        path = Path(self.resumed['path'])
        with zipfile.ZipFile(path) as archive:
            contents = {name: archive.read(name) for name in archive.namelist()}
        lines = contents['run.sh'].decode().splitlines(True)
        for index, line in enumerate(lines):
            if line.startswith('DATA = '): lines[index] = line.rstrip('\n') + '; print("extra behavior")\n'
        contents['run.sh'] = ''.join(lines).encode()
        with zipfile.ZipFile(path, 'w') as archive:
            for name, content in contents.items(): archive.writestr(name, content)
        with self.assertRaises(ControlError): plan(ReconcileCore().patch(path))

    def test_payload_hash_mismatch_blocks_queue(self):
        self.resumed_data['stages'][0]['after']['src/example.py'] = '0' * 64
        self.create_output()
        with self.assertRaises(ControlError): self.queue()

    def test_reversed_remaining_stages_block_queue(self):
        self.resumed_data['stages'].reverse(); self.create_output()
        with self.assertRaises(ControlError): self.queue()

    def test_missing_captured_time_blocks_queue(self):
        self.create_output(captured_at=None)
        with self.assertRaises(ControlError): self.queue()

    def test_wrong_intermediate_head_blocks_queue(self):
        self.resumed_data['binding'] = {**self.resumed_data['binding'], 'base_commit': 'f' * 40}
        self.create_output()
        with self.assertRaises(ControlError): self.queue()

    def test_result_outside_exchange_is_not_accepted(self):
        path = Path(self.final['path']); moved = self.home / 'outside.zip'; path.rename(moved)
        with self.assertRaises(ControlError): enqueue(self.paths, str(moved))

    def test_cli_requires_explicit_result_and_has_no_setup_side_effects(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit): main(['reconcile-apply'])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['reconcile-apply', '--result', self.final['path'], '--transport', 'exec'])
        output = io.StringIO()
        with redirect_stdout(output): self.assertEqual(main(['reconcile-apply', '--result', self.final['path']]), 0)
        self.assertTrue(json.loads(output.getvalue())['queued'])
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())

    def test_other_offline_work_is_blocked_without_replacing_queued_authority(self):
        from specroad_control.commands import probe, check, recover, configure
        from specroad_control.handover import check_boundary
        self.queue()
        config = self.paths.config.read_bytes()
        for label, action in (('probe', probe), ('check', check), ('recover', recover),
                              ('configure', lambda p: configure(p, thread_id=self.thread))):
            with self.subTest(action=label), self.assertRaises(ControlError) as caught:
                action(self.paths)
            self.assertEqual(caught.exception.code, 'apply_reconciliation_pending')
        with LedgerContext(self.paths, self.config) as ledger:
            with self.assertRaises(ControlError): check_boundary(ledger, self.paths)
        self.assertEqual(self.paths.config.read_bytes(), config)
        self.assertFalse((self.codex_home / 'calls.jsonl').exists())
