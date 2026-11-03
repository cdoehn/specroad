"""Exact native Result identities resolve a chain with unchanged repository state."""
from copy import deepcopy
from pathlib import Path
import shutil
from specroad_control.apply_reconcile_proof import hashed, public_plan
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from codex_control_tests.apply_reconcile_support import patch_package
from codex_control_tests.blocked_chain_support import log_for
from codex_control_tests.mixed_support import MixedCase, postimage


class PatchSourceSelectionTests(MixedCase):
    def test_two_results_with_one_binding_select_only_their_own_packages(self):
        other = self.result('other.zip')
        first = patch_package(self.exchange / 'first.zip', self.data())
        second = patch_package(self.exchange / 'second.zip', self.data(other))
        self.assertEqual(self.seed['binding'], other['binding'])
        self.assertNotEqual(self.seed['sha256'], other['sha256'])
        self.assertEqual([p['sha256'] for p in self.engine.exchange.patches(self.seed)], [first['sha256']])
        self.assertEqual([p['sha256'] for p in self.engine.exchange.patches(other)], [second['sha256']])

    def test_real_same_source_ambiguity_still_blocks_without_model_or_claim(self):
        patch_package(self.exchange / 'first.zip', self.data())
        data = self.data(); data['bundle_number'] = '556'
        patch_package(self.exchange / 'second.zip', data)
        with self.assertRaises(ControlError) as caught:
            self.engine.tick()
        self.assertEqual(caught.exception.code, 'ambiguous_patch')
        self.assertEqual(self.ledger().current()['stage'], 'ready')
        self.assertEqual(self.codex.calls, 0)

    def test_duplicate_bytes_and_archival_do_not_create_another_candidate(self):
        other = self.result('other.zip')
        first = patch_package(self.exchange / 'first.zip', self.data())
        patch_package(self.exchange / 'other-patch.zip', self.data(other))
        archive = self.exchange / 'PatchHarbor-Archive'; archive.mkdir()
        shutil.copyfile(first['path'], archive / 'duplicate.zip')
        Path(other['path']).rename(archive / 'other-result.zip')
        self.assertEqual([p['sha256'] for p in self.engine.exchange.patches(self.seed)], [first['sha256']])

    def test_manual_failure_chain_advances_in_hash_order_without_new_authority(self):
        # Two real failed results preserve one dirty repository binding, as in
        # the observed incident. All historical packages remain in Exchange.
        self.dispatch(True)
        failed = self.outcome(completed=0)
        self.engine.tick()
        initial = self.ledger().request_contract()
        self.assertEqual(initial, new_contract(2, allowed=False, version=4, continuation=True))
        data = self.correction()
        first = patch_package(self.exchange / 'manual-1.zip', data)
        work = postimage(self.files, self.latest_data['stages'][:1])
        later = self.result('manual-failed.zip', previous=failed, patch_sha=first['sha256'],
            binding=failed['binding'], base=self.files, work=work, log=log_for(data, [], failed=True),
            success=False, dirty=True, primary_kind='entrypoint_exit',
            captured_at='2026-01-01T02:00:00Z')
        continuation = deepcopy(data)
        continuation.update(bundle_number='557', source_result_sha256=later['sha256'],
            correction_of={'plan_sha256': hashed(public_plan(data)),
                           'remaining_commit_ids': [s['commit_id'] for s in data['stages']]})
        second = patch_package(self.exchange / 'manual-2.zip', continuation)
        self.assertEqual(later['binding'], failed['binding'])
        self.engine.tick()
        self.assertEqual(self.ledger().current()['patch_sha'], first['sha256'])
        self.assertEqual(self.ledger().output_kind(), 'unknown')
        self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], later['sha256'])
        self.assertEqual(self.ledger().current()['patch_sha'], second['sha256'])
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False, version=4))
        self.assertEqual(self.codex.calls, 1)
        self.latest_data = continuation
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False, version=4))
        self.assertEqual(self.codex.calls, 1)
