"""Real worker, inotify, IPC and child processes; Codex/Core are offline doubles."""
import json
import signal
import time
from specroad_control.ipc import request
from specroad_control.local import json_read
from codex_control_tests.automation_support import AutomationCase, read_package


class EventWorkerTests(AutomationCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(lambda: (self.codex_home / 'release').write_text('yes') if self.codex_home.exists() else None)

    def wait_for(self, predicate, timeout=8):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            value=predicate()
            if value: return value
            time.sleep(.02)
        self.fail('Expected state transition did not occur')

    def spawn(self):
        child,reply=super().spawn()
        self.addCleanup(lambda: (self.codex_home / 'release').write_text('yes') if self.codex_home.exists() else None)
        return child,reply

    def state(self): return request(self.paths,'status')['state']
    def count(self):
        path=self.codex_home/'calls.jsonl'
        return len(path.read_text().splitlines()) if path.exists() else 0

    def test_real_exchange_followup_runs_exactly_one_more_turn(self):
        self.settings(mode='patch')
        child,_=self.spawn()
        self.wait_for(lambda:self.state()['automation']['stage']=='waiting_result' and not self.state()['active_job'])
        self.assertEqual(self.count(),1)
        patch=next(self.exchange.glob('dev-*.zip'))
        self.result('followup.zip',previous=self.seed,patch_sha=read_package(patch)['sha256'])
        self.wait_for(lambda:self.count()==2 and not self.state()['active_job'])
        self.assertEqual(self.count(),2)
        request(self.paths,'stop'); self.assertEqual(child.wait(timeout=5),0)

    def test_pause_finishes_child_but_starts_nothing_new(self):
        self.settings(mode='patch',slow=True)
        child,_=self.spawn()
        self.wait_for(lambda:(self.codex_home/'started').exists())
        self.assertEqual(request(self.paths,'pause')['state']['phase'],'pausing')
        self.assertIsNone(child.poll())
        (self.codex_home/'release').write_text('yes')
        self.wait_for(lambda:self.state()['phase']=='paused')
        patch=read_package(next(self.exchange.glob('dev-*.zip')))
        self.result('pending.zip',previous=self.seed,patch_sha=patch['sha256'])
        time.sleep(.2)
        self.assertEqual(self.count(),1)
        request(self.paths,'resume')
        self.wait_for(lambda:self.count()==2)
        request(self.paths,'stop'); self.assertEqual(child.wait(timeout=5),0)

    def test_stop_waits_for_active_child_without_killing(self):
        self.settings(mode='patch',slow=True)
        child,_=self.spawn()
        self.wait_for(lambda:(self.codex_home/'started').exists())
        self.assertEqual(request(self.paths,'stop')['state']['phase'],'stopping')
        time.sleep(.15); self.assertIsNone(child.poll())
        (self.codex_home/'release').write_text('yes')
        self.assertEqual(child.wait(timeout=5),0)
        self.assertEqual(self.count(),1)
        self.assertEqual(json_read(self.paths.state_file)['phase'],'stopped')

    def test_sigterm_only_stops_after_active_child(self):
        self.settings(slow=True)
        child,_=self.spawn()
        self.wait_for(lambda:(self.codex_home/'started').exists())
        child.send_signal(signal.SIGTERM)
        self.wait_for(lambda:self.state()['phase']=='stopping')
        self.assertIsNone(child.poll())
        (self.codex_home/'release').write_text('yes')
        self.assertEqual(child.wait(timeout=5),0)

    def test_status_and_unrelated_events_never_start_another_turn(self):
        self.settings(mode='patch')
        child,_=self.spawn()
        self.wait_for(lambda:not self.state()['active_job'] and self.count()==1)
        for n in range(10):
            (self.exchange/f'unrelated-{n}.txt').write_text('noise')
            self.state()
        self.wait_for(lambda:not self.state()['active_job'])
        time.sleep(.2)
        self.assertEqual(self.count(),1)
        request(self.paths,'stop'); child.wait(timeout=5)

    def test_automatic_mode_survives_stop_restart_without_replay(self):
        self.settings(mode='patch')
        child,_=self.spawn()
        self.wait_for(lambda:self.count()==1 and not self.state()['active_job'])
        request(self.paths,'stop'); child.wait(timeout=5)
        second,_=self.spawn()
        self.wait_for(lambda:not self.state()['active_job'])
        self.assertEqual(self.count(),1)
        request(self.paths,'stop'); second.wait(timeout=5)
