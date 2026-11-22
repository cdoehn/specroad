"""Native additive migration retains init originals without promoting authority."""
from types import MappingProxyType
import json
import pytest
from specroad.cli.application import dispatch_result
from specroad.model.canonical import canonical_json_bytes
from specroad.model.errors import ModelError
from specroad.migration.planning import plan_migration
from specroad.migration._backup_source import _observe
from support.plan_models import migration
from support.read_only import no_write_attempts

JOURNAL = '.specroad/recovery/init-bootstrap/journal.json'


@pytest.fixture(scope='module')
def initialized_source(tmp_path_factory):
    # One real native setup per module/worker; cases own independent byte maps.
    root = tmp_path_factory.mktemp('plan-migration-originals') / 'project'
    result = dispatch_result(['init', str(root)])
    assert result.exit_code == 0, result.as_dict()
    files, _, check = _observe(root); check()
    assert JOURNAL in files
    return MappingProxyType(files)


def test_original_bootstrap_is_preserved_as_history_not_current_approval(initialized_source):
    from specroad.bundles.migration_source import prepare_source_backup, verify_source_backup
    from specroad.migration.transaction_target import materialized_files
    from specroad.migration.current_source import preservation_history
    source = dict(initialized_source); before = dict(source)
    fields, configuration = migration(source)
    with no_write_attempts():
        planned = plan_migration(source, **fields)
        target = materialized_files(planned.change_plan, source)
        backup = prepare_source_backup(source)
        reopened = verify_source_backup(backup.source_bytes, expected_sha256=backup.sha256,
            expected_source_files_sha256=backup.manifest['source_files_sha256'])
        history = preservation_history(target)
    assert source == before and reopened.files == source
    assert planned.ready and target == {**source, 'specroad.json': configuration}
    assert target[JOURNAL] == source[JOURNAL]
    assert JOURNAL in planned.data['change_plan']['operations'][0]['protected_paths']
    assert history['historical'] == preservation_history(source)['historical']
    assert not history['approval_granted'] and not history['current_context_verified']
    assert not history['external_run_verified'] and not planned.data['write_authorized']


@pytest.mark.parametrize('fault', ['noncanonical', 'unknown-field', 'state', 'unit-order',
    'identity-collision', 'resource-hash', 'extra-entry', 'oversized', 'extra-file'])
def test_malformed_bootstrap_original_blocks_planning_without_mutation(initialized_source, fault):
    source = dict(initialized_source)
    value = json.loads(source[JOURNAL])
    if fault == 'unknown-field': value['approval_granted'] = True
    elif fault == 'state': value['state'] = 'complete'
    elif fault == 'unit-order': value['units'].reverse()
    elif fault == 'identity-collision': value['stage_identity'] = value['root_identity']
    elif fault == 'resource-hash': value['entries']['profiles/core.json']['sha256'] = '0' * 64
    elif fault == 'extra-entry': value['entries']['spec/implementation-plans'] = dict(value['entries']['spec'])
    source[JOURNAL] = canonical_json_bytes(value)
    if fault == 'noncanonical': source[JOURNAL] += b'\n'
    elif fault == 'oversized': source[JOURNAL] += b' ' * 262145
    elif fault == 'extra-file': source[JOURNAL.rsplit('/',1)[0] + '/unlisted.json'] = b'{}'
    original = dict(source); fields, _ = migration(source)
    with no_write_attempts(), pytest.raises(ModelError):
        plan_migration(source, **fields)
    assert source == original


@pytest.mark.parametrize('path,reason', [
    ('.specroad/recovery/unregistered/journal.json', 'migration_protected_path'),
    ('.specroad/transactions/active/journal.json', 'migration_protected_path'),
    ('.specroad-bootstrap/journal.json', 'bundle_unsupported_payload')])
def test_unknown_or_active_operational_input_is_never_hidden(initialized_source, path, reason):
    from specroad.bundles.errors import BundleError
    source = {**initialized_source, path: b'{}'}
    before = dict(source); fields, _ = migration(source)
    with no_write_attempts(), pytest.raises((ModelError, BundleError)) as failure:
        plan_migration(source, **fields)
    assert failure.value.reason == reason and source == before
