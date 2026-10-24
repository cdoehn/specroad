"""Data oracles shared by format roundtrips and durable import continuations.

Callers supply independently expected records, bytes and statuses. These
checks do not infer missing data from the original model or inspect rendering.
"""
from hashlib import sha256

from specroad.graph.relations import SourceRelations
from specroad.graph.review_status import RelationReviewStatuses
from specroad.model.canonical import canonical_json_bytes


def assert_records_equal(actual, expected):
    """Compare complete decoded records by identity without dropping duplicates."""
    observed = {}
    for value in actual:
        assert value['id'] not in observed
        observed[value['id']] = value
    assert observed == {value['id']: value for value in expected}
    return observed


def assert_attachment_transport(exported, transported, attachments, files):
    """Check real payload bytes and the machine-readable export bindings."""
    assert transported == {f.path: f.content for f in files}
    assert exported.manifest['attachments'] == [
        {**a.data, 'included': True} for a in sorted(attachments, key=lambda a: a.path)]
    assert exported.manifest['output_sha256'] == sha256(exported.output_bytes).hexdigest()


def assert_review_status(records, source_id, relation_id, expected_status, *, selected_review_id=...):
    """Recompute native review context; transported records grant no approval."""
    sources = tuple(SourceRelations(canonical_json_bytes(value)) for value in records)
    statuses = RelationReviewStatuses(sources)
    result = statuses.for_relation(source_id, relation_id)
    assert result.status == expected_status and statuses.approval_granted is False
    if selected_review_id is not ...:
        assert result.selected_review_id == selected_review_id
    return result


def assert_import_plan_equal(report, expected_bytes):
    """Compare the entire canonical plan, including losses and diagnostics."""
    assert canonical_json_bytes(report) == expected_bytes
