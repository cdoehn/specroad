"""Versioned Codex history contract over real isolated Unix WebSockets."""
from contextlib import contextmanager
from dataclasses import replace
from copy import deepcopy
import json
from unittest.mock import patch
from specroad_control.codex import Codex
from specroad_control.codex_proxy import Proxy
from specroad_control.commands import recover
from specroad_control.config import render
from specroad_control.errors import ControlError
from specroad_control.job_contract import prompt_for, scope, SCHEMA
from specroad_control.ledger import Ledger
from specroad_control.local import private_dir, write_private
from codex_control_tests.automation_support import AutomationCase
from codex_control_tests.retry_support import initialize_git


def turn(ident='target', count=2, large=0):
    return {'id':ident, 'itemsView':'full', 'status':'failed',
            'error':{'codexErrorInfo':'serverOverloaded'},
            'items':[{'id':str(i),'type':'reasoning','text':('x'*large if i==0 else 'text')}
                     for i in range(count)]}


class TargetedHistoryTests(AutomationCase):
    def setUp(self):
        super().setUp()
        self.server = self.codex_daemon.server
        self.server.history['target'] = turn()

    def observe(self):
        with Proxy(self.config) as proxy:
            return proxy.inspect_turn('target')

    @contextmanager
    def mutate(self, fn):
        original = Proxy.call
        def call(proxy, method, params):
            reply = original(proxy, method, params)
            return fn(method, params, reply)
        with patch.object(Proxy, 'call', call):
            yield

    def test_unrelated_giant_turns_are_never_loaded(self):
        for i in range(51): self.server.history[str(i)] = turn(str(i), large=80*1024)
        self.assertEqual(self.observe()['turn'], turn())
        requests = self.server.requests
        self.assertFalse(any(x.get('params',{}).get('includeTurns') for x in requests))
        history = [x['params'] for x in requests if x.get('method')=='thread/turns/list']
        self.assertTrue(history)
        self.assertTrue(all(x['itemsView']=='notLoaded' for x in history))
        items = [x['params'] for x in requests if x.get('method')=='thread/items/list']
        self.assertTrue(all(x['turnId']=='target' for x in items))
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_all_target_item_pages_are_assembled(self):
        self.server.history['target'] = turn(count=125)
        self.assertEqual(self.observe()['turn'], turn(count=125))
        requests = [x['params'] for x in self.server.requests if x.get('method')=='thread/items/list']
        self.assertEqual([x.get('cursor') for x in requests],[None,'50','100'])

    def test_missing_target_does_not_borrow_other_turn(self):
        del self.server.history['target']; self.server.history['different'] = turn('different')
        with self.assertRaises(ControlError): self.observe()
        self.assertFalse(any(x.get('method')=='thread/items/list' for x in self.server.requests))

    def test_item_api_unsupported_uses_single_full_turn_fallback(self):
        self.settings(no_item_pages=True)
        for i in range(52): self.server.history[str(i)] = turn(str(i))
        self.assertEqual(self.observe()['turn'], turn())
        full = [x['params'] for x in self.server.requests if x.get('method')=='thread/turns/list'
                and x['params']['itemsView']=='full']
        self.assertEqual(len(full),3)
        self.assertTrue(all(x['limit']==1 for x in full))
        self.assertFalse(any(x.get('params',{}).get('includeTurns') for x in self.server.requests))

    def test_legacy_explicitly_unsupported_history_is_bounded_fallback(self):
        self.settings(legacy_history=True)
        self.assertEqual(self.observe()['turn'], turn())
        self.assertTrue(any(x.get('params',{}).get('includeTurns') for x in self.server.requests))
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_item_permission_error_does_not_fall_back_or_start(self):
        original=Proxy.call
        def call(proxy, method, params):
            if method=='thread/items/list':
                raise ControlError('codex_request_rejected','denied',details={'rpc_code':-32001})
            return original(proxy,method,params)
        with patch.object(Proxy,'call',call), self.assertRaises(ControlError) as caught:
            self.observe()
        self.assertEqual(caught.exception.details['rpc_code'],-32001)
        self.assertFalse(any(x.get('params',{}).get('itemsView')=='full' for x in self.server.requests))

    def test_missing_next_cursor_is_not_complete_evidence(self):
        def mutate(method,params,reply):
            if method=='thread/items/list':reply.pop('nextCursor')
            return reply
        with self.mutate(mutate), self.assertRaises(ControlError): self.observe()

    def test_item_from_other_turn_is_rejected(self):
        def mutate(method,params,reply):
            if method=='thread/items/list':reply['data'][0]['turnId']='foreign'
            return reply
        with self.mutate(mutate), self.assertRaises(ControlError): self.observe()

    def test_duplicate_items_across_pages_are_rejected(self):
        self.server.history['target'] = turn(count=70)
        self.server.history['target']['items'][50]['id']='0'
        with self.assertRaises(ControlError): self.observe()

    def test_summary_full_fallback_is_not_promoted_to_full(self):
        self.settings(no_item_pages=True)
        def mutate(method,params,reply):
            if method=='thread/turns/list' and params.get('itemsView')=='full':reply['data'][0]['itemsView']='summary'
            return reply
        with self.mutate(mutate), self.assertRaises(ControlError): self.observe()

    def test_truncated_item_is_rejected(self):
        self.server.history['target']['items'][0]['truncated']=True
        with self.assertRaises(ControlError): self.observe()

    def test_repeated_item_cursor_is_rejected(self):
        self.server.history['target'] = turn(count=125)
        def mutate(method,params,reply):
            if method=='thread/items/list' and params.get('cursor')=='50':reply['nextCursor']='50'
            return reply
        with self.mutate(mutate), self.assertRaises(ControlError): self.observe()

    def test_invalid_turn_metadata_status_is_rejected(self):
        self.server.history['target']['status']='almost_done'
        with self.assertRaises(ControlError): self.observe()

    def test_changed_terminal_metadata_is_not_a_consistent_snapshot(self):
        def mutate(method,params,reply):
            if method=='thread/items/list':self.server.history['target']['status']='interrupted'
            return reply
        with self.mutate(mutate), self.assertRaises(ControlError) as caught:self.observe()
        self.assertEqual(caught.exception.code,'codex_turn_history_changed')

    def test_turn_activated_during_pagination_is_preserved(self):
        def mutate(method,params,reply):
            if method=='thread/items/list': self.server.history['target']['status']='inProgress'
            return reply
        with self.mutate(mutate): actual=self.observe()
        self.assertEqual(actual,{'thread_status':'active','turn':None})
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_live_thread_becomes_active_after_items_is_preserved(self):
        reads=0
        def mutate(method,params,reply):
            nonlocal reads
            if method=='thread/read':
                reads+=1
                if reads>1:reply['thread']['status']={'type':'active'}
            return reply
        with self.mutate(mutate): actual=self.observe()
        self.assertEqual(actual,{'thread_status':'active','turn':None})

    def test_cumulative_item_byte_budget_is_enforced(self):
        self.server.history['target']=turn(count=2,large=1024)
        with patch('specroad_control.codex_history.MAX_HISTORY_BYTES',1000), self.assertRaises(ControlError) as caught:
            self.observe()
        self.assertEqual(caught.exception.code,'codex_turn_history_limit')

    def test_item_count_budget_is_enforced(self):
        self.server.history['target']=turn(count=5)
        with patch('specroad_control.codex_history.MAX_TURN_ITEMS',4), self.assertRaises(ControlError) as caught:
            self.observe()
        self.assertEqual(caught.exception.code,'codex_turn_history_limit')

    def test_items_page_budget_is_enforced(self):
        self.server.history['target']=turn(count=51)
        with patch('specroad_control.codex_history.MAX_ITEM_PAGES',1), self.assertRaises(ControlError) as caught:
            self.observe()
        self.assertEqual(caught.exception.code,'codex_turn_history_limit')

    def test_legacy_truncated_view_is_not_used(self):
        self.settings(legacy_history=True)
        self.server.history['target']['itemsView']='summary'
        with self.assertRaises(ControlError):self.observe()

    def test_complete_target_larger_than_previous_two_mib_limit(self):
        self.server.history['target']=turn(count=1,large=3*1024*1024)
        self.assertEqual(self.observe()['turn'],self.server.history['target'])
        self.assertFalse((self.codex_home/'calls.jsonl').exists())

    def test_runtime_unknown_does_not_read_history(self):
        self.settings(thread_status='unknown')
        self.assertEqual(self.observe(),{'thread_status':'unknown','turn':None})
        self.assertFalse(any(x.get('method')=='thread/turns/list' for x in self.server.requests))

    def test_active_turn_among_metadata_never_fetches_items(self):
        self.server.history['running']=turn('running');self.server.history['running']['status']='inProgress'
        self.assertEqual(self.observe(),{'thread_status':'active','turn':None})
        self.assertFalse(any(x.get('method')=='thread/items/list' for x in self.server.requests))

    def test_duplicate_turn_identity_is_rejected(self):
        self.server.history['duplicate']=turn()
        with self.assertRaises(ControlError):self.observe()

    def test_item_entries_missing_full_item_shape_are_rejected(self):
        def mutate(method,params,reply):
            if method=='thread/items/list':reply['data'][0]={'turnId':'target','summary':'not the item'}
            return reply
        with self.mutate(mutate), self.assertRaises(ControlError):self.observe()


class TargetedRecoveryTests(AutomationCase):
    def test_old_failed_job_recovery_with_large_unrelated_history_preserves_original_evidence(self):
        initialize_git(self.dev)
        self.config=replace(self.config,transport='app-server-proxy')
        write_private(self.paths.config,render(self.config).encode())
        directory=self.paths.state/'jobs'/self.seed['sha256']; private_dir(directory)
        self.settings(overload=True)
        with self.assertRaises(ControlError):Codex(self.config).run(prompt_for(self.seed),SCHEMA,directory)
        (directory/'failure.json').unlink()
        ledger=Ledger(self.paths.state/'automation.sqlite3',scope(self.config))
        try: ledger.change('running');ledger.change('uncertain',error='codex_turn_failed')
        finally: ledger.close()
        # Same structure as a long-lived real Dev thread, but synthetic contents.
        for i in range(55):self.codex_daemon.server.history[str(i)] = turn(str(i),large=64*1024)
        original={name:(directory/name).read_bytes() for name in ['events.jsonl','turn.json']}
        config=self.paths.config.read_bytes()
        outcome=recover(self.paths)
        self.assertEqual(outcome['stage'],'retry_wait')
        self.assertFalse(outcome['model_called']); self.assertFalse(outcome['service_started'])
        self.assertEqual(self.paths.config.read_bytes(),config)
        self.assertEqual({name:(directory/name).read_bytes() for name in original},original)
        self.assertEqual(len((self.codex_home/'calls.jsonl').read_text().splitlines()),1)
