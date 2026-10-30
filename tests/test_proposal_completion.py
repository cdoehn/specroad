"""Synthetic original atomic completions, never active Proposal publication."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from specroad.changes.authoring import prepare_authoring_request
from specroad.changes.core import prepare_change_plan
from specroad.changes.receipt_values import completion_marker_path, transaction_receipt_path, request_receipt_path
from specroad.changes.target_model import _default_scope
from specroad.changes._target_materialization import materialize_target
from specroad.model.audit_values import UtcTimestamp
from specroad.model.canonical import canonical_json_bytes, canonical_json_sha256
from specroad.proposals import ProposalContext, ProposalControlObservation, ProposalPublication, assess_proposal
from specroad.proposals.history import native_check
from specroad.proposals.receipts import read_proposal_receipts
from specroad.storage.json_syntax import parse_json_object
from specroad.validation import ModelDocument
from support.change_plans import document, result
from support.read_only import no_write_attempts
from test_proposal_history import HUMAN, history
from test_proposal_originals import original


def edited_draft(tmp_path):
    from test_proposal_originals import draft
    from specroad.changes.lifecycle import prepare_change_lifecycle
    from specroad.model.paths import artifact_path
    from specroad.proposals.context import specification_manifest
    from specroad.proposals.values import content_sha256
    model, value = draft(tmp_path)
    source = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    operations = [{'op': 'update', 'target': source['id'], 'expected_revision': source['revision'],
        'expected_sha256': canonical_json_sha256(source),
        'patch': [{'op': 'replace', 'path': '/statement', 'value': 'Originally published Proposal change'}]}]
    plan = document(operations, [])
    folded = prepare_change_lifecycle(model.artifacts, operations,
        metadata_policy_version=plan['metadata_policy_version'], actor=plan['actor'],
        planned_at=plan['planned_at'], source_files=model.source_files, **model.reservations)
    final = next(a for a in folded.artifacts if a['id'] == source['id'])
    target = materialize_target(model, (ModelDocument(artifact_path('goal', source['id'], 'SR'),
                                                    canonical_json_bytes(final)),))
    plan['base'] = value['base']
    plan['result_artifacts'] = [result(final)]
    plan['expected_result']['model_root_sha256'] = specification_manifest(target).sha256
    value['change_plan'] = prepare_change_plan(plan).data
    value['content_sha256'] = content_sha256(value)
    return model, value


def completed(tmp_path, *, changed=False):
    from test_proposal_originals import draft
    inputs, before = history(tmp_path, draft_factory=edited_draft if changed else draft)
    approved = inputs.originals[-1]
    context = inputs.contexts[-1]
    checked = native_check(context)
    value = deepcopy(approved.data)
    value.update(revision=value['revision'] + 1, proposal_status='applied',
                 updated_at='2026-10-29T00:00:04Z', updated_by=HUMAN.as_fields())
    event = {'from': 'approved', 'to': 'applied', 'reason': 'Synthetic original atomic completion',
             'result_sha256': sha256(checked).hexdigest()}
    value['control_history'].append({**event, 'binding': approved.binding.data,
                                    'actor': HUMAN.as_fields(), 'at': value['updated_at']})
    applied = original(value)
    from specroad.proposals.context import reconstruct_proposal_target
    target = reconstruct_proposal_target(replace(context, basis=before))
    after = materialize_target(target, (ModelDocument(applied.path, applied.source_bytes),))
    operation = {'op': 'proposal_control', 'target': applied.binding.proposal_id,
        'expected_revision': approved.data['revision'],
        'expected_sha256': canonical_json_sha256(approved.data),
        **{k: v for k, v in applied.binding.data.items() if k != 'proposal_id'}, 'events': [event]}
    outer = document([*value['change_plan']['operations'], operation],
                     [*value['change_plan']['result_artifacts'], result(applied.data)])
    outer.update(actor=HUMAN.as_fields(), planned_at=value['updated_at'])
    outer['base'] = {'scope_descriptor': _default_scope(),
                     'model_root_sha256': before.manifest(before.artifacts, _default_scope()).sha256}
    outer['expected_result']['model_root_sha256'] = after.manifest(after.artifacts, _default_scope()).sha256
    plan = prepare_change_plan(outer)
    author = prepare_authoring_request(command_id='proposal apply', actor=outer['actor'],
                                      operations=outer['operations'], request_id=outer['request_id'])
    authoring = {**author.data, 'plan_sha256': plan.sha256,
                 'scope_descriptor': outer['base']['scope_descriptor'],
                 'base_model_root_sha256': outer['base']['model_root_sha256']}
    txn = 'synthetic-proposal-completion'
    entries = []
    for path, raw in sorted(after.source_files.items()):
        old = before.source_files.get(path)
        if old == raw:
            continue
        index = len(entries)
        entries.append({'path': path, 'existed_before': old is not None,
            'before_size': None if old is None else len(old),
            'before_sha256': None if old is None else sha256(old).hexdigest(),
            'after_size': len(raw), 'after_sha256': sha256(raw).hexdigest(),
            'staging_path': '.specroad/transactions/' + txn + '/staging/' + str(index) + '.bin',
            'before_image_path': None if old is None else '.specroad/transactions/' + txn + '/before/' + str(index) + '.bin',
            'published': True})
    journal = {'format_version': 'transaction-journal-v1', 'state': 'committing',
        'transaction_id': txn, 'project_id': before.configuration.project_id,
        'root_identity': list(before.binding.root_identity), 'change_plan_id': outer['change_plan_id'],
        'request_id': outer['request_id'], 'actor': outer['actor'], 'planned_at': outer['planned_at'],
        'plan_sha256': plan.sha256, 'plan_bytes_sha256': sha256(plan.source_bytes).hexdigest(),
        'request_sha256': sha256(b'synthetic-original-request').hexdigest(),
        'authoring_binding': authoring, 'authoring_sha256': canonical_json_sha256(authoring),
        'base_model_root_sha256': outer['base']['model_root_sha256'],
        'target_model_root_sha256': outer['expected_result']['model_root_sha256'],
        'target_inventory': [{'path': p, 'size': len(b), 'sha256': sha256(b).hexdigest()}
                             for p, b in sorted(after.source_files.items())],
        'files': entries, 'published_count': len(entries)}
    outcome = {'exit_code': 0, 'status': 'success', 'write_state': 'committed',
        'transaction_id': txn, 'request_id': outer['request_id'],
        'target_model_root_sha256': journal['target_model_root_sha256'],
        'published_paths': [e['path'] for e in entries], 'created_ids': []}
    receipt = {'format_version': 'transaction-receipt-v1', 'outcome': 'committed',
        'journal': journal, 'journal_sha256': canonical_json_sha256(journal),
        'command_id': 'proposal apply', 'operations': outer['operations'],
        'operations_sha256': canonical_json_sha256(outer['operations']), 'created_ids': [], 'result_object': outcome}
    files = {transaction_receipt_path(txn): canonical_json_bytes(receipt)}
    refs = {'transaction': {'path': transaction_receipt_path(txn),
                           'sha256': sha256(files[transaction_receipt_path(txn)]).hexdigest()}}
    request = {'format_version': 'request-receipt-v1', 'namespace': 'normative_write',
        'request_id': outer['request_id'], 'project_id': journal['project_id'], 'transaction_id': txn,
        'actor': outer['actor'], 'operations_sha256': receipt['operations_sha256'],
        'base_model_root_sha256': journal['base_model_root_sha256'],
        'target_model_root_sha256': journal['target_model_root_sha256'], 'result': 'committed',
        'created_ids': [], 'result_object': outcome, 'transaction_receipt': refs['transaction']}
    path = request_receipt_path(outer['request_id']); files[path] = canonical_json_bytes(request)
    refs['request'] = {'path': path, 'sha256': sha256(files[path]).hexdigest()}
    files[completion_marker_path(txn)] = canonical_json_bytes({**journal, 'state': 'committed', 'receipts': refs})
    proof = ProposalPublication(plan, before, after, tuple(ModelDocument(p, b) for p, b in sorted(files.items())))
    control = ProposalControlObservation(applied, len(approved.data['control_history']), context,
        HUMAN, UtcTimestamp(value['updated_at']), 'approved', 'applied', event['reason'], checked)
    inputs = replace(inputs, originals=(*inputs.originals, applied),
        contexts=(*inputs.contexts, ProposalContext(applied, context.basis)),
        controls=(*inputs.controls, control), publications=(proof,))
    return inputs, after


@pytest.mark.parametrize('changed', [False, True])
def test_original_applied_completion_is_checked_but_never_reapplied(tmp_path, changed):
    inputs, model = completed(tmp_path, changed=changed)
    from specroad.bundles._receipts import completed_receipts
    files = {d.path: d.content for d in inputs.publications[0].receipts}
    with no_write_attempts():
        report = assess_proposal(inputs.originals[-1], inputs, model)
        journals = completed_receipts(files, model.configuration.project_id)
    assert report['historical_valid'] and report['observed_status'] == 'applied'
    assert not report['current_approval'] and not report['write_authorized'] and not report['apply_performed']
    assert len(journals) == 1
    if changed:
        goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
        assert goal['statement'] == 'Originally published Proposal change' and goal['revision'] == 2
    from specroad.changes.receipt_values import CommittedJournal, ReceiptError
    marker = next(raw for path, raw in files.items() if path.endswith('/committed.json'))
    with pytest.raises(ReceiptError):
        CommittedJournal(marker)


@pytest.mark.parametrize('fault', ['missing_receipt', 'target', 'plan', 'request', 'original'])
def test_completed_label_and_rehashed_foreign_receipts_do_not_prove_apply(tmp_path, fault):
    inputs, model = completed(tmp_path)
    proof = inputs.publications[0]
    if fault == 'missing_receipt':
        proof = replace(proof, receipts=proof.receipts[:-1])
    elif fault == 'target':
        proof = replace(proof, after=proof.before)
    elif fault == 'original':
        inputs = replace(inputs, originals=inputs.originals[:-1])
    else:
        changed = []
        for source in proof.receipts:
            value = parse_json_object(source.content)
            if source.path.endswith('/transaction.json'):
                value['journal']['plan_sha256' if fault == 'plan' else 'request_id'] = '0' * 64
                value['journal_sha256'] = canonical_json_sha256(value['journal'])
            changed.append(ModelDocument(source.path, canonical_json_bytes(value)))
        proof = replace(proof, receipts=tuple(changed))
    inputs = replace(inputs, publications=(proof,))
    from specroad.model.errors import ModelError
    with no_write_attempts(), pytest.raises(ModelError):
        assess_proposal(inputs.contexts[-1].original, inputs, model)
