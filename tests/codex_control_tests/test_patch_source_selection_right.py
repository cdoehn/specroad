"""Missing evidence, races, native identity conflicts and conservative legacy reads."""
from pathlib import Path
import json
from unittest.mock import patch
import zipfile
from specroad_control.automation import Engine, Gate
from specroad_control.apply_reconcile_proof import canonical
from specroad_control.errors import ControlError
from specroad_control.job_contract import new_contract
from codex_control_tests.apply_reconcile_support import patch_package, ReconcileCore
from codex_control_tests.mixed_support import MixedCase


def rewrite(path, member, raw):
    with zipfile.ZipFile(path) as archive:
        values = {name: archive.read(name) for name in archive.namelist()}
    values[member] = raw
    with zipfile.ZipFile(path, 'w') as archive:
        for name, value in values.items():
            archive.writestr(name, value)


class PatchSourceSelectionRightTests(MixedCase):
    def test_missing_foreign_result_never_silently_excludes_a_package(self):
        other = self.result('other.zip')
        patch_package(self.exchange / 'other-patch.zip', self.data(other))
        Path(other['path']).unlink()
        with self.assertRaises(ControlError) as caught:
            self.engine.tick()
        self.assertEqual(caught.exception.code, 'patch_source_unproven')
        self.assertEqual(self.ledger().current()['stage'], 'ready')
        self.assertEqual(self.codex.calls, 0)

    def test_exact_source_repository_dirty_and_inner_binding_cannot_disagree(self):
        for field, value in [('apply_repository', '/unrelated/apply'), ('initial_dirty', True),
                             ('binding', self.binding | {'state_fingerprint': 'c' * 16})]:
            with self.subTest(field=field):
                data = self.data(); data[field] = value
                fact = patch_package(self.exchange / 'invalid.zip', data)
                if field == 'binding':
                    # Outer native binding is genuine, inner DATA contradicts it.
                    with zipfile.ZipFile(fact['path']) as archive:
                        metadata = json.loads(archive.read('patch.json'))
                    rewrite(fact['path'], 'patch.json', canonical(metadata | self.binding))
                with self.assertRaises(ControlError) as caught:
                    self.engine.exchange.patches(self.seed)
                self.assertEqual(caught.exception.code, 'patch_source_unproven')

    def test_foreign_source_requires_real_repository_dirty_and_nonsimulation_proof(self):
        for changes in ({'repository_path': '/unrelated/apply'}, {'dirty': True}, {'dry_run': True}):
            with self.subTest(changes=changes):
                other = self.result('other.zip', **changes)
                data = self.data(other)
                # Claim compatibility with this repository, rather than the native facts.
                data.update(apply_repository=self.seed['repository_path'], initial_dirty=False)
                patch_package(self.exchange / 'other-patch.zip', data)
                with self.assertRaises(ControlError) as caught:
                    self.engine.exchange.patches(self.seed)
                self.assertEqual(caught.exception.code, 'patch_source_unproven')

    def test_foreign_run_id_with_conflicting_bytes_is_not_an_unrelated_hint(self):
        other = self.result('other.zip')
        self.result('conflicting.zip', run_id=other['run_id'])
        # Ensure different bytes despite the intentionally repeated run ID.
        rewrite(self.exchange / 'conflicting.zip', 'extra.txt', b'conflicting native package')
        patch_package(self.exchange / 'other-patch.zip', self.data(other))
        with self.assertRaises(ControlError) as caught:
            self.engine.exchange.patches(self.seed)
        self.assertEqual(caught.exception.code, 'result_identity_conflict')

    def test_patch_change_after_native_validation_cannot_fall_back_to_legacy(self):
        fact = patch_package(self.exchange / 'changing.zip', self.data())
        validate = self.engine.core.validate
        def change(*args):
            result = validate(*args)
            rewrite(fact['path'], 'run.sh', b'changed after native validation')
            return result
        with patch.object(self.engine.core, 'validate', side_effect=change):
            with self.assertRaises(ControlError):
                self.engine.tick()
        self.assertEqual(self.ledger().current()['stage'], 'ready')
        self.assertEqual(self.codex.calls, 0)

    def test_unreadable_plan_cannot_hide_a_competing_native_package(self):
        first = patch_package(self.exchange / 'first.zip', self.data())
        second = patch_package(self.exchange / 'opaque.zip', self.data())
        rewrite(second['path'], 'run.sh', b'#!/bin/sh\nexit 99\n')
        with self.assertRaises(ControlError) as caught:
            self.engine.tick()
        self.assertEqual(caught.exception.code, 'ambiguous_patch')
        self.assertEqual(self.codex.calls, 0)
        self.assertTrue(Path(first['path']).exists())

    def test_legacy_v1_keeps_four_value_selection_even_with_foreign_sha(self):
        data = self.data(); data.update(format_version=1, source_result_sha256='f' * 64)
        del data['handoff_kind']
        for stage in data['stages']:
            del stage['role']
        fact = patch_package(self.exchange / 'legacy.zip', data)
        self.assertEqual([p['sha256'] for p in self.engine.exchange.patches(self.seed)], [fact['sha256']])

    def test_restart_preserves_selected_patch_history_and_unknown_classification(self):
        self.ledger().bind_contract(new_contract(version=4))
        other = self.result('other.zip')
        first = patch_package(self.exchange / 'first.zip', self.data())
        patch_package(self.exchange / 'other-patch.zip', self.data(other))
        self.engine.tick()
        before = self.ledger().request_contract()
        self.engine.close()
        self.engine = Engine(self.config, self.paths, Gate(), core=ReconcileCore(), codex=self.codex)
        self.addCleanup(self.engine.close)
        self.engine.tick()
        self.assertEqual(self.ledger().current()['patch_sha'], first['sha256'])
        self.assertEqual(self.ledger().output_kind(), 'unknown')
        self.assertEqual(self.ledger().request_contract(), before)
        self.assertEqual(self.codex.calls, 0)

    def test_disappearing_source_is_a_stable_failure_without_claim_or_model(self):
        other = self.result('other.zip')
        patch_package(self.exchange / 'other-patch.zip', self.data(other))
        resolve = self.engine.exchange.source
        def disappear(source):
            if source['sha256'] == other['sha256']:
                raise FileNotFoundError('source disappeared')
            return resolve(source)
        with patch.object(self.engine.exchange, 'source', side_effect=disappear):
            with self.assertRaises(ControlError) as caught:
                self.engine.tick()
        self.assertEqual(caught.exception.code, 'patch_source_unproven')
        self.assertEqual(self.ledger().current()['stage'], 'ready')
        self.assertEqual(self.codex.calls, 0)
