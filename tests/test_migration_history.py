"""Original source hashes and historical evidence survive real migration."""
from hashlib import sha256
import json
import pytest

from specroad.archive.verification import verify_baseline_snapshot
from specroad.migration.history import (HistoricalVerification,
    verify_source_history, verify_migrated_history)
from specroad.security import ProjectBoundary
from support.legacy_manifest import migrated, write_files, MANIFEST
from support.migration_history import (evidence_source, BASELINE, EVIDENCE,
    REQUIREMENT, PROJECT_ID, historical_contract_host)
from support.reference01 import CONTRACT, minimal, full_project, seal
from support.read_only import no_write_attempts


def by_id(report, identity):
    return next(row for row in report['historical']['records'] if row['artifact_id'] == identity)


@pytest.mark.parametrize('result', ['passed', 'failed', 'incomplete', 'skipped'])
@pytest.mark.parametrize('nested', [False, True])
def test_history_retains_exact_records_and_source_algorithms_across_migration(result, nested):
    old, target, _ = migrated(evidence_source(result=result, nested=nested))
    before_bytes, after_bytes = dict(old), dict(target)
    with no_write_attempts():
        before = verify_source_history(old).data
        after = verify_migrated_history(target, project_id=PROJECT_ID).data
    assert before['historical'] == after['historical']
    assert before['legacy_manifest_sha256'] is None and after['legacy_manifest_sha256']
    original = json.loads(old[EVIDENCE]); row = by_id(after, original['id'])
    assert row['subjects'] == original['subjects'] and row['result'] == result
    assert row['context_hash_algorithm'] == 'reference01-verification-context-v1'
    assert row['original_byte_sha256'] == sha256(old[EVIDENCE]).hexdigest()
    assert old[EVIDENCE] == target[EVIDENCE] and old[BASELINE] == target[BASELINE]
    assert old[REQUIREMENT] != target[REQUIREMENT]
    for path in old:
        if path.startswith('archive/'):
            assert old[path] == target[path]
    for report in (before, after):
        assert report['historical_integrity_verified']
        assert not any(report[k] for k in ('external_run_verified', 'human_authority_verified',
            'current_context_verified', 'current_readiness_verified', 'approval_granted',
            'write_authorized', 'test_code_executed', 'historical_compatibility_claimed'))
    assert old == before_bytes and target == after_bytes


def test_fixed_contract_baseline_uses_stored_original_root_and_bytes(tmp_path):
    files = minimal()
    files[BASELINE] = (CONTRACT/'vectors/sealed-baseline.json').read_bytes()
    files.update({p.relative_to(CONTRACT/'vectors').as_posix(): p.read_bytes()
        for p in (CONTRACT/'vectors/archive').rglob('*') if p.is_file()})
    write_files(tmp_path, files)
    with no_write_attempts():
        result = verify_baseline_snapshot(ProjectBoundary(tmp_path), files[BASELINE])
    expected = json.loads((CONTRACT/'vectors/project-manifest.json').read_bytes())
    record = json.loads(files[BASELINE])
    assert result['model_root_algorithm'] == 'reference01-model-root-v1'
    assert result['model_root_sha256'] == record['model_root_sha256']
    assert by_id(result, 'SR-BASE-0001')['manifest'] == record['manifest']
    assert result['record_sha256'] == sha256(files[BASELINE]).hexdigest()
    assert result['snapshot_integrity_verified'] and not result['full_validation_passed']
    assert record['manifest'] == expected


def test_actual_writer_preserves_historical_report_and_baseline_verifier(tmp_path):
    from support.migration_transaction import setup, apply, normative
    root, old, plan, args = setup(tmp_path, files=evidence_source(nested=True))
    before = verify_source_history(old).data
    before_baseline = verify_baseline_snapshot(ProjectBoundary(root), old[BASELINE])
    observations = []
    args['gates'] = (historical_contract_host(observations),)
    outcome = apply(root, plan, args)
    assert outcome['write_state'] == 'committed'
    assert observations
    for observed in observations:
        assert observed['historical'] == before['historical']
        assert observed['historical_integrity_verified']
        assert not any(observed[k] for k in ('current_context_verified',
            'current_readiness_verified', 'external_run_verified', 'human_authority_verified',
            'approval_granted', 'write_authorized'))
    after = verify_migrated_history(normative(root), project_id=PROJECT_ID).data
    after_baseline = verify_baseline_snapshot(ProjectBoundary(root), old[BASELINE])
    assert before['historical'] == after['historical']
    for key in ('record_sha256', 'model_root_sha256', 'model_root_algorithm', 'historical'):
        assert before_baseline[key] == after_baseline[key]
    assert before_baseline['legacy_manifest_sha256'] is None
    assert after_baseline['legacy_manifest_sha256'] == after['legacy_manifest_sha256']
    assert (root/EVIDENCE).read_bytes() == old[EVIDENCE]
    assert (root/BASELINE).read_bytes() == old[BASELINE]
    assert not after_baseline['release_authorized'] and not after_baseline['approval_granted']


def test_historical_absent_configuration_is_not_invented():
    old, target, _ = migrated(full_project())
    result = verify_migrated_history(target, project_id=PROJECT_ID).data
    assert by_id(result, 'SR-EVD-0001')['configuration_binding'] == {}
    assert result['historical'] == verify_source_history(old).data['historical']


def test_original_whitespace_bytes_and_historical_report_are_owned():
    files = evidence_source()
    # The old evidence also occurs in its sealed snapshot; preserve both copies.
    old_raw = files[EVIDENCE]
    files[EVIDENCE] = json.dumps(json.loads(old_raw), indent=4).encode() + b'\r\n'
    # Rebuild the synthetic snapshots before passing anything to the reader.
    files = {p: raw for p, raw in files.items() if not p.startswith(('archive/', 'spec/baselines/'))}
    seal(files)
    old, target, _ = migrated(files)
    report = verify_migrated_history(target, project_id=PROJECT_ID)
    expected = report.sha256; detached = report.data
    detached['historical']['records'].clear(); target[EVIDENCE] = b'changed after ownership'
    assert report.sha256 == expected and report.data['historical']['records']
    assert by_id(report.data, 'SR-EVD-0001')['original_byte_sha256'] == sha256(old[EVIDENCE]).hexdigest()
    with pytest.raises(TypeError): bool(report)
    with pytest.raises(TypeError): HistoricalVerification()
