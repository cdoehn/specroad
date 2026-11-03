from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sqlite3
from specroad_control.automation import Engine, Gate, SCHEMA, scope
from specroad_control.commands import recover, configure
from specroad_control.codex import Codex
from specroad_control.config import load, render
from specroad_control.errors import ControlError
from specroad_control.exchange import Exchange
from specroad_control.ledger import Ledger
from specroad_control.local import json_write, lock, private_dir, write_private
from codex_control_tests.automation_support import AutomationCase, FakeCore, FakeCodex, package


class RecoveryTests(AutomationCase):
    def engine(self, mode='patch'):
        codex=FakeCodex(self,mode)
        engine=Engine(self.config,self.paths,Gate(),core=FakeCore(),codex=codex)
        self.addCleanup(engine.close)
        return engine,codex

    def test_failed_apply_unchanged_binding_does_not_reuse_attempted_patch(self):
        engine,codex=self.engine(); engine.tick()
        old_patch=engine.exchange.patches(self.seed)[0]
        # A failed Apply may leave HEAD AND its worktree fingerprint unchanged.
        self.result('failure.zip',previous=self.seed,patch_sha=old_patch['sha256'], binding=self.binding,
                    success=False,primary_kind='entrypoint_exit',dirty=False)
        # Make the correction bytes distinct (otherwise handoff must remain blocked).
        def corrected(prompt,schema,directory,*,readonly=False,authorize=lambda:True):
            self.assertTrue(authorize()); codex.calls+=1
            source=json.loads(prompt.split('\n')[1])
            patch=package(self.exchange/'correction.zip',{'kind':'patch','binding':source['binding'],'fix':True})
            return {'source_result_sha256':source['sha256'],'status':'patch_ready','patch_sha256':patch['sha256'],'message':''}
        codex.run=corrected
        self.assertTrue(engine.tick()['again']); self.assertEqual(codex.calls,2)
        with LedgerContext(self.paths, self.config) as ledger:
            self.assertNotEqual(ledger.current()['patch_sha'],old_patch['sha256'])

    def test_same_run_conflicting_bytes_do_not_depend_on_filename_order(self):
        package(self.exchange/'z-duplicate.zip',{**self.seed,'sha256':'not-used','conflict':True})
        engine,codex=self.engine()
        with self.assertRaises(ControlError) as caught: engine.tick()
        self.assertEqual(caught.exception.code,'result_identity_conflict'); self.assertEqual(codex.calls,0)

    def test_ambiguous_followup_results_do_not_choose_newest_name(self):
        engine,codex=self.engine(); engine.tick()
        patch=engine.exchange.patches(self.seed)[0]
        for name in ('old.zip','new.zip'): self.result(name,previous=self.seed,patch_sha=patch['sha256'])
        with self.assertRaises(ControlError) as caught: engine.tick()
        self.assertEqual(caught.exception.code,'ambiguous_result'); self.assertEqual(codex.calls,1)

    def test_dry_run_is_not_an_apply_receipt(self):
        engine,codex=self.engine(); engine.tick()
        patch=engine.exchange.patches(self.seed)[0]
        self.result('dry.zip',previous=self.seed,patch_sha=patch['sha256'],dry_run=True)
        self.assertFalse(engine.tick()['again']); self.assertEqual(codex.calls,1)

    def test_completion_recovery_never_calls_model(self):
        with LedgerContext(self.paths,self.config) as ledger:
            ledger.change('running')
        directory=self.paths.state/'jobs'/self.seed['sha256']; private_dir(directory)
        answer={'source_result_sha256':self.seed['sha256'],'status':'no_work','patch_sha256':'','message':''}
        json_write(directory/'protocol-completion.json',{'completed':True,'thread_id':self.thread,'transport':'exec','answer':answer})
        result=recover(self.paths)
        self.assertTrue(result['recovered']); self.assertEqual(result['stage'],'no_work'); self.assertFalse(result['model_called'])
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_existing_bound_patch_recovery_waits_without_replay(self):
        with LedgerContext(self.paths,self.config) as ledger:
            ledger.change('running')
        package(self.exchange/'output.zip',{'kind':'patch','binding':self.binding})
        result=recover(self.paths)
        self.assertEqual(result['stage'],'waiting_result'); self.assertFalse(result['model_called'])
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_uncertain_without_evidence_remains_blocked(self):
        with LedgerContext(self.paths,self.config) as ledger:
            ledger.change('running'); ledger.change('uncertain',error='lost_connection')
        with self.assertRaises(ControlError) as caught: recover(self.paths)
        self.assertEqual(caught.exception.code,'recovery_unproven')
        with LedgerContext(self.paths,self.config) as ledger: self.assertEqual(ledger.current()['stage'],'uncertain')

    def test_recovery_never_interrupts_a_busy_thread(self):
        with LedgerContext(self.paths,self.config) as ledger:
            ledger.change('running')
        self.settings(thread_status='active')
        with self.assertRaises(ControlError): recover(self.paths)
        with LedgerContext(self.paths,self.config) as ledger: self.assertEqual(ledger.current()['stage'],'running')

    def test_corrupt_meta_pointer_does_not_reseed(self):
        with LedgerContext(self.paths,self.config) as ledger:
            ledger.db.execute("UPDATE meta SET current='missing'")
        with self.assertRaises(ControlError) as caught:
            with LedgerContext(self.paths,self.config): pass
        self.assertEqual(caught.exception.code,'invalid_ledger')

    def test_cleared_pointer_with_existing_history_does_not_reseed(self):
        with LedgerContext(self.paths,self.config) as ledger:
            ledger.db.execute('UPDATE meta SET current=NULL')
        with self.assertRaises(ControlError):
            with LedgerContext(self.paths,self.config): pass

    def test_uncertain_state_cannot_be_requeued(self):
        with LedgerContext(self.paths,self.config) as ledger:
            ledger.change('running'); ledger.change('uncertain')
            with self.assertRaises(ControlError): ledger.change('ready')

    def test_pending_requires_valid_patch_hash(self):
        with LedgerContext(self.paths,self.config) as ledger:
            with self.assertRaises(ControlError): ledger.change('waiting_result',patch_sha='not-a-digest')
            self.assertEqual(ledger.current()['stage'],'ready')

    def test_fake_completion_wrong_thread_is_rejected(self):
        with LedgerContext(self.paths,self.config) as ledger:
            ledger.change('running')
        directory=self.paths.state/'jobs'/self.seed['sha256']; private_dir(directory)
        json_write(directory/'protocol-completion.json',{'completed':True,'thread_id':'wrong','transport':'exec','answer':{}})
        with self.assertRaises(ControlError) as caught: recover(self.paths)
        self.assertEqual(caught.exception.code,'recovery_evidence_invalid')

    def test_wrong_seed_repository_cannot_retarget_dev(self):
        source=self.result('foreign.zip',repository_path=str(self.home/'foreign-apply'))
        before=self.paths.config.read_bytes()
        with self.assertRaises(ControlError):
            configure(self.paths,thread_id=self.thread,result=source['path'],codex=str(self.binary),core_python=str(self.python))
        self.assertEqual(self.paths.config.read_bytes(),before)

    def test_running_worker_prevents_reconfiguration(self):
        with lock(self.paths.state/'worker.lock'):
            with self.assertRaises(ControlError):
                configure(self.paths,thread_id=self.thread,result=self.seed['path'],codex=str(self.binary),core_python=str(self.python))

    def test_newer_unclaimed_result_vetoes_development(self):
        earlier=datetime.now(timezone.utc)-timedelta(seconds=10)
        self.seed=package(Path(self.seed['path']),{**self.seed,'captured_at':earlier.isoformat()})
        # Replace only this never-dispatched isolated fixture's source.
        with LedgerContext(self.paths, self.config) as ledger:
            ledger.db.execute('UPDATE meta SET seed=?', (self.seed['sha256'],))
            ledger.db.execute('UPDATE jobs SET sha=?, source=?', (self.seed['sha256'], json.dumps(self.seed)))
        self.result('newer.zip',captured_at=datetime.now(timezone.utc).isoformat())
        engine,codex=self.engine()
        with self.assertRaises(ControlError) as caught: engine.tick()
        self.assertEqual(caught.exception.code,'source_superseded'); self.assertEqual(codex.calls,0)

    def test_preflight_busy_can_be_rechecked_without_replaying_work(self):
        self.settings(thread_status='active')
        with Engine(self.config,self.paths,Gate(),core=FakeCore()) as engine:
            self.assertTrue(engine.tick()['halted'])
            with LedgerContext(self.paths,self.config) as ledger: self.assertEqual(ledger.current()['stage'],'ready')
            self.settings(mode='patch')
            self.assertTrue(engine.tick()['again'])
        self.assertEqual(len((self.codex_home/'calls.jsonl').read_text().splitlines()),1)

    def test_missing_configuration_field_is_not_implicitly_enabled(self):
        from specroad_control.config import load
        data=self.paths.config.read_text().replace('session_id = "'+self.thread+'"','session_id = ""')
        write_private(self.paths.config,data.encode())
        with self.assertRaises(ControlError): load(self.paths)

    def test_seed_moved_to_archive_before_start_keeps_exact_hash(self):
        archive=self.exchange/'PatchHarbor-Archive'; archive.mkdir()
        Path(self.seed['path']).rename(archive/'seed-renamed.zip')
        engine,codex=self.engine()
        self.assertTrue(engine.tick()['again']); self.assertEqual(codex.calls,1)

    def test_check_after_archival_uses_claimed_history_not_original_filename(self):
        from specroad_control.commands import check
        engine,codex=self.engine(); engine.tick(); engine.close()
        archive=self.exchange/'PatchHarbor-Archive'; archive.mkdir()
        Path(self.seed['path']).rename(archive/'renamed.zip')
        self.assertTrue(check(self.paths)['core_validated'])
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_result_change_during_preflight_cannot_dispatch(self):
        engine,codex=self.engine()
        def race(prompt,schema,directory,*,readonly=False,authorize=lambda:True):
            # The source changes after prompt construction, before durable claim.
            package(Path(self.seed['path']),{**self.seed,'changed':True})
            authorize()
            self.fail('Dispatch must not be authorized')
        codex.run=race
        self.assertTrue(engine.tick()['halted']); self.assertEqual(codex.calls,0)
        with LedgerContext(self.paths,self.config) as ledger:
            self.assertEqual(ledger.current()['stage'],'ready')

    def test_cache_is_bounded(self):
        exchange=Exchange(self.config,FakeCore())
        exchange.cache={('unused',n):{} for n in range(256)}
        list(exchange.candidates('result',lambda _m:True))
        self.assertLessEqual(len(exchange.cache),256)

    def test_corrupt_native_contract_cannot_pass_as_valid(self):
        from specroad_control.core import Core
        self.result('wrong-types.zip',success='true')
        with self.assertRaises(ControlError) as caught:
            Core(self.config).result(self.exchange/'wrong-types.zip')
        self.assertEqual(caught.exception.code,'core_protocol_error')

    def test_child_retains_target_locks_if_controller_handle_is_closed(self):
        from concurrent.futures import ThreadPoolExecutor
        import time
        from specroad_control.automation import prompt_for
        self.settings(slow=True)
        engine=Engine(self.config,self.paths,Gate(),core=FakeCore())
        self.addCleanup(engine.close)
        directory=self.paths.state/'held-child'; private_dir(directory)
        with ThreadPoolExecutor(2) as pool:
            future=pool.submit(engine.codex.run,prompt_for(self.seed),SCHEMA,directory)
            try:
                deadline=time.monotonic()+5
                while not (self.codex_home/'started').exists() and time.monotonic()<deadline:
                    time.sleep(.02)
                self.assertTrue((self.codex_home/'started').exists())
                engine.close()
                with self.assertRaises(ControlError) as caught:
                    Engine(self.config,self.paths,Gate(),core=FakeCore())
                self.assertEqual(caught.exception.code,'already_running')
            finally:
                (self.codex_home/'release').write_text('yes')
            self.assertEqual(future.result(timeout=5)['status'],'no_work')

    def test_out_of_order_exec_events_are_not_completion(self):
        from specroad_control.automation import prompt_for
        self.settings(misordered=True)
        directory=self.paths.state/'misordered'; private_dir(directory)
        with self.assertRaises(ControlError):
            Codex(self.config).run(prompt_for(self.seed),SCHEMA,directory)

    def test_two_exec_turns_are_not_treated_as_single_turn(self):
        from specroad_control.automation import prompt_for
        self.settings(extra_turn=True)
        directory=self.paths.state/'two-turns'; private_dir(directory)
        with self.assertRaises(ControlError):
            Codex(self.config).run(prompt_for(self.seed),SCHEMA,directory)

    def test_inotify_overflow_requests_rescan_not_model_work(self):
        from unittest.mock import patch
        from specroad_control.notifications import Notifications,HEADER,IN_Q_OVERFLOW
        watcher=Notifications(self.exchange); self.addCleanup(watcher.close)
        with patch('specroad_control.notifications.os.read',side_effect=[HEADER.pack(-1,IN_Q_OVERFLOW,0,0),BlockingIOError()]):
            self.assertTrue(watcher.consume())
        self.assertFalse((self.codex_home/'calls.jsonl').exists())


class LedgerContext:
    def __init__(self,paths,config): self.paths,self.config=paths,config
    def __enter__(self):
        self.ledger=Ledger(self.paths.state/'automation.sqlite3',scope(self.config))
        return self.ledger
    def __exit__(self,*_args): self.ledger.close()
