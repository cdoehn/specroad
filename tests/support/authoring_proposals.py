"""Complete native input fixtures; actual publication runs only in Apply."""
from specroad.authoring.plans import preview_authoring_request
from specroad.changes import ChangePlan
from specroad.model.canonical import canonical_json_bytes as jcs
from specroad.model.identity_values import ArtifactIdentity
from specroad.model.identity_tokens import encode128
from specroad.qualification.project import validate_project
from specroad.validation import ModelGate
from specroad.validation.values import HOOK_NAMES
from test_proposal_basis import project
from support.folds import edit
from support.change_plans import document
from support.records import ref


def metadata(plan):
    return dict(identity=ArtifactIdentity(ref('PROP', '2'), 'random128-v1', 'proposal', 'SR'),
        title='Proposed native change', rationale='Review before changing the specification',
        changes=[dict(change_id='CHG-'+encode128(index.to_bytes(16, 'big')),
            targets=list(op.result_ids), rationale='Explicit prepared operation',
            requirement_or_issue_ids=[], sources=[], assumptions=[], confidence=None)
            for index, op in enumerate(plan.operations)])


def native_gates(model):
    def dependencies(context):
        return context.dependency_result({k: list(context.all_ids) for k in context.subjects})
    def check(context):
        files = dict(model.source_files)
        files.update({d.path: d.content for d in context.documents})
        validate_project(files)
        return context.result()
    return tuple(ModelGate(name, 'fixture-full-qualification-v1', dependencies, check,
        model._sources_sha256) for name in HOOK_NAMES if name not in ('profile_lint', 'language_policy'))


def planned(root, *, actor='human'):
    model = project(root, bundled=True)
    goal = next(a for a in model.artifacts if a['artifact_type'] == 'goal')
    fields = document([], [])
    fields['actor'] = {'actor_type': actor, 'actor_id': 'explicit-author'}
    gates = native_gates(model)
    result = preview_authoring_request(model, 'artifact.update', [edit(goal, 'Proposed goal title')],
        **{k: fields[k] for k in ('actor', 'planned_at', 'change_plan_id', 'request_id')}, gates=gates)
    return model, ChangePlan(jcs(result['plan'])), gates
