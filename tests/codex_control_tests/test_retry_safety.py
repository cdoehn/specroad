"""Retry guard, transaction and privacy regressions on independent fixtures."""
from dataclasses import replace
import json
import math
import os
import sqlite3
from unittest.mock import patch
from specroad_control.automation import Engine, Gate
from specroad_control.config import parse, render
from specroad_control.errors import ControlError
from specroad_control.local import json_write, json_read
from specroad_control.turn_failure import failure_details
from specroad_control.workspace import fingerprint
from codex_control_tests.test_overload_retry import RetryCase
from codex_control_tests.retry_support import git
from specroad_control.toml_compat import tomllib


class RetrySafetyTests(RetryCase):
    def test_changed_tracked_bytes_during_backoff_block_replay(self):
        self.engine.tick();self.now+=60
        (self.dev/'fixture.txt').write_text('changed')
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)
        self.assertEqual(self.ledger().current()['error'],'retry_workspace_changed')

    def test_new_untracked_file_blocks_replay(self):
        self.engine.tick();self.now+=60
        (self.dev/'new.py').write_text('pending user work')
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_same_worktree_but_changed_index_blocks_replay(self):
        self.engine.tick();self.now+=60
        git(self.dev,'rm','--cached','--','fixture.txt')
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_changed_permissions_block_replay(self):
        self.engine.tick();self.now+=60;(self.dev/'fixture.txt').chmod(0o700)
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_symlink_contents_are_hashed_not_followed(self):
        external=self.home/'outside';external.write_text('first')
        (self.dev/'pointer').symlink_to(external)
        before=fingerprint(self.dev);external.write_text('second')
        self.assertEqual(fingerprint(self.dev),before)
        (self.dev/'pointer').unlink();(self.dev/'pointer').symlink_to('different')
        self.assertNotEqual(fingerprint(self.dev),before)

    def test_fifo_in_worktree_is_rejected_without_blocking(self):
        (self.dev/'fixture.txt').unlink()
        os.mkfifo(self.dev/'fixture.txt')
        with self.assertRaises(ControlError):fingerprint(self.dev)

    def test_fingerprint_does_not_modify_git_index_or_files(self):
        before=(self.dev/'.git/index').read_bytes()
        first=fingerprint(self.dev);second=fingerprint(self.dev)
        self.assertEqual(first,second);self.assertEqual((self.dev/'.git/index').read_bytes(),before)

    def test_git_environment_cannot_retarget_workspace_guard(self):
        baseline=fingerprint(self.dev)
        with patch.dict(os.environ,{'GIT_DIR':'/nonexistent','GIT_INDEX_FILE':'/nonexistent'}):
            self.assertEqual(fingerprint(self.dev),baseline)

    def test_missing_baseline_disables_retry_but_not_normal_dispatch(self):
        with patch('specroad_control.automation.fingerprint',side_effect=ControlError('retry_workspace_unproven','test')):
            self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls,1)
        self.assertEqual(self.engine.summary()['retry_blocked_reason'],'retry_workspace_unproven')

    def test_missing_attempt_file_is_not_treated_as_legacy_automatically(self):
        self.engine.tick();self.now+=60
        (self.paths.state/'jobs'/self.seed['sha256']/'attempt.json').unlink()
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_failure_and_completion_conflict_prevents_retry(self):
        self.engine.tick();self.now+=60
        json_write(self.paths.state/'jobs'/self.seed['sha256']/'protocol-completion.json',{'completed':True})
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_duplicate_item_identity_invalidates_full_turn_proof(self):
        self.codex.effect={'id':'u','type':'reasoning'}
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_additional_user_instruction_prevents_automatic_replay(self):
        self.codex.effect={'id':'other','type':'userMessage','content':[{'type':'text','text':'Different work'}]}
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_pending_command_even_pwd_prevents_retry(self):
        self.codex.effect={'id':'pending','type':'commandExecution','command':'pwd','status':'inProgress','exitCode':None}
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_truncated_turn_items_prevent_retry(self):
        self.engine.tick();self.now+=60;self.codex.turns['turn-1']['itemsTruncated']=True
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_inprogress_exact_turn_never_replaced_even_with_idle_metadata(self):
        self.engine.tick();self.now+=86400;self.codex.turns['turn-1']['status']='inProgress'
        self.assertEqual(self.engine.tick()['retry_after'],30);self.assertEqual(self.codex.calls,1)

    def test_failure_without_will_retry_false_does_not_schedule(self):
        self.codex.will_retry=None
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)

    def test_conflicting_error_sources_cannot_classify_as_safe_overload(self):
        details=failure_details({'status':'failed','error':{'codexErrorInfo':'usageLimitExceeded'}},
                                {'error':{'codexErrorInfo':'serverOverloaded'},'willRetry':False})
        self.assertNotEqual(details['codex_error'],'serverOverloaded')

    def test_successful_turn_clears_prior_transient_error(self):
        details=failure_details({'status':'completed','error':None},
                                {'error':{'codexErrorInfo':'serverOverloaded'},'willRetry':True})
        self.assertIsNone(details['codex_error']);self.assertIsNone(details['codex_will_retry'])

    def test_config_disables_retries_without_changing_thread_model(self):
        self.engine.config=replace(self.config,retry_delays_seconds=())
        self.assertTrue(self.engine.tick()['halted']);self.assertEqual(self.codex.calls,1)
        self.assertEqual(self.engine.summary()['retry_blocked_reason'],'retry_exhausted')

    def test_invalid_retry_settings_rejected(self):
        doc=tomllib.loads(render(self.config))
        for invalid in ([True],[0],[2,1],[1.5],[-1],[1]*9,[86401]):
            doc['automation']['retry_delays_seconds']=invalid
            with self.assertRaises((ControlError,ValueError,TypeError)):parse(doc,self.paths)

    def test_retry_history_is_additive_and_preserves_jobs(self):
        before=self.ledger().current()['source']
        self.engine.tick();ledger=self.ledger()
        self.assertEqual(ledger.current()['source'],before)
        self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],1)
        self.assertEqual(ledger.retry_info(self.seed['sha256'])['number'],1)

    def test_retry_transaction_rolls_back_on_partial_update_failure(self):
        self.engine.tick();ledger=self.ledger();before=ledger.current()
        with self.assertRaises(RuntimeError):
            with ledger.transaction():
                ledger.db.execute("UPDATE retry_attempts SET number=2")
                raise RuntimeError('simulated abrupt operation failure')
        self.assertEqual(ledger.retry_info(self.seed['sha256'])['number'],1)
        self.assertEqual(ledger.current(),before)

    def test_gap_in_attempt_history_is_not_reset(self):
        self.engine.tick();ledger=self.ledger();ledger.db.execute('UPDATE retry_attempts SET number=2')
        with self.assertRaises(ControlError):self.engine.tick()
        self.assertEqual(self.codex.calls,1)

    def test_reused_failed_turn_cannot_expand_budget(self):
        self.engine.tick();ledger=self.ledger();failure=ledger.retry_info(self.seed['sha256'])['evidence']
        ledger.change('uncertain',error='codex_turn_failed')
        with self.assertRaises(ControlError) as caught:ledger.schedule_retry(failure,(60,180),self.now)
        self.assertEqual(caught.exception.code,'retry_evidence_reused')
        self.assertEqual(ledger.retry_info(self.seed['sha256'])['number'],1)

    def test_retained_budget_after_restart_cannot_create_extra_attempt(self):
        self.codex.failures=20;self.engine.config=replace(self.config,retry_delays_seconds=(1,))
        self.engine.tick();self.now+=1;self.engine.tick();self.engine.close()
        with Engine(self.engine.config,self.paths,Gate(),core=self.engine.core,codex=self.codex,clock=lambda:self.now) as restarted:
            self.assertTrue(restarted.tick()['halted'])
        self.assertEqual(self.codex.calls,2)
