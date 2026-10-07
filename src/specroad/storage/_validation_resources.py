"""Explicit project profile paths and exact read observations, never discovery."""
from ..model.errors import ModelError
from ..validation.values import ModelDocument
from .profiles import read_profile


def capture_profile_files(source, resources, profile, paths):
    if paths is None:
        return None  # Supplied byte values carry no claim about files on disk.
    if (type(paths) is not dict or set(paths) != set(profile.profile_chain)
            or any(type(p) is not str for p in paths.values())):
        raise ModelError("read_only_profile_paths_required")
    if len({p.casefold() for p in paths.values()}) != len(paths):
        raise ModelError("read_only_duplicate_profile_path")
    index = {p.key: p for p in resources}
    documents = []
    for key in profile.profile_chain:
        expected = index[key]
        actual = read_profile(source, paths[key], expected_key=key, expected_sha256=expected.sha256)
        if actual.source_bytes != expected.source_bytes:
            raise ModelError("read_only_profile_observation_changed", path=paths[key])
        documents.append(ModelDocument(paths[key], actual.source_bytes))
    return tuple(sorted(documents, key=lambda d: d.path))


def require_profile_files_current(source, documents):
    for document in documents or ():
        if source.read_normative(document.path) != document.content:
            raise ModelError("read_only_resource_changed", path=document.path)
