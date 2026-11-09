"""Owned ordered changes bound to a complete native plan, without write authority.

The planner supplies the complete replacement plan, including recalculated
results and root. Reordering operations never silently reuses a target hash.
This value does not revise a Proposal, invalidate reviews or publish files.
"""
from dataclasses import dataclass
import secrets

from ..changes import ChangePlan
from ..model._schema import validate_builtin
from ..model.audit_fields import audit_definitions
from ..model.canonical import canonical_json_bytes
from ..model.identity_tokens import encode128, decode128
from ..model.proposal_fields import proposal_authoring_fields
from ..storage.json_syntax import parse_json_object
from .authoring import Proposal
from .authoring_fields import validate_explanations
from .values import ProposalError, require


def _operations(plan):
    require(type(plan) is ChangePlan, 'native_proposal_plan_required')
    return plan.data['operations']


@dataclass(frozen=True, init=False)
class ProposalChanges:
    """An immutable planning value; identities travel with their explanations.

    Each edit takes a fully rebound ChangePlan, checked against the exact
    requested sequence. Live target verification and lifecycle/revision writes
    still belong to the native authoring host. Human numbering is not an ID.
    """
    change_plan: ChangePlan
    _encoded: bytes
    _creator: bytes
    changed_change_ids: tuple

    def __init__(self, proposal):
        require(type(proposal) is Proposal, 'native_proposal_required')
        object.__setattr__(self, 'change_plan', ChangePlan(
            canonical_json_bytes(proposal.data['change_plan'])))
        object.__setattr__(self, '_encoded', canonical_json_bytes({'changes': proposal.data['changes']}))
        object.__setattr__(self, '_creator', canonical_json_bytes(proposal.data['created_by']))
        object.__setattr__(self, 'changed_change_ids', ())

    @property
    def changes(self):
        return parse_json_object(self._encoded)['changes']

    @property
    def change_ids(self):
        return tuple(row['change_id'] for row in self.changes)

    @property
    def write_authorized(self):
        return False

    def _index(self, change_id):
        require(type(change_id) is str and change_id.startswith('CHG-'),
                'proposal_change_id_required', pointer='/change_id')
        decode128(change_id[4:])
        require(change_id in self.change_ids,
                'proposal_change_not_found', pointer='/change_id')
        return self.change_ids.index(change_id)

    def get(self, change_id):
        index = self._index(change_id)
        return {'operation': self.change_plan.data['operations'][index],
                'explanation': self.changes[index]}

    def _position(self, position, length):
        require(type(position) is int and 0 <= position <= length,
                'proposal_change_position', pointer='/position', exit_code=2)
        return position

    def _check_plan(self, plan, operations):
        actual = _operations(plan)
        require(canonical_json_bytes(actual) == canonical_json_bytes(operations),
                'proposal_change_order_mismatch', pointer='/change_plan/operations')
        require(plan.data['base'] == self.change_plan.data['base'],
                'proposal_change_basis_mismatch', pointer='/change_plan/base', exit_code=6)
        require(not any(op.op in ('proposal_control', 'baseline_create') for op in plan.operations)
                and not any(row['artifact']['artifact_type'] in ('proposal', 'baseline')
                            for row in plan.data['result_artifacts']),
                'proposal_control_operation_forbidden')

    def _replace(self, plan, changes, operations, changed):
        self._check_plan(plan, operations)
        validate_builtin(changes, {**proposal_authoring_fields()['changes'],
                                   '$defs': audit_definitions()})
        validate_explanations({'changes': changes, 'created_by': parse_json_object(self._creator)}, plan)
        result = object.__new__(type(self))
        object.__setattr__(result, 'change_plan', ChangePlan(plan.source_bytes))
        object.__setattr__(result, '_encoded', canonical_json_bytes({'changes': changes}))
        object.__setattr__(result, '_creator', self._creator)
        object.__setattr__(result, 'changed_change_ids', tuple(changed))
        return result

    def add(self, change_plan, *, explanation, position=None):
        """Append by default; insert before the old element at an explicit index."""
        operations = self.change_plan.data['operations']
        index = len(operations) if position is None else self._position(position, len(operations))
        proposed = _operations(change_plan)
        require(len(proposed) == len(operations) + 1,
                'proposal_change_order_mismatch', pointer='/change_plan/operations')
        operation = change_plan.operations[index]
        operations.insert(index, operation.data)
        # Reject changed/missing/extra old operations or a substituted basis
        # before drawing an identity, even when the entropy source is blocked.
        self._check_plan(change_plan, operations)
        require(type(explanation) is dict and set(explanation) == {
            'rationale', 'requirement_or_issue_ids', 'sources', 'assumptions', 'confidence'},
            'proposal_change_explanation_required', pointer='/explanation')
        targets = ([operation.data['path']] if operation.op == 'representation_normalize'
                   else list(operation.result_ids))
        changes = self.changes
        row = {**explanation, 'change_id': 'CHG-' + '0' * 26, 'targets': targets}
        # Validate the input before requesting entropy; the temporary identity
        # is never returned. Uniqueness is checked on the final allocated row.
        validate_builtin([row], {**proposal_authoring_fields()['changes'], '$defs': audit_definitions()})
        refs = row['requirement_or_issue_ids']
        require(len(set(refs)) == len(refs), 'duplicate_proposal_requirement',
                pointer='/explanation/requirement_or_issue_ids')
        if parse_json_object(self._creator)['actor_type'] == 'ai':
            require(type(row['confidence']) in (int, float), 'proposal_confidence_required',
                    pointer='/explanation/confidence')
        while True:
            try:
                identity = 'CHG-' + encode128(secrets.token_bytes(16))
            except OSError as error:
                raise ProposalError('proposal_change_entropy_unavailable', exit_code=5) from error
            if identity not in self.change_ids:
                break
        row['change_id'] = identity
        changes.insert(index, row)
        return self._replace(change_plan, changes, operations, (identity,))

    def move(self, change_id, position, *, change_plan):
        """Remove first, then insert at an index of the remaining sequence."""
        source = self._index(change_id)
        operations, changes = self.change_plan.data['operations'], self.changes
        index = self._position(position, len(changes) - 1)
        operation, explanation = operations.pop(source), changes.pop(source)
        operations.insert(index, operation)
        changes.insert(index, explanation)
        if source == index:
            require(type(change_plan) is ChangePlan
                    and change_plan.canonical_bytes == self.change_plan.canonical_bytes,
                    'proposal_noop_plan_changed', pointer='/change_plan')
        return self._replace(change_plan, changes, operations, () if source == index else (change_id,))

    def update(self, change_id, *, change_plan, explanation):
        """Replace exactly one operation and explanation, preserving its ID."""
        index = self._index(change_id)
        operations, changes = self.change_plan.data['operations'], self.changes
        proposed = _operations(change_plan)
        require(len(proposed) == len(operations), 'proposal_change_order_mismatch')
        operations[index] = proposed[index]
        require(type(explanation) is dict and set(explanation) == {
            'rationale', 'requirement_or_issue_ids', 'sources', 'assumptions', 'confidence'},
            'proposal_change_explanation_required', pointer='/explanation')
        op = change_plan.operations[index]
        changes[index] = {**explanation, 'change_id': change_id,
                         'targets': [op.data['path']] if op.op == 'representation_normalize' else list(op.result_ids)}
        unchanged = (canonical_json_bytes(changes) == canonical_json_bytes(self.changes)
                     and change_plan.canonical_bytes == self.change_plan.canonical_bytes)
        return self._replace(change_plan, changes, operations, () if unchanged else (change_id,))

    def remove(self, change_id, *, change_plan):
        index = self._index(change_id)
        operations, changes = self.change_plan.data['operations'], self.changes
        del operations[index]
        del changes[index]
        return self._replace(change_plan, changes, operations, (change_id,))
