"""Core semantic applicability and explicit field-reference dependencies.

No validators are imported from data. Field references are enumerated only from
known validated contracts; arbitrary strings never cause dependency discovery.
"""
from __future__ import annotations

from ..model.errors import ModelError
from ..graph.references import _check_endpoints

def _issue(error, artifact_id=None, path=None):
    return {**error.diagnostic(), "artifact_id": artifact_id,
            "path": error.path if error.path is not None else path, "severity": "error"}


def _applies(hook, data, profile):
    kind, maturity = data["artifact_type"], data["maturity"]
    if hook == "lifecycle":
        return maturity != "draft" or kind in ("proposal", "baseline", "evidence", "relation_review")
    if hook == "baseline_integrity":
        return kind == "baseline"
    if hook == "evidence_currentness":
        return kind in ("evidence", "verification", "test")
    if hook == "review_currentness":
        return kind == "relation_review" or (kind == "requirement" and maturity == "approved")
    if hook == "profile_lint":
        return profile is not None and bool(profile.data["merge"]["lint_rules"])
    if hook == "language_policy":
        return "language" in data
    if hook == "document_model":
        return kind in ("document", "section", "content_block", "view")
    if hook == "external_resources":
        return kind in ("source", "code_ref") or bool(data.get("attachments"))
    if hook == "configuration":
        return kind == "configuration" or "applicability" in data
    return hook.startswith("extension:")


def _field_targets(record, relations=None):
    """Declared fields only; review endpoint dependencies need resolved relations."""
    data = record.data
    kind = data["artifact_type"]
    candidates = []
    if kind == "interface":
        candidates.extend((data[k], "/" + k, "component") for k in ("source_component", "target_component"))
    if kind == "verification":
        candidates.extend((v, "/subjects/" + str(i), None) for i, v in enumerate(data["subjects"]))
        candidates.extend((v["test_id"], "/evidence_slots/" + str(i) + "/test_id", "test")
                          for i, v in enumerate(data["evidence_slots"]) if v["test_id"] is not None)
    if kind == "evidence":
        candidates.extend((v["artifact_id"], "/subjects/" + str(i) + "/artifact_id", None)
                          for i, v in enumerate(data["subjects"]))
        if data["run_context"] is not None and data["run_context"]["test_id"] is not None:
            candidates.append((data["run_context"]["test_id"], "/run_context/test_id", "test"))
    if kind == "configuration" and data.get("parent") is not None:
        candidates.append((data["parent"], "/parent", "configuration"))
    if kind == "relation_review" and relations is not None:
        relation = relations.get(data["relation_id"])
        if relation is None:
            raise ModelError("validation_review_relation_missing", path=record.path, pointer="/relation_id")
        candidates.extend((v, "/relation_id", None) for v in (relation.source.id, relation.target.id))
    for i, provenance in enumerate(data.get("provenance", ())):
        if provenance.get("source_id") is not None:
            candidates.append((provenance["source_id"], "/provenance/" + str(i) + "/source_id", "source"))
    if data.get("verification_waiver") is not None:
        candidates.append((data["verification_waiver"]["human_review_id"], "/verification_waiver/human_review_id", "relation_review"))
    return candidates


def _reference_issues(records):
    """Collect safe reference observations before any graph-dependent work.

    Source or relation identity conflicts stop target lookup for the entire
    supplied inventory. Each independent target error retains its own source
    location; no missing target is synthesized as an ArtifactIdentity.
    """
    index, issues = {}, []
    prefix = records[0].identity.id_prefix if records else None
    for record in records:
        if record.identity.id_prefix != prefix:
            issues.append(_issue(ModelError("mixed_project_prefix", path=record.path), record.identity.id))
        if record.identity.id in index:
            issues.append(_issue(ModelError("duplicate_artifact_id", path=record.path, pointer="/id"),
                                 record.identity.id))
        index[record.identity.id] = record
    if issues:
        return issues
    relation_ids, external_keys = set(), set()
    for record in records:
        for position, relation in enumerate(record.relations):
            pointer = "/relations/" + str(position)
            if relation.identity.id in relation_ids:
                issues.append(_issue(ModelError("duplicate_relation_id", path=record.path,
                    pointer=pointer + "/relation_id"), record.identity.id))
            relation_ids.add(relation.identity.id)
            for external_position, external in enumerate(relation.data["external_identities"]):
                key = tuple(external[name] for name in ("source_system", "source_document", "external_id"))
                if key in external_keys:
                    issues.append(_issue(ModelError("duplicate_external_relation_identity", path=record.path,
                        pointer=pointer + "/external_identities/" + str(external_position)), record.identity.id))
                external_keys.add(key)
    if issues:
        return issues
    for record in records:
        for position, relation in enumerate(record.relations):
            target = index.get(relation.target)
            try:
                if target is None:
                    raise ModelError("missing_relation_target", pointer="/target")
                _check_endpoints(relation, record.identity, target.identity)
            except ModelError as error:
                error.path = record.path
                error.pointer = "/relations/" + str(position) + error.pointer
                issues.append(_issue(error, record.identity.id))
    for record in records:
        data = record.data
        # Missing review relations are independent facts. A present relation's
        # endpoints are checked above; an invalid one never creates a secondary
        # missing-review or fabricated endpoint finding.
        if data["artifact_type"] == "relation_review" and data["relation_id"] not in relation_ids:
            issues.append(_issue(ModelError("validation_review_relation_missing", path=record.path,
                pointer="/relation_id"), record.identity.id))
        for target, pointer, target_kind in _field_targets(record):
            reason = None
            if target not in index:
                reason = "validation_field_target_missing"
            elif target_kind is not None and index[target].identity.artifact_type != target_kind:
                reason = "validation_field_target_type"
            if reason is not None:
                issues.append(_issue(ModelError(reason, path=record.path, pointer=pointer), record.identity.id))
    return issues


def _foreign_edges(records, references):
    """Only declared Core reference fields; never scan arbitrary strings/Extensions."""
    index = {r.identity.id: r for r in records}
    relations = {e.relation.identity.id: e for e in references.relations}
    edges = []
    for record in records:
        source = record.identity.id
        for target, pointer, target_kind in _field_targets(record, relations):
            if target not in index:
                raise ModelError("validation_field_target_missing", path=record.path, pointer=pointer)
            if target_kind is not None and index[target].identity.artifact_type != target_kind:
                raise ModelError("validation_field_target_type", path=record.path, pointer=pointer)
            edges.append((source, target))
    return edges
