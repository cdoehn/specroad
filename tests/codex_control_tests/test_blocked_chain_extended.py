"""Multi-correction recovery keeps all native evidence and the old blocked claim."""
from copy import deepcopy
import base64
import json
from pathlib import Path
import zipfile

from specroad_control.apply_reconcile import enqueue, validate_history
from specroad_control.apply_reconcile_proof import canonical, hashed, public_plan
from codex_control_tests.apply_reconcile_support import patch_package, ReconcileCore
from codex_control_tests.automation_support import read_package
from codex_control_tests.blocked_chain_support import log_for, stage
from codex_control_tests import test_blocked_chain as existing
from codex_control_tests.test_recovery import LedgerContext


def replace_member(fact, name, raw):
    path = Path(fact['path'])
    with zipfile.ZipFile(path) as archive:
        contents = {key: archive.read(key) for key in archive.namelist()}
    contents[name] = raw
    with zipfile.ZipFile(path, 'w') as archive:
        for key, value in contents.items():
            archive.writestr(key, value)
    return ReconcileCore().patch(path) if fact['kind'] == 'patch' else read_package(path)


class ExtendedChainTests(existing.BlockedChainTests):
    # Reuse all existing snapshot, archive, pause, transaction, identity and
    # history guards against the separately opted-in v3 implementation.
    def queue(self):
        return enqueue(self.paths, self.final['path'], blocked=True, extended_chain=True)

    def multi_chain(self, *, timeout=True, bridge=True):
        updates = {name: base64.b64decode(raw)
                   for name, raw in self.resumed_data['stages'][0]['payloads'].items()}
        after_w = self.dirty_files | updates
        after_r = after_w | {'src/example.py': b'value = 12\n'}
        self.middle = self.result('final.zip', previous=self.checkpoint, patch_sha=self.resumed['sha256'],
            base=after_w, work=after_r, log=log_for(self.resumed_data, ['e' * 40], failed=True),
            binding={**self.binding, 'base_commit': 'e' * 40, 'state_fingerprint': 'e' * 16},
            dirty=True, success=False, primary_kind='entrypoint_exit', captured_at='2026-01-01T02:00:00Z')
        corrected_r = {'src/example.py': b'value = 22\n'}
        corrected_c = {'src/example.py': b'value = (22)\n'}
        self.third_data = {**deepcopy(self.resumed_data), 'bundle_number': '003',
            'binding': self.middle['binding'], 'source_result_sha256': self.middle['sha256'],
            'correction_of': {'plan_sha256': hashed(public_plan(self.resumed_data)),
                              'remaining_commit_ids': ['example.R', 'example.C']},
            'stages': [stage('example.R', after_r, corrected_r),
                       stage('example.C', after_r | corrected_r, corrected_c)]}
        self.third = patch_package(self.exchange / 'third.zip', self.third_data)
        third_log = log_for(self.third_data, ['f' * 40], failed=True)
        if timeout:
            third_log = third_log.replace(b'"phase":"failed"', b'"phase":"testing"').replace(
                b'"error":"Test gate failed."', b'"error":null')
        self.timeout_result = self.result('timeout.zip', previous=self.middle, patch_sha=self.third['sha256'],
            base=after_r | corrected_r, work=after_r | corrected_c, log=third_log,
            binding={**self.binding, 'base_commit': 'f' * 40, 'state_fingerprint': 'f' * 16},
            dirty=True, success=False, primary_kind='timeout' if timeout else 'entrypoint_exit',
            captured_at='2026-01-01T03:00:00Z')
        if timeout:
            self.timeout_result = replace_member(self.timeout_result, 'logs/run.json', canonical({
                'run_id': self.timeout_result['run_id'], 'ended_at': '2026-01-01T03:00:00Z',
                'operation': 'apply', 'dry_run': False, 'primary_result': {'kind': 'timeout', 'success': False,
                    'timed_out': True, 'interrupted': False, 'entrypoint_started': True,
                    'entrypoint_exit_code': None}}))
        final_updates = {'src/example.py': b'value = (33)\n'}
        self.fourth_data = {**deepcopy(self.third_data), 'bundle_number': '004',
            'binding': self.timeout_result['binding'], 'source_result_sha256': self.timeout_result['sha256'],
            'correction_of': {'plan_sha256': hashed(public_plan(self.third_data)), 'remaining_commit_ids': ['example.C']},
            'stages': [stage('example.C', after_r | corrected_c, final_updates)]}
        self.fourth = patch_package(self.exchange / 'fourth.zip', self.fourth_data)
        self.final_files = after_r | final_updates
        self.corrected = self.result('corrected.zip', previous=self.timeout_result, patch_sha=self.fourth['sha256'],
            base=self.final_files, log=log_for(self.fourth_data, ['c' * 40]),
            binding={**self.binding, 'base_commit': 'c' * 40}, completed_commit='c' * 40,
            captured_at='2026-01-01T04:00:00Z')
        self.final = self.corrected
        if bridge:
            push_data = {**deepcopy(self.fourth_data), 'binding': self.corrected['binding']}
            self.push_patch = patch_package(self.exchange / 'push.zip', push_data)
            self.push_patch = replace_member(self.push_patch, 'run.sh', b'#!/bin/sh\n# Synthetic opaque native push fixture.\n')
            start = {'source_result_sha256': self.corrected['sha256'], 'target_commit': 'c' * 40,
                     'remote': 'origin', 'ref': 'refs/heads/dev', 'remote_before': 'b' * 40}
            log = b'SPECROAD_PUSH_START ' + canonical(start | {'force': False}) + b'\n'
            log += b'SPECROAD_PUSH_COMPLETE ' + canonical(start | {'remote_after': 'c' * 40, 'success': True,
                'local_product_changes': False, 'new_commit_created': False}) + b'\n'
            self.push_result = self.result('push-result.zip', previous=self.corrected, patch_sha=self.push_patch['sha256'],
                base=self.final_files, log=log, binding=self.corrected['binding'], captured_at='2026-01-01T05:00:00Z')
            self.next_data = {'format_version': 2, 'handoff_kind': 'patch_ready', 'bundle_number': '005',
                'source_result_sha256': self.push_result['sha256'], 'binding': self.push_result['binding'],
                'apply_repository': self.seed['repository_path'], 'branch': 'dev', 'initial_dirty': False,
                'correction_of': None, 'stages': [stage('next.W', self.final_files,
                    {'src/example.py': b'value = 44\n'}) | {'role': 'implementation'}]}
            self.next_patch = patch_package(self.exchange / 'next.zip', self.next_data)
            self.final_files |= {'src/example.py': b'value = 44\n'}
            self.final = self.result('next-result.zip', previous=self.push_result, patch_sha=self.next_patch['sha256'],
                base=self.final_files, log=log_for(self.next_data, ['1' * 40]),
                binding={**self.binding, 'base_commit': '1' * 40}, completed_commit='1' * 40,
                captured_at='2026-01-01T06:00:00Z')

    def test_multiple_corrections_native_timeout_push_and_later_plan_are_adopted_once(self):
        self.multi_chain()
        originals = {path: path.read_bytes() for path in self.exchange.iterdir() if path.is_file()}
        self.queue()
        with LedgerContext(self.paths, self.config) as ledger:
            doc = validate_history(ledger)
            self.assertEqual(doc['version'], 3)
            self.assertEqual([row['kind'] for row in doc['artifacts']['steps']],
                             ['failed_gate', 'failed_gate', 'timeout', 'completed_plan', 'unchanged_push', 'completed_plan'])
        with self.engine() as engine:
            self.assertTrue(engine.tick()['again']); self.assertEqual(engine.codex.calls, 0)
            with LedgerContext(self.paths, self.config) as ledger:
                self.assertEqual(ledger.current()['sha'], self.final['sha256'])
                self.assertEqual(ledger.seed_sha, self.seed['sha256'])
                self.assertEqual(ledger.request_contract()['clarifications_remaining'], 2)
                self.assertFalse(ledger.request_contract()['clarification_allowed'])
            self.assertTrue(engine.tick()['halted']); self.assertEqual(engine.codex.calls, 1)
        self.assertEqual(originals, {path: path.read_bytes() for path in originals})

    def test_multiple_failed_gates_without_timeout_or_bridge(self):
        self.multi_chain(timeout=False, bridge=False)
        self.queue()
        with self.engine() as engine:
            self.assertTrue(engine.tick()['again']); self.assertEqual(engine.codex.calls, 0)

    def test_legacy_blocked_command_keeps_original_chain_limit(self):
        self.multi_chain()
        from specroad_control.errors import ControlError
        with self.assertRaises(ControlError): enqueue(self.paths, self.final['path'], blocked=True)
        self.preserved()
