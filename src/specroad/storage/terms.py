"""Explicit, byte-preserving term reads, without automatic glossary discovery."""
from ..model.errors import ModelError
from .domain_artifact import read_domain_artifact
from .project import ProjectSource


def read_term_artifact(source, path):
    if type(source) is not ProjectSource:
        raise ModelError("term_project_source_required", path=path)
    result = read_domain_artifact(source, path, expected_type="term")
    source.check_current()
    if source.read_normative(path) != result.source_bytes:
        raise ModelError("term_changed_during_read", path=path)
    source.check_current()
    return result
