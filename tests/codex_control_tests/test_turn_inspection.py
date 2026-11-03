from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import time
from specroad_control.codex import Codex
from specroad_control.codex_proxy import Proxy
from specroad_control.errors import ControlError
from specroad_control.job_contract import prompt_for, SCHEMA
from specroad_control.local import json_read, private_dir
from codex_control_tests.automation_support import AutomationCase


class TurnInspectionTests(AutomationCase):
    def setUp(self):
        super().setUp()
        self.config=replace(self.config,transport='app-server-proxy')
        self.directory=self.paths.state/'test-turn';private_dir(self.directory)

    def failed(self):
        self.settings(overload=True)
        with self.assertRaises(ControlError) as caught:
            Codex(self.config).run(prompt_for(self.seed),SCHEMA,self.directory)
        self.assertEqual(caught.exception.details['codex_error'],'serverOverloaded')

    def test_real_websocket_stores_structured_failure_without_a_second_turn(self):
        self.failed()
        failure=json_read(self.directory/'failure.json')
        self.assertEqual(failure['turn_status'],'failed')
        self.assertFalse(failure['codex_will_retry'])
        with Proxy(self.config) as proxy: live=proxy.inspect_turn(failure['turn_id'])
        self.assertEqual(live['turn']['status'],'failed')
        self.assertTrue(live['turn']['items'])
        self.assertEqual(len((self.codex_home/'calls.jsonl').read_text().splitlines()),1)

    def test_history_read_falls_back_only_for_explicit_unsupported_api(self):
        self.failed(); self.settings(legacy_history=True)
        with Proxy(self.config) as proxy: live=proxy.inspect_turn('test-turn')
        self.assertEqual(live['turn']['id'],'test-turn')
        self.assertEqual(len((self.codex_home/'calls.jsonl').read_text().splitlines()),1)

    def test_unknown_turn_history_fails_closed(self):
        with Proxy(self.config) as proxy:
            with self.assertRaises(ControlError): proxy.inspect_turn('unknown')
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_active_thread_is_returned_without_start_or_history_guess(self):
        self.settings(thread_status='active')
        with Proxy(self.config) as proxy: live=proxy.inspect_turn('unknown')
        self.assertEqual(live,{'thread_status':'active','turn':None})
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_idle_notification_without_terminal_event_does_not_end_long_running_work(self):
        self.settings(slow=True,mode='no_work',pre_events=[{'method':'thread/status/changed',
                        'params':{'threadId':self.thread,'status':{'type':'idle'}}}])
        pool=ThreadPoolExecutor(1)
        try:
            future=pool.submit(Codex(self.config).run,prompt_for(self.seed),SCHEMA,self.directory)
            end=time.monotonic()+4
            while not (self.codex_home/'started').exists() and time.monotonic()<end:time.sleep(.02)
            time.sleep(.1)
            self.assertFalse(future.done())
            (self.codex_home/'release').write_text('go')
            self.assertEqual(future.result(4)['status'],'no_work')
            self.assertEqual(len((self.codex_home/'calls.jsonl').read_text().splitlines()),1)
        finally:
            (self.codex_home/'release').write_text('go')
            pool.shutdown(wait=True)
