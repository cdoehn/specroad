"""Original atomic publication proof, never a request to apply a Proposal."""
from dataclasses import dataclass
from hashlib import sha256

from ..changes.target_model import TargetModel, _default_scope
from ..changes.values import ChangePlan
from ..model.canonical import canonical_json_sha256
from ..validation import ModelDocument
from .context import ProposalContext, reconstruct_proposal_target
from .values import ProposalOriginal, require


@dataclass(frozen=True)
class ProposalPublication:
    plan: ChangePlan
    before: TargetModel
    after: TargetModel
    receipts: tuple

    def __post_init__(self):
        require(type(self.plan) is ChangePlan and type(self.before) is TargetModel
                and type(self.after) is TargetModel and type(self.receipts) is tuple
                and all(type(d) is ModelDocument for d in self.receipts),
                'proposal_native_publication_required')
        require(len({d.path for d in self.receipts}) == len(self.receipts),
                'proposal_duplicate_completion_path')
        object.__setattr__(self, 'before', self.before.snapshot())
        object.__setattr__(self, 'after', self.after.snapshot())

    @property
    def sha256(self):
        return canonical_json_sha256({'plan_bytes_sha256': sha256(self.plan.source_bytes).hexdigest(),
            'before_sources_sha256': self.before._sources_sha256,
            'after_sources_sha256': self.after._sources_sha256,
            'receipts': [{'path': d.path, 'size': len(d.content),
                          'sha256': sha256(d.content).hexdigest()}
                         for d in sorted(self.receipts, key=lambda d: d.path)]})


def verify_proposal_publication(proof, approved, applied, context):
    require(type(proof) is ProposalPublication and type(approved) is ProposalOriginal
            and type(applied) is ProposalOriginal and type(context) is ProposalContext,
            'proposal_native_publication_required')
    plan = proof.plan.data
    inner = applied.data['change_plan']
    require(approved.binding == applied.binding and approved.data['proposal_status'] == 'approved'
            and applied.data['proposal_status'] == 'applied', 'proposal_completion_state_mismatch')
    require(proof.before.source_files.get(approved.path) == approved.source_bytes
            and proof.after.source_files.get(applied.path) == applied.source_bytes,
            'proposal_completion_original_mismatch')
    require(proof.before.configuration.project_id == proof.after.configuration.project_id
            == context.basis.configuration.project_id, 'proposal_completion_project_mismatch', exit_code=6)
    require(plan['base']['scope_descriptor'] == _default_scope(),
            'proposal_completion_project_scope_required')
    require(plan['base']['model_root_sha256'] == proof.before.manifest(
                proof.before.artifacts, _default_scope()).sha256
            and plan['expected_result']['model_root_sha256'] == proof.after.manifest(
                proof.after.artifacts, _default_scope()).sha256,
            'proposal_completion_root_mismatch')
    operations = plan['operations']
    require(len(operations) == len(inner['operations']) + 1
            and operations[:-1] == inner['operations']
            and plan['preconditions'] == inner['preconditions']
            and plan['metadata_policy_version'] == inner['metadata_policy_version'],
            'proposal_completion_operations_mismatch')
    control = operations[-1]
    require(control['op'] == 'proposal_control' and control['target'] == applied.binding.proposal_id
            and control['expected_revision'] == approved.data['revision']
            and control['expected_sha256'] == canonical_json_sha256(approved.data)
            and all(control[k] == v for k, v in applied.binding.data.items() if k != 'proposal_id')
            and control['events'] == [{k: applied.data['control_history'][-1][k]
                for k in ('from', 'to', 'reason', 'result_sha256')}],
            'proposal_completion_control_mismatch')
    # The actual publication basis must have the approved specification root.
    # Preserve unrelated Proposal/Baseline controls and all resource/payload
    # bytes from that actual basis, not an earlier context's control history.
    computed = reconstruct_proposal_target(ProposalContext(context.original, proof.before))
    expected = {**computed.source_files, applied.path: applied.source_bytes}
    require(expected == proof.after.source_files, 'proposal_completion_target_mismatch')
    result_values = {r['artifact']['id']: r['artifact'] for r in plan['result_artifacts']}
    require(result_values == {**{r['artifact']['id']: r['artifact'] for r in inner['result_artifacts']},
                              applied.binding.proposal_id: applied.data},
            'proposal_completion_results_mismatch')
    from .receipts import read_proposal_receipts
    journal = read_proposal_receipts({d.path: d.content for d in proof.receipts},
                                    proof.before.configuration.project_id).data
    require(journal['authoring_binding']['command_id'] == 'proposal apply'
            and journal['plan_sha256'] == proof.plan.sha256
            and journal['plan_bytes_sha256'] == sha256(proof.plan.source_bytes).hexdigest()
            and journal['request_id'] == plan['request_id'] and journal['actor'] == plan['actor']
            and journal['change_plan_id'] == plan['change_plan_id']
            and journal['planned_at'] == plan['planned_at']
            and journal['authoring_binding']['scope_descriptor'] == plan['base']['scope_descriptor']
            and journal['base_model_root_sha256'] == plan['base']['model_root_sha256']
            and journal['target_model_root_sha256'] == plan['expected_result']['model_root_sha256'],
            'proposal_completion_binding_mismatch')
    from ..changes.metadata_time import next_update_time
    require(applied.data['updated_by'] == plan['actor'] and applied.data['updated_at'] ==
            next_update_time(plan['planned_at'], approved.data['updated_at']),
            'proposal_completion_metadata_mismatch')
    require(journal['authoring_binding']['operations'] == operations,
            'proposal_completion_operations_mismatch')
    for row in journal['target_inventory']:
        raw = proof.after.source_files.get(row['path'])
        require(raw is not None and (len(raw), sha256(raw).hexdigest()) ==
                (row['size'], row['sha256']), 'proposal_completion_target_bytes_missing')
    require({r['path'] for r in journal['target_inventory']} == set(proof.after.source_files),
            'proposal_completion_target_inventory_incomplete')
    for entry in journal['files']:
        old = proof.before.source_files.get(entry['path'])
        new = proof.after.source_files.get(entry['path'])
        require(new is not None and (len(new), sha256(new).hexdigest()) ==
                (entry['after_size'], entry['after_sha256']), 'proposal_completion_after_bytes_mismatch')
        require((old is not None) == entry['existed_before'], 'proposal_completion_before_missing')
        if old is not None:
            require((len(old), sha256(old).hexdigest()) ==
                    (entry['before_size'], entry['before_sha256']), 'proposal_completion_before_bytes_mismatch')
    changed = {p for p, raw in proof.after.source_files.items() if proof.before.source_files.get(p) != raw}
    require(changed == {r['path'] for r in journal['files']}, 'proposal_completion_write_set_mismatch')
