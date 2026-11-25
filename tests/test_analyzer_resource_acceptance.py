"""Deferred observations stay open; final stages require real matching evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from analyzer_benchmark.acceptance import POLICY, POLICY_PATH, PLAN_PATH, evaluate, final_required
from test_analyzer_resources import EVIDENCE, ROOT
from verification_support.bundle_apply import NativeApply
from verification_support.identity import source_identity

BUILD = '797fa5577f38ce87e0e62df7cecbe03fca370f1bbfa65efb7781b9592575663f'


def inputs(root, *, state='in_progress', completed=900, total=996, last='21.d.C'):
    for path in (POLICY_PATH, PLAN_PATH):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / POLICY_PATH).write_text(json.dumps(POLICY))
    (root / PLAN_PATH).write_text('```yaml\nimplementation_state: ' + state
        + '\nimplementation_plan_commits_completed: ' + str(completed)
        + '\nimplementation_plan_commits_total: ' + str(total)
        + '\nlast_completed_plan_commit: ' + last + '\n```\n')
    return root


def observations(root, build=BUILD):
    destination = root / 'verification/fixtures/analyzer-resources-builds' / build
    shutil.copytree(EVIDENCE, destination)
    return destination


def test_unmeasured_intermediate_build_is_deferred_without_success_or_outputs(tmp_path):
    root = inputs(tmp_path)
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = evaluate(root, expected_build='a' * 64, commit_id='21.d.C')
    assert result['status'] == 'deferred' and result['measurement_status'] == 'missing'
    assert result['measurement'] is None and result['final_obligation'] == 'pending'
    assert result['release_approved'] is result['human_corpus_review_completed'] is False
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('commit_id', ['20.n.W', '20.n.R', '20.n.C'])
def test_final_stage_overrides_development_deferral(tmp_path, commit_id):
    result = evaluate(inputs(tmp_path), expected_build='a' * 64, commit_id=commit_id)
    assert result['status'] == 'blocked' and result['final_required'] is True
    assert result['final_obligation'] == 'pending' and result['measurement'] is None


@pytest.mark.parametrize('progress', [
    {'state': 'completed'}, {'state': 'complete'}, {'completed': 996}, {'last': '20.n.W'},
])
def test_completed_or_final_progress_cannot_reenable_deferral(tmp_path, progress):
    result = evaluate(inputs(tmp_path, **progress), expected_build='a' * 64)
    assert result['final_required'] and result['status'] == 'blocked'


def test_explicit_final_check_requires_the_exact_build_and_preserves_old_evidence(tmp_path):
    root = inputs(tmp_path)
    directory = observations(root)
    before = {p.relative_to(directory): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    pending = evaluate(root, expected_build='a' * 64, final=True)
    assert pending['status'] == 'blocked' and pending['measurement_status'] == 'missing'
    passed = evaluate(root, expected_build=BUILD, final=True)
    assert passed['status'] == 'passed' and passed['measurement_status'] == 'passed'
    assert passed['final_obligation'] == 'satisfied'
    assert passed['release_approved'] is passed['human_corpus_review_completed'] is False
    assert before == {p.relative_to(directory): p.read_bytes() for p in directory.rglob('*') if p.is_file()}


def test_available_intermediate_observation_does_not_complete_final_acceptance(tmp_path):
    root = inputs(tmp_path)
    observations(root)
    result = evaluate(root, expected_build=BUILD)
    assert result['status'] == 'deferred' and result['measurement_status'] == 'passed'
    assert result['final_obligation'] == 'pending' and not result['final_required']


def test_plan_progress_is_bound_to_verification_source_identity(tmp_path):
    root = inputs(tmp_path)
    for directory in ('src/specroad', 'tests', 'tools'):
        (root / directory).mkdir(parents=True)
    (root / 'pyproject.toml').write_text('')
    before = source_identity(root)
    inputs(root, state='completed')
    after = source_identity(root)
    assert before != after
    (root / 'docs/unrelated.md').write_text('Presentation only.\n')
    assert source_identity(root) == after
    (root / PLAN_PATH).unlink()
    with pytest.raises(OSError):
        source_identity(root)


@pytest.mark.parametrize('fault', ['wrong-build', 'corrupt'])
def test_deferral_never_hides_invalid_supplied_measurement(tmp_path, fault):
    root = inputs(tmp_path)
    build = 'a' * 64 if fault == 'wrong-build' else BUILD
    directory = observations(root, build)
    if fault == 'corrupt':
        (directory / 'receipt.json').write_text('{}')
    result = evaluate(root, expected_build=build)
    assert result['status'] == result['measurement_status'] == 'blocked'
    assert result['final_obligation'] == 'pending'


@pytest.mark.parametrize('fault', ['missing-policy', 'changed-policy', 'duplicate-policy',
                                 'missing-progress', 'duplicate-progress', 'over-completed', 'unknown-state'])
def test_invalid_obligation_inputs_cannot_authorize_deferral(tmp_path, fault):
    root = inputs(tmp_path)
    policy, plan = root / POLICY_PATH, root / PLAN_PATH
    if fault == 'missing-policy':
        policy.unlink()
    elif fault == 'changed-policy':
        policy.write_text(json.dumps({**POLICY, 'final_obligation': 'optional'}))
    elif fault == 'duplicate-policy':
        policy.write_text(policy.read_text().replace('{', '{"format_version":1,', 1))
    elif fault == 'missing-progress':
        plan.write_text('No machine progress.\n')
    elif fault == 'duplicate-progress':
        plan.write_text(plan.read_text().replace('```\n', 'implementation_state: complete\n```\n'))
    elif fault == 'over-completed':
        inputs(root, completed=997)
    else:
        inputs(root, state='assume_passed')
    with pytest.raises((OSError, ValueError)):
        final_required(root)


def native_gate_inputs(root):
    # Only the real evidence-check CLI and its inert builder are needed.
    paths = ['tools/check_analyzer_resources.py', 'tools/build_core.py', 'tools/core_build_metadata.py',
             'tools/analyzer_benchmark/acceptance.py', 'tools/analyzer_benchmark/records.py',
             'tools/analyzer_benchmark/verify.py']
    for name in paths:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    package = root / 'src/specroad'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('')
    (package / '__main__.py').write_text('pass\n')
    return root


@pytest.mark.parametrize('with_policy', [True, False])
def test_native_final_gate_blocks_before_any_behavior_runner(tmp_path, monkeypatch, with_policy):
    root = native_gate_inputs(inputs(tmp_path / 'apply-fixture'))
    if not with_policy:
        (root / POLICY_PATH).unlink()
    python = root / '.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    (root / 'tools/run_apply_tests.py').write_text(
        'from pathlib import Path\nPath("TESTS_STARTED").write_text("unexpected")\n')
    monkeypatch.chdir(root)
    backend = NativeApply({})
    backend.report_dir = root / 'build'
    backend.report_dir.mkdir()
    with pytest.raises(subprocess.CalledProcessError) as failure:
        backend.test({'commit_id': '20.n.W', 'test_plan': {}}, 'a' * 40)
    assert failure.value.returncode == 2
    assert not (root / 'TESTS_STARTED').exists()
    assert not (root / 'build/20.n.W/gate').exists()


@pytest.mark.parametrize('last', ['21.e1.W', '21.e1.R', '21.e1.C',
                                '21.e2.W', '21.e2.R', '21.e2.C'])
def test_partitioned_intermediate_progress_keeps_unmeasured_obligation_open(tmp_path, last):
    root = inputs(tmp_path, completed=901, total=999, last=last)
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = evaluate(root, expected_build='a' * 64, commit_id=last)
    assert result['status'] == 'deferred' and result['measurement_status'] == 'missing'
    assert result['measurement'] is None and not result['final_required']
    assert result['final_obligation'] == 'pending'
    assert result['release_approved'] is result['human_corpus_review_completed'] is False
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('last', ['21.e0.W', '21.e01.W', '21.e-1.W',
                                '21.e1x.W', '21.e1.w', '21.e1.W.extra'])
def test_malformed_partition_progress_cannot_authorize_deferral(tmp_path, last):
    root = inputs(tmp_path, last=last)
    with pytest.raises(ValueError, match='invalid_last_plan_commit'):
        evaluate(root, expected_build='a' * 64)


@pytest.mark.parametrize('progress, options', [
    ({}, {'final': True}),
    ({}, {'commit_id': '20.n.W'}),
    ({}, {'commit_id': '20.n.R'}),
    ({}, {'commit_id': '20.n.C'}),
    ({'state': 'complete'}, {}),
    ({'state': 'completed'}, {}),
    ({'completed': 999}, {}),
])
def test_partitioned_progress_does_not_bypass_final_obligation(tmp_path, progress, options):
    root = inputs(tmp_path, total=999, last='21.e1.C', **progress)
    result = evaluate(root, expected_build='a' * 64, **options)
    assert result['status'] == 'blocked' and result['final_required']
    assert result['measurement_status'] == 'missing' and result['final_obligation'] == 'pending'
    assert result['release_approved'] is result['human_corpus_review_completed'] is False


@pytest.mark.parametrize('phase', ['W', 'R', 'C'])
def test_native_partition_gate_defers_but_explicit_final_check_blocks(tmp_path, phase):
    commit_id = '21.e1.' + phase
    root = native_gate_inputs(inputs(tmp_path, completed=901, total=999, last=commit_id))
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    command = [sys.executable, '-I', '-B', str(root / 'tools/check_analyzer_resources.py'),
               '--commit-id', commit_id]
    deferred = subprocess.run(command, cwd=root, capture_output=True, text=True)
    assert deferred.returncode == 0, deferred.stderr
    status = json.loads(deferred.stdout.split('SPECROAD_RESOURCE_OBLIGATION ', 1)[1])
    assert status['status'] == 'deferred' and status['measurement_status'] == 'missing'
    assert status['final_obligation'] == 'pending' and not status['final_required']
    final = subprocess.run([*command, '--final'], cwd=root, capture_output=True, text=True)
    assert final.returncode == 2, final.stderr
    strict = json.loads(final.stdout.split('SPECROAD_RESOURCE_OBLIGATION ', 1)[1])
    assert strict['status'] == 'blocked' and strict['final_required']
    assert strict['expected_build_sha256'] == status['expected_build_sha256']
    assert strict['final_obligation'] == 'pending' and strict['measurement_status'] == 'missing'
    assert strict['release_approved'] is strict['human_corpus_review_completed'] is False
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
