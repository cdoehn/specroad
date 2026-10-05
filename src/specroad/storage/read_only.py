"""Project-bound read-only validation/lint and model-independent diagnostics.

No cache, lock file, journal, output file or repair is created here. Operational
metadata is observed conservatively: unresolved entries are never interpreted as
completed transactions. The transaction/lock engines and full CLI preflight have
their own later contracts. These observations do not authorize writes and are
not an OS sandbox for explicitly supplied trusted Python validation callbacks."""
from __future__ import annotations
from hashlib import sha256
from ..model.errors import ModelError
from ..security import ProjectBoundary, SafetyViolation
from ..profiles.composition import compose_profiles
from ..validation import validate_model, assess_validation, ValidationResources
from ..lint import Glossary, LiteralPolicy, LiteralLintError, lint_literals, lint_core
from ..lint.reporting import lint_findings_report
from ..graph.relations import SourceRelations
from .domain_artifact import DomainArtifact
from .json_syntax import parse_json_object
from .read_only_values import READ_ONLY_VERSION, ReadOnlyResult
from ._read_only_reporting import _base, _failure, _blocked
from ._read_only_inputs import (_operational_metadata, _source, _ready,
                                 _capture_documents, _record_freshness)
from .language_registry import read_language_registry, require_registry_current

__all__ = ["READ_ONLY_VERSION", "ReadOnlyResult", "diagnose_read_only",
           "validate_project_read_only", "lint_project_read_only"]

def diagnose_read_only(root):
    """Inspect a blocked project's available metadata without loading its model.

    This succeeds as a metadata query even when recovery is required; it does
    not report a valid model or clear a lock. No config/artefact is opened.
    """
    data = _base("diagnose")
    try:
        data["phase"] = "operational"
        boundary = ProjectBoundary(root)
        first = _operational_metadata(boundary)
        if _operational_metadata(boundary) != first:
            raise ModelError("operational_metadata_changed")
        data.update(status="completed", exit_code=0, operational=first)
        return ReadOnlyResult._create(data)
    except (ModelError, OSError, SafetyViolation) as error:
        return _failure(data, error)


def validate_project_read_only(root, *, profile_resources, core_key, cli_profiles=(),
                               selected_ids=None, gates=(), fail_on="error", strict=False,
                               expected_project_id=None):
    """Validate current artifact sources with no project/operational writes.

    Profiles and semantic gates are explicitly supplied, never auto-discovered
    Python code. Composition occurs before artifact loading. This is a library
    reader; CLI selection, full resource/profile discovery and lock ownership
    resolution are not silently emulated. Missing semantic gates remain missing.
    """
    data = _base("validate")
    try:
        if type(fail_on) is not str or fail_on not in ("error", "warning") or type(strict) is not bool:
            raise ModelError("read_only_fail_policy_invalid")
        source, observation = _source(root, data, expected_project_id)
        if source is None:
            return _blocked(data, observation)
        data["phase"] = "language_resources"
        registry = (read_language_registry(source)
                    if source.configuration.data.get("language_registry") is not None else None)
        resources = ValidationResources(source.configuration_bytes, registry=registry)
        data["phase"] = "profiles"
        profile = compose_profiles(profile_resources, core_key=core_key,
            project_profiles=source.configuration.data["profiles"], cli_profiles=cli_profiles,
            language_registry=registry)
        data["phase"] = "operational"
        if not _ready(source, observation, data):
            return _blocked(data, data["operational"])
        data["phase"] = "model"
        data["normal_operation_started"] = True
        documents = _capture_documents(source)
        data["model_loaded"] = True
        data["source_bindings"] = [{"path": d.path, "sha256": sha256(d.content).hexdigest()} for d in documents]
        report = validate_model(documents, profile=profile, selected_ids=selected_ids,
                                gates=gates, resources=resources)
        assessment = assess_validation(report, fail_on=fail_on, strict=strict, documents=documents)
        if registry is not None:
            require_registry_current(source, registry)
        _record_freshness(source, observation, documents, data)
        data.update(status="completed", passed=assessment.passed, exit_code=assessment.exit_code,
                    checks_complete=report.complete, validation=assessment.as_dict())
        return ReadOnlyResult._create(data)
    except (ModelError, OSError, SafetyViolation) as error:
        return _failure(data, error)


def lint_project_read_only(root, *, policy, selected_ids, fail_on="error", strict=False,
                           expected_project_id=None, profile_resources=None,
                           core_key=None, cli_profiles=()):
    """Run Core minima/rationale and explicit literal lint over selected IDs.

    All current sources are captured to avoid silently incomplete references.
    A nonmatching language policy is not a passed whole-project lint run.
    Active project profiles require explicit resources; omission has no fallback.
    No optional analyzer, locale resolution or executable project input is used.
    Missing literal prerequisites leave the Core findings visible but incomplete.
    """
    data = _base("lint")
    try:
        if type(policy) is not LiteralPolicy:
            raise ModelError("read_only_literal_policy_required")
        if (type(selected_ids) not in (tuple, list) or not selected_ids
                or any(type(i) is not str or not i for i in selected_ids)
                or len(set(selected_ids)) != len(selected_ids)):
            raise ModelError("read_only_lint_selection_required")
        if type(fail_on) is not str or fail_on not in ("error", "warning") or type(strict) is not bool:
            raise ModelError("read_only_fail_policy_invalid")
        if type(cli_profiles) not in (tuple, list) or any(type(k) is not str for k in cli_profiles):
            raise ModelError("read_only_lint_profile_selection_required")
        selected_ids = tuple(sorted(selected_ids))
        source, observation = _source(root, data, expected_project_id)
        if source is None:
            return _blocked(data, observation)
        data["phase"] = "profiles"
        profile = None
        if profile_resources is None:
            if core_key is not None or cli_profiles or source.configuration.data["profiles"]:
                raise ModelError("read_only_lint_profile_resources_required")
        else:
            profile = compose_profiles(profile_resources, core_key=core_key,
                project_profiles=source.configuration.data["profiles"], cli_profiles=cli_profiles)
        data["phase"] = "operational"
        if not _ready(source, observation, data):
            return _blocked(data, data["operational"])
        data["phase"] = "model"
        data["normal_operation_started"] = True
        documents = _capture_documents(source)
        data["model_loaded"] = True
        data["source_bindings"] = [{"path": d.path, "sha256": sha256(d.content).hexdigest()} for d in documents]
        indexed, terms = {}, []
        for document in documents:
            value = parse_json_object(document.content, path=document.path)
            identity = value.get("id")
            if type(identity) is not str:
                raise ModelError("artifact_id_required", path=document.path)
            if identity in indexed:
                raise ModelError("duplicate_artifact_id", path=document.path)
            indexed[identity] = document, value
            if value.get("artifact_type") == "term":
                terms.append(DomainArtifact(document.content, expected_type="term", path=document.path))
        glossary = Glossary(terms)
        for identity in selected_ids:
            if identity not in indexed:
                raise ModelError("read_only_selected_id_missing")
        core = lint_core(tuple(SourceRelations(d.content, path=d.path) for d in documents),
                         selected_ids=selected_ids, profile=profile, fail_on=fail_on, strict=strict)
        results, unavailable = [], []
        for identity in selected_ids:
            document, value = indexed[identity]
            try:
                result = lint_literals(value, glossary=glossary, policy=policy, path=document.path)
            except LiteralLintError as error:
                if error.reason not in ("literal_declared_language_required", "literal_selected_term_missing"):
                    raise
                unavailable.append({"artifact_id": identity, "path": document.path,
                    "reason": error.reason, "pointer": error.pointer, "scope": "literal_checks"})
                continue
            results.append(result)
            if result["literal_checks_passed"] is None:
                unavailable.append({"artifact_id": identity, "path": document.path,
                    "reason": "no_applicable_literal_checks", "pointer": "", "scope": "literal_checks"})
        _record_freshness(source, observation, documents, data)
        findings = [finding for result in results for finding in result["diagnostics"]]
        findings.extend(core["diagnostics"])
        assessment = lint_findings_report(findings, fail_on=fail_on, strict=strict)
        failure = not assessment["findings_passed"]
        applicable = not unavailable
        data.update(status="completed" if applicable else "incomplete",
                    passed=(False if failure else True if applicable else None),
                    checks_complete=applicable, exit_code=(1 if failure else 0) if applicable else 5,
                    lint={"scope": "selected_core_and_literal_lint", "checked_ids": list(selected_ids),
                          "policy_sha256": policy.sha256, "glossary_sha256": glossary.sha256,
                          "unavailable": unavailable, "reports": results, "core": core,
                          **assessment})
        return ReadOnlyResult._create(data)
    except (ModelError, OSError, SafetyViolation) as error:
        return _failure(data, error)
