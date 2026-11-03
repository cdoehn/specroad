from dataclasses import replace
import json
from pathlib import Path
import selectors
import shutil
from specroad_control.automation import Engine, Gate, scope
from specroad_control.config import load, parse, render
from specroad_control.core import Core
from specroad_control.errors import ControlError
from specroad_control.exchange import Exchange, hint
from specroad_control.ledger import Ledger
from specroad_control.notifications import Notifications
from codex_control_tests.automation_support import AutomationCase, FakeCore, FakeCodex, package


class AutomationTests(AutomationCase):
    def engine(self, mode='patch'):
        codex=FakeCodex(self, mode)
        engine=Engine(self.config,self.paths,Gate(),core=FakeCore(),codex=codex)
        self.addCleanup(engine.close)
        return engine,codex

    def test_exact_once_then_wait_without_another_model_call(self):
        engine,codex=self.engine()
        self.assertTrue(engine.tick()['again'])
        for _ in range(3): self.assertFalse(engine.tick()['again'])
        self.assertEqual(codex.calls,1)
        self.assertEqual(engine.summary()['stage'],'waiting_result')

    def test_followup_result_is_bound_to_source_and_patch(self):
        engine,codex=self.engine(); engine.tick()
        patch=engine.exchange.patches(self.seed)[0]
        self.result('next.zip',previous=self.seed,patch_sha=patch['sha256'])
        engine.tick(); self.assertEqual(codex.calls,2)
        engine.tick(); self.assertEqual(codex.calls,2)

    def test_wrong_patch_hash_cannot_trigger(self):
        engine,codex=self.engine(); engine.tick()
        self.result('wrong.zip',previous=self.seed,patch_sha='0'*64)
        engine.tick(); self.assertEqual(codex.calls,1)

    def test_unrelated_control_result_does_not_trigger(self):
        engine,codex=self.engine(); engine.tick()
        self.result('control.zip',binding={**self.binding,'repo_id':'00000000-0000-4000-8000-000000000001'})
        engine.tick(); self.assertEqual(codex.calls,1)

    def test_existing_bound_patch_is_adopted_without_model(self):
        package(self.exchange/'already.zip',{'kind':'patch','binding':self.binding})
        engine,codex=self.engine(); engine.tick(); self.assertEqual(codex.calls,0)
        self.assertEqual(engine.summary()['stage'],'waiting_result')

    def test_ambiguous_patches_are_not_guessed(self):
        for n in range(2): package(self.exchange/f'{n}.zip',{'kind':'patch','binding':self.binding,'variant':n})
        engine,codex=self.engine()
        with self.assertRaises(ControlError): engine.tick()
        self.assertEqual(codex.calls,0)

    def test_failure_is_not_replayed(self):
        engine,codex=self.engine('failure')
        self.assertTrue(engine.tick()['halted']); self.assertTrue(engine.tick()['halted'])
        self.assertEqual(codex.calls,1)

    def test_no_work_finishes_without_loop(self):
        engine,codex=self.engine('no_work')
        self.assertTrue(engine.tick()['halted']); self.assertTrue(engine.tick()['halted'])
        self.assertEqual(codex.calls,1)

    def test_pause_prevents_dispatch(self):
        engine,codex=self.engine(); engine.gate.set(False)
        engine.tick(); self.assertEqual(codex.calls,0)
        engine.gate.set(True); engine.tick(); self.assertEqual(codex.calls,1)

    def test_restart_retains_result_claim(self):
        engine,codex=self.engine(); engine.tick(); engine.close()
        next_engine=Engine(self.config,self.paths,Gate(),core=FakeCore(),codex=codex)
        with next_engine: next_engine.tick()
        self.assertEqual(codex.calls,1)

    def test_same_target_cannot_have_two_controllers(self):
        engine,_=self.engine()
        with self.assertRaises(ControlError) as caught: Engine(self.config,self.paths,Gate(),core=FakeCore())
        self.assertEqual(caught.exception.code,'already_running')

    def test_result_can_move_to_archive_without_replay(self):
        engine,codex=self.engine(); engine.tick()
        archive=self.exchange/'PatchHarbor-Archive'; archive.mkdir()
        Path(self.seed['path']).rename(archive/'renamed.zip')
        engine.tick(); self.assertEqual(codex.calls,1)

    def test_partial_zip_cannot_be_a_candidate(self):
        (self.exchange/'bad.zip').write_bytes(b'PK partial')
        self.assertIsNone(hint(self.exchange/'bad.zip'))

    def test_changed_seed_fails_closed(self):
        package(Path(self.seed['path']), {**self.seed, 'changed': True})
        engine,codex=self.engine()
        with self.assertRaises(ControlError): engine.tick()
        self.assertEqual(codex.calls,0)

    def test_old_config_remains_inert(self):
        from specroad_control.local import write_private
        write_private(self.paths.config,('format_version=1\n[develop]\nrepository='+json.dumps(str(self.dev))+'\nsession_id=""\n[patchharbor]\nexchange='+json.dumps(str(self.exchange))+'\n').encode())
        self.assertFalse(load(self.paths).enabled)

    def test_private_config_roundtrip(self):
        self.assertEqual(load(self.paths),self.config)
        self.assertEqual(self.paths.config.stat().st_mode&0o777,0o600)

    def test_core_protocol_subprocess(self):
        core=Core(self.config)
        got=core.result(Path(self.seed['path']))
        self.assertEqual(got['sha256'],self.seed['sha256'])
        p=package(self.exchange/'patch.zip',{'kind':'patch','binding':self.binding})
        self.assertEqual(core.validate(Path(p['path']),self.seed)['sha256'],p['sha256'])

    def test_inotify_delivers_actual_atomic_publication(self):
        with selectors.DefaultSelector() as selector:
            watcher=Notifications(self.exchange); self.addCleanup(watcher.close)
            selector.register(watcher,selectors.EVENT_READ)
            self.result('new.zip')
            self.assertTrue(selector.select(2))
            self.assertTrue(watcher.consume())
            self.assertFalse(watcher.consume())

    def test_ledger_scope_change_rejected_without_reset(self):
        path=self.paths.state/'history.sqlite3'
        ledger=Ledger(path,'one',initial=self.seed); ledger.close()
        before=path.read_bytes()
        with self.assertRaises(ControlError): Ledger(path,'two')
        self.assertEqual(before,path.read_bytes())

    def test_native_rejection_is_not_taken_as_a_valid_hint(self):
        self.result('rejected.zip',reject=True)
        exchange=Exchange(self.config,FakeCore())
        self.assertEqual(len(list(exchange.candidates('result',lambda _m:True))),1)
