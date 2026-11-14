"""Complete correction prefixes may be followed by new planned implementation."""
from copy import deepcopy
from codex_control_tests.mixed_support import MixedCase, postimage, stage
from specroad_control.apply_snapshot import snapshot


class LookaheadTests(MixedCase):
    def append_group(self, value):
        _, current = snapshot(self.following)
        files = postimage({name: raw for name, (_mode, raw) in current.items()}, value['stages'])
        for index, suffix in enumerate('WRC', 4):
            updates = {'src/example.py': f'value = {index}\n'.encode()}
            value['stages'].append(stage('next.' + suffix, files, updates) | {'role': 'implementation'})
            files.update(updates)
        return value

    def test_open_rest_and_new_group_keep_separate_gates_and_followup(self):
        self.dispatch(); self.outcome(completed=1); self.engine.tick()
        value = self.append_group(self.correction())
        self.assertEqual(value['correction_of']['remaining_commit_ids'], ['feature.R', 'feature.C'])
        self.assertFalse(self.dispatch(data=value)['halted'])
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().current()['source']['sha256'], self.following['sha256'])
        self.assertEqual(self.ledger().request_contract()['clarifications_remaining'], 3)
        self.assertEqual(self.codex.calls, 2)

    def test_failure_in_appended_group_retains_only_its_unfinished_stages(self):
        self.dispatch(); self.outcome(completed=1); self.engine.tick()
        self.dispatch(data=self.append_group(self.correction()))
        self.outcome(completed=3); self.engine.tick()
        value = self.correction()
        self.assertEqual([s['commit_id'] for s in value['stages']], ['next.R', 'next.C'])
        self.assertFalse(self.dispatch(data=value)['halted'])
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], self.following['sha256'])

    def test_pending_clarification_is_byte_identical_before_extended_implementation(self):
        self.dispatch(True); prefix = deepcopy(self.latest_data['stages'][0])
        self.outcome(completed=0); self.engine.tick()
        value = self.append_group(self.correction())
        self.assertEqual(value['stages'][0]['after'], prefix['after'])
        self.assertFalse(self.dispatch(True, value)['halted'])
        self.outcome(); self.engine.tick()
        self.assertEqual(self.ledger().current()['sha'], self.following['sha256'])

    def test_appended_completed_id_is_not_a_new_planned_stage(self):
        self.dispatch(); self.outcome(completed=1); self.engine.tick()
        value = self.append_group(self.correction())
        value['stages'][2]['commit_id'] = 'feature.W'
        value['stages'][2]['test_plan']['commit_id'] = 'feature.W'
        self.assertTrue(self.dispatch(data=value)['halted'])
        self.assertIsNone(self.ledger().current()['patch_sha'])
