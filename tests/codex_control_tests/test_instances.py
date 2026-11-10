"""Independent namespaces and shared ownership; no host service is started."""
from dataclasses import replace
from uuid import uuid4
from unittest.mock import patch
from specroad_control import service
from specroad_control.automation import Engine, Gate
from specroad_control.config import parse, render
from specroad_control.errors import ControlError
from specroad_control.local import Paths
from specroad_control.toml_compat import tomllib
from codex_control_tests.automation_support import AutomationCase, FakeCore, FakeCodex


class InstanceTests(AutomationCase):
    def engine(self, config, paths):
        return Engine(config, paths, Gate(), core=FakeCore(), codex=FakeCodex(self))

    def other(self, **values):
        return replace(self.config, repository=self.home/'specroad-dev2',
                       repo_id=str(uuid4()), session_id=str(uuid4()), **values)

    def test_named_locations_are_independent_and_default_is_unchanged(self):
        second = Paths.discover(instance='dev2')
        self.assertEqual(second.home, self.paths.home/'instances/dev2')
        self.assertEqual(second.target_locks, self.paths.target_locks)
        for name in ('config', 'state', 'runtime', 'socket', 'logs', 'unit'):
            self.assertNotEqual(getattr(second, name), getattr(self.paths, name))
        self.assertEqual(self.paths.unit.name, 'specroad-control.service')

    def test_distinct_targets_can_hold_ownership_together(self):
        with self.engine(self.config, self.paths), self.engine(self.other(), Paths.discover(instance='dev2')):
            pass

    def test_each_shared_target_blocks_a_second_owner(self):
        with self.engine(self.config, self.paths):
            for field in ('repository', 'repo_id', 'session_id'):
                candidate = replace(self.other(), **{field: getattr(self.config, field)})
                with self.subTest(field=field), self.assertRaises(ControlError) as caught:
                    with self.engine(candidate, Paths.discover(instance='dev2')):
                        self.fail('Conflicting owner was accepted')
                self.assertEqual(caught.exception.code, 'already_running')

    def test_explicit_apply_binding_roundtrips_without_changing_legacy_config(self):
        second = Paths.discover(instance='dev2')
        candidate = replace(self.other(), exchange=self.home/'exchange2', apply_repository=self.home/'specroad-apply2')
        self.assertEqual(parse(tomllib.loads(render(candidate)), second), candidate)
        self.assertEqual(self.config.apply_directory, self.home/'specroad-apply')
        self.assertEqual(self.other().apply_directory, self.home/'specroad-apply2')

    def test_service_inspection_routes_only_to_selected_unit(self):
        second = Paths.discover(instance='dev2')
        reply = type('Reply', (), {'returncode': 0, 'stdout': 'LoadState=not-found\n'})()
        with patch.object(service, 'command', return_value=reply) as call:
            service.inspect(second)
        self.assertEqual(call.call_args.args[0][1], second.unit.name)


def test_native_typed_plan_can_be_read_for_the_explicit_second_branch(tmp_path):
    from codex_control_tests.apply_reconcile_support import patch_package
    from specroad_control.apply_reconcile_proof import plan
    from test_apply_commit_plan import bundle
    data = bundle(); data['branch'] = 'dev2'
    package = patch_package(tmp_path/'second.zip', data)
    assert plan(package)[0]['branch'] == 'dev2'
