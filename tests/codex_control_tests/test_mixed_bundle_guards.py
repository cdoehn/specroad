"""Authority corruption, malformed native evidence and correction boundary tests."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

from specroad_control.apply_reconcile_history import stable
from specroad_control.apply_reconcile_proof import canonical, plan, public_plan, hashed, compare, completion
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from specroad_control.local import json_read, json_write
from specroad_control.mixed_contract import CAPABILITY, CAPABILITY_PATH, MIXED
from specroad_control.mixed_evidence import verify_handoff, verify_followup
from specroad_control.ph_bridge import development_capability
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.mixed_support import MixedCase, SPEC, PLAN, postimage, write_result


class MixedGuardTests(MixedCase):
    def rejected_plan(self, data, *, mixed=False):
        patch_fact = patch_package(self.exchange/'inspect-only.zip', data)
        with self.assertRaises(ControlError):
            verify_handoff(self.engine, self.seed, patch_fact, new_contract(version=4), MIXED if mixed else 'patch_ready')

    def test_incomplete_or_reordered_rest_is_not_a_correction(self):
        self.dispatch(True); self.outcome(completed=1); self.engine.tick()
        data = self.correction()
        for fault in ('omit','reverse','role','unbound'):
            value = deepcopy(data)
            if fault=='omit': value['stages'].pop()
            elif fault=='reverse': value['stages'].reverse()
            elif fault=='role': value['stages'][0]['role']='correction'
            else: value['correction_of']=None
            fact = patch_package(self.exchange/(fault+'.zip'), value)
            with self.subTest(fault=fault), self.assertRaises(ControlError):
                verify_handoff(self.engine, self.following, fact, self.ledger().request_contract(), 'patch_ready')

    def test_correction_metadata_shape_is_closed(self):
        for value in ({}, {'plan_sha256':'a'*64,'remaining_commit_ids':['wrong']},
                      {'plan_sha256':'a'*64,'remaining_commit_ids':['feature.W','feature.R','feature.C'],'extra':1}):
            data=self.data(); data['correction_of']=value
            with self.subTest(value=value): self.rejected_plan(data)

    def test_test_selectors_are_typed_and_cannot_hide_changed_files(self):
        for key,value in (('test_files','tests/test_example.py'),('test_ids',[1]),('format_version',True),('reason','')):
            data=self.data(); data['stages'][0]['test_plan'][key]=value
            with self.subTest(key=key): self.rejected_plan(data)

    def test_three_clarifications_or_wrong_roles_fail_before_adoption(self):
        for fault in ('second','late','unknown','alibi','unchanged'):
            data=self.data(mixed=True)
            if fault=='second': data['stages'][1]['role']='clarification'
            elif fault=='late': data['stages'][0],data['stages'][1]=data['stages'][1],data['stages'][0]
            elif fault=='unknown': data['stages'][0]['role']='review'
            elif fault=='alibi':
                for row in data['stages'][1:]: row['before']=dict(row['after'])
            else: data['stages'][0]['before']=dict(data['stages'][0]['after'])
            with self.subTest(fault=fault): self.rejected_plan(data,mixed=True)

    def test_malformed_installed_capability_is_rejected(self):
        files=self.files | {CAPABILITY_PATH:canonical(CAPABILITY | {'implementation_required':1})}
        fact=self.result('bad-marker.zip',base=files)
        with self.assertRaises(ValueError): development_capability(Path(fact['path']),fact['sha256'])

    def test_missing_durable_continuation_row_is_not_inferred(self):
        ledger=self.ledger(); ledger.bind_contract(new_contract(version=4))
        ledger.db.execute('DELETE FROM clarification_continuations'); ledger.db.commit()
        with self.assertRaises(ControlError): ledger.request_contract()

    def test_orphan_continuation_row_is_not_new_authority(self):
        ledger=self.ledger()
        ledger.db.execute('CREATE TABLE clarification_continuations (sha TEXT PRIMARY KEY,pending INTEGER)')
        ledger.db.execute('INSERT INTO clarification_continuations VALUES(?,1)',(self.seed['sha256'],)); ledger.db.commit()
        with self.assertRaises(ControlError): ledger.request_contract()

    def test_legacy_contract_cannot_acquire_continuation_row(self):
        ledger=self.ledger(); ledger.bind_contract(new_contract())
        ledger.db.execute('CREATE TABLE clarification_continuations (sha TEXT PRIMARY KEY,pending INTEGER)')
        ledger.db.execute('INSERT INTO clarification_continuations VALUES(?,1)',(self.seed['sha256'],)); ledger.db.commit()
        with self.assertRaises(ControlError): ledger.request_contract()

    def test_changed_attempt_budget_does_not_advance_result(self):
        self.dispatch(True); self.outcome()
        path=self.paths.state/'jobs'/self.seed['sha256']/'attempt.json'
        attempt=json_read(path); attempt['request_contract']['clarifications_remaining']=1; json_write(path,attempt)
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'],self.seed['sha256'])

    def test_same_result_cannot_be_consumed_twice(self):
        self.dispatch(True); self.outcome(completed=1); self.engine.tick()
        selected=self.ledger().request_contract()
        for _ in range(2): self.engine.tick()
        self.assertEqual(self.ledger().request_contract(),selected)
        self.assertEqual(self.ledger().db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],2)

    def test_unknown_manual_prefix_failure_does_not_get_continuation(self):
        self.ledger().bind_contract(new_contract(2,allowed=False,version=4))
        self.latest_data=self.data(mixed=True)
        self.latest_patch=patch_package(self.exchange/'manual.zip',self.latest_data)
        self.engine.tick(); self.outcome(completed=0,dirty=False); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(),new_contract(2,allowed=False,version=4))

    def test_no_started_entrypoint_is_not_execution_evidence(self):
        self.dispatch(); result=self.outcome()
        for key,value in (('entrypoint_started',False),('dry_run',True),('repository_path','/wrong'),('patch_sha256','f'*64)):
            with self.subTest(key=key), self.assertRaises(ControlError):
                verify_followup(self.engine,self.seed,self.latest_patch['sha256'],result | {key:value},'patch_ready')

    def test_failed_progress_active_commit_must_belong_to_boundary(self):
        self.dispatch(True)
        def mutate(raw):
            lines=raw.decode().splitlines(); value=json.loads(lines[-1].split(' ',1)[1]); value['active_commit_id']='foreign'
            return lines[0].encode()+b'\nSPECROAD_APPLY_PROGRESS '+canonical(value)
        self.outcome(completed=1,mutate_log=mutate)
        with self.assertRaises(ControlError): self.engine.tick()

    def test_missing_or_extra_progress_fields_fail_closed(self):
        self.dispatch()
        def mutate(raw):
            lines=raw.decode().splitlines(); value=json.loads(lines[-1].split(' ',1)[1]); value['approved']=True
            return lines[0].encode()+b'\nSPECROAD_APPLY_PROGRESS '+canonical(value)
        self.outcome(mutate_log=mutate)
        with self.assertRaises(ControlError): self.engine.tick()

    def test_old_recovery_fact_shape_remains_stable_with_native_opt_in(self):
        old={key:value for key,value in self.seed.items() if key!='development_contract'}
        self.assertEqual(stable({'source':old}),stable({'source':self.seed}))
        self.assertNotEqual(stable({'source':old}),stable({'source':self.seed | {'sha256':'f'*64}}))

    def test_recovery_does_not_bypass_unchanged_clarification_contract(self):
        data=self.data(mixed=True); data['initial_dirty']=True
        original=patch_package(self.exchange/'original.zip',data)
        checkpoint=self.result('checkpoint.zip',dirty=True,
            work=postimage(self.files,data['stages'][:1]), binding=self.binding | {'state_fingerprint':'c'*16})
        resumed=deepcopy(data)
        resumed.update(binding=checkpoint['binding'],source_result_sha256=checkpoint['sha256'],bundle_number='556',
            correction_of={'plan_sha256':hashed(public_plan(data)),'remaining_commit_ids':[s['commit_id'] for s in data['stages']]})
        resumed['stages'][0]['before']=dict(resumed['stages'][0]['after'])
        candidate=patch_package(self.exchange/'resumed.zip',resumed)
        # Existing SpecRoad v2 intentionally rejects unchanged clarification
        # markers. Recovery must not bypass that restriction or invent a grant.
        with self.assertRaises((ControlError,ValueError)): compare(original,candidate,self.seed,checkpoint)

    def test_new_opt_in_does_not_reactivate_blocked_legacy_job(self):
        ledger=self.ledger(); ledger.bind_contract(new_contract(1,allowed=False))
        ledger.change('running'); ledger.change('uncertain',error='dev_blocked')
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.codex.calls,0)
        self.assertEqual(ledger.request_contract(),new_contract(1,allowed=False))

    def test_corrected_implementation_may_change_bytes_without_new_clarification(self):
        self.dispatch(True); self.outcome(completed=1); self.engine.tick()
        data=self.correction(); first=data['stages'][0]; raw=b'value = 10\n'
        first['payloads']['src/example.py']=base64.b64encode(raw).decode(); first['after']['src/example.py']=sha256(raw).hexdigest()
        data['stages'][1]['before']['src/example.py']=sha256(raw).hexdigest()
        self.assertFalse(self.dispatch(data=data)['halted'])
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(),new_contract(version=4))

    def test_exact_pending_prefix_can_finish_with_zero_new_slots(self):
        self.ledger().bind_contract(new_contract(1,version=4))
        self.dispatch(True); self.outcome(completed=0,dirty=False); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(),new_contract(0,allowed=False,version=4,continuation=True))
        self.assertFalse(self.dispatch(True,self.correction())['halted'])
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(),new_contract(version=4))

    def test_readonly_retry_requires_exact_original_v4_authority(self):
        from types import SimpleNamespace
        from specroad_control.retry_proof import proof
        from specroad_control.job_contract import prompt_for
        from specroad_control.continuation_evidence import request_prompt
        directory=self.home/'attempt'; directory.mkdir(mode=0o700)
        selected=new_contract(1,version=4)
        attempt={'source_sha256':self.seed['sha256'],'thread_id':self.thread,'number':0,
            'workspace_sha256':'b'*64,'request_contract':selected,
            'request_source':{k:self.seed[k] for k in ('path','sha256','binding','run_id')}}
        failure={'thread_id':self.thread,'turn_id':'isolated-turn','turn_status':'failed',
            'codex_error':'serverOverloaded','codex_will_retry':False}
        json_write(directory/'attempt.json',attempt); json_write(directory/'failure.json',failure)
        json_write(directory/'turn.json',{'thread_id':self.thread,'turn_id':'isolated-turn'})
        message={'id':'input','type':'userMessage','content':[{'type':'text','text':request_prompt(attempt,self.seed)}]}
        live={'thread_status':'idle','turn':{'id':'isolated-turn','status':'failed',
            'error':{'codexErrorInfo':'serverOverloaded'},'items':[message]}}
        codex=SimpleNamespace(inspect_turn=lambda ident:live)
        with patch('specroad_control.retry_proof.fingerprint',return_value='b'*64):
            self.assertFalse(proof(self.config,codex,directory,self.seed)['legacy'])
            message['content'][0]['text']=request_prompt(attempt | {'request_contract':new_contract(version=4)},self.seed)
            with self.assertRaises(ControlError) as caught: proof(self.config,codex,directory,self.seed)
            self.assertEqual(caught.exception.code,'retry_source_unproven')

    def test_v4_budget_and_continuation_insert_roll_back_together(self):
        import sqlite3
        self.dispatch(True); result=self.outcome(completed=0,dirty=False)
        ledger=self.ledger(); before=ledger.current(); insert=ledger._insert_contract
        def failing_insert(*args):
            insert(*args)
            raise sqlite3.OperationalError('Isolated persistence fault')
        with patch.object(ledger,'_insert_contract',side_effect=failing_insert), self.assertRaises(sqlite3.Error):
            ledger.enqueue(result,decision_evidence={'verified':True,'pending_clarification':True})
        self.assertEqual(ledger.current(),before)
        self.assertEqual(ledger.request_contract(),new_contract(version=4))
        for table in ('jobs','request_contracts','clarification_budgets','clarification_continuations'):
            self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],1)


    def test_retained_pending_prefix_keeps_targets_and_consumes_no_second_slot(self):
        self.dispatch(True); self.outcome(completed=0, dirty=True); self.engine.tick()
        selected = self.ledger().request_contract()
        self.assertEqual(selected, new_contract(2, allowed=False, version=4, continuation=True))
        data = self.correction()
        first = data['stages'][0]
        self.assertEqual(first['before'], first['after'])
        self.assertEqual(first['after'], self.latest_data['stages'][0]['after'])
        self.assertFalse(self.dispatch(True, data)['halted'])
        self.assertEqual(self.ledger().request_contract(), selected)
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))


    def test_materialized_prefix_still_requires_exact_native_ancestry_and_preimages(self):
        self.dispatch(True); self.outcome(completed=0, dirty=True); self.engine.tick()
        selected = self.ledger().request_contract()
        original = self.correction()
        for fault in ('changed-target', 'wrong-preimage', 'no-binding', 'wrong-plan', 'role', 'omit'):
            data = deepcopy(original); first = data['stages'][0]
            if fault == 'changed-target':
                raw = b'Another normative decision'
                first['after'][SPEC] = sha256(raw).hexdigest()
                first['payloads'][SPEC] = base64.b64encode(raw).decode()
            elif fault == 'wrong-preimage': first['before'][SPEC] = '0' * 64
            elif fault == 'no-binding': data['correction_of'] = None
            elif fault == 'wrong-plan': data['correction_of']['plan_sha256'] = '0' * 64
            elif fault == 'role': first['role'] = 'correction'
            else:
                data['stages'].pop()
                data['correction_of']['remaining_commit_ids'] = [s['commit_id'] for s in data['stages']]
            fact = patch_package(self.exchange / (fault + '.zip'), data)
            with self.subTest(fault=fault), self.assertRaises((ControlError, ValueError)):
                verify_handoff(self.engine, self.following, fact, selected, MIXED)
        self.assertEqual(self.ledger().request_contract(), selected)
