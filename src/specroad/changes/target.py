"""One target-evaluation path for explicit direct and saved-plan adapters.

Complete supplied-model checks, recomputed metadata/root and semantic diff do
not replace live inventory, durable transaction preparation or authorization.
"""
from hashlib import sha256
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model.paths import artifact_path
from ..storage.json_syntax import parse_json_object
from ..validation import ModelDocument, validate_model, assess_validation, ValidationResources
from .values import ChangePlan
from .lifecycle import prepare_plan_lifecycle, prepare_change_lifecycle
from .core import prepare_change_plan
from .target_values import TargetError, TargetPolicy, TargetAssessment, TARGET_VERSION
from .target_model import TargetModel, _sequence, _project_scope
from ._target_checks import _gates, _empty_target_gates, _describe

def assess_change_target(plan, model, *, policy, gates=(), strict=False):
    """Recompute every result and validate ALL target artifacts, not touched IDs.

    Failure reports can be inspected but cannot be promoted to a prepared
    transaction. Mandatory command gates and missing model services fail closed.
    """
    if type(plan) is not ChangePlan or type(model) is not TargetModel or type(policy) is not TargetPolicy:
        raise TargetError('target_plan_model_policy_required')
    if type(strict) is not bool: raise TargetError('target_strict_boolean_required')
    model = model.snapshot()
    policy = TargetPolicy(policy.command_id, policy.version, policy.required_gate_ids)
    plan = ChangePlan(plan.source_bytes)  # Enforce the unchanged self-hash again.
    value = plan.data
    scope = _project_scope(value['base']['scope_descriptor'])
    base = model.manifest(model.artifacts, scope)
    if value['base']['model_root_sha256'] != base.sha256:
        raise TargetError('target_base_root_mismatch', pointer='/base/model_root_sha256')
    folded = prepare_plan_lifecycle(plan, model.artifacts, observed_base_root=base.sha256,
        observed_scope=scope, source_files=model.source_files, **model.reservations)
    artifacts = folded.artifacts
    target = model.manifest(artifacts, scope)
    if target.sha256 != value['expected_result']['model_root_sha256']:
        raise TargetError('target_result_root_mismatch', pointer='/expected_result/model_root_sha256')
    originals = {parse_json_object(d.content)['id']:d for d in model.documents}
    documents = []
    for artifact in artifacts:
        old = originals.get(artifact['id'])
        raw = old.content if old is not None and canonical_json_sha256(parse_json_object(old.content)) == canonical_json_sha256(artifact) else canonical_json_bytes(artifact)
        documents.append(ModelDocument(artifact_path(artifact['artifact_type'],artifact['id'],model.configuration.id_prefix), raw))
    documents = tuple(sorted(documents,key=lambda d:d.path))
    registered, missing = _gates(gates,policy,plan,model)
    resources = ValidationResources(model.configuration_bytes, registry=model.language_registry,
        profile_resources=model.profile_resources,
        core_key=model.profile.profile_chain[0], cli_profiles=model.profile.profile_chain[1:],
        language_packages=model.language_packages)
    report = validate_model(documents, profile=model.profile, gates=registered, resources=resources)
    report = _empty_target_gates(report, registered, model.profile)
    assessment = assess_validation(report, fail_on=model.configuration.data['validation_policy'].get('fail_on','error'),
                                   strict=strict, documents=documents)
    diff, impact = _describe(model, artifacts)
    valid = assessment.passed and report.complete and not missing
    binding = {'version':TARGET_VERSION, 'plan_sha256':plan.sha256, 'base_model_root':base.sha256,
        'target_model_root':target.sha256, 'resources_sha256':model.resources_sha256,
        'validation_input_sha256':report.data['input_sha256'], 'command':policy.data(),
        'strict':strict, 'source_files':[{'path':p,'sha256':sha256(b).hexdigest()}
                                      for p,b in sorted(model.source_files.items())]}
    return TargetAssessment._create({'format_version':TARGET_VERSION,
        'input_sha256':canonical_json_sha256(binding), 'binding':binding,
        'base_manifest':base.data, 'target_manifest':target.data,
        'target_validated':bool(valid), 'checks_complete':report.complete and not missing,
        'missing_command_gates':missing,
        'validation':assessment.as_dict(), 'diff':diff, 'impact':impact,
        'lifecycle':{'metadata_applied':folded.metadata_applied, 'decisions':folded.decisions,
                     'history_complete':False, 'previously_approved_ids':folded.previously_approved_ids},
        'validation_scope':'complete_supplied_project_target', 'project_files_verified':False,
        'atomic_snapshot':False, 'transaction_prepared':False, 'execution_ready':False,
        'approval_granted':False, 'write_authorized':False},plan,documents)


def prepare_change_target(model, operations, *, change_plan_id, request_id, actor,
        planned_at, scope_descriptor, metadata_policy_version, policy, gates=(),
        preconditions=(), strict=False):
    """Create a regular plan from explicit inputs, then use the saved-plan path.

    No ID/time/user discovery. Both entry paths run the same full target gates.
    An invalid target can be inspected, never passed off as a prepared write.
    Operations are explicit prepared data, not raw CLI drafts: create payloads
    must satisfy the existing plan contract, including bound creation metadata.
    """
    if type(model) is not TargetModel or type(policy) is not TargetPolicy:
        raise TargetError('target_model_policy_required')
    from .values import ChangeOperation
    from ._patch_values import _snapshot
    model = model.snapshot()
    scope = _project_scope(scope_descriptor)
    operations = [ChangeOperation(v).data for v in _sequence(operations, 'target_operations_required')]
    preconditions = _snapshot(list(_sequence(preconditions, 'target_preconditions_required')), '/preconditions').data
    folded = prepare_change_lifecycle(model.artifacts, operations,
        metadata_policy_version=metadata_policy_version, actor=actor, planned_at=planned_at,
        preconditions=preconditions, source_files=model.source_files, **model.reservations)
    plan = prepare_change_plan({'format_version':'1.2.0',
        'metadata_policy_version':metadata_policy_version, 'change_plan_id':change_plan_id,
        'request_id':request_id, 'actor':actor, 'planned_at':planned_at,
        'base':{'scope_descriptor':scope, 'model_root_sha256':model.manifest(model.artifacts,scope).sha256},
        'operations':operations, 'preconditions':preconditions,
        'result_artifacts':[{'artifact':c.data, 'sha256':c.candidate_sha256} for c in folded.candidates],
        'expected_result':{'model_root_sha256':model.manifest(folded.artifacts,scope).sha256}})
    return assess_change_target(plan, model, policy=policy, gates=gates, strict=strict)
