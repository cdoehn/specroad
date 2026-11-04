"""16.h robustness: exact individual consent and immutable lossless boundary."""
import copy
import json
from dataclasses import FrozenInstanceError
from unittest.mock import patch
import pytest

from specroad.migration.losses import (assess_migration_preservation, check_loss_acceptance,
    MigrationLossError)
from specroad.migration.plan_values import MigrationPlanError
from specroad.migration.planning import plan_migration
from specroad.model.errors import ModelError
from support.migration_plans import FIELDS, target_inputs
from support.reference01 import encoded, put, digest
from support.migration_losses import (REQ, candidate, assess, extension_source,
    with_config_extensions, target_with_extensions)


def two_losses():
    files, inputs, target, _ = candidate()
    value = json.loads(target[REQ]); value['title'] = 'changed'; del value['extensions']['example.note']
    target[REQ] = encoded(value)
    return files, inputs, target, assess(files, target, inputs)


def test_default_rejects_every_missing_individual_acceptance_and_returns_all_ids():
    files, inputs, target, report = two_losses(); before = copy.deepcopy((files, inputs, target))
    with pytest.raises(MigrationLossError) as caught:
        check_loss_acceptance(report, expected_report_sha256=report.sha256)
    assert caught.value.reason == 'migration_loss_acceptance_required'
    assert list(caught.value.missing_loss_ids) == sorted(r['loss_id'] for r in report.data['losses'])
    assert caught.value.diagnostic()['missing_loss_ids'] == list(caught.value.missing_loss_ids)
    assert caught.value.unknown_loss_ids == () and (files, inputs, target) == before


def test_partial_acceptance_has_no_partial_success():
    _, _, _, report = two_losses(); rows = report.data['losses']
    with pytest.raises(MigrationLossError) as caught:
        check_loss_acceptance(report, expected_report_sha256=report.sha256, accept_loss=[rows[0]['loss_id']])
    assert caught.value.missing_loss_ids == (rows[1]['loss_id'],)


def test_full_explicit_acceptance_retains_every_loss_detail_but_grants_nothing():
    _, _, _, report = two_losses(); rows = report.data['losses']
    result = check_loss_acceptance(report, expected_report_sha256=report.sha256,
        accept_loss=[r['loss_id'] for r in reversed(rows)])
    assert result.data == {'format_version': 'migration-loss-acceptance-v1',
        'report_sha256': report.sha256, 'accepted_losses': rows,
        'write_authorized': False, 'approval_granted': False}
    assert not result.write_authorized
    result.data['accepted_losses'].clear()
    assert len(result.data['accepted_losses']) == 2
    with pytest.raises(TypeError): bool(result)
    with pytest.raises(FrozenInstanceError): result._encoded = b'{}'


def test_lossless_report_requires_no_individual_decision():
    files, inputs, target, _ = candidate(); report = assess(files, target, inputs)
    result = check_loss_acceptance(report, expected_report_sha256=report.sha256)
    assert result.data['accepted_losses'] == [] and not result.write_authorized


@pytest.mark.parametrize('selected', [True, False, '*', ['*'], [True], ['LOSS-0'],
    {'accept_all': True}, {'LOSS-'+'a'*64}, None])
def test_blanket_or_malformed_acceptances_are_rejected(selected):
    _, _, _, report = two_losses()
    with pytest.raises(MigrationPlanError) as caught:
        check_loss_acceptance(report, expected_report_sha256=report.sha256, accept_loss=selected)
    assert caught.value.reason == 'migration_loss_ids_required'


def test_duplicate_and_unknown_decisions_are_not_silently_normalized():
    _, _, _, report = two_losses(); ids = [r['loss_id'] for r in report.data['losses']]
    with pytest.raises(MigrationPlanError) as caught:
        check_loss_acceptance(report, expected_report_sha256=report.sha256, accept_loss=ids + ids[:1])
    assert caught.value.reason == 'migration_duplicate_loss_acceptance'
    foreign = 'LOSS-'+'f'*64
    with pytest.raises(MigrationLossError) as caught:
        check_loss_acceptance(report, expected_report_sha256=report.sha256, accept_loss=ids+[foreign])
    assert caught.value.reason == 'migration_loss_acceptance_mismatch'
    assert caught.value.unknown_loss_ids == (foreign,)


@pytest.mark.parametrize('changed', ['source', 'target', 'inputs'])
def test_changed_observation_requires_new_loss_ids_and_expected_report_hash(changed):
    files, inputs, target, first = two_losses()
    if changed == 'source': files['additional.txt'] = b'bound additional source'
    if changed == 'target': target['additional.txt'] = b'bound additional target'
    if changed == 'inputs': inputs['requirement_mappings'][0]['language'] = 'de'
    second = assess(files, target, inputs)
    assert second.sha256 != first.sha256
    assert set(r['loss_id'] for r in second.data['losses']).isdisjoint(r['loss_id'] for r in first.data['losses'])
    with pytest.raises(MigrationLossError) as caught:
        check_loss_acceptance(second, expected_report_sha256=first.sha256,
            accept_loss=[r['loss_id'] for r in first.data['losses']])
    assert caught.value.reason == 'migration_loss_report_changed' and caught.value.exit_code == 6
    with pytest.raises(MigrationLossError):
        check_loss_acceptance(second, expected_report_sha256=second.sha256,
            accept_loss=[r['loss_id'] for r in first.data['losses']])


def test_serialized_or_self_rehashed_report_cannot_replace_native_qualification():
    _, _, _, report = two_losses(); value = report.data
    value['losses'] = []; value['lossless'] = True
    value['report_sha256'] = digest({k: v for k, v in value.items() if k != 'report_sha256'})
    with pytest.raises(MigrationPlanError) as caught:
        check_loss_acceptance(value, expected_report_sha256=value['report_sha256'])
    assert caught.value.reason == 'migration_native_loss_report_required'


@pytest.mark.parametrize('expected', [None, True, '', 'A'*64, 'f'*63])
def test_expected_report_binding_is_explicit_and_exact(expected):
    _, _, _, report = two_losses()
    with pytest.raises(MigrationPlanError) as caught:
        check_loss_acceptance(report, expected_report_sha256=expected)
    assert caught.value.reason == 'migration_expected_hash_required'


@pytest.mark.parametrize('old,new', [(None, False), (False, 0), (True, 1),
    ([1, 2], [2, 1]), ({'a': None}, {}), ('e\u0301', 'é')])
def test_typed_values_order_null_and_unicode_are_not_coerced(old, new):
    files = extension_source(); value = json.loads(files[REQ]); value['extensions']['example.typed'] = old
    put(files, value); files, inputs, target, _ = candidate(files)
    value = json.loads(target[REQ]); value['extensions']['example.typed'] = new; target[REQ] = encoded(value)
    report = assess(files, target, inputs)
    assert not report.lossless and len(report.data['losses']) == 1
    row = report.data['losses'][0]
    assert row['pointer'].startswith('/extensions/example.typed')


def test_jcs_equivalent_number_spelling_is_not_information_loss():
    files = extension_source(); value = json.loads(files[REQ]); value['extensions']['example.number'] = 1
    put(files, value); files, inputs, target, _ = candidate(files)
    value = json.loads(target[REQ]); value['extensions']['example.number'] = 1.0
    target[REQ] = encoded(value)
    assert assess(files, target, inputs).lossless


def test_pointer_escapes_and_array_units_are_exact():
    files = extension_source(); value = json.loads(files[REQ])
    value['extensions']['example.units'] = {'x/y~z': None, 'array': [1, {'n': 2}]}
    put(files, value); files, inputs, target, _ = candidate(files)
    value = json.loads(target[REQ]); value['extensions']['example.units'] = {'array': [1, {'n': 3}]}
    target[REQ] = encoded(value); rows = assess(files, target, inputs).data['losses']
    assert [r['pointer'] for r in rows] == ['/extensions/example.units/array', '/extensions/example.units/x~1y~0z']
    assert rows[0]['before']['value'] == [1, {'n': 2}]
    assert rows[1]['before'] == {'present': True, 'value': None}
    assert rows[1]['after'] == {'present': False, 'value': None}


@pytest.mark.parametrize('field', ['id', 'created_by', 'updated_by', 'revision', 'relations', 'external_identities'])
def test_no_broad_field_exception_can_hide_changed_ids_metadata_or_relations(field):
    files, inputs, target, _ = candidate(); value = json.loads(target[REQ])
    replacement = {'id': 'SR-REQ-0002', 'created_by': {'actor_type': 'tool', 'actor_id': 'forged'},
        'updated_by': {'actor_type': 'tool', 'actor_id': 'forged'}, 'revision': 99,
        'relations': [], 'external_identities': []}
    value[field] = replacement[field]; target[REQ] = encoded(value)
    rows = assess(files, target, inputs).data['losses']
    assert rows and all(r['pointer'].startswith('/'+field) for r in rows)


def test_complete_consent_does_not_make_a_lossy_reference_plan_executable():
    files = extension_source(); with_config_extensions(files, {'example.config': {'retain': True}})
    good_inputs = target_with_extensions(files, {'example.config': {'retain': True}})
    files, _, target, _ = candidate(files, good_inputs)
    value = json.loads(target['specroad.json']); value['extensions'] = {}; target['specroad.json'] = encoded(value)
    observation = assess(files, target, good_inputs)
    accepted = check_loss_acceptance(observation, expected_report_sha256=observation.sha256,
        accept_loss=[r['loss_id'] for r in observation.data['losses']])
    assert accepted.data['accepted_losses'] and not accepted.write_authorized
    result = plan_migration(files, inputs=target_inputs(files), **FIELDS)
    assert not result.ready and result.change_plan is None
    assert result.data['loss_report']['losses']


def test_invalid_source_and_unsafe_target_paths_are_not_ordinary_acceptable_losses():
    files, inputs, target, _ = candidate()
    files['specroad.json'] = b'{"schema_version":"invented"}'
    with pytest.raises(ModelError): assess(files, target, inputs)
    files = extension_source(); target['../escape'] = b'unsafe'
    with pytest.raises(ModelError): assess(files, target, inputs)
