"""Native qualification adapter for the common guarded writer.

Normal ChangePlan adapters share this writer. Snapshot/bootstrap integration
is a separate adapter; qualification and file effects remain common.
There is no recovery or resume branch in this path.
"""
from types import SimpleNamespace
from ..storage.json_syntax import parse_json_object as parsed
from ..storage.resource_discovery import current_json_paths
from ..model.paths import CURRENT_JSON_CLASSES
from ..validation import ModelDocument, validate_model, assess_validation
from ._target_materialization import materialize_target, validation_resources
from ._target_checks import _gates, _empty_target_gates
from .publication_check import recheck_publication, _same_request
from .publication_values import PublicationPreflight, PublicationAuthority
from .write_guard_values import require
from ._guarded_publication import _Inputs, _run as _publish


def _checkpoint(event):
    """Internal fault-injection boundary; never loaded from project data."""


def _run(inputs, held):
    return _publish(inputs, held, checkpoint=_checkpoint)


def publish_guarded_change(preflight, *, held_lock, authority, gates=()):
    """Publish a complete native checked change in the caller's actual lock."""
    require(type(preflight) is PublicationPreflight and type(authority) is PublicationAuthority,
            'native_write_inputs_required',exit_code=2)
    gates=tuple(gates);request=preflight.request;plan=request.plan;model=preflight._model
    recheck_publication(preflight,request,held_lock=held_lock,
        transaction_id=held_lock.record.data['transaction_id'],authority=authority,gates=gates)
    before={**model.source_files,**{d.path:d.content for d in preflight._package_files}}
    target={**before,**{d.path:d.content for d in request.documents}}
    def inventory_check(expected):
        from ..model.configuration import ProjectConfiguration
        config=ProjectConfiguration(parsed(expected['specroad.json']))
        from ..model.paths import classify_path
        source=SimpleNamespace(boundary=held_lock._files.boundary,configuration=config,
                               classify=lambda p:classify_path(p,config))
        require(current_json_paths(source)==tuple(sorted(p for p in expected if source.classify(p) in CURRENT_JSON_CLASSES)),
                'write_inventory_changed',exit_code=6)
    def qualify(actual):
        documents=tuple(ModelDocument(p,actual[p]) for p in sorted(actual) if p in model.source_files or p in {d.path for d in request.documents})
        result=materialize_target(model,documents)
        require(result.manifest(result.artifacts,plan.data['base']['scope_descriptor']).sha256==request.data['target_root_sha256'],
                'write_target_root_changed',exit_code=6)
        registered,missing=_gates(gates,preflight._policy,plan,result)
        report=_empty_target_gates(validate_model(result.documents,profile=result.profile,gates=registered,
                resources=validation_resources(result)),registered,result.profile)
        assessment=assess_validation(report,fail_on=result.configuration.data['validation_policy'].get('fail_on','error'),
                                    strict=preflight._strict,documents=result.documents)
        require(not missing and report.complete and assessment.passed,'write_target_invalid',exit_code=3)
        detached=request.detached();allowed=authority.check(detached);_same_request(detached,request)
        require(type(allowed) is bool and allowed,'write_authority_denied',exit_code=7)
        return report.data
    inputs=_Inputs(plan,model.binding.project_id,request.data['authoring_binding']['command_id'],before,target,inventory_check,qualify)
    try:
        return _run(inputs,held_lock)
    except OSError as error:
        from .write_guard_values import WriteGuardError
        raise WriteGuardError('publication_io_failure', exit_code=5) from error
