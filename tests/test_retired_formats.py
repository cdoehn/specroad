"""Closed current configuration and matching relocated portable contracts."""
import json

import pytest

from specroad.model.configuration import ProjectConfiguration
from specroad.model.configuration_schema import SCHEMA_ID
from specroad.model.errors import ModelError
from specroad.model.schema_catalog import SchemaCatalog, SchemaLookupError
from support.model import configuration_value
from support.portable import build_distribution
from support.processes import run_python
from support.read_only import inventory, no_write_attempts


@pytest.mark.parametrize('value', [True, False, None, 0, 'yes', {}])
def test_auto_recover_is_rejected_as_removed_field_not_silently_ignored(tmp_path, value):
    config = configuration_value(transaction_policy={'auto_recover': value, 'retain_receipts': True})
    before = inventory(tmp_path)
    with no_write_attempts():
        with pytest.raises(ModelError) as caught:
            ProjectConfiguration(config)
        assert caught.value.reason == 'unknown_field'
        assert caught.value.pointer == '/transaction_policy/auto_recover'
        with pytest.raises(ModelError):
            SchemaCatalog().validate(SCHEMA_ID, config)
    assert inventory(tmp_path) == before


@pytest.mark.parametrize('policy', [{}, {'retain_receipts': True}])
def test_current_receipt_policy_still_has_matching_native_and_schema_contract(policy):
    value = configuration_value(transaction_policy=policy)
    assert ProjectConfiguration(value).data == value
    SchemaCatalog().validate(SCHEMA_ID, value)


@pytest.mark.parametrize('identity', ['restore-command-v1', 'recovery-status-v1'])
def test_retired_repair_results_are_not_active_distribution_schemas(identity):
    with pytest.raises(SchemaLookupError):
        SchemaCatalog().get(identity)


def test_module_and_pyz_publish_same_current_contracts_without_repair_commands(tmp_path):
    output = tmp_path / 'distribution'; build_distribution(output)
    moved = tmp_path / 'relocated'; output.rename(moved)
    before = inventory(tmp_path)
    for target in (moved / 'module', moved / 'specroad.pyz'):
        shown = run_python(['-I', '-S', '-B', str(target), 'schema', 'show', SCHEMA_ID,
                            '--format=json'], tmp_path, capture=True)
        assert shown.returncode == 0, shown.stderr
        assert json.loads(shown.stdout)['result'] == SchemaCatalog().show(SCHEMA_ID)
        for words in (['recover', 'restore'], ['recover', 'run'], ['recover', 'discard']):
            result = run_python(['-I', '-S', '-B', str(target), *words, '--format=json'],
                                tmp_path, capture=True)
            assert result.returncode == 2
    assert inventory(tmp_path) == before
