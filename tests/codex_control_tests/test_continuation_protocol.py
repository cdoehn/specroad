"""Continuation races over the real local wire, with independent fake servers."""
from contextlib import contextmanager
from dataclasses import replace
from specroad_control.codex import Codex
from specroad_control.codex_proxy import Proxy
from specroad_control.errors import ControlError
from specroad_control.job_contract import prompt_for, SCHEMA
from specroad_control.local import private_dir
from specroad_control import continuation
from codex_control_tests.automation_support import AutomationCase
from unittest.mock import patch


class ContinuationProtocolTests(AutomationCase):
    def setUp(self):
        super().setUp()
        self.config=replace(self.config,transport='app-server-proxy')
        self.settings(thread_status='systemError')
        self.server=self.codex_daemon.server
        self.server.history['target']={'id':'target','status':'failed',
            'error':{'codexErrorInfo':'serverOverloaded'},'items':[{'id':'r','type':'reasoning'}]}

    @contextmanager
    def mutate(self, fn):
        original=Proxy.call
        def call(proxy,method,params):
            result=original(proxy,method,params)
            return fn(method,params,result)
        with patch.object(Proxy,'call',call): yield

    def observe(self):
        return Codex(self.config).inspect_continuation('target')

    def test_manual_turn_arriving_during_item_read_blocks(self):
        def mutate(method,params,result):
            if method=='thread/items/list':self.server.history['other']={'id':'other','status':'completed','items':[]}
            return result
        with self.mutate(mutate), self.assertRaises(ControlError): self.observe()

    def test_background_start_during_item_read_blocks(self):
        def mutate(method,params,result):
            if method=='thread/items/list':self.settings(thread_status='systemError',background_terminals=[{'processId':'1'}])
            return result
        with self.mutate(mutate), self.assertRaises(ControlError) as caught:self.observe()
        self.assertEqual(caught.exception.code,'continuation_background_active')

    def test_truncated_background_inventory_is_never_empty_proof(self):
        def mutate(method,params,result):
            if method=='thread/backgroundTerminals/list':result.pop('nextCursor')
            return result
        with self.mutate(mutate), self.assertRaises(ControlError):self.observe()

    def test_reactivated_thread_after_items_never_authorizes_continuation(self):
        def mutate(method,params,result):
            if method=='thread/items/list':self.settings(thread_status='active')
            return result
        with self.mutate(mutate):live=self.observe()
        with self.assertRaises(ControlError) as caught:continuation.terminal(live,'target')
        self.assertEqual(caught.exception.code,'dev_turn_active')

    def test_resume_race_with_manual_work_does_not_issue_turn_start(self):
        live=self.observe(); evidence={'turn_id':'target','history_sha256':continuation.sha(live['turn'])}
        directory=self.paths.state/'dispatch';private_dir(directory)
        def mutate(method,params,result):
            if method=='thread/resume':self.server.history['other']={'id':'other','status':'completed','items':[]}
            return result
        with self.mutate(mutate), self.assertRaises(ControlError):
            Codex(self.config).run(prompt_for(self.seed),SCHEMA,directory,continuation=evidence)
        self.assertFalse(any(r.get('method')=='turn/start' for r in self.server.requests))

    def test_same_latest_identity_with_changed_history_blocks_dispatch(self):
        live=self.observe(); evidence={'turn_id':'target','history_sha256':continuation.sha(live['turn'])}
        self.server.history['target']['items'][0]['content']=['changed']
        directory=self.paths.state/'dispatch';private_dir(directory)
        with self.assertRaises(ControlError):
            Codex(self.config).run(prompt_for(self.seed),SCHEMA,directory,continuation=evidence)
        self.assertFalse(any(r.get('method')=='turn/start' for r in self.server.requests))

    def test_metadata_calls_do_not_request_thread_model_or_effort_changes(self):
        self.observe()
        requests=self.server.requests
        self.assertTrue(any(r.get('params',{}).get('capabilities')=={'experimentalApi':True} for r in requests))
        self.assertFalse(any(r.get('method') in ('thread/resume','turn/start','turn/interrupt','thread/backgroundTerminals/clean',
                                               'thread/backgroundTerminals/terminate') for r in requests))
