"""21.e1.R: exact replay, real denial, original identities and passive readers."""
from copy import deepcopy
from base64 import b64decode
import json
import pytest
from specroad.authoring.native_generic import author_generic
from specroad.authoring.force_native import author_force
from specroad.changes import ChangePlan, PublicationAuthority, prepare_change_plan
from specroad.changes.force_write import apply_force_plan
from specroad.changes.force_saved import apply_saved
from specroad.cli.application import execute_request
from specroad.cli.invocation_context import InvocationContextBuilder
from specroad.cli.result_schemas import validate_result_document
from specroad.model.errors import ModelError
from specroad.model.canonical import canonical_json_bytes as jcs
from support.force_cases import fixture, files, replacement, ACTOR, ALLOW
from test_force_domains import AI, product


def update(root, path):
    value = json.loads((root/path).read_bytes())
    return dict(command_id='artifact.update', target=value['id'], expected_revision=999,
        patch=[dict(op='replace', path='/title', value='Explicit forced target')])


@pytest.mark.parametrize('mutation', ['actor', 'reason', 'intent', 'expected_root', 'proposal', 'execution'])
def test_native_replay_rejects_every_changed_request_binding(tmp_path, mutation):
    root, path = fixture(tmp_path/'project'); intent = update(root, path)
    options = dict(actor=AI, request_id='bound-native-request', force=True,
        force_reason='Original explicit reason', authority=ALLOW)
    result = author_force(root, intent, **options)
    before = files(root)
    if mutation == 'actor': options['actor'] = ACTOR
    elif mutation == 'reason': options['force_reason'] = 'Different explicit reason'
    elif mutation == 'intent': intent['patch'][0]['value'] = 'A different target'
    elif mutation == 'expected_root': options['expected_model_root'] = '0'*64
    elif mutation == 'proposal': options['as_proposal'] = True
    else:
        options['execution_binding'] = dict(planned_at='2026-11-24T12:00:00Z',
            change_plan_id='new-plan', transaction_id='new-transaction')
    with pytest.raises(ModelError) as caught:
        author_force(root, intent, **options)
    assert caught.value.exit_code == 6 and files(root) == before
    assert result['approval_granted'] is False


def test_native_explicit_execution_binding_is_used_and_checked_before_replay(tmp_path):
    root, path = fixture(tmp_path/'project'); intent = update(root, path)
    execution = dict(planned_at='2026-11-24T12:00:00Z', change_plan_id='explicit-plan',
        transaction_id='explicit-native-transaction')
    options = dict(actor=ACTOR, request_id='explicit-execution', force=True,
        authority=ALLOW, execution_binding=execution)
    result = author_force(root, intent, **options)
    plan = result['audit']['plan']
    assert plan['planned_at'] == execution['planned_at']
    assert plan['change_plan_id'] == execution['change_plan_id']
    assert result['completion']['transaction_id'] == execution['transaction_id']
    before = files(root)
    assert author_force(root, intent, **options)['replayed']
    assert files(root) == before
    invalid = deepcopy(plan); invalid.pop('change_plan_sha256')
    invalid['native_intent']['execution_binding']['change_plan_id'] = 'unbound-plan'
    with pytest.raises(ModelError): prepare_change_plan(invalid)


@pytest.mark.parametrize('fault', ['host', 'io'])
def test_proposal_failed_publication_keeps_real_negative_findings(tmp_path, monkeypatch, fault):
    from support.proposal_apply import ApplyCase
    from specroad.proposals.force import author
    case = ApplyCase(tmp_path/'project'); before = product(case.root)
    authority = ALLOW
    if fault == 'host':
        authority = PublicationAuthority('denied-force-proposal', '1', lambda request: False)
    else:
        from specroad.changes import guarded_write
        def interrupt(event):
            if event == 'marker_synced': raise OSError('synthetic publication interruption')
        monkeypatch.setattr(guarded_write, '_checkpoint', interrupt)
    with pytest.raises(ModelError) as caught:
        author(case.root, case.original.data['id'], command='proposal.review.start',
            expected_revision=999, actor=AI, request_id='failed-proposal', authority=authority)
    attempt = caught.value.authoring_attempt
    assert caught.value.exit_code == (7 if fault == 'host' else 5)
    assert attempt['outcome'] == 'failed' and attempt['force']['used']
    assert attempt['write_state'] == ('not_committed' if fault == 'host' else 'unknown')
    assert attempt['current_target_verified'] is False and attempt['approval_granted'] is False
    assert product(case.root) == before
    assert not list((case.root/'.specroad/receipts').rglob('committed.json'))


def test_native_cli_failure_exposes_actual_force_ledger(tmp_path):
    root, path = fixture(tmp_path/'project'); intent = update(root, path); before = product(root)
    request = dict(command_id='artifact.update', arguments={'target': intent['target']}, force=True,
        options={'--expected-revision':'999', '--set':['/title="Explicit forced target"'],
            '--actor-type':'ai', '--actor-id':AI['actor_id'], '--project':str(root)})
    result = execute_request(request, cwd=root, context_builder=InvocationContextBuilder(
        publication_authority=PublicationAuthority('host-denial', '1', lambda request: False))).result
    assert result.exit_code == 7 and result.force['used'] and result.status.value == 'failed'
    assert result.details['authoring_attempt']['write_state'] == 'not_committed'
    assert product(root) == before


def test_saved_negative_checks_continue_independently_and_failure_retains_them(tmp_path):
    from support.merge_publication import setup
    root, plan, options, _ = setup(tmp_path); before = product(root); observed=[]
    def check_one():
        observed.append('first')
        raise ModelError('merge_conflict')
    def check_two():
        observed.append('second')
        raise ModelError('approval_required')
    with pytest.raises(ModelError) as caught:
        apply_saved(root, plan, command='merge.apply', expected_plan_sha256='0'*64,
            force=True, observe=(check_one, check_two),
            authority=PublicationAuthority('denied-saved', '1', lambda request: False))
    assert observed == ['first', 'second'] and product(root) == before
    attempt = caught.value.authoring_attempt
    assert attempt['write_state'] == 'not_committed'
    gates = {r['gate_id'] for r in attempt['force']['overrides']}
    assert {'hash:saved_plan', 'merge_conflict:merge_conflict', 'approval:approval_required'} <= gates


def test_removed_force_creation_stays_in_historical_identity_reservations(tmp_path):
    from test_authoring_inputs import fields
    from specroad.authoring.project_sources import AuthoringSources
    root, _ = fixture(tmp_path/'project')
    creation = author_generic(root, dict(command_id='artifact.create', artifact_type='goal', fields=fields('goal')),
        actor=AI, request_id='create-historical', force=True, authority=ALLOW)
    targets = [(op['path'], json.loads(b64decode(op['target']['bytes_base64'])))
        for op in creation['audit']['plan']['operations'] if op['observed_byte_sha256']=='absent']
    assert len(targets)==1
    path, value = targets[0]
    removal = replacement(root, path, None, request_id='delete-historical')
    apply_force_plan(root, removal, actor=ACTOR, request_id='delete-historical', force=True, authority=ALLOW)
    source = AuthoringSources(root)
    assert value['id'] in source.model.reservations['reserved_artifact_ids']
    assert not (root/path).exists()


def test_force_review_origin_does_not_become_current_but_new_independent_review_can(tmp_path):
    from test_relation_review_status import endpoints, review, TIME
    from specroad.graph.relations import SourceRelations
    from specroad.graph.review_status import RelationReviewStatuses
    from specroad.model.paths import artifact_path
    from specroad.changes.force_history import provenance
    from specroad.qualification.receipts import receipt_history
    source, target = endpoints(); original = review(source,target)
    root, _ = fixture(tmp_path/'project')
    path = artifact_path('relation_review', original['id'], 'SR')
    plan = replacement(root,path,jcs(original),expected='0'*64)
    completed=apply_force_plan(root,plan,actor=ACTOR,request_id=plan.data['request_id'],force=True,authority=ALLOW)
    _,journals=receipt_history(files(root),plan.data['project_id'])
    origins=provenance(journals,product(root))
    assert any(row['path']==path for row in origins)
    def statuses(*reviews):
        values=(source,target,*reviews)
        records=tuple(SourceRelations(jcs(v),path=artifact_path(v['artifact_type'],v['id'],'SR')) for v in values)
        return RelationReviewStatuses(records,force_provenance=origins).for_relation(
            source['id'],source['relations'][0]['relation_id'])
    assert statuses(original).status=='suspect'
    independent=review(source,target,number=21,time='2026-10-11T00:00:00Z')
    assert statuses(original,independent).status=='current'
    assert statuses(original,independent).selected_review_id==independent['id']
    assert completed['approval_granted'] is False


def test_native_force_result_and_plan_are_advertised_by_real_schemas(tmp_path):
    from specroad.model.schema_catalog import SchemaCatalog
    root,path=fixture(tmp_path/'project')
    value=author_generic(root,update(root,path),actor=AI,force=True,dry_run=True)
    SchemaCatalog().validate('urn:specroad:schema:1.4.0:change-plan',value['audit']['plan'])
    validate_result_document('native-authoring-command-v1',dict(format_version='native-authoring-command-v1',
        command_id='artifact.update',outcome=value))
    for schema in ('proposal-review-start-v1','proposal-review-v1','proposal-apply-v1',
                   'merge-apply-command-v1','migration-command-v1'):
        validate_result_document(schema,value)
    invalid=deepcopy(value['audit']['plan']);invalid['native_intent']['arbitrary_authority']=True
    with pytest.raises(ModelError): ChangePlan(jcs(invalid))
