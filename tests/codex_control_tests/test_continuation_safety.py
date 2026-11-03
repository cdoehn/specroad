"""Durable proof, concurrent changes and protocol compatibility boundaries."""
from dataclasses import replace
import json
from pathlib import Path
from unittest.mock import patch
from specroad_control.automation import Engine, Gate
from specroad_control.errors import ControlError
from specroad_control.local import json_read, json_write
from specroad_control import continuation
from codex_control_tests.automation_support import FakeCore, package
from codex_control_tests.test_overload_retry import RetryCase
from codex_control_tests.test_continuation import PartialCodex
from codex_control_tests.retry_support import git


class ContinuationSafetyTests(RetryCase):
    def setUp(self):
        super().setUp()
        self.codex = PartialCodex(self)
        self.engine.codex = self.codex
        self.codex.observe = self.engine.observe

    def directory(self):
        return self.paths.state/'jobs'/self.seed['sha256']

    def test_restart_preserves_due_proof_and_partial_files(self):
        self.engine.tick()
        saved = self.ledger().retry_info(self.seed['sha256'])
        self.engine.close()
        with Engine(self.config, self.paths, Gate(), core=FakeCore(), codex=self.codex, clock=lambda:self.now) as engine:
            self.assertEqual(engine.tick()['retry_after'], 60)
            self.assertEqual(engine.summary()['retry_mode'], 'continuation')
            self.now += 60; engine.tick()
        self.assertEqual(self.codex.calls, 2)
        self.assertEqual(self.ledger().retry_info(self.seed['sha256']), saved)
        self.assertEqual((self.dev/'partial.txt').read_text(), 'preserved work 1')

    def test_empty_text_elements_in_persisted_user_input_are_accepted(self):
        self.codex.after_failure = lambda _: self.codex.turns['turn-1']['items'][0]['content'][0].update(text_elements=[])
        self.assertEqual(self.engine.tick()['retry_after'], 60)

    def test_serialized_request_reloads_with_identical_prompt_bytes(self):
        self.engine.tick()
        attempt=json_read(self.directory()/'attempt.json')
        expected=continuation.request_prompt(attempt,self.seed)
        self.assertEqual(self.codex.prompts[0],expected)
        self.assertEqual(json_read(self.directory()/'dispatch.json')['prompt_sha256'],continuation.sha(expected))

    def test_failed_test_command_with_known_exitcode_is_terminal(self):
        self.codex.effect={'id':'tests','type':'commandExecution','source':'agent','status':'failed',
                           'exitCode':1,'command':'python3 -B tools/test_parallel.py','cwd':str(self.dev)}
        self.assertEqual(self.engine.tick()['retry_after'],60)

    def test_plan_item_without_tool_effect_is_allowed(self):
        self.codex.effect={'id':'plan','type':'plan','text':'Continue existing local work'}
        self.assertEqual(self.engine.tick()['retry_after'],60)

    def test_pending_user_question_requires_input(self):
        self.codex.effect={'id':'question','type':'agentMessage','questions':[{'title':'Choose semantics'}]}
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.engine.summary()['retry_blocked_reason'],'continuation_input_pending')

    def test_nonempty_text_elements_are_not_silently_ignored(self):
        self.codex.after_failure = lambda _: self.codex.turns['turn-1']['items'][0]['content'][0].update(text_elements=[{'text':'extra'}])
        self.assertTrue(self.engine.tick()['halted'])

    def test_manual_shell_in_same_turn_is_not_a_controller_action(self):
        self.codex.effect = {'id':'manual', 'type':'commandExecution', 'command':'pwd',
                            'cwd':str(self.dev), 'source':'userShell','status':'completed','exitCode':0}
        self.assertTrue(self.engine.tick()['halted'])

    def test_missing_command_origin_still_blocks(self):
        self.codex.effect = {'id':'old', 'type':'commandExecution','command':'pwd',
                            'cwd':str(self.dev),'status':'completed','exitCode':0}
        self.assertTrue(self.engine.tick()['halted'])

    def test_receipt_cannot_claim_unrestricted_network(self):
        def corrupt(directory):
            value = json_read(directory/'dispatch.json')
            value['sandboxPolicy']['networkAccess'] = True
            json_write(directory/'dispatch.json', value)
        self.codex.after_failure = corrupt
        self.assertTrue(self.engine.tick()['halted'])
        self.assertIsNone(self.ledger().retry_info(self.seed['sha256']))

    def test_changed_original_attempt_receipt_invalidates_checkpoint(self):
        self.engine.tick(); self.now += 60
        path = self.directory()/'attempt.json'; value = json_read(path)
        value['workspace_sha256'] = 'f'*64; json_write(path, value)
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls, 1)

    def test_changed_attempt_number_is_not_recreated(self):
        self.engine.tick(); self.now += 60
        path = self.directory()/'attempt.json'; value=json_read(path); value['number']=7
        json_write(path,value)
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls, 1)

    def test_original_prompt_binding_is_not_borrowed_from_another_source(self):
        def corrupt(directory):
            value=json_read(directory/'attempt.json'); value['request_source']['sha256']='f'*64
            json_write(directory/'attempt.json',value)
        self.codex.after_failure=corrupt
        self.assertTrue(self.engine.tick()['halted'])

    def test_source_can_move_to_archive_without_losing_original_request_proof(self):
        self.engine.tick(); self.now += 60
        archive=self.exchange/self.config.archive_directory; archive.mkdir()
        Path(self.seed['path']).rename(archive/'seed.zip')
        self.engine.tick()
        self.assertEqual(self.codex.calls, 2)
        self.assertEqual(json.loads(self.codex.prompts[1].splitlines()[1])['path'], str(archive/'seed.zip'))

    def test_source_missing_prevents_new_dispatch(self):
        self.engine.tick(); self.now += 60; Path(self.seed['path']).unlink()
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.codex.calls, 1)

    def test_index_change_during_wait_is_not_undone(self):
        self.engine.tick(); self.now += 60; git(self.dev, 'add', '--', 'partial.txt')
        index = (self.dev/'.git/index').read_bytes()
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls, 1)
        self.assertEqual((self.dev/'.git/index').read_bytes(), index)

    def test_partial_files_do_not_allow_unbounded_retries_when_disabled(self):
        self.engine.config=replace(self.config, retry_delays_seconds=())
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls, 1)
        self.assertEqual(self.engine.summary()['retry_blocked_reason'], 'retry_exhausted')

    def test_existing_waiting_bundle_adopted_before_due_time(self):
        self.engine.tick()
        package(self.exchange/'output.zip',{'kind':'patch','binding':self.binding})
        self.assertTrue(self.engine.tick()['again'])
        self.assertEqual(self.ledger().current()['stage'], 'waiting_result')
        self.assertEqual(self.codex.calls, 1)

    def test_ambiguous_outputs_do_not_start_new_work(self):
        self.engine.tick()
        package(self.exchange/'one.zip',{'kind':'patch','binding':self.binding})
        package(self.exchange/'two.zip',{'kind':'patch','binding':self.binding,'different':True})
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.codex.calls, 1)

    def test_published_patch_and_following_result_join_the_existing_apply_chain(self):
        self.engine.tick()
        output=package(self.exchange/'done.zip',{'kind':'patch','binding':self.binding})
        following=self.result('applied.zip',previous=self.seed,patch_sha=output['sha256'])
        self.engine.tick()
        self.assertEqual(self.ledger().current()['stage'],'waiting_result')
        self.engine.gate.set(False)
        self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], following['sha256'])
        self.assertEqual(self.codex.calls, 1)

    def test_patch_arriving_at_final_dispatch_is_adopted_without_a_model_call(self):
        self.engine.tick(); self.now += 60
        original=self.codex.run
        def run(*args, **kwargs):
            package(self.exchange/'last-moment.zip',{'kind':'patch','binding':self.binding})
            return original(*args,**kwargs)
        with patch.object(self.codex,'run',side_effect=run):
            self.assertTrue(self.engine.tick()['again'])
        self.assertEqual(self.codex.calls,1)
        self.assertEqual(self.ledger().current()['stage'],'waiting_result')

    def test_pause_at_dispatch_keeps_continuation_available_for_resume(self):
        self.engine.tick(); self.now += 60
        original=self.codex.run
        def run(*args, **kwargs):
            self.engine.gate.set(False)
            return original(*args,**kwargs)
        with patch.object(self.codex,'run',side_effect=run): self.engine.tick()
        self.assertEqual(self.codex.calls,1)
        self.engine.gate.set(True); self.engine.tick(); self.assertEqual(self.codex.calls,2)

    def test_workspace_edit_at_dispatch_blocks_without_reset(self):
        self.engine.tick(); self.now += 60
        original=self.codex.run
        def run(*args, **kwargs):
            (self.dev/'partial.txt').write_text('concurrent edit')
            return original(*args,**kwargs)
        with patch.object(self.codex,'run',side_effect=run): self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls,1)
        self.assertEqual((self.dev/'partial.txt').read_text(),'concurrent edit')

    def test_active_turn_at_dispatch_remains_in_waiting_state(self):
        self.engine.tick(); self.now += 60
        original=self.codex.run
        def run(*args, **kwargs):
            self.codex.status='active'
            return original(*args,**kwargs)
        with patch.object(self.codex,'run',side_effect=run): self.assertEqual(self.engine.tick()['retry_after'],30)
        self.assertEqual(self.ledger().current()['stage'],'retry_wait')
        self.assertEqual(self.codex.calls,1)

    def test_live_background_after_wait_is_preserved(self):
        self.engine.tick(); self.now += 60; self.codex.background=[{'processId':'live'}]
        self.assertEqual(self.engine.tick()['retry_after'],30)
        self.assertEqual(self.ledger().current()['stage'],'retry_wait')
        self.assertEqual(self.codex.calls,1)

    def test_damaged_proof_cannot_downgrade_continuation_into_original_N(self):
        self.engine.tick(); ledger=self.ledger()
        receipt=ledger.retry_info(self.seed['sha256']); evidence=receipt['evidence']; evidence['mode']='readonly'
        ledger.db.execute('UPDATE retry_attempts SET failure=?',(json.dumps(evidence),))
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.codex.calls,1)

    def test_failure_after_claim_without_terminal_receipt_remains_uncertain(self):
        self.engine.tick(); self.now += 60
        def disconnect(prompt,schema,directory,*,authorize,**kwargs):
            self.assertTrue(authorize())
            raise ControlError('codex_connection_lost','unknown execution')
        with patch.object(self.codex,'run',side_effect=disconnect): self.assertTrue(self.engine.tick()['halted'])
        self.engine.tick()
        self.assertEqual(self.ledger().current()['stage'],'uncertain')
        self.assertEqual(self.ledger().retry_info(self.seed['sha256'])['number'],1)

    def test_live_failure_with_user_interruption_cannot_override_original_overload(self):
        self.engine.tick(); self.now += 60; self.codex.turns['turn-1']['status']='interrupted'
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls,1)

    def test_no_unasked_turn_is_inferred_from_preexisting_uncertain_job(self):
        self.ledger().change('running'); self.ledger().change('uncertain',error='codex_turn_failed')
        self.assertTrue(self.engine.tick()['halted']); self.assertEqual(self.codex.calls,0)

    def test_unknown_or_nonterminal_items_do_not_get_a_checkpoint(self):
        for item in ({'id':'a','type':'fileChange','status':'inProgress','changes':[]},
                     {'id':'a','type':'fileChange','status':'completed','changes':[{'path':'relative.py'}]},
                     {'id':'a','type':'fileChange','status':'completed','changes':[{'path':str(self.home/'elsewhere')}]},
                     {'id':'a','type':'commandExecution','status':'completed','exitCode':True,'command':'pwd','source':'agent','cwd':str(self.dev)}):
            with self.subTest(item=item):
                turn={'itemsView':'full','items':[{'id':'u','type':'userMessage','content':[{'type':'text','text':'p'}]},item]}
                with self.assertRaises(ControlError): continuation.prove_items(turn,'p',self.config)
