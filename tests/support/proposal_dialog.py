"""Synthetic host; every Proposal write uses a public native entry point."""
from specroad.authoring._inspection_snapshot import InspectionSnapshot
from specroad.authoring.execution import apply_authoring_plan
from specroad.changes import PublicationAuthority
from specroad.changes.core import prepare_change_plan
from specroad.changes.lifecycle import prepare_change_lifecycle
from specroad.model.audit_values import Actor, Revision, UtcTimestamp
from specroad.proposals import Proposal, ProposalContext, ProposalOriginal, prepare_proposal_change_for_model
from specroad.proposals._review_control import read_review_start_observations
from specroad.proposals.change import publish_proposal_change
from specroad.proposals.context import specification_manifest
from specroad.proposals.review_start import review_start_project
from test_proposal_basis import put_model
from .authoring_proposals import planned, metadata
from .change_plans import result
from .proposal_apply import ApplyCase, multiple_change


EXPLANATION = dict(rationale='Synthetic human-requested revision',
    requirement_or_issue_ids=[], sources=[], assumptions=[], confidence=None)


class DialogCase(ApplyCase):
    def __init__(self, root):
        self.root = root
        model, plan, gates = planned(root)
        self.initial_model = model
        self.requests = []
        def capture(request):
            self.requests.append(request)
            return True
        self.authority = PublicationAuthority('synthetic-dialog-host', '1', capture)
        self.created = apply_authoring_plan(plan, model, command_id='artifact.update',
            transaction_id='dialog-create', authority=self.authority, as_proposal=True,
            proposal_fields=metadata(plan), gates=gates)
        path = self.created['proposal_path']
        first = ProposalOriginal((root/path).read_bytes(), path=path)
        self.originals, self.contexts = [first], [ProposalContext(first, self.model)]
        self.reviews, self.controls = [], []
        self.current_decisions = True

    @property
    def model(self):
        return InspectionSnapshot(self.root, None).model

    @property
    def time(self):
        return '2026-11-18T00:%02d:00Z' % self.original.data['revision']

    def remember_edit(self):
        current = ProposalOriginal((self.root/self.original.path).read_bytes(), path=self.original.path)
        self.originals.append(current)
        self.contexts.append(ProposalContext(current, self.model))

    def capture(self, *, start=False):
        if not start:
            return super().capture()
        current = ProposalOriginal((self.root/self.original.path).read_bytes(), path=self.original.path)
        self.controls.extend(read_review_start_observations(current,
            len(self.original.data['control_history']), self.contexts[-1]))
        self.originals.append(current)
        self.contexts.append(ProposalContext(current, self.model))

    def start(self):
        revision = self.original.data['revision']
        outcome = review_start_project(self.root, self.original.data['id'], expected_revision=revision,
            actor={'actor_type': 'human', 'actor_id': 'synthetic-dialog-author'}, planned_at=self.time,
            change_plan_id='dialog-start-plan-'+str(revision), transaction_id='dialog-start-'+str(revision),
            authority=self.authority, services=self.services)
        self.capture(start=True)
        return outcome

    def options(self, actor='reviewer-one', **changes):
        return super().options(actor, **{'planned_at': self.time, **changes})

    def approve(self):
        for index in range(self.model.configuration.data['validation_policy'].get('minimum_human_proposal_approvals', 1)):
            self.decide('synthetic-dialog-reviewer-'+str(index))

    def apply_options(self, **changes):
        return super().apply_options(**{'planned_at': '2026-11-19T00:00:00Z', **changes})

    def replan(self, operations):
        model = self.model
        value = self.original.data['change_plan']
        value.pop('change_plan_sha256')
        value['operations'] = operations
        folded = prepare_change_lifecycle(model.artifacts, operations,
            metadata_policy_version=value['metadata_policy_version'], actor=value['actor'],
            planned_at=value['planned_at'], source_files=model.source_files, **model.reservations)
        values = [candidate.data for candidate in folded.candidates]
        value['result_artifacts'] = [result(record) for record in values]
        value['expected_result']['model_root_sha256'] = specification_manifest(put_model(model, *values)).sha256
        return prepare_change_plan(value)

    def prepare(self, action='update', *, dry_run=False, request_id=None):
        original = self.original
        operations = original.data['change_plan']['operations']
        identity = original.data['changes'][0]['change_id']
        arguments = {}
        if action == 'add':
            create = multiple_change(self.model)['change_plan'].data['operations'][0]
            # The embedded plan owns its own audit defaults.
            fields = original.data['change_plan']
            create['artifact'].update(created_by=fields['actor'], updated_by=fields['actor'],
                created_at=fields['planned_at'], updated_at=fields['planned_at'])
            operations.append(create)
            arguments['explanation'] = EXPLANATION
        elif action == 'update':
            operations[0]['patch'][0]['value'] = 'Revised dialogue goal'
            arguments.update(change_id=identity, explanation=EXPLANATION)
        elif action == 'remove':
            operations.pop(0)
            arguments['change_id'] = identity
        else:
            operations.append(operations.pop(0))
            arguments.update(change_id=identity, position=len(operations)-1)
        if action == 'move' and len(operations) == 1:
            from specroad.changes import ChangePlan
            from specroad.model.canonical import canonical_json_bytes
            plan = ChangePlan(canonical_json_bytes(original.data['change_plan']))
        else:
            plan = self.replan(operations)
        return prepare_proposal_change_for_model(self.model,
            Proposal(original.source_bytes, path=original.path), action=action,
            change_plan=plan, expected_revision=Revision(original.data['revision']),
            actor=Actor('human', 'synthetic-dialog-author'), planned_at=UtcTimestamp(self.time),
            request_id=request_id or 'dialog-change-'+str(original.data['revision']),
            dry_run=dry_run, **arguments)

    def publish(self, edit, *, model=None, **changes):
        revision = edit.revision.before.data['revision']
        options = dict(change_plan_id='dialog-change-plan-'+str(revision),
            planned_at='2026-11-18T00:%02d:00Z' % revision,
            transaction_id='dialog-change-'+str(revision), authority=self.authority, services=self.services)
        return publish_proposal_change(edit, self.model if model is None else model, **{**options, **changes})
