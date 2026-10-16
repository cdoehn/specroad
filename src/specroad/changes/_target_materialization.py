"""Rebuild target inputs from exact supplied publication documents, without I/O."""
from .target_model import TargetModel
from ..validation import ValidationResources
from ..model.paths import classify_path, PathClass


def materialize_target(model, documents):
    """Combine a checked write set with unchanged, independently bound sources.

    Existing resource/configuration replacement is representation-only in the
    supported planner. TargetModel recomputes identities and profile bindings;
    this helper grants no permission to edit arbitrary resources or their values.
    """
    configuration = model.configuration_bytes
    artifacts = {d.path: d for d in model.documents}
    resources = {d.path: d for d in model.resource_files}
    for document in documents:
        if document.path == 'specroad.json':
            configuration = document.content
        elif (document.path in resources or
              classify_path(document.path, model.configuration) is PathClass.ARCHIVE_OBJECT):
            resources[document.path] = document
        else:
            artifacts[document.path] = document
    return TargetModel(configuration, model.binding, tuple(artifacts.values()),
        profile=model.profile, resource_files=tuple(resources.values()),
        attachments=model.attachment_descriptors, language_packages=model.language_packages,
        **model.reservations)


def validation_resources(model):
    return ValidationResources(model.configuration_bytes, registry=model.language_registry,
        profile_resources=model.profile_resources,
        core_key=model.profile.profile_chain[0], cli_profiles=model.profile.profile_chain[1:],
        language_packages=model.language_packages)


def publication_target(preflight):
    return materialize_target(preflight._model, preflight.request.documents)
