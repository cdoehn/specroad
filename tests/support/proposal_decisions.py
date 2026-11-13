"""Synthetic host retaining actual originals from completed native writer calls."""
from dataclasses import replace
from hashlib import sha256

from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.changes import PublicationAuthority
from specroad.model.canonical import canonical_json_bytes
from specroad.proposals import prepare_proposal_for_model, ProposalOriginal, ProposalContext, ProposalInputs
from specroad.proposals.observations import ProposalVerifier, ProposalVerification
from specroad.proposals._review_control import read_review_start_observations
from specroad.proposals._decision_control import read_review_observations
from specroad.proposals.review_start import review_start_project
from specroad.proposals.review_decision import review_project
from specroad.recovery.services import RestoreServices
from test_proposal_basis import project, fields, planned_change
from .model import put


class ReviewCase:
    def __init__(self, root, *, minimum=2, changed=True, start=True):
        self.root = root
        model = project(root)
        configuration = model.configuration.data
        configuration['validation_policy']['minimum_human_proposal_approvals'] = minimum
        put(root, 'specroad.json', canonical_json_bytes(configuration))
        model = InspectionSnapshot(root, None).model
        first = prepare_proposal_for_model(model, **(planned_change(model) if changed else fields(model))).original
        put(root, first.path, first.source_bytes)
        self.originals, self.contexts = [first], [ProposalContext(first, InspectionSnapshot(root, None).model)]
        self.reviews, self.controls = [], []
        self.current_decisions = True
        self.authority = PublicationAuthority('synthetic-review-host', '1', lambda request: True)
        if start:
            review_start_project(root, first.data['id'], expected_revision=1,
                actor={'actor_type': 'human', 'actor_id': 'synthetic-author'}, planned_at='2026-11-11T01:00:00Z',
                change_plan_id='synthetic-start-plan', transaction_id='synthetic-start', authority=self.authority)
            self.capture(start=True)

    @property
    def original(self):
        return self.originals[-1]

    def capture(self, *, start=False):
        before = self.original
        current = ProposalOriginal((self.root / before.path).read_bytes(), path=before.path)
        if start:
            self.controls.extend(read_review_start_observations(current, 0, self.contexts[-1]))
        else:
            review, controls = read_review_observations(current, self.contexts[-1])
            self.reviews.append(review); self.controls.extend(controls)
        self.originals.append(current)
        self.contexts.append(ProposalContext(current, InspectionSnapshot(self.root, None).model))

    def inputs(self, model, original):
        assert original == self.original
        def verify(inputs):
            item = inputs.observation
            assert item in (*self.reviews, *self.controls)
            assert item.original in self.originals and item.context in self.contexts
            assert item.original.source_bytes == self.originals[item.original.data['revision'] - 1].source_bytes
            return ProposalVerification(inputs.sha256, sha256(item.row_bytes).hexdigest(), True, True,
                item in self.reviews and item.decision == 'approved' and self.current_decisions)
        return ProposalInputs(tuple(self.originals), tuple(self.contexts), tuple(self.reviews), tuple(self.controls),
            ProposalVerifier('synthetic-actual-originals', '1', verify))

    @property
    def services(self):
        return RestoreServices(proposal_inputs=self.inputs)

    def options(self, actor='reviewer-one', **changes):
        revision = self.original.data['revision']
        result = dict(expected_revision=revision, decision='approved', actor={'actor_type': 'human', 'actor_id': actor},
            comment='Explicit synthetic human assessment of statement and normative_force',
            planned_at='2026-11-11T02:00:%02dZ' % revision, change_plan_id='synthetic-review-plan-' + str(revision),
            transaction_id='synthetic-review-' + str(revision), authority=self.authority, services=self.services)
        result.update(changes)
        return result

    def decide(self, actor='reviewer-one', **changes):
        result = review_project(self.root, self.original.data['id'], **self.options(actor, **changes))
        if not result['dry_run'] and not result['replayed']:
            self.capture()
        return result
