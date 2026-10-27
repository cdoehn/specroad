"""Real outer-owner exits and native inode recovery; no production approval claim."""
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from base64 import b64encode
import json
import os
from pathlib import Path
import sys
import tempfile

import pytest

from specroad.changes._lock_process import LinuxOwnerProbe
from specroad.model.canonical import canonical_json_bytes
from specroad.recovery import RestoreError
from specroad.work import restore_owner as implementation
from specroad.work._restore_owner_records import read_file_binding, unblob
from specroad.work.restore_owner import (recover_restore_work_owner,
    RestoreWorkOwnerRecovery, RestoreWorkOwnerError)
from support.read_only import inventory, no_write_attempts
from support.restore import restore_case, plan_for
from support.processes import run_python
from test_work_restore_binding import registry
from test_work_restore_execution import stored, run
from test_work_resume import recorded, setup as read_only_store


pytestmark = pytest.mark.skipif(sys.platform != 'linux',
                                reason='Native Linux Work inode/owner recovery')


def child(store, stage):
    root = Path(__file__).resolve().parents[1]
    initial = store._initial
    packet = {'raw': b64encode(initial.raw).decode(),
        'objects': {key: b64encode(raw).decode() for key, raw in initial.objects.items()}}
    # Complete trusted inputs can exceed the OS argument limit. This private
    # test fixture is outside Work; the child never infers trust from its store.
    with tempfile.NamedTemporaryFile(mode='w', dir=store._location.path.parent,
                                     prefix='.owner-test-', suffix='.json', delete=False) as stream:
        json.dump(packet, stream)
        packet_path = stream.name
    prefix = 'import sys;sys.path[:0]=' + repr([str(root / 'src'), str(root / 'tests')]) + '\n'
    code = prefix + '''
import os, json
from pathlib import Path
from base64 import b64decode
from specroad import _build
from specroad.security import ProjectBoundary
from specroad.work.root import WorkDirectory
from specroad.work.checkpoints import CheckpointStore
from specroad.work.manifest import read_work_manifest
from specroad.work import restore_owner as implementation
from test_work_restore_binding import registry
from specroad.cli.commands import builtin_registry
from hashlib import sha256
_build.BUILD_METADATA = {'format_version': 1, 'hash_algorithm': 'specroad-dev-payload-v1', 'build_sha256': '4' * 64}
''' + 'packet=json.loads(Path(' + repr(packet_path) + ').read_text())\n'
    code += 'stage=' + repr(stage) + '\n'
    # The trusted test packet is independent input, not discovered from Work.
    code += 'work_registry = registry() if ' + repr(initial.as_dict()['command_id'] == 'recover.restore') + ' else builtin_registry()\n'
    code += 'initial=read_work_manifest(b64decode(packet["raw"]), {k:b64decode(v) for k,v in packet["objects"].items()}, registry=work_registry, expected_tool_build=' + repr(initial.as_dict()['tool_build']) + ')\n'
    code += 'location=WorkDirectory(initial, protected_roots=tuple(ProjectBoundary(p) for p in ' + repr([str(b.root) for b in store._location._protected]) + '), directory=' + repr(str(store._location.path)) + ')\n'
    code += '''
store=CheckpointStore(location, initial)
if stage == 'orphan':
    with location.for_checkpoint():
        os._exit(77)
elif stage == 'staged':
    original = implementation._write_new
    def write(*args):
        original(*args)
        os._exit(78)
    implementation._write_new = write
elif stage == 'replace':
    original = implementation.replace_bound_image
    def exchange(*args, **kwargs):
        original(*args, **kwargs)
        os._exit(78)
    implementation.replace_bound_image = exchange
else:
    original = implementation.HandoffFiles.write
    def write(self, name, raw):
        original(self, name, raw)
        if name.endswith('.complete.json') == (stage == 'complete'):
            os._exit(78)
    implementation.HandoffFiles.write = write
raw=(location._requested / 'work-lock.json').read_bytes()
implementation.recover_restore_work_owner(store, registry=registry(),
    expected_work_lock_sha256=sha256(raw).hexdigest(), reason='Explicit synthetic child recovery')
'''
    result = run_python(['-I', '-B', '-c', code], root, capture=True)
    assert result.returncode in (77, 78), result.stderr.decode()
    return result.returncode


def orphan(store):
    assert child(store, 'orphan') == 77
    return (store._location.path / 'work-lock.json').read_bytes()


@pytest.fixture
def case(recorded, tmp_path):
    options, original, _ = restore_case(tmp_path)
    plan = plan_for(options)
    initial, location, store = stored(tmp_path, plan)
    return initial, location, store, plan


def recover(store, **options):
    raw = (store._location.path / 'work-lock.json').read_bytes()
    return recover_restore_work_owner(store, registry=registry(),
        **{'expected_work_lock_sha256': sha256(raw).hexdigest(),
           'reason': 'Explicit synthetic current handoff', **options})


def audits(location):
    directory = location.path / 'checkpoints/restore-owner-handoffs'
    return {p.name: p.read_bytes() for p in directory.iterdir()}


def test_native_dead_owner_preserves_exact_bytes_and_checkpoint_then_normal_writers_work(case):
    initial, location, store, plan = case
    old = orphan(store)
    old_info = (location.path / 'work-lock.json').stat()
    checkpoint = (location.path / 'work.json').read_bytes()
    project = inventory(Path(plan.data['project_root']))
    outcome = recover(store, reason='  Explicit current test reason  ')
    data = outcome.as_dict()
    assert data['checkpoint_sha256'] == initial.as_dict()['checkpoint_sha256']
    assert data['checkpoint_generation'] == 0 and data['checkpoint_changed'] is False
    assert data['project_mutation_possible'] is data['work_completion_recorded'] is False
    assert (location.path / 'work.json').read_bytes() == checkpoint
    assert inventory(Path(plan.data['project_root'])) == project
    assert not (location.path / 'work-lock.json').exists()
    records = audits(location)
    intent = json.loads(records[data['handoff_sha256'] + '.json'])
    assert read_file_binding(intent['old_owner']) == (old, (old_info.st_dev, old_info.st_ino))
    assert intent['reason'] == 'Explicit current test reason'
    assert unblob(intent['checkpoint']) == checkpoint
    assert sha256(records[data['handoff_sha256'] + '.json']).hexdigest() == data['handoff_sha256']
    assert len(records) == 2 and intent['root_binding']['work_id'] == initial.as_dict()['work_id']
    assert json.loads(records[data['handoff_sha256'] + '.complete.json'])['new_owner'] == intent['new_owner']
    with pytest.raises(TypeError):
        bool(outcome)
    with pytest.raises(TypeError):
        RestoreWorkOwnerRecovery()
    with pytest.raises(FrozenInstanceError):
        outcome._raw = b''
    data['work_id'] = 'changed detached value'
    assert outcome.as_dict()['work_id'] == initial.as_dict()['work_id']
    # Re-enter the normal writer lease without fabricating Restore completion.
    assert store._update(lambda current: current).raw == initial.raw
    assert store.read().raw == initial.raw
    assert audits(location) == records


def test_owner_recovery_does_not_replace_fresh_native_restore_authority(case):
    _, location, store, plan = case
    orphan(store)
    recover(store)
    from specroad.changes.recovery_values import RecoveryAuthority
    before = inventory(Path(plan.data['project_root']))
    with pytest.raises(RestoreError):
        run(store, authority=RecoveryAuthority('synthetic-deny', '1', lambda _: False))
    assert inventory(Path(plan.data['project_root'])) == before
    result = run(store).as_dict()
    assert result['checkpoint_changed'] is result['work_completion_recorded'] is False


@pytest.mark.parametrize('options', [
    {'expected_work_lock_sha256': None}, {'expected_work_lock_sha256': 'x' * 64},
    {'expected_work_lock_sha256': 'A' * 64}, {'reason': None}, {'reason': ' \t '},
])
def test_explicit_current_pair_is_required_without_any_write(case, options):
    _, location, store, _ = case
    orphan(store)
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(RestoreWorkOwnerError) as caught:
        recover(store, **options)
    assert caught.value.exit_code == 2 and not caught.value.work_mutation_possible
    assert inventory(location.path) == before


def test_read_only_work_cannot_use_restore_owner_takeover(recorded, tmp_path):
    _, _, location, store = read_only_store(tmp_path)
    orphan(store)
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(RestoreWorkOwnerError) as caught:
        recover(store)
    assert caught.value.exit_code == 2 and inventory(location.path) == before


@pytest.mark.parametrize('fault,code', [
    ('wrong-hash', 6), ('wrong-work', 6), ('missing-owner', 6),
    ('invalid-owner', 3), ('unknown-start', 5), ('remote-host', 5), ('mode', 7),
])
def test_owner_binding_and_safety_fail_closed(case, fault, code):
    _, location, store, _ = case
    raw = orphan(store)
    path = location.path / 'work-lock.json'
    options = {}
    if fault == 'wrong-hash':
        options['expected_work_lock_sha256'] = '0' * 64
    elif fault == 'missing-owner':
        path.unlink()
    elif fault == 'invalid-owner':
        path.write_bytes(b'{bad')
    elif fault == 'mode':
        path.chmod(0o644)
    else:
        value = json.loads(raw)
        value[{'wrong-work': 'work_id', 'unknown-start': 'process_start_id', 'remote-host': 'host_id'}[fault]] = (
            None if fault == 'unknown-start' else 'foreign')
        path.write_bytes(canonical_json_bytes(value))
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(RestoreWorkOwnerError) as caught:
        if fault == 'missing-owner':
            recover_restore_work_owner(store, registry=registry(),
                expected_work_lock_sha256=sha256(raw).hexdigest(), reason='current explicit request')
        else:
            recover(store, **options)
    assert caught.value.exit_code == code and not caught.value.work_mutation_possible
    assert caught.value.mutation_possible is caught.value.recovery_required is False
    assert inventory(location.path) == before


def test_free_kernel_mutex_alone_does_not_authorize_a_live_owner(case):
    _, location, store, _ = case
    with location.for_checkpoint() as held:
        raw = held._owner[0]
        with pytest.raises(RestoreWorkOwnerError) as busy:
            recover(store)
        assert busy.value.exit_code == 5
        assert held._owner[0] == raw
    path = location.path / 'work-lock.json'
    path.write_bytes(raw)
    path.chmod(0o600)
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(RestoreWorkOwnerError) as alive:
        recover(store)
    assert alive.value.exit_code == 5 and not alive.value.work_mutation_possible
    assert inventory(location.path) == before


@pytest.mark.parametrize('state,start,allowed', [
    ('unknown', None, False), ('alive', 'same', False), ('dead', None, False),
    ('absent', 'same', False), ('absent', None, True), ('dead', 'same', True),
    ('alive', 'different-start', True),
])
def test_native_adapter_observations_require_known_terminal_absent_or_reused_identity(state, start, allowed):
    current = LinuxOwnerProbe().current()
    previous = replace(current, process_id=12345, process_start_id='same')
    class Probe:
        def current(self):
            return current
        def process(self, pid):
            assert pid == previous.process_id
            return state, start
    if allowed:
        assert implementation._observe(Probe(), previous)[1]['state'] == state
    else:
        with pytest.raises(RestoreError) as caught:
            implementation._observe(Probe(), previous)
        assert caught.value.exit_code == 5


@pytest.mark.parametrize('boundary', ['staged', 'intent', 'replace', 'complete'])
def test_real_abrupt_exit_recovers_actual_stage_with_new_explicit_consent(case, boundary):
    _, location, store, _ = case
    original = orphan(store)
    pointer = (location.path / 'work.json').read_bytes()
    assert child(store, boundary) == 78
    actual = (location.path / 'work-lock.json').read_bytes()
    assert (actual == original) is (boundary in ('staged', 'intent'))
    prior = audits(location) if boundary != 'staged' else {}
    if boundary in ('replace', 'complete'):
        with no_write_attempts(), pytest.raises(RestoreWorkOwnerError) as stale:
            recover(store, expected_work_lock_sha256=sha256(original).hexdigest())
        assert stale.value.exit_code == 6
    recover(store)
    assert not (location.path / 'work-lock.json').exists()
    assert (location.path / 'work.json').read_bytes() == pointer
    assert all(audits(location)[name] == raw for name, raw in prior.items())
    assert store.read().raw == store._initial.raw


def test_post_replace_sync_error_preserves_new_owner_and_reports_only_work_effects(case, monkeypatch):
    _, location, store, _ = case
    original = orphan(store)
    real = implementation.replace_bound_image
    def failing(*args, **kwargs):
        callback = kwargs['after_replace']
        def installed(info):
            callback(info)
            raise OSError('synthetic durability failure after actual replace')
        kwargs['after_replace'] = installed
        return real(*args, **kwargs)
    monkeypatch.setattr(implementation, 'replace_bound_image', failing)
    with pytest.raises(RestoreWorkOwnerError) as caught:
        recover(store)
    assert (location.path / 'work-lock.json').read_bytes() != original
    diagnostic = caught.value.diagnostic()
    assert diagnostic['exit_code'] == 5
    assert diagnostic['work_mutation_possible'] is diagnostic['owner_recovery_required'] is True
    assert diagnostic['mutation_possible'] is diagnostic['recovery_required'] is False
    assert len(audits(location)) == 1
    # This new owner is still this live process, so it cannot steal its own
    # interrupted record merely because the kernel mutex has been released.
    monkeypatch.setattr(implementation, 'replace_bound_image', real)
    with no_write_attempts(), pytest.raises(RestoreWorkOwnerError) as alive:
        recover(store)
    assert alive.value.exit_code == 5


@pytest.mark.parametrize('fault', ['record-bytes', 'missing-intent', 'missing-checkpoint', 'missing-audit'])
def test_handoff_proofs_are_mandatory_and_never_replaced_by_saved_observations(case, fault):
    _, location, store, _ = case
    orphan(store)
    assert child(store, 'complete') == 78
    directory = location.path / 'checkpoints/restore-owner-handoffs'
    intent = next(p for p in directory.iterdir() if not p.name.endswith('.complete.json'))
    if fault == 'record-bytes':
        intent.write_bytes(b'{}')
    elif fault == 'missing-intent':
        intent.unlink()
    elif fault == 'missing-audit':
        for path in directory.iterdir():
            path.unlink()
        directory.rmdir()
    else:
        pointer = json.loads((location.path / 'work.json').read_bytes())
        (location.path / 'checkpoints' / (pointer['checkpoint']['sha256'] + '.json')).unlink()
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(RestoreWorkOwnerError) as caught:
        recover(store)
    assert caught.value.exit_code in (3, 6) and not caught.value.work_mutation_possible
    assert inventory(location.path) == before


@pytest.mark.parametrize('fault', ['owner', 'root', 'checkpoint', 'build'])
def test_late_native_probe_cannot_bypass_current_work_bindings(case, monkeypatch, fault):
    _, location, store, _ = case
    original = orphan(store)
    class MutatingProbe(LinuxOwnerProbe):
        calls = 0
        def current(self):
            identity = super().current()
            self.calls += 1
            if self.calls == 2:
                if fault == 'build':
                    from specroad import _build
                    monkeypatch.setattr(_build, 'BUILD_METADATA',
                        dict(_build.BUILD_METADATA, build_sha256='5' * 64))
                else:
                    name, key, replacement = {
                        'owner': ('work-lock.json', 'owner_nonce', '0' * 32),
                        'root': ('root.json', 'initial_checkpoint_sha256', '0' * 64),
                        'checkpoint': ('work.json', 'checkpoint_generation', 99),
                    }[fault]
                    path = location.path / name
                    value = json.loads(path.read_bytes())
                    value[key] = replacement
                    path.write_bytes(canonical_json_bytes(value))
            return identity
    with pytest.raises(RestoreWorkOwnerError) as caught:
        recover(store, owner_probe=MutatingProbe())
    assert caught.value.exit_code == 6 and caught.value.work_mutation_possible
    assert caught.value.owner_recovery_required and not caught.value.mutation_possible
    records = audits(location)
    assert len(records) == 1
    intent = json.loads(next(iter(records.values())))
    assert read_file_binding(intent['old_owner'])[0] == original
    actual = (location.path / 'work-lock.json').read_bytes()
    assert actual != read_file_binding(intent['new_owner'])[0]
    if fault != 'owner':
        assert actual == original


def test_incompatible_initial_build_is_a_conflict_without_writes(case, monkeypatch):
    _, location, store, _ = case
    orphan(store)
    from specroad import _build
    monkeypatch.setattr(_build, 'BUILD_METADATA', dict(_build.BUILD_METADATA, build_sha256='5' * 64))
    before = inventory(location.path)
    with no_write_attempts(), pytest.raises(RestoreWorkOwnerError) as caught:
        recover(store)
    assert caught.value.exit_code == 6 and not caught.value.work_mutation_possible
    assert inventory(location.path) == before
