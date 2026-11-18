"""Native refusals preserve actual dialogue evidence and interrupted writes."""
from dataclasses import replace
import json

import pytest

from specroad.changes import PublicationAuthority, prepare_authoring_request
from specroad.changes.normal_access import NormalAccessError
from specroad.model.canonical import canonical_json_bytes as jcs, canonical_json_sha256
from specroad.model.errors import ModelError
from specroad.proposals import ProposalVerifier
from specroad.proposals.history import assess_proposal
from specroad.proposals._change_control import reduce_change
from specroad.proposals.values import content_sha256
from specroad.qualification.services import QualificationServices
from support.proposal_dialog import DialogCase
from support.read_only import inventory, no_write_attempts


def test_canonical_noop_retains_actual_approval_without_a_new_revision_or_receipt(tmp_path):
    case = DialogCase(tmp_path/'project')
    case.start(); case.approve()
    original = case.original
    before = inventory(case.root)
    result = case.publish(case.prepare('move'))
    assert result['no_change'] and result['completion'] is None
    assert result['proposal'] == original.data
    assert inventory(case.root) == before
    assessment = assess_proposal(original, case.inputs(case.model, original), case.model, services=case.services)
    assert assessment['current_approval']


def test_rejected_dialogue_preserves_real_decisions_and_never_changes_the_specification(tmp_path):
    case = DialogCase(tmp_path/'project')
    case.start(); case.decide(decision='rejected')
    before = inventory(case.root)
    assert case.original.data['proposal_status'] == 'rejected'
    assert case.original.data['reviews'][-1]['decision'] == 'rejected'
    with no_write_attempts(), pytest.raises(ModelError) as refused:
        case.prepare()
    assert refused.value.reason == 'proposal_terminal_revision_changed'
    with pytest.raises(ModelError) as refused:
        case.apply(dry_run=True)
    assert refused.value.reason == 'proposal_apply_requires_approved'
    assert inventory(case.root) == before
    for path, raw in case.initial_model.source_files.items():
        assert (case.root/path).read_bytes() == raw


@pytest.mark.parametrize('fault', ['basis', 'proposal_bytes'])
@pytest.mark.parametrize('dry_run', [False, True])
def test_changed_live_basis_or_exact_preimage_is_not_overwritten(tmp_path, fault, dry_run):
    case = DialogCase(tmp_path/'project')
    model = case.model; edit = case.prepare(dry_run=dry_run)
    if fault == 'proposal_bytes':
        path = case.original.path
        raw = json.dumps(case.original.data, indent=2).encode()
    else:
        goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
        path = next(d.path for d in model.documents if json.loads(d.content)['id'] == goal['id'])
        raw = jcs({**goal, 'statement': 'Independent later content'})
    (case.root/path).write_bytes(raw)  # External interference, never a positive dialogue write.
    before = inventory(case.root)
    with no_write_attempts(), pytest.raises(ModelError) as refused:
        case.publish(edit, model=model)
    assert refused.value.exit_code == 6
    assert (case.root/path).read_bytes() == raw and inventory(case.root) == before


def test_confirmed_revision_replays_from_real_receipts_after_current_basis_changes(tmp_path):
    case = DialogCase(tmp_path/'project')
    model = case.model; edit = case.prepare()
    first = case.publish(edit, model=model)
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    path = next(d.path for d in model.documents if json.loads(d.content)['id'] == goal['id'])
    (case.root/path).write_bytes(jcs({**goal, 'statement': 'Later independent specification'}))
    before = inventory(case.root); count = len(case.requests)
    with no_write_attempts():
        replay = case.publish(edit, model=model, transaction_id='dialog-retry')
    assert replay['replayed'] and not replay['current_target_verified']
    assert not replay['completion']['current_target_verified']
    assert replay['completion']['receipts'] == first['completion']['receipts']
    assert len(case.requests) == count and inventory(case.root) == before


def test_reusing_a_confirmed_request_for_different_content_is_a_conflict(tmp_path):
    case = DialogCase(tmp_path/'project')
    first = case.prepare(request_id='same-request')
    case.publish(first); case.remember_edit()
    other = case.prepare('add', request_id='same-request')
    before = inventory(case.root)
    with no_write_attempts(), pytest.raises(ModelError) as refused:
        case.publish(other)
    assert refused.value.exit_code == 6 and inventory(case.root) == before


@pytest.mark.parametrize('fault', ['missing', 'origin', 'binding', 'late_revocation'])
def test_actual_history_and_live_provenance_are_required_again_at_publication(tmp_path, fault):
    case = DialogCase(tmp_path/'project')
    case.start(); case.approve()
    edit = case.prepare(); original = case.original
    revoked = [fault != 'late_revocation']
    def inputs(model, value):
        old = case.inputs(model, value)
        def verify(observation):
            proof = old.verifier.check(observation)
            if not revoked[0]:
                return proof
            return replace(proof, **({'input_sha256': '0'*64} if fault == 'binding' else
                                     {'origin_verified': False}))
        return replace(old, verifier=ProposalVerifier('synthetic-dialog-origin', '1', verify))
    services = QualificationServices() if fault == 'missing' else QualificationServices(proposal_inputs=inputs)
    def authorize(request):
        revoked[0] = True
        return True
    authority = (PublicationAuthority('synthetic-revoking-dialog', '1', authorize)
                 if fault == 'late_revocation' else case.authority)
    with pytest.raises(ModelError):
        case.publish(edit, services=services, authority=authority)
    assert (case.root/original.path).read_bytes() == original.source_bytes
    for path, raw in case.initial_model.source_files.items():
        assert (case.root/path).read_bytes() == raw
    assert not (case.root/'.specroad/write-state/pending.json').exists()


def test_denied_host_authority_does_not_publish_prepared_content(tmp_path):
    case = DialogCase(tmp_path/'project')
    original = case.original
    denied = PublicationAuthority('synthetic-denied-dialog', '1', lambda request: False)
    with pytest.raises(ModelError) as refused:
        case.publish(case.prepare(), authority=denied)
    assert refused.value.exit_code == 7
    assert (case.root/original.path).read_bytes() == original.source_bytes
    assert not (case.root/'.specroad/write-state/pending.json').exists()


@pytest.mark.parametrize('fault', ['foreign_content', 'review', 'base', 'change_id', 'action'])
def test_fully_bound_record_cannot_smuggle_unrelated_content_control_or_scope(tmp_path, fault):
    case = DialogCase(tmp_path/'project')
    edit = case.prepare()
    before, after = edit.revision.before, edit.revision.after
    record = after.data
    operation = dict(op='proposal_change', target=before.data['id'],
        expected_revision=before.data['revision'], expected_sha256=canonical_json_sha256(before.data),
        action='update', changed_change_ids=list(edit.changed_change_ids), record=record)
    if fault == 'foreign_content': record['rationale'] = 'Unrequested replacement'
    elif fault == 'review': record.update(proposal_status='approved', maturity='approved')
    elif fault == 'base': record['base']['model_root_sha256'] = '0'*64
    elif fault == 'change_id': operation['changed_change_ids'] = ['CHG-'+'1'*26]
    else: operation['action'] = 'remove'
    record['content_sha256'] = content_sha256(record)
    original_inventory = inventory(case.root)
    with no_write_attempts(), pytest.raises(ModelError):
        reduce_change(before, operation, actor=edit.request.data['actor'], planned_at=case.time)
    assert inventory(case.root) == original_inventory


@pytest.mark.parametrize('command', ['change apply', 'artifact update', 'proposal create', 'proposal change add'])
def test_content_write_operation_cannot_use_a_generic_or_wrong_specialist(tmp_path, command):
    case = DialogCase(tmp_path/'project')
    edit = case.prepare()
    before = edit.revision.before
    operation = dict(op='proposal_change', target=before.data['id'], expected_revision=before.data['revision'],
        expected_sha256=canonical_json_sha256(before.data), action='update',
        changed_change_ids=list(edit.changed_change_ids), record=edit.revision.after.data)
    with no_write_attempts(), pytest.raises(ModelError) as refused:
        prepare_authoring_request(command_id=command, actor=edit.request.data['actor'],
            operations=[operation], request_id='wrong-specialist')
    assert refused.value.reason == 'proposal_change_specialist_required'


@pytest.mark.parametrize('phase', ['staged:0', 'receipts_synced'])
def test_interrupted_actual_writer_keeps_native_corruption_guard_without_retry(tmp_path, monkeypatch, phase):
    from specroad.changes import guarded_write, inspect_write_state
    case = DialogCase(tmp_path/'project')
    model = case.model; edit = case.prepare()
    reached = []
    def stop(event):
        if event == phase:
            reached.append(event)
            raise OSError('synthetic interrupted write')
    monkeypatch.setattr(guarded_write, '_checkpoint', stop)
    with pytest.raises(ModelError) as interrupted:
        case.publish(edit, model=model)
    assert interrupted.value.exit_code == 5 and reached == [phase]
    assert inspect_write_state(case.root)['state'] == 'corrupted'
    assert (case.root/'.specroad/write-state/pending.json').exists()
    expected = edit.revision.before if phase == 'staged:0' else edit.revision.after
    assert (case.root/expected.path).read_bytes() == expected.source_bytes
    before = inventory(case.root)
    with no_write_attempts(), pytest.raises(NormalAccessError):
        case.publish(edit, model=model, transaction_id='forbidden-retry')
    assert inventory(case.root) == before
