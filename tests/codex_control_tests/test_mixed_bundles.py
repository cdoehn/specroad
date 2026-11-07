"""Optional clarification and regular W/R/C through the real Control state machine."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from specroad_control.automation import Engine, Gate
from specroad_control.errors import ControlError
from specroad_control.job_contract import contract, new_contract, schema_for
from specroad_control.local import json_read
from specroad_control.mixed_contract import CAPABILITY, MIXED, capability
from specroad_control.mixed_evidence import verify_handoff, verify_followup
from specroad_control.apply_reconcile_proof import canonical
from specroad_control.ph_bridge import development_capability
from codex_control_tests.apply_reconcile_support import patch_package, ReconcileCore
from codex_control_tests.mixed_support import MixedCase, SPEC, PLAN


class MixedBundleTests(MixedCase):
    def test_regular_plan_needs_no_clarification_commit(self):
        self.assertFalse(self.dispatch()['halted'])
        self.assertEqual(self.ledger().output_kind(), 'patch_ready')
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))
        self.assertEqual([s['commit_id'] for s in self.latest_data['stages']], ['feature.W', 'feature.R', 'feature.C'])
        self.assertTrue(all(SPEC not in s['after'] for s in self.latest_data['stages']))
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))
        self.assertEqual(self.codex.calls, 1)

    def test_optional_prefix_and_three_real_commits_complete_one_handoff(self):
        self.assertFalse(self.dispatch(True)['halted'])
        self.assertEqual(self.ledger().output_kind(), MIXED)
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))
        self.assertEqual(self.ledger().current()['sha'], self.following['sha256'])
        self.assertEqual(self.codex.calls, 1)

    def test_split_plan_prefix_and_bound_remainder_keep_scope_and_budget(self):
        from support.plan_scope import PLAN_PARTS, add_plan_payload
        data = self.data(mixed=True)
        for name in PLAN_PARTS:
            add_plan_payload(data['stages'][0], name)
        self.assertFalse(self.dispatch(True, data)['halted'])
        self.outcome(completed=0); self.engine.tick()
        expected = new_contract(2, allowed=False, version=4, continuation=True)
        self.assertEqual(self.ledger().request_contract(), expected)
        remaining = self.correction()
        changed = deepcopy(remaining)
        add_plan_payload(changed['stages'][0], PLAN_PARTS[0], b'Changed acceptance\n')
        fact = patch_package(self.exchange/'changed-plan-part.zip', changed)
        with self.assertRaises(ControlError):
            verify_handoff(self.engine, self.following, fact, expected, MIXED)
        # The rejected package is not submitted to the next dispatch.
        Path(fact['path']).unlink()
        self.assertFalse(self.dispatch(True, remaining)['halted'])
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))
        self.assertEqual(self.codex.calls, 2)

    def test_result_does_not_complete_on_document_commit_alone(self):
        self.dispatch(True); self.outcome(completed=1); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False, version=4))
        remaining = self.correction()
        self.assertEqual([s['commit_id'] for s in remaining['stages']], ['feature.W', 'feature.R', 'feature.C'])
        self.assertFalse(self.dispatch(data=remaining)['halted'])
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))

    def test_failed_prefix_before_install_preserves_exact_pending_authority(self):
        self.dispatch(True); self.outcome(completed=0, dirty=False); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False, version=4, continuation=True))
        self.assertFalse(self.dispatch(True, self.correction())['halted'])
        self.outcome(completed=0, dirty=False); self.engine.tick()
        self.assertEqual(self.ledger().request_contract()['clarifications_remaining'], 2)
        self.assertTrue(self.ledger().request_contract()['clarification_continuation'])
        self.assertFalse(self.dispatch(True, self.correction())['halted'])
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))

    def test_committed_work_is_not_replayed_after_right_gate_failure(self):
        self.dispatch(True); self.outcome(completed=2); self.engine.tick()
        data = self.correction()
        self.assertEqual([s['commit_id'] for s in data['stages']], ['feature.R', 'feature.C'])
        self.assertFalse(self.dispatch(data=data)['halted'])
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))

    def test_dirty_correction_failing_before_commit_keeps_base_distinct(self):
        self.dispatch(True); self.outcome(completed=1); self.engine.tick()
        self.dispatch(data=self.correction()); self.outcome(completed=0); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(2, allowed=False, version=4))

    def test_no_budget_consumption_while_waiting_for_result(self):
        self.dispatch(True)
        for _ in range(3):
            self.assertFalse(self.engine.tick()['again'])
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))
        self.assertEqual(self.codex.calls, 1)

    def test_restart_and_pause_preserve_pending_prefix_and_budget(self):
        self.dispatch(True); self.outcome(completed=0, dirty=False); self.engine.tick()
        selected = self.ledger().request_contract()
        self.engine.close()
        gate = Gate(); gate.set(False)
        self.engine = Engine(self.config, self.paths, gate, core=ReconcileCore(), codex=self.codex)
        self.addCleanup(self.engine.close)
        for _ in range(2): self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), selected)
        self.assertEqual(self.codex.calls, 1)

    def test_unknown_package_never_renews_budget(self):
        self.ledger().bind_contract(new_contract(1, allowed=False, version=4))
        data = self.data()
        self.latest_data = data
        self.latest_patch = patch_package(self.exchange / 'manual.zip', data)
        self.engine.tick()
        self.assertEqual(self.ledger().output_kind(), 'unknown')
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(1, allowed=False, version=4))
        self.assertEqual(self.codex.calls, 0)

    def test_existing_v3_attempt_is_pinned_until_normal_completion(self):
        self.ledger().bind_contract(new_contract(1, allowed=False))
        self.dispatch()
        self.assertEqual(self.ledger().request_contract(), new_contract(1, allowed=False))
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))

    def test_v4_disallows_separate_spec_clarification(self):
        self.codex.kind = 'spec_clarification'
        self.assertTrue(self.engine.tick()['halted'])
        self.assertEqual(self.ledger().current()['error'], 'clarification_limit')

    def test_exhausted_contract_still_permits_regular_plan(self):
        self.ledger().bind_contract(new_contract(0, allowed=False, version=4))
        self.assertFalse(self.dispatch()['halted'])
        self.assertNotIn(MIXED, self.codex.schemas[-1]['properties']['status']['enum'])

    def test_no_fresh_clarification_after_failure(self):
        self.dispatch(True); self.outcome(completed=1); self.engine.tick()
        self.assertTrue(self.dispatch(True)['halted'])
        self.assertEqual(self.ledger().current()['error'], 'clarification_limit')

    def test_pending_clarification_target_must_remain_byte_identical(self):
        self.dispatch(True); self.outcome(completed=0, dirty=False); self.engine.tick()
        data = self.correction()
        import base64
        from hashlib import sha256
        raw = b'A different decision\n'
        data['stages'][0]['payloads'][SPEC] = base64.b64encode(raw).decode()
        data['stages'][0]['after'][SPEC] = sha256(raw).hexdigest()
        self.assertTrue(self.dispatch(True, data)['halted'])
        self.assertEqual(self.ledger().output_kind(), None)

    def test_source_snapshot_preimage_is_required(self):
        data = self.data()
        data['stages'][0]['before']['src/example.py'] = 'f' * 64
        self.assertTrue(self.dispatch(data=data)['halted'])
        self.assertIsNone(self.ledger().output_kind())

    def test_success_record_without_promised_file_bytes_does_not_advance(self):
        self.dispatch(True)
        self.outcome(mutate_base=lambda files: files | {'src/example.py': b'wrong\n'})
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])
        self.assertEqual(self.ledger().request_contract(), new_contract(version=4))

    def test_missing_stage_gate_cannot_reset_budget(self):
        self.dispatch(True)
        def mutate(raw):
            lines = raw.decode().splitlines()
            record = json.loads(lines[-1].split(' ', 1)[1])
            del record['committed'][0]['gate']
            return lines[0].encode() + b'\nSPECROAD_APPLY_PROGRESS ' + canonical(record)
        self.outcome(mutate_log=mutate)
        with self.assertRaises(ControlError): self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], self.seed['sha256'])

    def test_missing_original_zip_blocks_remaining_sequence(self):
        self.dispatch(True); self.outcome(completed=1); self.engine.tick()
        data = self.correction()
        Path(self.latest_patch['path']).unlink()
        self.assertTrue(self.dispatch(data=data)['halted'])
        self.assertIsNone(self.ledger().output_kind())

    def test_hiding_prefix_as_patch_ready_is_rejected(self):
        data = self.data(mixed=True); data['handoff_kind'] = 'patch_ready'
        self.assertTrue(self.dispatch(data=data)['halted'])
        self.assertIsNone(self.ledger().output_kind())

    def test_mixed_bundle_requires_actual_implementation(self):
        data = self.data(mixed=True)
        data['stages'] = data['stages'][:1]
        self.assertTrue(self.dispatch(True, data)['halted'])
        self.assertIsNone(self.ledger().output_kind())

    def test_prefix_cannot_change_product_code(self):
        data = self.data(mixed=True)
        for field in ('before', 'after', 'payloads'):
            data['stages'][0][field].update(data['stages'][1][field])
        self.assertTrue(self.dispatch(True, data)['halted'])

    def test_changed_behavior_test_cannot_be_omitted_from_gate(self):
        from codex_control_tests.blocked_chain_support import stage
        data = self.data()
        data['stages'][0] = stage('feature.W', self.files, {'tests/test_added.py': b'def test_added():\n    assert True\n'}) | {'role': 'implementation'}
        self.assertTrue(self.dispatch(data=data)['halted'])

    def test_native_capability_is_read_from_exact_committed_snapshot(self):
        actual = development_capability(Path(self.seed['path']), self.seed['sha256'])
        self.assertEqual(actual, CAPABILITY)
        with self.assertRaises(ValueError):
            development_capability(Path(self.seed['path']), '0' * 64)


class AbsentOptInTests(MixedCase):
    installed = False

    def test_no_installed_opt_in_keeps_legacy_default(self):
        self.assertFalse(self.dispatch()['halted'])
        self.assertEqual(self.ledger().request_contract(), new_contract())
        self.assertIsNone(development_capability(Path(self.seed['path']), self.seed['sha256']))


class TypedContractTests(unittest.TestCase):
    def test_optional_schema_retains_regular_status_in_all_v4_modes(self):
        for selected in (new_contract(version=4), new_contract(0, allowed=False, version=4),
                         new_contract(0, allowed=False, version=4, continuation=True)):
            values = schema_for(selected)['properties']['status']['enum']
            self.assertIn('patch_ready', values)
            self.assertNotIn('spec_clarification', values)
            self.assertEqual(MIXED in values, selected['clarification_allowed'] or selected['clarification_continuation'])

    def test_capability_rejects_missing_extra_and_boolean_numbers(self):
        for key, value in CAPABILITY.items():
            bad = deepcopy(CAPABILITY); del bad[key]
            with self.subTest(key=key), self.assertRaises(ValueError): capability(bad)
            bad = deepcopy(CAPABILITY); bad[key] = not value if type(value) is bool else True if type(value) is int else ''
            with self.subTest(key=key), self.assertRaises(ValueError): capability(bad)
        with self.assertRaises(ValueError): capability(CAPABILITY | {'extra': 1})

    def test_continuation_and_fresh_authority_are_mutually_exclusive(self):
        with self.assertRaises(ControlError): new_contract(version=4, continuation=True)
        for value in (0, 1, None, 'false'):
            with self.subTest(value=value), self.assertRaises(ControlError):
                contract(new_contract(version=4) | {'clarification_continuation': value})

    def test_legacy_contracts_cannot_receive_continuation_flag(self):
        for version in (1, 2, 3):
            with self.subTest(version=version), self.assertRaises(ControlError):
                new_contract(version=version, continuation=True)
