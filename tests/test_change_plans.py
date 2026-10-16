"""Value contracts and genuine round trips, not presentation or documentation."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from unittest.mock import patch
import builtins
import pytest

from specroad.changes import (ChangePlan, ChangeOperation, ChangePlanError,
                              prepare_change_plan, change_plan_schema, OPERATION_TYPES)
from specroad.model.canonical import canonical_json_bytes
from specroad.model._schema import validate_builtin
from support.change_plans import document, operation, result
from support.domain import domain_value
from support.records import record_value


def test_create_plan_is_bound_and_roundtrips_without_changing_values():
    value = document(); original = deepcopy(value)
    plan = prepare_change_plan(value)
    assert value == original
    assert plan.sha256 == hashlib.sha256(canonical_json_bytes(original)).hexdigest()
    assert ChangePlan(plan.canonical_bytes).data == plan.data
    assert plan.data['planned_at'] == original['planned_at']
    assert plan.data['result_artifacts'][0]['artifact'] == original['result_artifacts'][0]['artifact']


def test_update_plan_preserves_patch_order_and_expected_values():
    op = operation('update'); op['patch'].insert(0, {'op':'test','path':'/revision','value':1})
    final = domain_value(statement='Changed.', revision=2)
    plan = prepare_change_plan(document([op], [result(final)]))
    assert plan.operations[0].data == op
    assert plan.operations[0].op == 'update'
    assert ChangePlan(plan.canonical_bytes).data == plan.data


@pytest.mark.parametrize('kind', OPERATION_TYPES)
def test_each_core_operation_has_a_real_closed_typed_contract(kind):
    op = operation(kind)
    parsed = ChangeOperation(op)
    assert parsed.data == op and parsed.op == kind
    assert parsed.executable is False


def test_normalization_keeps_original_raw_bytes_separately():
    plan = prepare_change_plan(document())
    raw = json.dumps(plan.data, ensure_ascii=True, indent=3).encode()
    loaded = ChangePlan(raw)
    assert loaded.source_bytes == raw
    assert loaded.canonical_bytes == plan.canonical_bytes
    assert loaded.sha256 == plan.sha256


def test_plan_and_operations_are_independent_immutable_values():
    value = document(); plan = prepare_change_plan(value); baseline = plan.data
    value['operations'][0]['artifact']['title'] = 'Later edit'
    copy = plan.data; copy['result_artifacts'].clear()
    op = plan.operations[0]; op.data['artifact']['title'] = 'Detached edit'
    assert plan.data == baseline
    with pytest.raises(FrozenInstanceError): plan.source_bytes = b'{}'


def test_compiled_schema_accepts_the_exact_parsed_plan():
    plan = prepare_change_plan(document()); schema = change_plan_schema()
    validate_builtin(plan.data, schema)
    schema['properties'].clear()
    validate_builtin(plan.data, change_plan_schema())


def test_existing_self_hash_cannot_be_silently_replaced():
    plan = prepare_change_plan(document())
    with pytest.raises(ChangePlanError): prepare_change_plan(plan.data)


def test_plan_hash_detects_tampered_request():
    data = prepare_change_plan(document()).data; data['request_id'] = 'changed'
    with pytest.raises(ChangePlanError) as err: ChangePlan(canonical_json_bytes(data))
    assert err.value.reason == 'change_plan_hash_mismatch' and err.value.code == 'SRV146'


def test_nested_self_hash_fields_are_not_excluded_from_the_hash():
    data = document(); data['operations'][0]['artifact']['extensions'] = {'acme.test': {'change_plan_sha256':'one'}}
    data['result_artifacts'] = [result(data['operations'][0]['artifact'])]
    first = prepare_change_plan(data)
    data['operations'][0]['artifact']['extensions']['acme.test']['change_plan_sha256'] = 'two'
    data['result_artifacts'] = [result(data['operations'][0]['artifact'])]
    assert prepare_change_plan(data).sha256 != first.sha256


@pytest.mark.parametrize('name', ['actor','request_id','planned_at','base','operations','preconditions','result_artifacts','expected_result'])
def test_no_required_envelope_value_is_invented(name):
    data = document(); data.pop(name)
    with pytest.raises(ChangePlanError): prepare_change_plan(data)


@pytest.mark.parametrize('name', ['merge-metadata-v1','migration-metadata-v1','unknown',None])
def test_nonregular_metadata_policy_is_not_an_authoring_escape(name):
    data = document(); data['metadata_policy_version'] = name
    with pytest.raises(ChangePlanError) as err: prepare_change_plan(data)
    assert err.value.code == 'SRV174'


def test_unknown_operation_and_external_loader_declaration_rejected_without_io():
    for bad in [{'op':'shell','command':'rm -rf never'}, {'op':'create', **operation(), 'schema_url':'file:///private'}]:
        with patch.object(builtins, 'open', side_effect=AssertionError('Unexpected file read')):
            with pytest.raises(ChangePlanError): ChangeOperation(bad)


@pytest.mark.parametrize('kind', ['evidence','baseline','proposal','relation_review'])
def test_generic_create_cannot_fabricate_special_records(kind):
    artifact = record_value(kind)
    with pytest.raises(ChangePlanError) as err:
        ChangeOperation({'op':'create','artifact':artifact,'result_id':artifact['id']})
    assert err.value.reason == 'specialized_operation_required'


@pytest.mark.parametrize('pointer', ['', '/id', '/maturity', '/revision', '/created_at', '/relations/0/type'])
def test_generic_update_cannot_modify_controlled_fields(pointer):
    op = operation('update'); op['patch'] = [{'op':'replace','path':pointer,'value':'bad'}]
    with pytest.raises(ChangePlanError): ChangeOperation(op)


def test_move_cannot_remove_protected_source_while_writing_ordinary_target():
    op = operation('update'); op['patch'] = [{'op':'move','from':'/id','path':'/title'}]
    with pytest.raises(ChangePlanError): ChangeOperation(op)


def test_json_patch_unknown_members_remain_passive_hashed_data():
    op = operation('update'); op['patch'][0]['comment'] = {'op':'execute','file':'not-opened'}
    assert ChangeOperation(op).data == op


def test_raw_json_rejects_duplicate_keys():
    with pytest.raises(ChangePlanError) as err: ChangePlan(b'{"actor":{},"actor":{}}')
    assert err.value.reason == 'duplicate_key'


@pytest.mark.parametrize('raw', [b'\xff', b'{} false', b'[]', b'{"number":NaN}'])
def test_invalid_raw_bytes_do_not_load_a_plan(raw):
    with pytest.raises(ChangePlanError): ChangePlan(raw)


def test_shape_validation_never_grants_execution_or_write_authority():
    plan = prepare_change_plan(document())
    assert plan.validation_scope == 'change_plan_fields_only'
    assert plan.execution_ready is False and plan.write_authorized is False


def test_all_core_operation_names_are_present():
    assert set(OPERATION_TYPES) == {"create", "update", "relation_add", "relation_remove",
        "transition", "retire", "evidence_record", "attachment_add", "attachment_remove",
        "representation_normalize", "relation_review_record", "proposal_control", "baseline_create"}
