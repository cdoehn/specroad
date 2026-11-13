"""Small approved projects with actual native control writes and completions."""
from dataclasses import replace
from hashlib import sha256

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.changes import PublicationAuthority
from specroad.changes._lock_files import LockFiles
from specroad.changes.receipt_read import _CompletionProof
from specroad.proposals import ProposalContext, ProposalOriginal, ProposalInputs
from specroad.proposals._apply_control import read_apply_observation
from specroad.proposals.apply import apply_project
from specroad.proposals.observations import ProposalVerifier, ProposalVerification
from specroad.proposals.publication import ProposalPublication
from specroad.storage.project import ProjectSource
from specroad.validation import ModelDocument
from .proposal_decisions import ReviewCase


class ApplyCase(ReviewCase):
    def __init__(self, root, **options):
        super().__init__(root, minimum=1, **options)
        self.decide()
        self.before = InspectionSnapshot(root, None).model
        self.requests = []
        def capture(request):
            self.requests.append(request)
            return True
        self.authority = PublicationAuthority('synthetic-apply-host', '1', capture)

    def apply_options(self, **changes):
        value = dict(expected_revision=self.original.data['revision'],
            actor={'actor_type': 'human', 'actor_id': 'synthetic-applier'},
            planned_at='2026-11-13T00:00:00Z', change_plan_id='synthetic-apply-plan',
            transaction_id='synthetic-apply', request_id='synthetic-apply-request',
            authority=self.authority, services=self.services)
        value.update(changes)
        return value

    def apply(self, **changes):
        return apply_project(self.root, self.original.data['id'], **self.apply_options(**changes))

    def completion_inputs(self, transaction='synthetic-apply'):
        # Read the real completed transaction; never synthesize success receipts.
        source = ProjectSource(self.root)
        after = InspectionSnapshot(self.root, None).model
        applied = ProposalOriginal(after.source_files[self.original.path], path=self.original.path)
        with LockFiles(self.root) as files:
            proof = _CompletionProof(files, source, transaction)
            receipts = tuple(ModelDocument(p, proof.read(p)) for p in (*proof.receipt_paths, proof.archive_path))
            proof.check()
        plan = self.requests[-1].plan
        publication = ProposalPublication(plan, self.before, after, receipts)
        control = read_apply_observation(applied, ProposalContext(self.original, self.before))
        old = self.inputs(self.before, self.original)
        def verify(inputs):
            if inputs.observation == control:
                return ProposalVerification(inputs.sha256, sha256(control.row_bytes).hexdigest(), True, True, False)
            return old.verifier.check(inputs)
        result = ProposalInputs((*old.originals, applied),
            (*old.contexts, ProposalContext(applied, self.before)), old.reviews,
            (*old.controls, control), ProposalVerifier('synthetic-completed-apply', '1', verify), (publication,))
        return result, after


def multiple_change(model):
    """One creation plus an ordered update, with a real checked embedded plan."""
    from specroad.changes.lifecycle import prepare_change_lifecycle
    from specroad.changes.core import prepare_change_plan
    from test_proposal_basis import fields, put_model
    from .change_plans import document, result
    from .domain import domain_value
    from .folds import edit
    from .records import ref
    from specroad.proposals.context import specification_manifest
    supplied = fields(model)
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    created = domain_value('goal'); created['id'] = ref('GOAL', '1')
    plan = document([], [])
    created.update(created_by=plan['actor'], updated_by=plan['actor'],
                   created_at=plan['planned_at'], updated_at=plan['planned_at'])
    plan['operations'] = [{'op': 'create', 'artifact': created, 'result_id': created['id']},
                          edit(goal, 'Ordered approved result')]
    plan['base'] = supplied['change_plan'].data['base']
    folded = prepare_change_lifecycle(model.artifacts, plan['operations'],
        metadata_policy_version=plan['metadata_policy_version'], actor=plan['actor'], planned_at=plan['planned_at'],
        source_files=model.source_files, **model.reservations)
    results = [c.data for c in folded.candidates]
    plan['result_artifacts'] = [result(v) for v in results]
    plan['expected_result']['model_root_sha256'] = specification_manifest(put_model(model, *results)).sha256
    supplied['change_plan'] = prepare_change_plan(plan)
    supplied['changes'] = [dict(change_id='CHG-' + str(index) * 26, targets=[identity],
        rationale='Ordered native change', requirement_or_issue_ids=[], sources=[], assumptions=[], confidence=None)
        for index, identity in enumerate((created['id'], goal['id']))]
    return supplied
