"""Real shipped profiles and offline bytes for productive validation adapters."""
from types import SimpleNamespace

from specroad.changes import TargetModel
from specroad.model.canonical import canonical_json_bytes
from specroad.model.model_manifest import ProjectReadBinding
from specroad.model.paths import artifact_path
from specroad.profiles import compose_profiles
from specroad.storage.language_registry import bundled_language_registry, registry_binding
from specroad.storage.profiles import load_bundled_profile
from specroad.validation import ModelDocument, ValidationResources
from .model import configuration_value, put
from .profile_composition import profile


def inputs(values, *, software="software-en@0.2.0", rules=(), registry_present=True, **config):
    registry = bundled_language_registry() if registry_present else None
    profiles = [load_bundled_profile("core@0.2.0"), load_bundled_profile(software)]
    if rules:
        profiles.append(profile("local", lint_rules=list(rules)))
    configuration = configuration_value(profiles=[p.key for p in profiles[1:]],
        language_policy={"allowed_ranges": ["en"]},
        **({"language_registry": registry_binding(registry)} if registry is not None else {}))
    configuration.update(config)
    raw = canonical_json_bytes(configuration)
    effective = compose_profiles(profiles, core_key=profiles[0].key,
        project_profiles=configuration["profiles"], language_registry=registry)
    documents = tuple(ModelDocument(artifact_path(v["artifact_type"], v["id"], "SR"),
                                    canonical_json_bytes(v)) for v in values)
    files = [ModelDocument("profiles/" + p.profile_id + ".json", p.source_bytes) for p in profiles]
    if registry is not None:
        files.append(ModelDocument(configuration["language_registry"]["path"], registry.source_bytes))
    return SimpleNamespace(configuration=configuration, configuration_bytes=raw, documents=documents,
        profile=effective, profiles=profiles, files=tuple(files), registry=registry,
        resources=ValidationResources(raw, registry=registry))


def write_project(root, data):
    put(root, "specroad.json", data.configuration_bytes)
    for document in (*data.documents, *data.files):
        put(root, document.path, document.content)


def target_model(data):
    return TargetModel(data.configuration_bytes, ProjectReadBinding("sample", "/explicit/provider", (1, 2)),
        data.documents, profile=data.profile, resource_files=data.files)
