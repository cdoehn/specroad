"""Operational policy negatives, real Bundle bytes, native Work continuation and physical failures."""
from contextlib import contextmanager
from hashlib import sha256
from io import BytesIO
import json
import os
from zipfile import ZipFile, ZIP_DEFLATED
import pytest

from specroad.force import ForceDecisions, ForceRequest
from specroad.force_operations import scope
from specroad.cli.application import execute, execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.result_schemas import validate_result_document
from specroad.model.errors import ModelError
from specroad.security import SafetyViolation
from specroad.bundles import prepare_project_bundle, verify_bundle, BundleError
from specroad.bundles.extraction import extract_bundle
from specroad.storage.archive import decode_zip, encode_zip, ArchiveError
from specroad.work.force_attempt import own_attempt
from specroad.work.resume import resume_read_only_work
from support.force_cases import fixture, replacement, files, ACTOR, ALLOW
from support.read_only import inventory
from test_force_operations import operational, apply, marker
from test_work_resume import recorded, setup as work_setup
from test_project_bundle import project


@contextmanager
def forced(owners=()):
    ledger = ForceDecisions(ForceRequest(True, 'Explicit operational test'))
    with scope(ledger, {'owners': list(owners)}): yield ledger


@pytest.mark.parametrize('variant', ['compressed', 'wrong_hash', 'invalid_manifest_binding'])
def test_bundle_negative_checks_preserve_actual_bytes_and_allow_native_extraction(tmp_path, variant):
    source = tmp_path / 'source'; project(source)
    original = prepare_project_bundle(source)
    raw = original.source_bytes
    expected = original.sha256
    if variant == 'compressed':
        stream = BytesIO()
        with ZipFile(stream, 'w', compression=ZIP_DEFLATED) as archive:
            with ZipFile(BytesIO(raw)) as canonical:
                for name in canonical.namelist(): archive.writestr(name, canonical.read(name))
        raw = stream.getvalue(); expected = sha256(raw).hexdigest()
    elif variant == 'wrong_hash': expected = '0' * 64
    else:
        from test_bundle_verification import rebind
        raw = rebind(original, origin_model_root_sha256='1' * 64, bundle_model_root_sha256='1' * 64)
        expected = sha256(raw).hexdigest()
    with pytest.raises(BundleError): verify_bundle(raw, expected_sha256=expected)
    before = inventory(source)
    with forced() as ledger:
        verified = verify_bundle(raw, expected_sha256=expected)
        assert verified['format_version'] == 'force-bundle-verify-v1'
        assert verified['force']['used'] and not verified['container_verified']
        assert verified['external_hash_verified'] is (variant != 'wrong_hash')
        assert not verified['approval_granted'] and not verified['write_authorized']
        validate_result_document('bundle-verify-v1', verified)
        result = extract_bundle(raw, tmp_path / 'restored', expected_sha256=expected)
        validate_result_document('bundle-extract-v1', result)
        assert result['format_version'] == 'force-bundle-extract-v1'
        assert result['force']['used'] and ledger.summary['used']
        for path, content in original.files.items():
            assert (tmp_path / 'restored' / path).read_bytes() == content
    assert inventory(source) == before


def test_cli_force_bundle_verification_is_scoped_and_never_becomes_a_normal_pass(tmp_path):
    source = tmp_path / 'source'; project(source)
    original = prepare_project_bundle(source)
    filename = tmp_path / 'bundle.zip'; filename.write_bytes(original.source_bytes)
    request = {'command_id': 'bundle.verify', 'arguments': {'file': str(filename)},
        'options': {'--expected-sha256': '0' * 64}, 'force': True}
    before = inventory(tmp_path)
    done = execute_request(request, cwd=tmp_path).result
    assert done.exit_code == 0 and done.status.value == 'forced', done.as_dict()
    assert done.as_dict()['summary']['force']['used'] and done.result['external_hash_verified'] is False
    normal = execute_request({k: v for k, v in request.items() if k != 'force'}, cwd=tmp_path).result
    assert normal.exit_code == 3 and normal.status.value == 'failed'
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('value', ['owned/CON.txt', 'owned/colon:name.txt', 'owned/trailing.'])
def test_literal_portable_path_policy_is_overridden_only_on_explicit_call(tmp_path, value):
    from specroad.storage.archive import validate_portable_archive_paths
    root, _ = fixture(tmp_path / 'project')
    with pytest.raises((ArchiveError, ModelError)): validate_portable_archive_paths([value])
    plan = operational(replacement(root, value, b'explicit target'))
    result = apply(root, plan)
    assert result['force']['used'] and (root / value).read_bytes() == b'explicit target'
    assert any(v['gate_id'].startswith('path:') for v in result['force']['overrides'])
    proof = result['completion']
    from specroad.changes.force_operational_receipts import read_force_attempt
    assert read_force_attempt(root, proof['transaction_id'], expected_project_id=plan.data['project_id']).data['receipt_verified']
    with pytest.raises((ArchiveError, ModelError)): validate_portable_archive_paths([value])


def test_archive_resource_limit_records_exact_negative_and_all_bytes():
    raw = encode_zip({'owned.bin': b'complete payload'}, max_uncompressed_bytes=1024)
    with pytest.raises(ArchiveError): decode_zip(raw, max_uncompressed_bytes=1)
    with forced() as ledger:
        assert decode_zip(raw, max_uncompressed_bytes=1) == {'owned.bin': b'complete payload'}
        row = next(v for v in ledger.summary['overrides'] if v['gate_id'] == 'resource_limit:archive_bytes')
        assert row['observed_binding'] == len(b'complete payload') and row['requested_binding'] == 1
    with pytest.raises(ArchiveError): decode_zip(raw, max_uncompressed_bytes=1)


@pytest.mark.parametrize('fault', ['unreadable', 'duplicate', 'navigation'])
def test_unknown_or_ambiguous_bundle_bytes_never_invent_target_data(tmp_path, fault):
    raw = b'not a readable archive'
    if fault != 'unreadable':
        stream = BytesIO()
        with ZipFile(stream, 'w') as archive:
            if fault == 'duplicate':
                archive.writestr('same', b'first')
                with pytest.warns(UserWarning): archive.writestr('same', b'second')
            else: archive.writestr('../outside', b'not a relative product resource')
        raw = stream.getvalue()
    with forced(), pytest.raises((ArchiveError, BundleError, ModelError, ValueError)):
        extract_bundle(raw, tmp_path / 'target')
    assert not (tmp_path / 'target').exists() and not (tmp_path / 'outside').exists()


@pytest.mark.parametrize('select_owner', [False, True])
def test_native_work_force_clones_bound_inputs_and_preserves_busy_original(recorded, tmp_path, select_owner):
    initial, roots, location, store = work_setup(tmp_path)
    with location.for_checkpoint() as other:
        raw = (location.path / 'work-lock.json').read_bytes()
        before = inventory(location.path)
        with pytest.raises(BlockingIOError): resume_read_only_work(store)
        owners = [{'path': 'work-lock.json', 'sha256': sha256(raw).hexdigest()}] if select_owner else []
        with forced(owners) as ledger:
            if not select_owner:
                with pytest.raises((BlockingIOError, SafetyViolation)): own_attempt(store)
            else:
                clone = own_attempt(store)
                assert clone._location.path != location.path
                assert clone.read().raw == initial.raw
                result = resume_read_only_work(clone, cwd=tmp_path)
                assert result.executed and result.command_exit_code == 0
                assert json.loads(result.outcome_bytes)['command'] == 'version'
                assert ledger.summary['used']
                assert any(v['gate_id'] == 'lock:work_exclusivity' for v in ledger.summary['overrides'])
                assert not (clone._location.path / 'work-lock.json').exists()
        assert inventory(location.path) == before
        other.check()


def test_force_private_work_mode_runs_native_handler_without_chmod_of_original(recorded, tmp_path):
    _, _, location, store = work_setup(tmp_path)
    location.path.chmod(0o755)
    before_mode = location.path.stat().st_mode
    with pytest.raises(SafetyViolation): resume_read_only_work(store)
    with forced() as ledger:
        result = resume_read_only_work(store, cwd=tmp_path)
        assert result.executed and result.command_exit_code == 0
        assert any(v['gate_id'] == 'safety:private_work_storage' for v in ledger.summary['overrides'])
    assert location.path.stat().st_mode == before_mode


def test_structured_owner_input_is_explicit_typed_and_not_ambient(tmp_path):
    root, path = fixture(tmp_path / 'project'); old, _, _ = marker(root)
    plan = operational(replacement(root, path, b'actual target'))
    filename = tmp_path / 'plan.json'; filename.write_bytes(plan.source_bytes)
    request = {'command_id': 'change.apply', 'arguments': {'plan_file': str(filename)}, 'force': True,
        'operational_binding': {'owners': []}, 'options': {
            '--actor-type': ACTOR['actor_type'], '--actor-id': ACTOR['actor_id'], '--request-id': plan.data['request_id']}}
    done = execute_request(request, cwd=root, context_builder=InvocationContextBuilder(publication_authority=ALLOW)).result
    assert done.exit_code == 0 and done.status.value == 'forced', done.as_dict()
    assert done.result['outcome']['complete'] and (root / path).read_bytes() == b'actual target'
    invalid = execute_request({'command_id': 'help', 'operational_binding': {'owners': [
        {'path': '.specroad/locks/project.json', 'sha256': '1' * 64}]}}, cwd=tmp_path).result
    assert invalid.exit_code == 2


def test_public_work_resume_uses_new_attempt_and_keeps_original_request(recorded, tmp_path):
    from specroad.cli.results import thaw
    from test_analyzer_work import early, store_at, finish
    from test_analyzer_subjects import project as analyzer_project
    from test_analyzer_cli import BUILTIN
    from specroad.analyzers.requests import AnalyzerRequest
    root = tmp_path / 'project'; analyzer_project(root)
    original = tmp_path / 'work'
    first = early(['request', '--project', str(root), '--analyzer', BUILTIN,
        '--analysis-id', 'force-own-analysis', '--work-dir', str(original)], tmp_path)
    assert first.exit_code == 8
    store = store_at(original)
    with store._location.for_checkpoint() as other:
        owner = (original / 'work-lock.json').read_bytes()
        before = inventory(original)
        result = execute(['work', 'resume', str(original), '--force', '--force-owner',
            'work-lock.json=' + sha256(owner).hexdigest()], cwd=tmp_path).result
        assert result.exit_code in (0, 8), result.as_dict()
        assert result.as_dict()['summary']['force']['used']
        selection = next(v for v in result.as_dict()['summary']['force']['overrides']
            if v['gate_id'] == 'work_marker:retained_owner')
        new_path = selection['requested_binding']['work_dir']
        assert new_path != str(original)
        assert inventory(original) == before
        other.check()
        if result.exit_code == 8: result = finish(new_path, tmp_path)
        assert result.exit_code == 0, result.as_dict()
        request = AnalyzerRequest(json.dumps(thaw(result.result)['data']).encode())
        assert request.data['request_id'] == 'force-own-analysis'
        assert len(request.data['subjects']) == 2
        assert inventory(original) == before
