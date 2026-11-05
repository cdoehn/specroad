"""Reject evidence gaps without rewriting native Results, claims or budgets."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import zipfile

from specroad_control import blocked_chain_extended as proof
from specroad_control.apply_reconcile import enqueue
from specroad_control.apply_reconcile_proof import canonical, hashed, public_plan
from specroad_control.errors import ControlError
from codex_control_tests import test_blocked_chain_extended as fixture
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.blocked_chain_support import BlockedChainCase, log_for, stage


class ExtendedChainRightTests(BlockedChainCase):
    queue = fixture.ExtendedChainTests.queue
    multi_chain = fixture.ExtendedChainTests.multi_chain
    engine = fixture.existing.BlockedChainTests.engine
    preserved = fixture.existing.BlockedChainTests.preserved
    rejected = fixture.existing.BlockedChainTests.rejected

    def test_outer_timeout_requires_all_native_terminal_facts(self):
        self.multi_chain()
        original = Path(self.timeout_result['path']).read_bytes()
        with zipfile.ZipFile(self.timeout_result['path']) as archive:
            run = json.loads(archive.read('logs/run.json'))
        mutations = [('timed_out', False), ('interrupted', True), ('entrypoint_started', False),
                     ('entrypoint_exit_code', 0), ('success', True), ('kind', 'entrypoint_exit')]
        for key, value in mutations:
            with self.subTest(field=key):
                Path(self.timeout_result['path']).write_bytes(original)
                changed = deepcopy(run); changed['primary_result'][key] = value
                fact = fixture.replace_member(self.timeout_result, 'logs/run.json', canonical(changed))
                with self.assertRaisesRegex(ControlError, 'Outer timeout'):
                    proof.partial_progress(fact, self.third_data)
        for key, value in [('ended_at', None), ('run_id', 'different'), ('dry_run', True)]:
            with self.subTest(field=key):
                Path(self.timeout_result['path']).write_bytes(original)
                fact = fixture.replace_member(self.timeout_result, 'logs/run.json', canonical(run | {key: value}))
                with self.assertRaisesRegex(ControlError, 'Outer timeout'):
                    proof.partial_progress(fact, self.third_data)

    def test_timeout_does_not_invent_failed_progress_or_successful_current_gate(self):
        self.multi_chain()
        with zipfile.ZipFile(self.timeout_result['path']) as archive:
            raw = archive.read('logs/execution.log')
        changed = raw.replace(b'"phase":"testing"', b'"phase":"failed"')
        changed = changed.replace(b'"error":null', b'"error":"invented failure"')
        fact = fixture.replace_member(self.timeout_result, 'logs/execution.log', changed)
        with self.assertRaisesRegex(ControlError, 'Outer timeout'):
            proof.partial_progress(fact, self.third_data)

    def test_push_bridge_requires_matching_complete_nonforce_record_pair(self):
        self.multi_chain()
        path = Path(self.push_result['path']); original = path.read_bytes()
        with zipfile.ZipFile(path) as archive: raw = archive.read('logs/execution.log')
        mutations = [raw.replace(b'"force":false', b'"force":true'),
                     raw.replace(b'"success":true', b'"success":false'),
                     raw.replace(b'"local_product_changes":false', b'"local_product_changes":true'),
                     raw.replace(b'"new_commit_created":false', b'"new_commit_created":true'),
                     raw + raw, raw.splitlines(keepends=True)[0],
                     raw.replace(b'"ref":"refs/heads/dev"', b'"ref":"refs/heads/main"', 1)]
        for index, value in enumerate(mutations):
            with self.subTest(index=index):
                path.write_bytes(original)
                fact = fixture.replace_member(self.push_result, 'logs/execution.log', value)
                with self.assertRaises(ControlError): proof.push_source(fact)

    def test_all_original_roles_and_mandatory_tests_survive_corrections(self):
        left = deepcopy(self.original_data); left['format_version'] = 2
        for item in left['stages']: item['role'] = 'implementation'
        right = deepcopy(self.resumed_data)
        for item in right['stages']: item['role'] = 'implementation'
        right['correction_of']['plan_sha256'] = hashed(public_plan(left))
        for mutate in ('role', 'identity', 'message', 'scope', 'test', 'program', 'rest'):
            with self.subTest(mutate=mutate):
                bad = deepcopy(right)
                if mutate == 'role': bad['stages'][0]['role'] = 'correction'
                if mutate == 'identity': bad['stages'][0]['commit_id'] = 'different.W'
                if mutate == 'message': bad['stages'][0]['message'] += ' changed'
                if mutate == 'scope': bad['stages'][0]['after'].pop('src/new.py')
                if mutate == 'test': bad['stages'][0]['test_plan']['test_files'] = []
                if mutate == 'rest': bad['stages'].pop()
                with self.assertRaises(ControlError):
                    proof.correction(left, bad, 1, 'different' if mutate == 'program' else 'same', 'same')

    def test_open_clarification_payload_cannot_change(self):
        left = deepcopy(self.original_data)
        left['stages'][0]['role'] = 'clarification'
        right = deepcopy(left); right['initial_dirty'] = True; right['bundle_number'] = '009'
        right['correction_of'] = {'plan_sha256': hashed(public_plan(left)),
                                 'remaining_commit_ids': [item['commit_id'] for item in left['stages']]}
        right['stages'][0]['after']['spec/example.md'] = '0' * 64
        with self.assertRaisesRegex(ControlError, 'clarification bytes'):
            proof.correction(left, right, 0, 'same', 'same')

    def test_push_bridge_cannot_hide_extra_local_files(self):
        self.multi_chain()
        with zipfile.ZipFile(self.push_result['path']) as archive:
            log = archive.read('logs/execution.log')
        push_files = self.final_files | {'src/example.py': b'value = (33)\n', 'src/foreign.py': b'foreign = True\n'}
        self.push_result = self.result('push-result.zip', previous=self.corrected, patch_sha=self.push_patch['sha256'],
            base=push_files, log=log, binding=self.corrected['binding'], captured_at='2026-01-01T05:00:00Z')
        self.next_data['source_result_sha256'] = self.push_result['sha256']
        self.next_patch = patch_package(self.exchange / 'next.zip', self.next_data)
        self.final = self.result('next-result.zip', previous=self.push_result, patch_sha=self.next_patch['sha256'],
            base=self.final_files, log=log_for(self.next_data, ['1' * 40]),
            binding={**self.binding, 'base_commit': '1' * 40}, completed_commit='1' * 40,
            captured_at='2026-01-01T06:00:00Z')
        with self.assertRaisesRegex(ControlError, 'push bridge'): self.queue()
        self.preserved()

    def test_missing_middle_archive_blocks_and_preserves_claim(self):
        self.multi_chain(); Path(self.middle['path']).unlink(); self.rejected()

    def test_known_intermediate_result_is_not_reassigned(self):
        self.multi_chain()
        from specroad_control.ledger import Ledger
        original = Ledger.known_runs
        with patch.object(Ledger, 'known_runs', lambda ledger: original(ledger) | {self.middle['run_id']}):
            self.rejected()

    def test_chain_limit_fails_closed_before_any_history_write(self):
        self.multi_chain()
        with patch.object(proof, 'MAX_LINKS', 5): self.rejected()

    def test_mutated_archive_after_queue_blocks_idle_adoption(self):
        self.multi_chain(); self.queue()
        with Path(self.third['path']).open('ab') as stream: stream.write(b'changed')
        with self.engine() as engine:
            with self.assertRaises(ControlError): engine.tick()
            self.assertEqual(engine.codex.calls, 0)
        self.preserved()

    def test_archived_multistep_chain_keeps_exact_pending_identity(self):
        self.multi_chain(); self.queue()
        archive = self.exchange / 'PatchHarbor-Archive'; archive.mkdir()
        for path in list(self.exchange.glob('*.zip')): path.rename(archive / path.name)
        with self.engine() as engine:
            self.assertTrue(engine.tick()['again']); self.assertEqual(engine.codex.calls, 0)

    def test_extended_switch_cannot_relax_normal_reconciliation(self):
        with self.assertRaises(ControlError): enqueue(self.paths, self.final['path'], extended_chain=True)
        self.preserved()

    def test_conflicting_intermediate_run_identity_is_not_hidden_by_binding_filter(self):
        self.multi_chain()
        self.result('identity-conflict.zip', run_id=self.middle['run_id'],
                    binding={**self.binding, 'base_commit': '9' * 40}, captured_at='2026-01-01T02:00:00Z')
        with self.assertRaises(ControlError) as caught: self.queue()
        self.assertEqual(caught.exception.code, 'result_identity_conflict'); self.preserved()

    def test_commit_hash_cannot_reappear_in_a_later_independent_plan(self):
        self.multi_chain()
        self.final = self.result('next-result.zip', previous=self.push_result, patch_sha=self.next_patch['sha256'],
            base=self.final_files, log=log_for(self.next_data, ['d' * 40]),
            binding={**self.binding, 'base_commit': 'd' * 40}, completed_commit='d' * 40,
            captured_at='2026-01-01T06:00:00Z')
        with self.assertRaisesRegex(ControlError, 'commit hash is repeated'): self.queue()
        self.preserved()

    def test_zero_committed_prefix_keeps_original_base_and_complete_dirty_first_stage(self):
        work = {'src/example.py': b'value = 1\n'}
        self.original_data['stages'] = [stage('example.W', self.initial_files, work)]
        self.original = patch_package(self.exchange/'original.zip', self.original_data)
        dirty = self.initial_files | work
        self.checkpoint = self.result('checkpoint.zip', previous=self.seed, patch_sha=self.original['sha256'],
            base=self.initial_files, work=dirty, log=log_for(self.original_data, [], failed=True),
            binding={**self.seed['binding'], 'state_fingerprint': 'd' * 16},
            dirty=True, success=False, primary_kind='entrypoint_exit', captured_at='2026-01-01T01:00:00Z')
        updates = {'src/example.py': b'value = 11\n'}
        self.resumed_data.update(binding=self.checkpoint['binding'], source_result_sha256=self.checkpoint['sha256'],
            correction_of={'plan_sha256': hashed(public_plan(self.original_data)), 'remaining_commit_ids': ['example.W']},
            stages=[stage('example.W', dirty, updates)])
        self.resumed = patch_package(self.exchange/'resumed.zip', self.resumed_data)
        self.final = self.result('final.zip', previous=self.checkpoint, patch_sha=self.resumed['sha256'],
            base=self.initial_files | updates, log=log_for(self.resumed_data, ['c' * 40]),
            binding={**self.binding, 'base_commit': 'c' * 40}, completed_commit='c' * 40,
            captured_at='2026-01-01T02:00:00Z')
        self.queue()
        with self.engine() as engine:
            self.assertTrue(engine.tick()['again']); self.assertEqual(engine.codex.calls, 0)
