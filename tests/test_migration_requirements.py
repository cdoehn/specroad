"""Authored language/force/text mappings, independent source and target oracles."""
import copy
import json
from hashlib import sha256
import pytest

from specroad.changes import ChangePlan
from specroad.model.domain_schemas import validate_domain_fields
from specroad.model.errors import ModelError
from specroad.migration.planning import plan_migration
from specroad.migration.plan_values import MigrationPlanError
from support.migration_plans import FIELDS, planned_files, vector_source
from support.migration_requirements import REQUIREMENT_PATH, decision, supplied
from support.reference01 import CONTRACT, digest, put


def test_authored_language_default_matches_the_independent_literal_target():
    files = vector_source(); row = decision(files); del row['language']
    original = copy.deepcopy(row); before = dict(files)
    inputs = supplied(files, [row], default_language='en')
    result = plan_migration(files, inputs=inputs, **FIELDS)
    assert result.ready
    target = json.loads(planned_files(files, result.change_plan)[REQUIREMENT_PATH])
    assert target == json.loads((CONTRACT/'vectors/requirement-after.json').read_bytes())
    assert digest(target) == '520e42f0647bae17a37b8bf8c1c9717fa274a890f0164e97f7ecebeb817ffcb3'
    assert row == original and files == before
    assert inputs['requirement_mappings'] == [{**row, 'language': 'en'}]
    assert set(inputs) == {'format_version', 'target_configuration', 'target_resources',
                           'requirement_mappings', 'proposal_mappings'}


@pytest.mark.parametrize('force', ['must', 'must_not', 'should', 'may'])
def test_explicit_force_and_complete_target_text_are_used_without_interpretation(force):
    files = vector_source(); old = json.loads(files[REQUIREMENT_PATH])
    old.update(statement='The system shall MUSS retain this source wording.', priority='mandatory')
    if force == 'should':
        old.update(deviation_conditions='Only after a documented exception review.',
                   deviation_authority='synthetic-deviation-reviewer')
    put(files, old)
    text = '  MUSS / shall: e\u0301; keep authored text exactly.  '
    row = decision(files, language='de-DE', force=force, statement=text)
    result = plan_migration(files, inputs=supplied(files, [row]), **FIELDS)
    target = json.loads(planned_files(files, result.change_plan)[REQUIREMENT_PATH])
    validate_domain_fields(target, expected_type='requirement')
    assert target['id'] == old['id'] and target['id_scheme'] == 'legacy-sequential-v1'
    assert (target['language'], target['normative_force'], target['statement']) == ('de-DE', force, text)
    assert target['priority'] == 'mandatory' and target['extensions'] == old['extensions']
    assert target['created_at'] == old['created_at'] and target['created_by'] == old['created_by']
    assert target['revision'] == old['revision'] + 1 and target['updated_at'] == FIELDS['planned_at']
    if force == 'should':
        assert target['deviation_conditions'] == 'Only after a documented exception review.'
        assert target['deviation_authority'] == 'synthetic-deviation-reviewer'


@pytest.mark.parametrize('missing', ['deviation_conditions', 'deviation_authority', 'both'])
def test_should_mapping_rejects_missing_deviation_details_without_source_mutation(missing):
    files = vector_source(); old = json.loads(files[REQUIREMENT_PATH])
    old.update(deviation_conditions='Only after a documented exception review.',
               deviation_authority='synthetic-deviation-reviewer')
    for field in ('deviation_conditions', 'deviation_authority'):
        if missing == field or missing == 'both': del old[field]
    put(files, old); before = dict(files)
    inputs = supplied(files, [decision(files, force='should')])
    with pytest.raises(MigrationPlanError) as caught:
        plan_migration(files, inputs=inputs, **FIELDS)
    assert caught.value.reason == 'schema_any_of' and caught.value.pointer == '/target'
    assert caught.value.exit_code == 3 and files == before


def test_each_requirement_override_survives_a_shared_explicit_language_default():
    files = vector_source(); second = json.loads(files[REQUIREMENT_PATH])
    second['id'] = 'SR-REQ-0002'; second['title'] = 'Second independent requirement'; put(files, second)
    first = decision(files, force='may'); del first['language']
    other = decision(files, identity=second['id'], language='ja', force='must_not', statement='原文を保持する。')
    rows = [other, first]; before = copy.deepcopy(rows)
    inputs = supplied(files, rows, default_language='de-DE')
    result = plan_migration(files, inputs=inputs, **FIELDS)
    assert result.ready
    target = planned_files(files, result.change_plan)
    assert json.loads(target[REQUIREMENT_PATH])['language'] == 'de-DE'
    actual = json.loads(target['spec/requirements/SR-REQ-0002.json'])
    assert (actual['language'], actual['normative_force'], actual['statement']) == ('ja', 'must_not', '原文を保持する。')
    assert rows == before
    assert [r['artifact_id'] for r in inputs['requirement_mappings']] == ['SR-REQ-0001', 'SR-REQ-0002']


def test_default_expansion_and_explicit_rows_produce_the_same_bound_plan():
    files = vector_source(); row = decision(files); no_language = dict(row); del no_language['language']
    defaulted = supplied(files, [no_language], default_language='en')
    explicit = supplied(files, [row])
    assert defaulted == explicit
    a = plan_migration(files, inputs=defaulted, **FIELDS)
    b = plan_migration(files, inputs=explicit, **FIELDS)
    assert a.canonical_bytes == b.canonical_bytes
    assert ChangePlan(a.change_plan.canonical_bytes).canonical_bytes == a.change_plan.canonical_bytes


def test_decisions_are_detached_from_mutable_caller_rows_and_resources():
    files = vector_source(); row = decision(files); del row['language']
    rows = [row]; inputs = supplied(files, rows, default_language='en')
    result = plan_migration(files, inputs=inputs, **FIELDS)
    plan_bytes = result.change_plan.canonical_bytes
    row['statement'] = 'Changed after preparation'; rows.clear()
    assert inputs['requirement_mappings'][0]['statement'] == 'Preserve original bytes.'
    inputs['requirement_mappings'][0]['normative_force'] = 'may'
    assert result.change_plan.canonical_bytes == plan_bytes
    assert result.change_plan.data['operations'][0]['inputs']['requirement_mappings'][0]['normative_force'] == 'must'


def test_missing_requirement_mapping_blocks_the_whole_plan_even_with_a_default():
    files = vector_source(); before = dict(files)
    result = plan_migration(files, inputs=supplied(files, [], default_language='en'), **FIELDS)
    assert result.data['blockers'] == [{'reason': 'requirement_mapping_required', 'path': REQUIREMENT_PATH}]
    assert not result.ready and result.change_plan is None
    assert result.data['expected_target_model_root_sha256'] is None and files == before


@pytest.mark.parametrize('field', ['language', 'normative_force', 'statement', 'source_sha256', 'artifact_id'])
def test_no_implicit_value_completes_an_incomplete_requirement_decision(field):
    files = vector_source(); row = decision(files); del row[field]
    with pytest.raises(ModelError): supplied(files, [row])


@pytest.mark.parametrize('field', ['normative_force', 'statement', 'source_sha256', 'artifact_id'])
def test_language_default_never_supplies_another_required_decision(field):
    files = vector_source(); row = decision(files); del row['language']; del row[field]
    with pytest.raises(ModelError): supplied(files, [row], default_language='en')


def test_authored_mapping_is_bound_to_the_old_full_hash_not_just_identity():
    files = vector_source(); row = decision(files); del row['language']
    old = json.loads(files[REQUIREMENT_PATH]); old['title'] = 'A new source revision'; put(files, old)
    with pytest.raises(MigrationPlanError) as caught:
        plan_migration(files, inputs=supplied(files, [row], default_language='en'), **FIELDS)
    assert caught.value.reason == 'migration_mapping_source_changed' and caught.value.exit_code == 6


def test_requirement_schema_fields_and_authored_decisions_have_distinct_plan_bindings():
    files = vector_source(); row = decision(files, language='fr', force='may', statement='Conserver les octets.')
    result = plan_migration(files, inputs=supplied(files, [row]), **FIELDS)
    op = result.change_plan.data['operations'][0]
    assert op['inputs']['requirement_mappings'] == [row]
    assert op['inputs_sha256'] == digest(op['inputs'])
    fields = next(r['fields'] for r in op['new_required_fields'] if r['path'] == REQUIREMENT_PATH)
    assert fields == ['id_scheme', 'language', 'normative_force', 'relations/*/id_scheme', 'relations/*/relation_id']
    assert result.data['approval_granted'] is False and result.write_authorized is False
    assert result.data['backup_verified'] is False and result.data['public_apply_supported'] is True
    original = files[REQUIREMENT_PATH]; h = sha256(original).hexdigest()
    assert planned_files(files, result.change_plan)['archive/objects/' + h[:2] + '/' + h] == original
