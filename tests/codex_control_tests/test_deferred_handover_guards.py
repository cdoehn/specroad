"""Lifecycle races, restart authority and preserved evidence at publication boundaries."""
from contextlib import closing, redirect_stdout, redirect_stderr
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from unittest.mock import patch

from specroad_control.cli import main
from specroad_control.config import load
from specroad_control.errors import ControlError
from specroad_control.handover import handover
from specroad_control.handover_evidence import canonical, receipt
from specroad_control.handover_queue import (startup, request_read, state_read, public_status,
                                           request_hash, REQUEST, STATUS)
from specroad_control.ipc import request
from specroad_control.local import REPO, write_private, lock
from codex_control_tests.test_deferred_handover import DeferredCase


HOOK = r'''
from pathlib import Path
import os,sys,time
from specroad_control import handover_queue as q
from specroad_control.local import Paths
from specroad_control.daemon import run
home=Path(sys.argv[1]); mode=sys.argv[2]
if mode=='before_commit':
 original=q._handover_locked
 def change(*a,**kw):
  (home/'barrier').write_text('ready')
  while not (home/'release').exists(): time.sleep(.01)
  return original(*a,**kw)
 q._handover_locked=change
elif mode=='after_scope':
 original=q.state_write
 def change(*a,**kw):
  if len(a)>2 and a[2]=='complete': os._exit(73)
  return original(*a,**kw)
 q.state_write=change
elif mode=='before_cleanup':
 def change(*a,**kw):
  os._exit(74)
 q.finish_request=change
elif mode=='changed_completion':
 original=q.finish_request
 def change(paths,doc):
  import sqlite3
  with sqlite3.connect(paths.state/'automation.sqlite3') as db:
   db.execute('UPDATE jobs SET updated=updated+1')
  return original(paths,doc)
 q.finish_request=change
raise SystemExit(run(Paths.discover()))
'''


class DeferredHandoverGuardTests(DeferredCase):
    def hook_worker(self, mode):
        real = subprocess.Popen
        def launch(_args, **kwargs):
            return real([sys.executable, '-B', '-c', HOOK, str(self.home), mode], cwd=REPO, **kwargs)
        with patch('codex_control_tests.test_deferred_handover.subprocess.Popen', side_effect=launch):
            return self.worker()

    def barrier(self):
        end = time.monotonic()+10
        while not (self.home/'barrier').exists() and time.monotonic()<end:
            self.assertIsNone(self.child.poll())
            time.sleep(.02)
        self.assertTrue((self.home/'barrier').exists())

    def test_pause_during_authorized_transfer_prevents_post_transfer_model(self):
        self.queue()
        self.thread_settings(new='idle')
        self.hook_worker('before_commit')
        self.barrier()
        reply = request(self.paths, 'pause')
        self.assertEqual(reply['state']['desired'], 'paused')
        (self.home/'release').write_text('go')
        self.await_state(lambda s: 'handover_request_id' not in s and s['phase']=='paused')
        self.assertEqual(load(self.paths).session_id, self.target)
        self.assertEqual(self.calls(), [])

    def test_stop_during_transfer_finishes_history_but_never_starts_development(self):
        self.queue()
        self.thread_settings(new='idle')
        child = self.hook_worker('before_commit')
        self.barrier()
        self.assertEqual(request(self.paths, 'stop')['state']['phase'], 'stopping')
        (self.home/'release').write_text('go')
        self.assertEqual(child.wait(timeout=12), 0)
        self.assertEqual(load(self.paths).session_id, self.target)
        self.assertEqual(self.calls(), [])
        self.assertFalse((self.paths.state/REQUEST).exists())

    def test_pause_survives_controlled_stop_and_restart_of_waiting_worker(self):
        self.queue()
        child = self.worker()
        self.await_state(lambda s: (s['automation'] or {}).get('new_thread_status')=='active')
        request(self.paths, 'pause')
        self.await_state(lambda s:s['phase']=='paused' and not s['active_job'])
        request(self.paths, 'stop')
        self.assertEqual(child.wait(timeout=10), 0)
        self.thread_settings(new='idle')
        self.worker()
        state=self.await_state(lambda s:s['phase']=='paused' and not s['active_job'])
        self.assertIn('handover_request_id', state)
        self.assertEqual(self.calls(), [])
        request(self.paths, 'resume')
        self.await_state(lambda s:(s['automation'] or {}).get('stage')=='no_work' and not s['active_job'])
        self.assertEqual(len(self.calls()), 1)

    def test_crash_after_scope_change_is_blocked_on_restart_without_replay(self):
        self.queue()
        self.thread_settings(new='idle')
        child=self.hook_worker('after_scope')
        self.assertEqual(child.wait(timeout=12), 73)
        self.assertEqual(self.calls(), [])
        self.assertEqual(state_read(self.paths,request_read(self.paths))['phase'], 'applying')
        with self.assertRaises(ControlError) as caught:
            startup(self.paths)
        self.assertEqual(caught.exception.code,'handover_deferred_blocked')

    def test_non_resume_authority_is_durable_before_queue_removal(self):
        self.queue(resume=False)
        self.thread_settings(new='idle')
        child=self.hook_worker('before_cleanup')
        self.assertEqual(child.wait(timeout=12), 74)
        state=json.loads(self.paths.state_file.read_text())
        self.assertEqual(state['desired'], 'paused')
        self.assertEqual(state_read(self.paths,request_read(self.paths))['phase'], 'complete')
        self.assertEqual(self.calls(), [])
        with self.assertRaises(ControlError) as caught:
            startup(self.paths)
        self.assertEqual(caught.exception.code,'handover_deferred_blocked')

    def test_corrupt_sidecar_is_preserved_when_live_worker_blocks(self):
        self.queue()
        self.worker()
        self.await_state(lambda s:(s['automation'] or {}).get('new_thread_status')=='active')
        raw=(self.paths.state/REQUEST).read_bytes()
        write_private(self.paths.state/STATUS,b'{}')
        self.await_state(lambda s:s['runtime_error'] is not None and not s['active_job'])
        self.assertEqual((self.paths.state/STATUS).read_bytes(),b'{}')
        self.assertEqual((self.paths.state/REQUEST).read_bytes(),raw)
        self.assertEqual(self.calls(),[])

    def test_completed_history_change_keeps_start_barrier_before_dispatch(self):
        self.queue()
        self.thread_settings(new='idle')
        self.hook_worker('changed_completion')
        self.await_state(lambda s:s['runtime_error']=='handover_request_changed' and not s['active_job'])
        self.assertTrue((self.paths.state/REQUEST).exists())
        self.assertEqual(self.calls(),[])

    def test_changed_request_is_preserved_when_live_worker_blocks(self):
        self.queue()
        self.worker()
        self.await_state(lambda s:(s['automation'] or {}).get('new_thread_status')=='active')
        doc=request_read(self.paths)
        doc['resume_after']=False
        changed=canonical(doc)
        write_private(self.paths.state/REQUEST,changed)
        old_state=(self.paths.state/STATUS).read_bytes()
        self.await_state(lambda s:s['runtime_error'] is not None and not s['active_job'])
        self.assertEqual((self.paths.state/REQUEST).read_bytes(),changed)
        self.assertEqual((self.paths.state/STATUS).read_bytes(),old_state)
        self.assertEqual(self.calls(),[])

    def test_changed_history_during_wait_does_not_gain_a_new_claim(self):
        self.queue()
        self.worker()
        self.await_state(lambda s:(s['automation'] or {}).get('new_thread_status')=='active')
        with closing(sqlite3.connect(self.paths.state/'automation.sqlite3')) as db, db:
            db.execute('UPDATE jobs SET updated=updated+1')
        changed=self.rows()
        self.await_state(lambda s:s['runtime_error']=='handover_request_changed' and not s['active_job'])
        self.assertEqual(self.rows(),changed)
        self.assertEqual(self.calls(),[])

    def test_unknown_status_after_queue_blocks_without_model(self):
        self.queue()
        self.thread_settings(new='systemError')
        self.worker()
        self.await_state(lambda s:s['runtime_error']=='dev_thread_busy' and not s['active_job'])
        self.assertEqual(self.calls(),[])

    def test_old_thread_also_must_become_idle_before_transfer(self):
        self.thread_settings(old='active',new='idle')
        self.queue()
        self.worker()
        self.await_state(lambda s:(s['automation'] or {}).get('old_thread_status')=='active')
        self.assertEqual(self.calls(),[])
        self.thread_settings(new='idle')
        self.await_state(lambda s:(s['automation'] or {}).get('stage')=='no_work' and not s['active_job'])
        self.assertEqual(len(self.calls()),1)

    def test_orphan_sidecar_is_not_overwritten_by_new_request(self):
        write_private(self.paths.state/STATUS,b'{"foreign":"evidence"}')
        with self.assertRaises(ControlError) as caught:
            self.queue()
        self.assertEqual(caught.exception.code,'handover_request_conflict')
        self.assertEqual((self.paths.state/STATUS).read_bytes(),b'{"foreign":"evidence"}')
        self.assertFalse((self.paths.state/REQUEST).exists())
        for operation in (load, startup):
            with self.assertRaises(ControlError) as caught:
                operation(self.paths)
            self.assertEqual(caught.exception.code,'handover_deferred')
        self.assertEqual(public_status(self.paths),{'phase':'blocked','error':'handover_request_conflict'})

    def test_malformed_or_unbound_request_is_not_treated_as_absence(self):
        self.queue()
        original=request_read(self.paths)
        for name,value in (('version',True),('resume_after',1),('extra','unknown'),('history_sha256','broken')):
            with self.subTest(name=name):
                write_private(self.paths.state/REQUEST,canonical({**original,name:value}))
                with self.assertRaises(ControlError) as caught:
                    startup(self.paths)
                self.assertEqual(caught.exception.code,'invalid_handover_request')
        self.assertEqual(self.calls(),[])

    def test_status_before_start_reports_armed_request(self):
        self.queue()
        output=io.StringIO()
        with patch('specroad_control.cli.service.inspect',return_value={'ActiveState':'inactive'}),redirect_stdout(output):
            self.assertEqual(main(['status']),0)
        reply=json.loads(output.getvalue())
        self.assertEqual(reply['handover'],{'phase':'armed','resume_after':True,'error':None})
        self.assertFalse(reply['worker_reachable'])

    def test_status_can_report_broken_request_without_repair(self):
        self.queue()
        write_private(self.paths.state/REQUEST,b'{}')
        self.assertEqual(public_status(self.paths),{'phase':'blocked','error':'invalid_handover_request'})
        self.assertEqual((self.paths.state/REQUEST).read_bytes(),b'{}')

    def test_cli_requires_deferred_mode_for_resume_authority(self):
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as caught:
            main(['handover','--thread-id',self.target,'--thread-cwd',str(self.target_cwd),'--resume-after'])
        self.assertEqual(caught.exception.code,2)
        with redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            main(['check','--defer'])

    def test_direct_crash_recovery_binds_explicit_original_cwd(self):
        self.thread_settings(new='idle')
        def fail_config(path,data,**kw):
            if path==self.paths.config:
                raise OSError('injected failure')
            return write_private(path,data,**kw)
        kwargs={'thread_id':self.target,'thread_cwd':str(self.target_cwd),'from_cwd':str(self.old_cwd)}
        with patch('specroad_control.handover.write_private',side_effect=fail_config),self.assertRaises(OSError):
            handover(self.paths,**kwargs)
        with self.assertRaises(ControlError) as caught:
            handover(self.paths,**{**kwargs,'from_cwd':str(self.dev)})
        self.assertEqual(caught.exception.code,'invalid_handover_intent')
        self.assertTrue(handover(self.paths,**kwargs)['resumed_handover'])
        self.assertEqual(len(self.receipts()),1)

    def test_original_and_new_receipt_versions_share_one_valid_chain(self):
        self.thread_settings(new='idle',old_cwd=self.dev)
        handover(self.paths,thread_id=self.target,thread_cwd=str(self.target_cwd))
        self.assertNotIn('version',self.receipts()[0])
        self.thread,self.target=self.target,self.thread
        self.thread_settings(new='idle')
        handover(self.paths,thread_id=self.target,thread_cwd=str(self.target_cwd),from_cwd=str(self.old_cwd))
        config=load(self.paths)
        with closing(self.database(config)):
            self.assertEqual(len(self.receipts()),2)
        self.assertEqual(self.receipts()[1]['version'],2)
