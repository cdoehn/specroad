"""No inferred decisions, no inherited approval, no rewritten historical bytes."""
import copy
import json
from hashlib import sha256
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch
import pytest

from specroad.model.errors import ModelError
from specroad.migration.planning import plan_migration, migration_inputs
from specroad.migration.plan_recheck import recheck_migration_plan
from specroad.migration.plan_values import MigrationPlanError
from support.model import configuration_value
from support.migration_plans import FIELDS, planned_files, vector_source, target_inputs
from support.migration_requirements import REQUIREMENT_PATH, decision, supplied
from support.reference01 import (artifact, relation, digest, encoded, put,
                                 full_project, finish_proposal, seal)


@pytest.mark.parametrize('language', ['', False, 0, [], {}, 'en_US', 'de--DE', 'en-u', 'en-u-ca-u-nu', 'de\n'])
def test_invalid_explicit_default_is_rejected_even_when_every_row_has_a_language(language):
    files = vector_source()
    with pytest.raises(ModelError): supplied(files, [decision(files)], default_language=language)


@pytest.mark.parametrize('language', [None, False, '', 'en_US', 'en-u', 'de--DE'])
def test_shared_default_never_repairs_an_explicit_invalid_row_value(language):
    files = vector_source()
    with pytest.raises(ModelError):
        supplied(files, [decision(files, language=language)], default_language='en')


@pytest.mark.parametrize('language', ['en_US', 'en-u', 'de--DE', 'en-u-ca-u-nu'])
def test_direct_normalized_inputs_reject_invalid_language_before_missing_target_blockers(language):
    files = vector_source(); inputs = target_inputs(files)
    inputs['requirement_mappings'][0]['language'] = language
    inputs['target_configuration'] = None; inputs['target_resources'] = []
    before = copy.deepcopy(inputs)
    with pytest.raises(MigrationPlanError) as caught: plan_migration(files, inputs=inputs, **FIELDS)
    assert caught.value.exit_code == 3 and inputs == before


@pytest.mark.parametrize('kind', ['duplicate', 'unknown', 'non_requirement', 'approval_flag', 'detector_value'])
def test_default_does_not_bypass_closed_mapping_identity_or_authority(kind):
    files = vector_source(); row = decision(files); del row['language']; rows = [row]
    if kind == 'duplicate': rows.append(dict(row))
    elif kind == 'unknown': row['artifact_id'] = 'SR-REQ-9999'
    elif kind == 'non_requirement': row['artifact_id'] = 'SR-GOAL-0001'
    elif kind == 'approval_flag': row['approved'] = True
    else: row['detected_language'] = 'en'
    with pytest.raises(ModelError):
        plan_migration(files, inputs=supplied(files, rows, default_language='en'), **FIELDS)


@pytest.mark.parametrize('field', ['language', 'normative_force', 'statement'])
def test_saved_plan_recheck_binds_every_authored_decision_independently(field):
    files = vector_source(); original = decision(files)
    plan = plan_migration(files, inputs=supplied(files, [original]), **FIELDS).change_plan
    changed = dict(original)
    changed[field] = {'language': 'fr', 'normative_force': 'may', 'statement': 'A different authorized target.'}[field]
    replacement = plan_migration(files, inputs=supplied(files, [changed]), **FIELDS).change_plan
    assert replacement.sha256 != plan.sha256
    assert replacement.data['expected_result'] != plan.data['expected_result']
    with pytest.raises(MigrationPlanError) as caught:
        recheck_migration_plan(replacement.canonical_bytes, files, expected_target_version='0.2.0',
            expected_plan_sha256=replacement.sha256,
            expected_inputs_sha256=plan.data['operations'][0]['inputs_sha256'])
    assert caught.value.reason == 'migration_mapping_request_changed' and caught.value.exit_code == 6


def test_target_locale_and_configuration_default_do_not_author_requirement_language():
    files = vector_source(); row = decision(files); del row['language']
    config = configuration_value(project_id='synthetic-reference-project', default_locale='ja',
        language_policy={'default_language': 'fr'})
    with pytest.raises(ModelError): supplied(files, [row], configuration=encoded(config))
    result = plan_migration(files, inputs=supplied(files, [row], default_language='en',
                                                configuration=encoded(config)), **FIELDS)
    assert json.loads(planned_files(files, result.change_plan)[REQUIREMENT_PATH])['language'] == 'en'


def test_target_language_policy_still_rejects_an_explicit_disallowed_default():
    files = vector_source(); row = decision(files); del row['language']
    config = configuration_value(project_id='synthetic-reference-project',
        language_policy={'default_language': 'en', 'allowed_ranges': ['en'], 'disallowed_language': 'error'})
    with pytest.raises(MigrationPlanError) as caught:
        plan_migration(files, inputs=supplied(files, [row], default_language='de',
                                            configuration=encoded(config)), **FIELDS)
    assert caught.value.reason == 'migration_target_language_policy'


def test_migration_needs_new_approval_even_when_the_author_keeps_the_old_statement():
    files = vector_source(); old = json.loads(files[REQUIREMENT_PATH])
    old.update(maturity='approved', rationale='Synthetic prior author rationale.')
    # A stored synthetic approval still requires a complete source graph.
    verification = artifact('verification')
    verification.update(subjects=[old['id']], configuration_policy='independent')
    put(files, verification)
    old['relations'].append(relation('verified_by', verification['id']))
    put(files, old)
    raw = files[REQUIREMENT_PATH]; before = dict(files)
    result = plan_migration(files, inputs=supplied(files, [decision(files)]), **FIELDS)
    assert result.ready and files == before
    target = planned_files(files, result.change_plan); actual = json.loads(target[REQUIREMENT_PATH])
    assert actual['statement'] == old['statement'] and actual['maturity'] == 'draft'
    assert actual['revision'] == old['revision'] + 1
    assert any(r['type'] == 'verified_by' and r['target'] == verification['id']
               for r in actual['relations'])
    h = sha256(raw).hexdigest(); assert target['archive/objects/' + h[:2] + '/' + h] == raw
    assert result.data['approval_granted'] is False


def test_changed_requirement_decisions_never_fill_fields_into_immutable_evidence_or_reviews():
    files = finish_proposal(full_project(), 'rejected'); seal(files, 3)
    before = dict(files); inputs = target_inputs(files)
    inputs['requirement_mappings'] = [decision(files, language='ja', force='may', statement='元のバイト列を保持する。')]
    result = plan_migration(files, inputs=inputs, **FIELDS)
    assert result.ready and files == before
    target = planned_files(files, result.change_plan)
    for name, raw in files.items():
        if name.startswith(('spec/evidence/', 'spec/baselines/', 'spec/relation-reviews/', 'spec/proposals/', 'archive/')):
            assert target[name] == raw
    for prefix in ('spec/evidence/', 'spec/baselines/', 'spec/relation-reviews/'):
        names = [name for name in files if name.startswith(prefix)]
        assert names
        for name in names:
            record = json.loads(target[name])
            assert record['schema_version'] == '0.1.0'
            assert 'language' not in record and 'normative_force' not in record
    old_raw = files[REQUIREMENT_PATH]; h = sha256(old_raw).hexdigest()
    assert target['archive/objects/' + h[:2] + '/' + h] == old_raw
    original = json.loads(old_raw); current = json.loads(target[REQUIREMENT_PATH])
    assert current['id'] == original['id'] and current['revision'] == original['revision'] + 1
    assert (current['language'], current['normative_force'], current['statement']) == ('ja', 'may', '元のバイト列を保持する。')
    evidence = json.loads(target['spec/evidence/SR-EVD-0001.json'])
    assert evidence['subjects'][0]['artifact_sha256'] == digest(original)
    assert evidence['subjects'][0]['artifact_sha256'] != digest(current)


def test_incomplete_mapping_reports_all_missing_subjects_without_a_partial_target():
    files = vector_source(); other = json.loads(files[REQUIREMENT_PATH]); other['id'] = 'SR-REQ-0002'; put(files, other)
    result = plan_migration(files, inputs=migration_inputs(), **FIELDS)
    missing = result.data['blockers']
    assert {'reason': 'target_configuration_required', 'path': 'specroad.json'} in missing
    assert {r['path'] for r in missing if r['reason'] == 'requirement_mapping_required'} == {
        REQUIREMENT_PATH, 'spec/requirements/SR-REQ-0002.json'}
    assert result.change_plan is None and result.data['expected_target_model_root_sha256'] is None


def test_mapping_and_planning_do_not_detect_translate_write_or_start_a_process():
    files = vector_source(); before = dict(files)
    row = decision(files, language='ja', force='may', statement='MUSS shall text remains exactly supplied.')
    with patch.object(Path, 'write_bytes', side_effect=AssertionError('write')), \
         patch.object(Path, 'write_text', side_effect=AssertionError('write')), \
         patch.object(subprocess, 'Popen', side_effect=AssertionError('process')), \
         patch.object(socket, 'socket', side_effect=AssertionError('network')):
        inputs = supplied(files, [row], default_language='de')
        result = plan_migration(files, inputs=inputs, **FIELDS)
    assert result.ready and files == before
    value = json.loads(planned_files(files, result.change_plan)[REQUIREMENT_PATH])
    assert (value['language'], value['normative_force'], value['statement']) == ('ja', 'may', row['statement'])
    assert result.write_authorized is False
