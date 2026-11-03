from dataclasses import replace
import json
from specroad_control.automation import prompt_for,SCHEMA
from specroad_control.codex import Codex
from specroad_control.commands import configure
from specroad_control.config import load, render
from specroad_control.errors import ControlError
from specroad_control.local import private_dir, write_private
from codex_control_tests.automation_support import AutomationCase


class ProxyTransportTests(AutomationCase):
    def setUp(self):
        super().setUp()
        self.config=replace(self.config,transport='app-server-proxy')
        self.settings(mode='no_work')
        write_private(self.paths.config,render(self.config).encode())

    def invoke(self,**kw):
        directory=self.paths.state/'proxy-job'; private_dir(directory)
        return Codex(self.config).run(prompt_for(self.seed),SCHEMA,directory,**kw)

    def test_existing_daemon_resumes_exact_thread_without_new_server(self):
        result=self.invoke()
        self.assertEqual(result['status'],'no_work')
        calls=[json.loads(x) for x in (self.codex_home/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls,[['app-server','unix']])
        params=json.loads((self.codex_home/'request.json').read_text())
        self.assertEqual(params['threadId'],self.thread)
        self.assertEqual(params['cwd'],str(self.dev))
        self.assertNotIn('model',params); self.assertNotIn('effort',params)
        self.assertEqual(params['approvalPolicy'],'never')
        self.assertEqual(params['sandboxPolicy']['writableRoots'],[str(self.dev),str(self.exchange)])
        self.assertFalse(params['sandboxPolicy']['networkAccess'])

    def test_failed_proxy_turn_has_no_fallback_to_exec(self):
        self.settings(fail=True)
        with self.assertRaises(ControlError): self.invoke()
        calls=[json.loads(x) for x in (self.codex_home/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls,[['app-server','unix']])

    def test_busy_proxy_thread_is_not_steered_or_queued(self):
        self.settings(thread_status='active')
        with self.assertRaises(ControlError): self.invoke()
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_wrong_resume_id_prevents_turn(self):
        self.settings(returned_id='00000000-0000-4000-8000-000000000003')
        with self.assertRaises(ControlError): self.invoke()
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_proxy_pause_before_dispatch_does_not_call_model(self):
        with self.assertRaises(ControlError) as caught: self.invoke(authorize=lambda:False)
        self.assertEqual(caught.exception.code,'dispatch_paused')
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_proxy_probe_limits_sandbox_to_read_only(self):
        from specroad_control.commands import probe
        result=probe(self.paths)
        self.assertTrue(result['same_thread_protocol']); self.assertEqual(result['remote_visibility'],'not_verified')
        params=json.loads((self.codex_home/'request.json').read_text())
        self.assertEqual(params['sandboxPolicy']['type'],'readOnly')

    def test_configure_alternative_does_not_call_model(self):
        result=configure(self.paths,thread_id=self.thread,result=self.seed['path'],codex=str(self.binary),core_python=str(self.python),transport='app-server-proxy')
        self.assertFalse(result['model_called']); self.assertEqual(load(self.paths).transport,'app-server-proxy')


# Exercise real worker lifecycle and inotify with the alternative transport too.
from codex_control_tests import test_event_worker as worker_cases

class ProxyEventWorkerTests(worker_cases.EventWorkerTests):
    def setUp(self):
        super().setUp()
        self.config=replace(self.config,transport='app-server-proxy')
        write_private(self.paths.config,render(self.config).encode())
