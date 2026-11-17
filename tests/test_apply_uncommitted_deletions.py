"""Real Git boundaries for deleting an explicit, never-committed preimage.

The injected gate is a driver fixture, not a product test receipt. Native
registration and gate verification keep their existing integration coverage.
"""
import base64
from copy import deepcopy
from hashlib import sha256
import sys

import pytest

from apply_deletion_support import git_apply, regular_file
from support.transport_runtime import ARTIFACT_SHA256, RUNTIME_FIXTURE
from verification_support.bundle_apply import run_bundle
from verification_support.bundle_contract import public_plan, validate_continuation


TEMPORARY = 'temporary.py'
PREIMAGE = b'explicit uncommitted bytes\n'
TARGET = b'new surviving content\n'


@pytest.fixture(autouse=True)
def native_payload_runtime(monkeypatch):
    """Use the pinned real writer without a host installation or lasting imports."""
    runtime = RUNTIME_FIXTURE/'patchharbor-1.8.0.pyz'
    assert sha256(runtime.read_bytes()).hexdigest() == ARTIFACT_SHA256

    def native_modules():
        return [name for name in sys.modules
                if name == 'patchharbor' or name.startswith('patchharbor.')]

    with monkeypatch.context() as imports:
        for name in native_modules():
            imports.delitem(sys.modules, name)
        imports.syspath_prepend(str(runtime))
        try:
            from patchharbor import payload_files
            assert payload_files.__file__ == str(runtime) + '/patchharbor/payload_files.py'
            yield
        finally:
            for name in native_modules():
                del sys.modules[name]


def ephemeral(tmp_path, state='untracked'):
    backend = git_apply(tmp_path)
    regular_file(backend.root/TEMPORARY, PREIMAGE)
    stage = backend.data['stages'][0]
    digest = sha256(PREIMAGE).hexdigest()
    stage.update(before={TEMPORARY: digest, 'survives.py': sha256(b'keep\n').hexdigest()},
                 after={'survives.py': sha256(TARGET).hexdigest()},
                 payloads={'survives.py': base64.b64encode(TARGET).decode()},
                 deletions={TEMPORARY: digest},
                 delete_preimages={TEMPORARY: base64.b64encode(PREIMAGE).decode()})
    backend.data['initial_dirty'] = True
    if state == 'staged':
        backend.git('add', '--', TEMPORARY)
    return backend


def assert_completed(backend, original):
    assert backend.head() != original
    assert not (backend.root/TEMPORARY).exists()
    assert (backend.root/'survives.py').read_bytes() == TARGET
    assert (backend.root/'gone.py').read_bytes() == b'original\n'
    assert backend.git('diff', '--name-status', original, 'HEAD') == b'M\tsurvives.py\n'
    assert not backend.git('ls-files', '--', TEMPORARY)
    assert not backend.git('status', '--porcelain')
    assert backend.git('rev-list', '--count', original+'..HEAD') == b'1\n'


@pytest.mark.parametrize('state', ['untracked', 'staged'])
def test_bound_temporary_deletion_does_not_invent_a_committed_git_deletion(tmp_path, state):
    backend = ephemeral(tmp_path, state)
    original = backend.head()
    result = run_bundle(backend.data, backend)
    assert result['phase'] == 'completed'
    assert backend.gates == [(original, {TEMPORARY: sha256(PREIMAGE).hexdigest()})]
    assert_completed(backend, original)


@pytest.mark.parametrize('state', ['untracked', 'staged'])
def test_failed_gate_keeps_absent_preimage_and_resumes_exactly_the_open_stage(tmp_path, state):
    backend = ephemeral(tmp_path, state)
    original = backend.head()
    prior = public_plan(backend.data)
    backend.fail_gate = True
    with pytest.raises(ValueError):
        run_bundle(backend.data, backend)
    assert backend.head() == original and not (backend.root/TEMPORARY).exists()
    assert (backend.root/'survives.py').read_bytes() == TARGET
    assert len(backend.gates) == 1
    progress = backend.events[-1]
    assert progress['committed'] == [] and progress['remaining_commit_ids'] == ['step.W']
    correction = deepcopy(backend.data)
    correction.update(source_result_sha256='e'*64, initial_dirty=True,
        correction_of={'plan_sha256': progress['plan_sha256'], 'remaining_commit_ids': ['step.W']})
    correction['stages'][0]['before'] = {'survives.py': sha256(TARGET).hexdigest()}
    validate_continuation(prior, progress, correction)
    assert correction['stages'][0]['delete_preimages'] == backend.data['stages'][0]['delete_preimages']
    backend.data = correction
    backend.fail_gate = False
    assert run_bundle(correction, backend)['phase'] == 'completed'
    assert len(backend.gates) == 2 and all(head == original for head, _ in backend.gates)
    assert_completed(backend, original)


@pytest.mark.parametrize('fault', ['reappear', 'payload', 'tracked-deletion', 'foreign-work', 'foreign-index'])
def test_ephemeral_cleanup_does_not_hide_post_gate_changes(tmp_path, monkeypatch, fault):
    backend = ephemeral(tmp_path)
    original = backend.head()
    real_gate = backend.test

    def gate(stage, head):
        evidence = real_gate(stage, head)
        if fault == 'reappear':
            regular_file(backend.root/TEMPORARY, b'foreign\n')
        elif fault == 'payload':
            regular_file(backend.root/'survives.py', b'foreign\n')
        elif fault == 'tracked-deletion':
            (backend.root/'gone.py').unlink()
        elif fault == 'foreign-work':
            regular_file(backend.root/'foreign.py', b'foreign\n')
        else:
            regular_file(backend.root/'gone.py', b'foreign\n')
            backend.git('add', '--', 'gone.py')
        return evidence

    monkeypatch.setattr(backend, 'test', gate)
    with pytest.raises(ValueError):
        run_bundle(backend.data, backend)
    assert len(backend.gates) == 1 and backend.head() == original
    assert backend.events[-1]['committed'] == []
    assert backend.events[-1]['remaining_commit_ids'] == ['step.W']
    if fault == 'reappear':
        assert (backend.root/TEMPORARY).read_bytes() == b'foreign\n'
    elif fault == 'payload':
        assert (backend.root/'survives.py').read_bytes() == b'foreign\n'
    elif fault == 'tracked-deletion':
        assert not (backend.root/'gone.py').exists()
    elif fault == 'foreign-work':
        assert (backend.root/'foreign.py').read_bytes() == b'foreign\n'
    else:
        assert backend.git('show', ':gone.py') == b'foreign\n'


def test_staged_temporary_bytes_must_match_the_bound_deletion_preimage(tmp_path):
    backend = ephemeral(tmp_path)
    original = backend.head()
    regular_file(backend.root/TEMPORARY, b'foreign index bytes\n')
    backend.git('add', '--', TEMPORARY)
    regular_file(backend.root/TEMPORARY, PREIMAGE)
    with pytest.raises(ValueError):
        run_bundle(backend.data, backend)
    assert not backend.gates and backend.head() == original
    assert backend.git('show', ':'+TEMPORARY) == b'foreign index bytes\n'


def test_real_tracked_deletion_remains_in_the_same_commit_as_temporary_cleanup(tmp_path):
    backend = ephemeral(tmp_path)
    original = backend.head()
    stage = backend.data['stages'][0]
    stage['before']['gone.py'] = sha256(b'original\n').hexdigest()
    stage['deletions']['gone.py'] = stage['before']['gone.py']
    stage['delete_preimages']['gone.py'] = base64.b64encode(b'original\n').decode()
    assert run_bundle(backend.data, backend)['phase'] == 'completed'
    assert len(backend.gates) == 1
    assert backend.git('diff', '--name-status', original, 'HEAD') == b'D\tgone.py\nM\tsurvives.py\n'
    assert not (backend.root/TEMPORARY).exists() and not (backend.root/'gone.py').exists()
    assert (backend.root/'survives.py').read_bytes() == TARGET
    assert not backend.git('status', '--porcelain')


def test_only_uncommitted_cleanup_cannot_create_an_empty_commit(tmp_path):
    backend = ephemeral(tmp_path)
    original = backend.head()
    stage = backend.data['stages'][0]
    stage['before'].pop('survives.py')
    stage['after'] = {}; stage['payloads'] = {}
    with pytest.raises(ValueError):
        run_bundle(backend.data, backend)
    assert not backend.gates and backend.head() == original
    assert (backend.root/'survives.py').read_bytes() == b'keep\n'


def test_unchanged_write_payload_is_not_a_substitute_for_a_real_commit_change(tmp_path):
    backend = ephemeral(tmp_path)
    original = backend.head()
    stage = backend.data['stages'][0]
    stage['after']['survives.py'] = sha256(b'keep\n').hexdigest()
    stage['payloads']['survives.py'] = base64.b64encode(b'keep\n').decode()
    with pytest.raises(ValueError):
        run_bundle(backend.data, backend)
    assert not backend.gates and backend.head() == original
