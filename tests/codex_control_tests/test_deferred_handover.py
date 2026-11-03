"""Real isolated Control worker/IPC; Codex and native-reader protocol doubles only."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from specroad_control.config import load, render
from specroad_control.errors import ControlError
from specroad_control.handover import handover
from specroad_control.handover_queue import enqueue, startup, REQUEST, STATUS
from specroad_control.ipc import request
from specroad_control.local import REPO, write_private
from codex_control_tests.test_thread_handover import HandoverCase


class DeferredCase(HandoverCase):
    def setUp(self):
        super().setUp()
        self.old_cwd = self.home/'control-work'
        self.old_cwd.mkdir()
        self.config = replace(self.config, transport='app-server-proxy')
        write_private(self.paths.config, render(self.config).encode())
        self.thread_settings()

    def thread_settings(self, *, old='notLoaded', new='active', old_cwd=None, new_cwd=None):
        self.settings(thread=self.target, mode='no_work', threads={
            self.thread: {'returned_id': self.thread, 'cwd': str(old_cwd or self.old_cwd), 'thread_status': old},
            self.target: {'returned_id': self.target, 'cwd': str(new_cwd or self.target_cwd), 'thread_status': new}})

    def queue(self, *, resume=True, **kwargs):
        return enqueue(self.paths, thread_id=self.target, thread_cwd=str(self.target_cwd),
                       from_cwd=str(kwargs.get('from_cwd', self.old_cwd)), resume_after=resume)

    def worker(self):
        log = tempfile.TemporaryFile()
        self.addCleanup(log.close)
        child = subprocess.Popen([sys.executable, '-B', str(self.paths.home / 'releases' / ('a' * 40) / 'control'), 'run'],
                                 env=dict(os.environ), stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        def close():
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=20)
        self.addCleanup(close)
        self.worker_log = log
        self.child = child
        return child

    def await_state(self, predicate, *, timeout=12):
        deadline = time.monotonic()+timeout
        last = None
        while time.monotonic() < deadline:
            if self.child.poll() is not None:
                self.worker_log.seek(0)
                self.fail('Isolated worker stopped: '+self.worker_log.read().decode())
            try:
                last = request(self.paths, 'status')['state']
                if predicate(last):
                    return last
            except ControlError as exc:
                if exc.code != 'not_running':
                    raise
            time.sleep(.02)
        self.fail('Isolated worker did not reach expected state: '+repr(last))

    def calls(self):
        path = self.codex_home/'calls.jsonl'
        return path.read_text().splitlines() if path.exists() else []


class DeferredHandoverTests(DeferredCase):
    def test_explicit_old_cwd_allows_direct_handover_without_rewriting_old_thread(self):
        self.thread_settings(new='idle')
        before = self.rows()
        handover(self.paths, thread_id=self.target, thread_cwd=str(self.target_cwd), from_cwd=str(self.old_cwd))
        self.assertEqual(self.rows(), before)
        self.assertEqual(load(self.paths).session_id, self.target)
        receipt = self.receipts()[0]
        self.assertEqual(receipt['version'], 2)
        self.assertEqual(receipt['from_thread_cwd'], str(self.old_cwd))
        self.assertIsNone(receipt['request_sha256'])
        self.assertLessEqual({d.get('method') for d in self.codex_daemon.server.requests},
                             {'initialize', 'initialized', 'thread/read'})

    def test_old_cwd_change_still_requires_explicit_binding(self):
        self.thread_settings(new='idle')
        with self.assertRaises(ControlError) as caught:
            self.transfer()
        self.assertEqual(caught.exception.code, 'wrong_thread_repository')
        self.assertEqual(load(self.paths), self.config)

    def test_queue_preserves_config_history_and_pause_without_starting_anything(self):
        old_config, old_rows = self.paths.config.read_bytes(), self.rows()
        state = self.paths.state_file.read_bytes()
        result = self.queue()
        self.assertTrue(result['queued'])
        self.assertFalse(result['model_called'])
        self.assertFalse(result['service_started'])
        self.assertEqual(self.paths.config.read_bytes(), old_config)
        self.assertEqual(self.rows(), old_rows)
        self.assertEqual(self.paths.state_file.read_bytes(), state)
        self.assertEqual(self.calls(), [])

    def test_identical_queued_request_is_idempotent(self):
        self.queue()
        before = (self.paths.state/REQUEST).read_bytes()
        self.assertTrue(self.queue()['already_queued'])
        self.assertEqual((self.paths.state/REQUEST).read_bytes(), before)

    def test_changed_request_cannot_replace_existing_authority(self):
        self.queue()
        before = (self.paths.state/REQUEST).read_bytes()
        with self.assertRaises(ControlError) as caught:
            self.queue(resume=False)
        self.assertEqual(caught.exception.code, 'handover_request_changed')
        self.assertEqual((self.paths.state/REQUEST).read_bytes(), before)

    def test_ordinary_operations_are_blocked_while_queued(self):
        self.queue()
        with self.assertRaises(ControlError) as caught:
            load(self.paths)
        self.assertEqual(caught.exception.code, 'handover_deferred')
        self.assertEqual(startup(self.paths)[0], self.config)

    def test_worker_waits_for_active_chat_then_resumes_exact_new_thread_once(self):
        self.queue()
        self.worker()
        state = self.await_state(lambda s: (s['automation'] or {}).get('new_thread_status') == 'active')
        self.assertEqual(state['automation']['stage'], 'handover_waiting')
        self.assertEqual(self.calls(), [])
        self.thread_settings(new='idle')
        state = self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'no_work' and not s['active_job'])
        self.assertIsNone(state['runtime_error'])
        self.assertEqual(load(self.paths).session_id, self.target)
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse((self.paths.state/REQUEST).exists())
        self.assertEqual(len(list((self.paths.state/'handovers').glob('*.json'))), 1)
        dispatch = json.loads((self.codex_home/'request.json').read_text())
        self.assertEqual(dispatch['threadId'], self.target)
        self.assertEqual(dispatch['cwd'], str(self.target_cwd))
        self.assertEqual(dispatch['sandboxPolicy']['writableRoots'], [str(self.target_cwd), str(self.exchange)])

    def test_without_resume_authority_new_worker_remains_paused(self):
        self.queue(resume=False)
        self.thread_settings(new='idle')
        before = self.rows()
        self.worker()
        self.await_state(lambda s: 'handover_request_id' not in s and s['phase'] == 'paused')
        self.assertEqual(load(self.paths).session_id, self.target)
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.calls(), [])

    def test_pause_waits_for_metadata_then_prevents_handover_until_resume(self):
        self.queue()
        self.worker()
        self.await_state(lambda s: (s['automation'] or {}).get('new_thread_status') == 'active')
        request(self.paths, 'pause')
        self.await_state(lambda s: s['phase']=='paused' and not s['active_job'])
        self.thread_settings(new='idle')
        self.assertEqual(self.paths.config.read_bytes(), render(self.config).encode())
        self.assertEqual(self.calls(), [])
        request(self.paths, 'resume')
        self.await_state(lambda s: (s['automation'] or {}).get('stage') == 'no_work' and not s['active_job'])
        self.assertEqual(len(self.calls()), 1)

    def test_stop_while_waiting_leaves_request_and_no_model(self):
        self.queue()
        child = self.worker()
        self.await_state(lambda s: (s['automation'] or {}).get('new_thread_status') == 'active')
        request(self.paths, 'stop')
        self.assertEqual(child.wait(timeout=10), 0)
        self.assertEqual(self.calls(), [])
        self.assertTrue((self.paths.state/REQUEST).exists())
        self.assertEqual(self.paths.config.read_bytes(), render(self.config).encode())

    def test_unknown_thread_status_is_not_queued(self):
        self.thread_settings(new='systemError')
        with self.assertRaises(ControlError) as caught:
            self.queue()
        self.assertEqual(caught.exception.code, 'dev_thread_busy')
        self.assertFalse((self.paths.state/REQUEST).exists())

    def test_invalid_old_cwd_does_not_broaden_new_thread_permissions(self):
        with self.assertRaises(ControlError) as caught:
            self.queue(from_cwd=self.dev)
        self.assertEqual(caught.exception.code, 'handover_cwd_mismatch')
        self.thread_settings(new_cwd=self.exchange)
        with self.assertRaises(ControlError) as caught:
            self.queue()
        self.assertEqual(caught.exception.code, 'handover_cwd_mismatch')

    def test_changed_config_after_queue_blocks_start(self):
        self.queue()
        write_private(self.paths.config, self.paths.config.read_bytes()+b'\n# external edit\n')
        with self.assertRaises(ControlError) as caught:
            startup(self.paths)
        self.assertEqual(caught.exception.code, 'handover_request_changed')

    def test_prior_mutation_marker_blocks_automatic_replay(self):
        self.queue()
        from specroad_control.handover_queue import request_read, state_write
        state_write(self.paths, request_read(self.paths), 'applying')
        with self.assertRaises(ControlError) as caught:
            startup(self.paths)
        self.assertEqual(caught.exception.code, 'handover_deferred_blocked')
        self.assertEqual(self.calls(), [])
