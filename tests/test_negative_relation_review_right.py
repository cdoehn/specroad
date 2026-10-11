"""Review outcomes, unchanged approvals and real interrupted native writes.

All projects and historical reviews are owned synthetic fixtures. These tests
do not certify host authentication, general approval services or a CLI command.
"""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from specroad.authoring import negative_reviews as service
from specroad.authoring.review_status import relation_review_diagnostics, relation_review_status
from specroad.changes import (AuthoringError, ChangePlanError, CommittingJournal, CommittedJournal,
    LockRecord, RecoveryAuthority, TargetError, TargetModel, inspect_project_lock,
    transaction_recovery_lock, rollback_interrupted_transaction, complete_published_transaction,
    cleanup_recovered_transaction, prepare_change_target)
from specroad.changes.idempotency_values import RequestIdConflict
from specroad.changes.reviews import review_context
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.profiles import ProfileResource, compose_profiles
from specroad.storage.language_registry import bundled_language_registry
from specroad.validation import ModelDocument
from support.domain import domain_value, approved_value
from support.model import put
from support.profile_composition import relation as profile_relation
from support.profiles import profile_data
from support.read_only import inventory as file_inventory, no_write_attempts
from support.relations import aid, edge
from test_negative_relation_review import (ACTOR, TIME, OLD_TIME, REASON, negative_project, options, call, operation)
from test_relation_authoring import stored_project, receipt
from test_relation_review_status import review


def rebuild(root, model, values):
    documents = [ModelDocument(artifact_path(a['artifact_type'], a['id'], 'SR'),
                               canonical_json_bytes(a)) for a in values]
    result = TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files, **model.reservations)
    for document in documents: put(root, document.path, document.content)
    return result


def current(root, model):
    documents = [ModelDocument(p.relative_to(root).as_posix(), p.read_bytes())
                 for p in sorted((root / 'spec').glob('*/*.json'))]
    return TargetModel(model.configuration_bytes, model.binding, documents,
        profile=model.profile, resource_files=model.resource_files, **model.reservations)


def coupled(model, source, gates=(), *, decision, request='next', relation=None):
    arguments = {**options(model, gates), 'request_id': request,
                 'transaction_id': 'txn-' + request, 'change_plan_id': 'CP-' + request}
    return service.record_coupled_relation_review(model, source['id'],
        relation or source['relations'][0]['relation_id'], decision=decision,
        reason='A new explicit human judgment.', expected_revision=source['revision'], **arguments)


def optional_project(root):
    model, source, history, gates = negative_project(root)
    target = domain_value('requirement', id=aid(number=2))
    source = {**source, 'relations': [*source['relations'], edge('depends_on', target['id'], number=12)]}
    model = rebuild(root, model, [source if a['id'] == source['id'] else a for a in model.artifacts] + [target])
    return model, source, history, gates


@pytest.mark.parametrize('strict', [False, True])
def test_successful_negative_write_still_fails_separate_read_only_review_assessment(tmp_path, strict):
    root = tmp_path / 'project'; model, source, _, gates = negative_project(root)
    before_context = review_context(model.artifacts, source['id'], source['relations'][0]['relation_id'])
    result = call(model, source, options(model, gates)); live = current(root, model)
    before = file_inventory(root)
    with no_write_attempts(): assessment = relation_review_diagnostics(live, strict=strict)
    assert receipt(root, result)['result_object']['exit_code'] == 0
    assert receipt(root, result)['result_object']['status'] == 'success'
    assert result['write_state'] == 'committed' and result['assessment_status'] == 'failed'
    assert assessment['exit_code'] == 1 and assessment['status'] == 'failed'
    assert any(d['code'] == 'SRV027' and d['severity'] == 'error'
               and d['category'] == 'review_outcome' for d in assessment['diagnostics'])
    after_context = review_context(live.artifacts, source['id'], source['relations'][0]['relation_id'])
    assert after_context.relation_sha256 == before_context.relation_sha256
    assert after_context.source.context_sha256 == before_context.source.context_sha256
    assert after_context.target.context_sha256 == before_context.target.context_sha256
    status = relation_review_status(live, source['id'], source['relations'][0]['relation_id'])
    assert status['status'] == 'invalid' and status['selected_review_id'] == result['review_id']
    assert file_inventory(root) == before


@pytest.mark.parametrize('decision', ['confirmed', 'rejected'])
def test_new_judgment_after_withdrawal_never_revises_or_reapproves_requirement(tmp_path, decision):
    root = tmp_path / 'project'; model, source, _, gates = negative_project(root)
    first = call(model, source, options(model, gates)); live = current(root, model)
    proposed = next(a for a in live.artifacts if a['id'] == source['id'])
    assert proposed['maturity'] == 'proposed' and proposed['revision'] == 5
    path = artifact_path('requirement', source['id'], 'SR'); before = (root / path).read_bytes()
    old_review = (root / first['path']).read_bytes()
    second = coupled(live, proposed, gates, decision=decision)
    assert second['review_id'] != first['review_id'] and second['approval_withdrawals'] == []
    assert not second['approval_granted'] and (root / path).read_bytes() == before
    assert (root / first['path']).read_bytes() == old_review
    record = json.loads((root / second['path']).read_bytes())
    assert json.loads(old_review)['created_at'] == '2026-10-11T02:30:00Z'
    assert record['created_at'] == '2026-10-11T02:30:00.000001Z'
    assert record['revision'] == 1 and record['maturity'] == 'approved' and record['review_state'] == 'recorded'
    expected = 'current' if decision == 'confirmed' else 'invalid'
    status = relation_review_status(current(root, model), source['id'], source['relations'][0]['relation_id'])
    assert status['status'] == second['relation_status'] == expected
    assert status['selected_review_id'] == second['review_id']
    proof = receipt(root, second)
    assert proof['created_ids'] == [second['review_id']]
    assert proof['result_object']['published_paths'] == [second['path']]
    before_retry = file_inventory(root)
    with no_write_attempts(), patch.object(service, 'project_lock', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError):
        repeated = coupled(live, proposed, gates, decision=decision)
    assert repeated['replayed'] and repeated['completion']['receipts'] == second['completion']['receipts']
    assert repeated['assessment_status'] == second['assessment_status']
    assert file_inventory(root) == before_retry


@pytest.mark.parametrize('strict', [False, True])
def test_optional_negative_relation_preserves_valid_approved_requirement_bytes(tmp_path, strict):
    root = tmp_path / 'project'; model, source, _, gates = optional_project(root)
    before = file_inventory(root)
    result = service.record_coupled_relation_review(model, source['id'], source['relations'][2]['relation_id'],
        decision='rejected', reason='Optional relation is inaccurate.', expected_revision=4,
        strict=strict, **options(model, gates))
    assert result['approval_withdrawals'] == [] and result['assessment_status'] == 'failed'
    assert receipt(root, result)['result_object']['published_paths'] == [result['path']]
    after = {row[0]: row[1:] for row in file_inventory(root)}
    for name, *original in before: assert after[name] == tuple(original)
    retained = next(a for a in current(root, model).artifacts if a['id'] == source['id'])
    assert retained['maturity'] == 'approved' and retained['revision'] == 4


@pytest.mark.parametrize('maturity', ['draft', 'proposed', 'in_review', 'rejected', 'superseded', 'retired'])
def test_negative_review_never_changes_nonapproved_source_maturity_or_revision(tmp_path, maturity):
    root = tmp_path / 'project'; gates = ()
    if maturity == 'in_review':
        # In-review Requirements already require complete formal approval
        # fields and verification links; an incomplete draft is not this fixture.
        model, source, _, gates = negative_project(root)
        source = {**source, 'maturity': maturity}
        model = rebuild(root, model, [source if a['id'] == source['id'] else a for a in model.artifacts])
    else:
        model, source, _ = stored_project(root, with_edges=True, maturity=maturity)
    path = artifact_path('requirement', source['id'], 'SR'); original = (root / path).read_bytes()
    result = call(model, source, options(model, gates))
    assert result['approval_withdrawals'] == [] and (root / path).read_bytes() == original
    assert receipt(root, result)['result_object']['published_paths'] == [result['path']]


def test_negative_outcome_never_waives_incomplete_in_review_formal_fields(tmp_path):
    root = tmp_path / 'project'; model, source, _ = stored_project(root, with_edges=True, maturity='in_review')
    before = file_inventory(root)
    with pytest.raises(TargetError) as error:
        call(model, source, options(model))
    assert error.value.reason == 'complete_target_validation_required'
    assert file_inventory(root) == before


def test_optional_review_cannot_preserve_a_broken_mandatory_approval(tmp_path):
    root = tmp_path / 'project'; model, source, history, gates = optional_project(root)
    broken = {**history[0], 'decision': 'rejected'}
    model = rebuild(root, model, [broken if a['id'] == broken['id'] else a for a in model.artifacts])
    before = file_inventory(root)
    with pytest.raises(TargetError):
        coupled(model, source, gates, decision='rejected', relation=source['relations'][2]['relation_id'])
    assert file_inventory(root) == before


def test_composed_both_direction_rule_withdraws_both_requirements_once(tmp_path):
    root = tmp_path / 'project'; model, source, _, gates = negative_project(root)
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    test = next(a for a in model.artifacts if a['artifact_type'] == 'test')
    target = approved_value('requirement', id=aid(number=2), revision=8,
        relations=[edge('addresses', goal['id'], number=12), edge('verified_by', test['id'], number=13)])
    source = {**source, 'relations': [edge('refines', target['id'], number=10), source['relations'][1]]}
    profile = ProfileResource(canonical_json_bytes(profile_data(profile_id='core', relation_rules=[
        profile_relation('owned:refinement', maturities=['approved'], relation_types=['refines'],
                         endpoint_types=['requirement'], direction='both', severity='error')])))
    effective = compose_profiles([profile], core_key=profile.key, language_registry=bundled_language_registry())
    resources = [ModelDocument(d.path, profile.source_bytes if d.path == 'profiles/core.json' else d.content)
                 for d in model.resource_files]
    values = [goal, test, source, target]; history = []
    for owner, targets in ((source, (target, test)), (target, (goal, test))):
        for position, endpoint in enumerate(targets):
            ordered = [owner['relations'][position], owner['relations'][1 - position]]
            recorded = review({**owner, 'relations': ordered}, endpoint, number=20 + len(history), time=OLD_TIME)
            recorded['source_artifact_sha256'] = canonical_json_sha256(owner)
            history.append(recorded)
    model = TargetModel(model.configuration_bytes, model.binding,
        [ModelDocument(artifact_path(a['artifact_type'], a['id'], 'SR'), canonical_json_bytes(a))
         for a in values + history], profile=effective, resource_files=resources)
    for path, raw in model.source_files.items(): put(root, path, raw)
    result = call(model, source, options(model, gates))
    assert {w['artifact_id'] for w in result['approval_withdrawals']} == {source['id'], target['id']}
    for old in (source, target):
        actual = json.loads((root / artifact_path('requirement', old['id'], 'SR')).read_bytes())
        assert actual == {**old, 'maturity': 'proposed', 'revision': old['revision'] + 1,
                          'updated_at': TIME, 'updated_by': ACTOR}
    assert len(receipt(root, result)['result_object']['published_paths']) == 3


def test_confirmation_can_be_recorded_while_another_optional_review_remains_negative(tmp_path):
    root = tmp_path / 'project'; model, source, _, gates = optional_project(root)
    first = coupled(model, source, gates, decision='rejected', relation=source['relations'][2]['relation_id'])
    live = current(root, model)
    second = coupled(live, source, gates, decision='confirmed', request='confirm-origin')
    assert second['relation_status'] == 'current' and second['assessment_status'] == 'passed'
    assert second['assessment_scope'] == 'recorded_review_outcome_only'
    assert second['approval_withdrawals'] == []
    all_reviews = relation_review_diagnostics(current(root, model))
    assert all_reviews['exit_code'] == 1 and all_reviews['status'] == 'failed'
    assert (root / first['path']).is_file()


@pytest.mark.parametrize('actor_type', ['ai', 'ci', 'tool'])
def test_coupled_confirmation_still_requires_human_authority_before_io(tmp_path, actor_type):
    model, source, _, gates = negative_project(tmp_path / 'project'); before = file_inventory(tmp_path)
    args = {**options(model, gates), 'actor': {**ACTOR, 'actor_type': actor_type}}
    with no_write_attempts(), pytest.raises(AuthoringError) as error:
        service.record_coupled_relation_review(model, source['id'], source['relations'][0]['relation_id'],
            reason='Not a human review.', decision='confirmed', expected_revision=4, **args)
    assert error.value.exit_code == 7 and file_inventory(tmp_path) == before


@pytest.mark.parametrize('damage', ['missing_target', 'self_reference'])
def test_structural_invalidity_is_not_a_review_outcome_exception(tmp_path, damage):
    root = tmp_path / 'project'; model, source, goals = stored_project(root, with_edges=True)
    values = model.artifacts
    if damage == 'missing_target': values = [a for a in values if a['id'] != goals[0]['id']]
    else:
        source = {**source, 'relations': [{**source['relations'][0], 'target': source['id']}, source['relations'][1]]}
        values = [source if a['id'] == source['id'] else a for a in values]
    model = rebuild(root, model, values); before = file_inventory(root)
    with no_write_attempts(), patch.object(service, 'project_lock', side_effect=AssertionError), \
            patch('secrets.token_bytes', side_effect=AssertionError), pytest.raises(ChangePlanError) as error:
        call(model, source, options(model))
    assert error.value.exit_code == 3 and file_inventory(root) == before


def test_changed_decision_cannot_reuse_the_original_negative_receipt(tmp_path):
    model, source, _, gates = negative_project(tmp_path / 'project')
    call(model, source, options(model, gates)); before = file_inventory(tmp_path)
    with no_write_attempts(), pytest.raises(RequestIdConflict):
        service.record_coupled_relation_review(model, source['id'], source['relations'][0]['relation_id'],
            reason=REASON, decision='confirmed', expected_revision=4, **options(model, gates))
    assert file_inventory(tmp_path) == before


@pytest.mark.parametrize('extra', ['content', 'lifecycle'])
def test_saved_review_never_accepts_extra_content_or_lifecycle_operations(tmp_path, extra):
    model, source, _, gates = negative_project(tmp_path / 'project'); op = operation(model, source)
    second = ({'op': 'update', 'target': source['id'], 'expected_revision': source['revision'],
               'patch': [{'op': 'replace', 'path': '/statement', 'value': 'Other content.'}]}
              if extra == 'content' else {'op': 'transition', 'target': source['id'], 'from': 'approved',
                                          'to': 'proposed', 'metadata': {'reason': 'Separate transition'}})
    with no_write_attempts(), pytest.raises(TargetError) as error:
        prepare_change_target(model, [op.data, second], change_plan_id='CP-extra', request_id='extra',
            actor=ACTOR, planned_at=TIME, scope_descriptor=service._SCOPE,
            metadata_policy_version='change-metadata-v1', policy=service._POLICY, gates=gates)
    assert error.value.reason == 'review_requires_one_isolated_operation' and error.value.exit_code == 3


def _original_model(root, encoded):
    raw = {path: bytes.fromhex(value) for path, value in encoded.items()}
    profile = ProfileResource(raw['profiles/core.json']); registry = bundled_language_registry()
    effective = compose_profiles([profile], core_key=profile.key, language_registry=registry)
    config = json.loads(raw['specroad.json']); state = root.stat()
    return TargetModel(raw['specroad.json'],
        ProjectReadBinding(config['project_id'], str(root), (state.st_dev, state.st_ino)),
        [ModelDocument(p, b) for p, b in raw.items() if p.startswith('spec/')], profile=effective,
        resource_files=[ModelDocument(p, b) for p, b in raw.items() if p != 'specroad.json' and not p.startswith('spec/')])


@pytest.mark.parametrize('cut', ['first_target', 'last_target', 'receipt'])
def test_real_process_loss_recovers_entire_review_withdrawal_and_same_receipt(tmp_path, cut):
    root = tmp_path / 'project'; repo = Path(__file__).resolve().parents[1]
    code = r'''
import sys, os, json
from pathlib import Path
from unittest.mock import patch
sys.path[:0] = [str(Path(sys.argv[1])/'src'), str(Path(sys.argv[1])/'tests')]
from test_negative_relation_review import negative_project, options, call
from specroad.authoring import negative_reviews as service
root=Path(sys.argv[2]); cut=sys.argv[3]
model, source, _, gates=negative_project(root)
print(json.dumps({'files':{p:b.hex() for p,b in model.source_files.items()},
    'source':source, 'modes':{p:(root/p).stat().st_mode & 0o777 for p in model.source_files}}),flush=True)
native=os.replace; published=[]
def replace(src,dst,**kwargs):
    result=native(src,dst,**kwargs)
    if isinstance(dst,str) and dst.startswith(('SR-REQ-', 'SR-RREV-')):
        published.append(dst)
        if (cut=='first_target' and len(published)==1) or (cut=='last_target' and len(published)==2):
            os._exit(23)
    return result
def lost_output(*args,**kwargs): os._exit(23)
with patch('os.replace',side_effect=replace):
    if cut=='receipt':
        with patch.object(service,'cleanup_completed_transaction',side_effect=lost_output):
            call(model,source,options(model,gates))
    else: call(model,source,options(model,gates))
raise AssertionError('Native cut point was not reached')
'''
    child = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(repo), str(root), cut],
                           capture_output=True, text=True, check=False, timeout=90)
    assert child.returncode == 23, child.stderr
    fixture = json.loads(child.stdout); model = _original_model(root, fixture['files'])
    source = fixture['source']; transaction = 'txn-negative'
    assert inspect_project_lock(root).data['owner_state'] == 'dead'
    lock = LockRecord((root / '.specroad/locks/project.json').read_bytes())
    journal_path = root / '.specroad/transactions' / transaction / 'journal.json'
    raw = journal_path.read_bytes()
    journal = (CommittedJournal if cut == 'receipt' else CommittingJournal)(raw)
    authority = RecoveryAuthority('owned-coupled-recovery', '1', lambda request: True)
    with transaction_recovery_lock(root, transaction, project_id=model.configuration.project_id,
            request_id='negative-1', expected_lock_sha256=lock.sha256, expected_journal_sha256=journal.sha256,
            authority=authority, actor=ACTOR, reason='Recover the stopped owned reviewer.', force=True) as held:
        if cut == 'first_target':
            rollback_interrupted_transaction(transaction, held_lock=held, authority=authority,
                                            expected_journal_sha256=journal.sha256)
        elif cut == 'last_target':
            complete_published_transaction(transaction, held_lock=held, authority=authority,
                                           expected_journal_sha256=journal.sha256)
        cleaned = cleanup_recovered_transaction(transaction, held_lock=held, authority=authority,
            expected_journal_sha256=sha256(journal_path.read_bytes()).hexdigest()).data
    assert cleaned['cleanup_completed']
    path = artifact_path('requirement', source['id'], 'SR')
    if cut == 'first_target':
        assert {p: (root / p).read_bytes() for p in model.source_files} == model.source_files
        assert len(list((root / 'spec/relation-reviews').glob('*.json'))) == 2
    else:
        actual = json.loads((root / path).read_bytes())
        assert actual['maturity'] == 'proposed' and actual['revision'] == 5
        before_retry = file_inventory(root)
        with no_write_attempts(), patch.object(service, 'project_lock', side_effect=AssertionError), \
                patch('secrets.token_bytes', side_effect=AssertionError):
            replay = call(model, source, options(model))
            again = call(model, source, options(model))
        assert replay['replayed'] and replay['completion']['receipts'] == again['completion']['receipts']
        assert replay['review_id'] == again['review_id']
        assert replay['approval_withdrawals'][0]['target_revision'] == 5
        assert len(list((root / 'spec/relation-reviews').glob('*.json'))) == 3
        assert file_inventory(root) == before_retry
    for p, mode in fixture['modes'].items(): assert (root / p).stat().st_mode & 0o777 == mode
    assert (root / 'foreign.bin').read_bytes() == b'untouched\0\xff'
