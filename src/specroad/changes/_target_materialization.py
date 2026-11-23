"""Rebuild target inputs from exact supplied publication documents, without I/O."""
from .target_model import TargetModel
from ..validation import ValidationResources
from ..model.paths import classify_path, PathClass


def materialize_target(model, documents, *, replace_plan_sources=False):
    """Combine a checked write set with unchanged, independently bound sources.

    Existing resource/configuration replacement is representation-only in the
    supported planner. TargetModel recomputes identities and profile bindings;
    this helper grants no permission to edit arbitrary resources or their values.
    """
    configuration = model.configuration_bytes
    artifacts = {d.path: d for d in model.documents}
    resources = {d.path: d for d in model.resource_files}
    plans = {} if replace_plan_sources else {s.path: s for s in model.plan_sources}
    for document in documents:
        if document.path == 'specroad.json':
            configuration = document.content
        elif classify_path(document.path, model.configuration) is PathClass.PLAN:
            from ..storage.plan_markdown import parse_plan
            plans[document.path] = parse_plan(document.content, path=document.path)
        elif (document.path in resources or
              classify_path(document.path, model.configuration) is PathClass.ARCHIVE_OBJECT):
            resources[document.path] = document
        else:
            artifacts[document.path] = document
    return TargetModel(configuration, model.binding, tuple(artifacts.values()),
        profile=model.profile, resource_files=tuple(resources.values()),
        attachments=model.attachment_descriptors, language_packages=model.language_packages,
        plan_sources=tuple(plans.values()), **model.reservations)


def validation_resources(model):
    return ValidationResources(model.configuration_bytes, registry=model.language_registry,
        profile_resources=model.profile_resources,
        core_key=model.profile.profile_chain[0], cli_profiles=model.profile.profile_chain[1:],
        language_packages=model.language_packages)


def publication_target(preflight):
    model = preflight._model
    files = {**model.source_files, **{d.path: d.content for d in preflight.request.documents}}
    for path in preflight.request.data.get('deleted_paths', []):
        files.pop(path)
    from ..validation import ModelDocument
    return materialize_target(model, tuple(ModelDocument(p, raw) for p, raw in files.items()),
                              replace_plan_sources=True)
