from dataclasses import replace
import json
from specroad_control.automation import prompt_for,SCHEMA
from specroad_control.codex import Codex
from specroad_control.commands import probe,check,configure
from specroad_control.errors import ControlError
from specroad_control.local import private_dir
from codex_control_tests.automation_support import AutomationCase


class CodexTests(AutomationCase):
    def invoke(self):
        directory=self.paths.state/'job'; private_dir(directory)
        return Codex(self.config).run(prompt_for(self.seed),SCHEMA,directory)

    def test_existing_thread_preflight_is_read_only(self):
        evidence=check(self.paths)
        self.assertTrue(evidence['thread_resolved']); self.assertFalse(evidence['model_called'])
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_explicit_same_thread_resume_and_final_contract(self):
        answer=self.invoke()
        self.assertEqual(answer['status'],'no_work')
        calls=[json.loads(x) for x in (self.codex_home/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][-2:], [self.thread,'-'])
        self.assertIn('--output-schema',calls[0]); self.assertNotIn('--last',calls[0])
        self.assertFalse(any('dangerously' in x or '--full-auto' == x for x in calls[0]))

    def test_busy_thread_never_starts_a_turn(self):
        self.settings(thread_status='active')
        with self.assertRaises(ControlError) as caught: self.invoke()
        self.assertEqual(caught.exception.code,'dev_thread_busy')
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_missing_thread_is_never_created(self):
        self.settings(missing=True)
        with self.assertRaises(ControlError): self.invoke()
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_wrong_cwd_never_starts_a_turn(self):
        self.settings(cwd=str(self.home))
        with self.assertRaises(ControlError) as caught: self.invoke()
        self.assertEqual(caught.exception.code,'wrong_thread_repository')
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_wrong_thread_event_is_not_success(self):
        self.settings(event_thread='00000000-0000-4000-8000-000000000002')
        with self.assertRaises(ControlError) as caught: self.invoke()
        self.assertEqual(caught.exception.code,'wrong_thread')

    def test_missing_completion_is_uncertain(self):
        self.settings(missing_completed=True)
        with self.assertRaises(ControlError): self.invoke()

    def test_malformed_event_is_not_success(self):
        self.settings(malformed=True)
        with self.assertRaises(ControlError): self.invoke()

    def test_failed_turn_is_not_success(self):
        self.settings(fail=True)
        with self.assertRaises(ControlError): self.invoke()

    def test_pause_at_dispatch_boundary_has_no_model_effect(self):
        directory=self.paths.state/'job'; private_dir(directory)
        with self.assertRaises(ControlError) as caught:
            Codex(self.config).run('never',SCHEMA,directory,authorize=lambda:False)
        self.assertEqual(caught.exception.code,'dispatch_paused')
        self.assertFalse((self.codex_home/'calls.jsonl').exists())
        self.assertEqual(list(directory.iterdir()),[])

    def test_probe_records_protocol_not_claimed_remote_visibility(self):
        reply=probe(self.paths)
        self.assertTrue(reply['model_called']); self.assertTrue(reply['same_thread_protocol'])
        self.assertEqual(reply['remote_visibility'],'not_verified')
        self.assertFalse(reply['service_started'])
        calls=(self.codex_home/'calls.jsonl').read_text()
        self.assertIn('read-only',calls)

    def test_configure_validates_but_does_not_start(self):
        reply=configure(self.paths,thread_id=self.thread,result=self.seed['path'],codex=str(self.binary),core_python=str(self.python))
        self.assertTrue(reply['configured']); self.assertFalse(reply['service_started']); self.assertFalse(reply['model_called'])
        self.assertFalse((self.codex_home/'calls.jsonl').exists())
