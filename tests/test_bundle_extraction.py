"""15.e.W: verified bytes, journaled publication and preserved partial boundaries."""
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from specroad.authoring import _bootstrap_io as bootstrap
from specroad.bundles import prepare_project_bundle, prepare_partial_bundle, verify_bundle
from specroad.bundles import extraction
from specroad.bundles.extraction import extract_bundle
from specroad.bundles._extraction_record import COMPLETED
from specroad.bundles.manifest import MANIFEST_NAME
from specroad.cli.application import dispatch_result, execute_request
from specroad.cli.commands import builtin_registry
from specroad.cli.result_schemas import validate_result_document
from specroad.cli.self_description import describe_command
from specroad.security import SafetyViolation, ProjectBoundary
from specroad.storage.project import ProjectSource
from specroad.storage.operational_preflight import observe_operational_preflight
from support.model import put
from support.read_only import inventory, no_write_attempts
from test_bundle_verification import bundle, rebind
from test_bundle_verification_right import reviewed, context_path, path
from test_partial_bundle import scope
from test_partial_bundle_right import configured


def check_files(target, original, result):
    validate_result_document('bundle-extract-v1', result)
    assert result['project_root'] == str(target.resolve())
    assert result['manifest'] == original.manifest
    assert result['file'] == {'size': len(original.source_bytes), 'sha256': original.sha256}
    assert result['bootstrap_state'] == 'complete'
    files = {**original.files, MANIFEST_NAME: original.manifest_bytes}
    assert result['files'] == [{'path': p, 'size': len(raw), 'sha256': sha256(raw).hexdigest()}
                              for p, raw in sorted(files.items())]
    assert all((target / p).read_bytes() == raw for p, raw in files.items())
    actual = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    assert actual == set(files) | {'/'.join((*COMPLETED, 'journal.json'))}
    assert not (target / bootstrap.STAGING).exists()
    assert not (target / '.git').exists()
    assert not result['full_semantic_validation'] and not result['approval_granted']
    assert not result['creator_authenticated']


@pytest.mark.parametrize('route', ['bytes', 'cli', 'request', 'registry'])
@pytest.mark.parametrize('target_exists', [False, True])
def test_verified_project_roundtrip_to_new_or_empty_root(tmp_path, route, target_exists):
    original = bundle(tmp_path / 'origin')
    target = tmp_path / 'extracted project'
    if target_exists: target.mkdir()
    old_inode = target.stat().st_ino if target_exists else None
    source = tmp_path / 'input.zip'; source.write_bytes(original.source_bytes)
    if route == 'bytes':
        value = extract_bundle(original.source_bytes, target, expected_sha256=original.sha256)
    else:
        argv = ['bundle', 'extract', source.name, '--output', target.name,
                '--expected-sha256', original.sha256]
        if route == 'cli': result = dispatch_result(argv, cwd=tmp_path)
        elif route == 'request':
            result = execute_request({'command_id': 'bundle.extract', 'arguments': {'file': source.name},
                'options': {'--output': target.name, '--expected-sha256': original.sha256}}, cwd=tmp_path).result
        else:
            registry = builtin_registry()
            result = registry.execute_result(registry.parse(argv), cwd=tmp_path)
        assert result.exit_code == 0, result.as_dict()
        value = result.as_dict()['result']
    check_files(target, original, value)
    assert value['external_hash_verified']
    loaded = ProjectSource(target)
    assert loaded.configuration.project_id == original.manifest['project_id']
    assert observe_operational_preflight(loaded.boundary)['consistency_state'] == 'consistent'
    reproduced = prepare_project_bundle(target)
    assert reproduced.source_bytes == original.source_bytes
    if target_exists: assert target.stat().st_ino == old_inode


@pytest.mark.parametrize('kind', ['document', 'release'])
@pytest.mark.parametrize('context', ['review', 'configuration'])
def test_partial_manifest_and_separate_context_survive_without_promotion(tmp_path, kind, context):
    root = tmp_path / 'origin'
    if context == 'review':
        values, review = reviewed(root, kind)
        original = prepare_partial_bundle(root, scope(kind))
        target_value = values[-2]
        assert context_path(target_value) in original.files and path(target_value) not in original.files
    else:
        _, chain, _ = configured(root, kind)
        original = prepare_partial_bundle(root, scope(kind, configuration_id=chain[-1]['id']))
    target = tmp_path / 'partial'
    value = extract_bundle(original.source_bytes, target)
    check_files(target, original, value)
    assert value['manifest']['read_only'] and value['manifest']['idempotency_scope'] == 'local_only'
    assert value['validation_scope'] == 'partial_payload_model'
    with pytest.raises(SafetyViolation), no_write_attempts():
        ProjectSource(target)
    before = inventory(target)
    with no_write_attempts():
        result = dispatch_result(['bundle', 'create', '--scope', 'project', '--project', str(target),
                                  '--output', str(tmp_path / 'forbidden.zip')])
    assert result.exit_code == 7 and inventory(target) == before
    assert not (tmp_path / 'forbidden.zip').exists()
    # Removing the root marker alone cannot erase its retained bootstrap proof.
    (target / MANIFEST_NAME).unlink()
    with pytest.raises(SafetyViolation), no_write_attempts():
        ProjectSource(target)


def test_full_project_does_not_turn_historical_manifest_into_live_byte_lock(tmp_path):
    original = bundle(tmp_path / 'origin'); target = tmp_path / 'project'
    extract_bundle(original.source_bytes, target)
    source = ProjectSource(target)
    item = next(p for p in original.files if p.startswith('spec/goals/'))
    value = json.loads((target / item).read_bytes()); value['statement'] = 'A legitimate new goal value.'
    # Simulate an independently authorized later editor; extraction itself grants
    # no transaction permission. Existing target validation remains authoritative.
    put(target, item, json.dumps(value).encode())
    assert source.require_write_target(item)
    later = prepare_project_bundle(target)
    assert verify_bundle(later.source_bytes)['manifest']['bundle_kind'] == 'project'
    assert later.sha256 != original.sha256
    assert (target / MANIFEST_NAME).read_bytes() == original.manifest_bytes


@pytest.mark.parametrize('kind', ['file', 'directory', 'hidden', 'symlink', 'target_symlink'])
def test_foreign_target_contents_are_never_overwritten(tmp_path, kind):
    original = bundle(tmp_path / 'origin'); target = tmp_path / 'target'
    foreign = tmp_path / 'foreign'; foreign.mkdir(); (foreign / 'keep').write_bytes(b'foreign')
    if kind == 'target_symlink': target.symlink_to(foreign)
    else:
        target.mkdir()
        if kind == 'directory': (target / 'empty').mkdir()
        elif kind == 'symlink': (target / 'link').symlink_to(foreign)
        else: (target / ('.hidden' if kind == 'hidden' else 'file')).write_bytes(b'keep')
    source = tmp_path / 'input.zip'; source.write_bytes(original.source_bytes)
    before = inventory(tmp_path)
    with no_write_attempts():
        result = dispatch_result(['bundle', 'extract', str(source), '--output', str(target)])
    assert result.exit_code == (7 if kind == 'target_symlink' else 6)
    assert result.as_dict()['result'] is None and inventory(tmp_path) == before


@pytest.mark.parametrize('kind', ['invalid_zip', 'bad_model', 'wrong_hash', 'input_symlink', 'missing'])
def test_bad_inputs_fail_before_target_creation(tmp_path, kind):
    original = bundle(tmp_path / 'origin'); source = tmp_path / 'input.zip'
    raw = original.source_bytes
    if kind == 'invalid_zip': raw = b'not a zip'
    if kind == 'bad_model': raw = rebind(original, bundle_model_root_sha256='a' * 64, origin_model_root_sha256='a' * 64)
    if kind == 'input_symlink':
        other = tmp_path / 'other'; other.write_bytes(raw); source.symlink_to(other)
    elif kind != 'missing': source.write_bytes(raw)
    before = inventory(tmp_path)
    argv = ['bundle', 'extract', str(source), '--output', str(tmp_path / 'output')]
    if kind == 'wrong_hash': argv += ['--expected-sha256', '0' * 64]
    with no_write_attempts(): result = dispatch_result(argv)
    assert result.exit_code == (7 if kind == 'input_symlink' else 5 if kind == 'missing' else 3)
    assert result.as_dict()['result'] is None and inventory(tmp_path) == before


@pytest.mark.parametrize('point', ['prepare', 'publish'])
@pytest.mark.parametrize('existing', [False, True])
def test_native_failures_restore_original_missing_or_empty_target(tmp_path, point, existing, monkeypatch):
    original = bundle(tmp_path / 'origin'); target = tmp_path / 'output'
    if existing: target.mkdir()
    source = tmp_path / 'input.zip'; source.write_bytes(original.source_bytes)
    before = inventory(tmp_path)
    if point == 'prepare':
        native = bootstrap.BootstrapTree.write
        def fail(tree, path, raw):
            native(tree, path, raw)
            if path == 'specroad.json': raise OSError('injected preparation failure')
        monkeypatch.setattr(bootstrap.BootstrapTree, 'write', fail)
    else:
        native = bootstrap.rename_new; calls = []
        def fail(*args):
            native(*args); calls.append(1)
            if len(calls) == 2: raise OSError('injected publication failure')
        monkeypatch.setattr(bootstrap, 'rename_new', fail)
    result = dispatch_result(['bundle', 'extract', str(source), '--output', str(target)])
    assert result.exit_code == 5, result.as_dict()
    assert inventory(tmp_path) == before


def test_same_verified_input_resumes_proven_publication_prefix(tmp_path, monkeypatch):
    original = bundle(tmp_path / 'origin'); target = tmp_path / 'target'; target.mkdir()
    native_rename = bootstrap.rename_new
    calls = []
    def interrupt(*args):
        native_rename(*args); calls.append(1)
        if len(calls) == 2: raise OSError('simulated interruption')
    with monkeypatch.context() as active:
        active.setattr(bootstrap, 'rename_new', interrupt)
        active.setattr(bootstrap.BootstrapTree, 'cleanup', lambda tree: (_ for _ in ()).throw(OSError('crashed cleanup')))
        with pytest.raises(bootstrap.BootstrapError): extract_bundle(original.source_bytes, target)
    assert (target / bootstrap.STAGING / 'journal.json').exists()
    value = extract_bundle(original.source_bytes, target)
    check_files(target, original, value)
    assert ProjectSource(target).configuration.project_id == original.manifest['project_id']


def test_completed_bootstrap_is_rechecked_without_reinstalling_files(tmp_path):
    original = bundle(tmp_path / 'origin'); target = tmp_path / 'target'
    first = extract_bundle(original.source_bytes, target)
    before = inventory(target)
    with patch.object(bootstrap, 'rename_new', side_effect=AssertionError('no second publication')):
        again = extract_bundle(original.source_bytes, target)
    assert again == first and inventory(target) == before


@pytest.mark.parametrize('alteration', ['foreign', 'changed', 'journal'])
def test_changed_completed_bootstrap_is_not_overwritten_or_accepted(tmp_path, alteration):
    original = bundle(tmp_path / 'origin'); target = tmp_path / 'target'
    extract_bundle(original.source_bytes, target)
    if alteration == 'foreign': (target / 'foreign').write_bytes(b'preserve')
    elif alteration == 'changed': (target / MANIFEST_NAME).write_bytes(b'changed by owner')
    else: (target.joinpath(*COMPLETED) / 'journal.json').write_bytes(b'{}')
    before = inventory(target)
    with no_write_attempts(), pytest.raises(bootstrap.BootstrapError):
        extract_bundle(original.source_bytes, target)
    assert inventory(target) == before


def test_input_change_during_verification_is_rejected_without_target_write(tmp_path):
    original = bundle(tmp_path / 'origin'); source = tmp_path / 'input.zip'; source.write_bytes(original.source_bytes)
    target = tmp_path / 'output'; native = extraction.verify_bundle
    def changed(*args, **kwargs):
        value = native(*args, **kwargs); source.write_bytes(b'changed concurrently'); return value
    with patch.object(extraction, 'verify_bundle', changed):
        result = dispatch_result(['bundle', 'extract', str(source), '--output', str(target)])
    assert result.exit_code == 6 and not target.exists()
    assert source.read_bytes() == b'changed concurrently'


def test_configuration_is_last_and_every_published_unit_has_bound_journal(tmp_path, monkeypatch):
    original = bundle(tmp_path / 'origin'); target = tmp_path / 'output'
    native = bootstrap.rename_new; moved = []
    def observe(function, source_fd, source, target_fd, destination):
        journal = json.loads((target / bootstrap.STAGING / 'journal.json').read_bytes())
        assert journal['format'] == 'specroad-bundle-bootstrap-v1'
        assert journal['entries'][MANIFEST_NAME]['sha256'] == sha256(original.manifest_bytes).hexdigest()
        assert not (target / 'specroad.json').exists()
        moved.append(destination); native(function, source_fd, source, target_fd, destination)
    monkeypatch.setattr(bootstrap, 'rename_new', observe)
    check_files(target, original, extract_bundle(original.source_bytes, target))
    assert moved[-1] == 'specroad.json'


@pytest.mark.parametrize('argv', [[], ['file.zip'], ['file.zip', '--output', ''],
                                  ['file.zip', '--output', 'out', '--profile', 'ai-runtime']])
def test_incomplete_or_unimplemented_requests_never_create_root(tmp_path, argv):
    before = inventory(tmp_path)
    with no_write_attempts(): result = dispatch_result(['bundle', 'extract', *argv], cwd=tmp_path)
    assert result.exit_code in (2, 5) and inventory(tmp_path) == before


def test_command_contract_is_projectless_root_creation(tmp_path):
    with no_write_attempts(): contract = describe_command(builtin_registry(), 'bundle.extract')
    assert contract['command_class'] == contract['preflight_profile'] == 'root_creation'
    assert contract['lock_kind'] == 'bootstrap' and not contract['requires_project'] and not contract['requires_git']
    assert contract['write_effects']['scope'] == 'new_root'
    assert contract['stdout']['result_schema'] == 'bundle-extract-v1'
