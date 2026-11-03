from dataclasses import replace
from unittest.mock import patch
import json
import math
from specroad_control.codex import Codex
from specroad_control.codex_proxy import Proxy
from specroad_control.errors import ControlError
from specroad_control.job_contract import prompt_for,SCHEMA
from specroad_control.local import private_dir,json_read
from specroad_control.telemetry import record
from codex_control_tests.automation_support import AutomationCase


class RetryObservationTests(AutomationCase):
    def setUp(self):
        super().setUp();self.config=replace(self.config,transport='app-server-proxy')
        self.directory=self.paths.state/'observation';private_dir(self.directory)

    def test_disconnect_observes_running_turn_without_replacement_or_interruption(self):
        self.settings(disconnect_turn=True)
        with self.assertRaises(ControlError) as caught:
            Codex(self.config).run(prompt_for(self.seed),SCHEMA,self.directory)
        self.assertEqual(caught.exception.code,'codex_connection_lost')
        self.assertEqual(caught.exception.details['thread_status'],'active')
        observation=json_read(self.directory/'observation.json')
        self.assertEqual(observation['decision'],'preserve_active')
        self.assertFalse((self.directory/'failure.json').exists())
        self.assertEqual(len((self.codex_home/'calls.jsonl').read_text().splitlines()),1)

    def test_malformed_runtime_status_does_not_become_idle(self):
        with patch.object(Proxy,'inspect_thread',return_value={'status':None}):
            with Proxy(self.config) as proxy:
                self.assertEqual(proxy.inspect_turn('turn')['thread_status'],'unknown')
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_idle_metadata_without_exact_terminal_history_is_not_completion(self):
        with Proxy(self.config) as proxy:
            with self.assertRaises(ControlError):proxy.inspect_turn('never-started')
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_error_kind_unsupported_is_distinct_from_unknown_connection(self):
        with Proxy(self.config) as proxy:
            real=proxy.call
            def call(method,params):
                if method=='thread/turns/list':raise ControlError('codex_request_rejected','no',details={'rpc_code':-32001})
                return real(method,params)
            with patch.object(proxy,'call',side_effect=call):
                with self.assertRaises(ControlError) as caught:proxy.inspect_turn('test')
                self.assertEqual(caught.exception.details['rpc_code'],-32001)

    def test_nan_log_values_do_not_mask_the_original_error(self):
        doc=record('automation_error',error='codex_turn_failed',retry_at=float('nan'),message='private')
        self.assertEqual(doc['error'],'codex_turn_failed');self.assertNotIn('retry_at',doc)
        self.assertNotIn('private',json.dumps(doc))

    def test_full_history_malformed_page_is_blocked(self):
        with Proxy(self.config) as proxy:
            real=proxy.call
            def call(method,params):
                return {'data':[{'status':'failed'}]} if method=='thread/turns/list' else real(method,params)
            with patch.object(proxy,'call',side_effect=call):
                with self.assertRaises(ControlError) as caught:proxy.inspect_turn('test')
                self.assertEqual(caught.exception.code,'codex_turn_history_invalid')
