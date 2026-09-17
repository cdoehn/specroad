"""Read relation records under the existing project/path/identity boundary."""

from ..graph.relations import SourceRelations
from ..model.errors import ModelError
from .artifact_common import read_common_artifact


def read_source_relations(source, path, *, expected_type=None):
    common = read_common_artifact(source, path, expected_type=expected_type)
    result = SourceRelations(common.source_bytes, expected_type=expected_type, path=path)
    # An observed replacement, even with equal semantic values, invalidates
    # this byte-bound read. This is not an atomic snapshot or a write permit.
    if source.read_normative(path) != common.source_bytes:
        raise ModelError("relation_source_changed", path=path)
    source.check_current()
    return result
