"""Project-bound read-only validation/lint and model-independent diagnostics.

No cache, lock file, journal, output file or repair is created here. Operational
metadata is observed conservatively: unresolved entries are never interpreted as
completed transactions. The transaction/lock engines and full CLI preflight have
their own later contracts. These observations do not authorize writes and are
not an OS sandbox for explicitly supplied trusted Python validation callbacks.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.paths import PathClass, artifact_path
from ..security import ProjectBoundary, SafetyViolation
from ..security.resource_access import directory_entries
from ..profiles.composition import compose_profiles
from ..profiles.composition_values import ProfileCompositionError
from ..validation import ModelDocument, validate_model, assess_validation
from ..lint import Glossary, LiteralPolicy, lint_literals
from .domain_artifact import DomainArtifact
from .json_syntax import parse_json_object
from .project import ProjectSource
from .resource_discovery import current_json_paths

READ_ONLY_VERSION = "project-read-only-v1"


@dataclass(frozen=True, init=False)
class ReadOnlyResult:
    """Detached report, never a permission to publish or a whole-project approval."""
    _encoded: bytes

    def __init__(self, *args, **kwargs):
        raise TypeError("Use the project read-only entry functions")

    @classmethod
    def _create(cls, value):
        result = object.__new__(cls)
        object.__setattr__(result, "_encoded", canonical_json_bytes(value))
        return result

    @property
    def data(self):
        return parse_json_object(self._encoded)

    @property
    def passed(self):
        return self.data["passed"] is True

    @property
    def exit_code(self):
        return self.data["exit_code"]

    def __bool__(self):
        raise TypeError("Use result.passed explicitly")


def _operational_metadata(boundary):
    """Only shallow names/types of active locations; no journal/cache contents.

    An empty/absent active namespace permits an observation, not an ownership
    proof. Unknown operational files can be writer/lock metadata: keep them and
    block normal reads until the appropriate later resolver can assess them.
    Completed receipts and caches are not required input to this read path.
    """
    entries = directory_entries(boundary, ".specroad", missing_ok=True)
    observed, unresolved, unknown = [], [], []
    for name, directory in (() if entries is None else entries):
        path = ".specroad/" + name
        observed.append({"path": path, "directory": directory})
        if directory and name in ("cache", "requests"):
            continue
        if directory and name in ("transactions", "recovery"):
            for child, is_directory in directory_entries(boundary, path):
                logical = path + "/" + child
                observed.append({"path": logical, "directory": is_directory})
                if name == "transactions" and child == "receipts" and is_directory:
                    continue
                unresolved.append(logical)
        else:
            unknown.append(path)
    state = "recovery_required" if unresolved else "unknown" if unknown else "consistent"
    return {"consistency_state": state, "recovery_required": bool(unresolved),
            "unresolved_paths": sorted(unresolved), "unknown_paths": sorted(unknown),
            "observed_entries": sorted(observed, key=lambda v: v["path"]),
            "writer_owner": None, "writer_ownership_verified": False,
            "journal_contents_loaded": False, "cache_contents_loaded": False,
            "recovery_performed": False, "model_loaded": False,
            "inspection_scope": "shallow_operational_entries", "atomic_snapshot": False}


def _base(operation):
    return {"format_version": READ_ONLY_VERSION, "operation": operation,
            "passed": None, "checks_complete": False, "exit_code": 5, "status": "blocked",
            "normal_operation_started": False, "model_loaded": False,
            "project_id": None, "read_only": True, "project_complete": False,
            "write_authorized": False, "approval_granted": False,
            "atomic_snapshot": False, "operational": None, "diagnostics": [],
            "source_bindings": [], "validation": None, "lint": None}


def _failure(data, error):
    if isinstance(error, ModelError):
        diagnostic = error.diagnostic()
        code = 3
    elif isinstance(error, SafetyViolation):
        diagnostic = {"reason": "unsafe_project_read"}
        code = 5
    else:
        diagnostic = {"reason": "project_read_unavailable", "errno": error.errno}
        code = 5
    data.update(status="failed", passed=False, exit_code=code,
                validation=None, lint=None, diagnostics=[diagnostic])
    return ReadOnlyResult._create(data)


def _blocked(data, observation):
    data["operational"] = observation
    data["diagnostics"] = [{"code": "SRV168" if observation["recovery_required"] else "READ_STATE_UNKNOWN",
        "reason": "recovery_required" if observation["recovery_required"] else "operational_state_unresolved",
        "severity": "error"}]
    return ReadOnlyResult._create(data)


def diagnose_read_only(root):
    """Inspect a blocked project's available metadata without loading its model.

    This succeeds as a metadata query even when recovery is required; it does
    not report a valid model or clear a lock. No config/artefact is opened.
    """
    data = _base("diagnose")
    try:
        boundary = ProjectBoundary(root)
        first = _operational_metadata(boundary)
        if _operational_metadata(boundary) != first:
            raise ModelError("operational_metadata_changed")
        data.update(status="completed", exit_code=0, operational=first)
        return ReadOnlyResult._create(data)
    except (ModelError, OSError, SafetyViolation) as error:
        return _failure(data, error)


def _artifact_names(source):
    return tuple(path for path in current_json_paths(source)
                 if source.classify(path) is PathClass.ARTIFACT)


def _capture_documents(source):
    names = _artifact_names(source)
    documents = tuple(ModelDocument(name, source.read_normative(name)) for name in names)
    # Invalid JSON/schema values are diagnosed by validate_model, not repaired.
    for document in documents:
        try:
            value = parse_json_object(document.content, path=document.path)
        except ModelError:
            continue
        if type(value.get("id")) is str and type(value.get("artifact_type")) is str:
            expected = artifact_path(value["artifact_type"], value["id"], source.configuration.id_prefix)
            if expected != document.path:
                raise ModelError("artifact_path_identity_mismatch", path=document.path)
    return documents


def _fresh(source, operational, documents):
    source.check_current()
    if _operational_metadata(source.boundary) != operational:
        raise ModelError("operational_metadata_changed")
    if _artifact_names(source) != tuple(document.path for document in documents):
        raise ModelError("read_only_membership_changed")
    for document in documents:
        if source.read_normative(document.path) != document.content:
            raise ModelError("read_only_source_changed", path=document.path)
    source.check_current()
    if _operational_metadata(source.boundary) != operational:
        raise ModelError("operational_metadata_changed")


def _source(root, data, expected_project_id):
    boundary = ProjectBoundary(root)
    observation = _operational_metadata(boundary)
    data["operational"] = observation
    if observation["consistency_state"] != "consistent":
        return None, observation
    source = ProjectSource(boundary.root, expected_project_id=expected_project_id)
    # ProjectSource creates its own capability. Reject replacement in between.
    boundary._check_root()
    if boundary._root_identity != source.boundary._root_identity:
        raise ModelError("read_only_project_replaced")
    data["project_id"] = source.configuration.project_id
    return source, observation


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
        profile = compose_profiles(profile_resources, core_key=core_key,
            project_profiles=source.configuration.data["profiles"], cli_profiles=cli_profiles)
        data["normal_operation_started"] = True
        documents = _capture_documents(source)
        data["model_loaded"] = True
        data["source_bindings"] = [{"path": d.path, "sha256": sha256(d.content).hexdigest()} for d in documents]
        report = validate_model(documents, profile=profile, selected_ids=selected_ids, gates=gates)
        assessment = assess_validation(report, fail_on=fail_on, strict=strict, documents=documents)
        _fresh(source, observation, documents)
        data.update(status="completed", passed=assessment.passed, exit_code=assessment.exit_code,
                    checks_complete=report.complete, validation=assessment.as_dict())
        return ReadOnlyResult._create(data)
    except (ModelError, OSError, SafetyViolation) as error:
        return _failure(data, error)


def lint_project_read_only(root, *, policy, selected_ids, fail_on="error", strict=False,
                           expected_project_id=None):
    """Run only explicit literal lint over selected IDs and stored glossary terms.

    All current sources are captured to avoid silently incomplete references.
    A nonmatching language policy is not a passed whole-project lint run.
    No optional analyzer, locale resolution or executable project input is used.
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
        selected_ids = tuple(sorted(selected_ids))
        source, observation = _source(root, data, expected_project_id)
        if source is None:
            return _blocked(data, observation)
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
        results = []
        for identity in selected_ids:
            if identity not in indexed:
                raise ModelError("read_only_selected_id_missing")
            document, value = indexed[identity]
            results.append(lint_literals(value, glossary=glossary, policy=policy, path=document.path))
        _fresh(source, observation, documents)
        findings = [finding for result in results for finding in result["diagnostics"]]
        threshold = {"info": 0, "warning": 1, "error": 2}["warning" if strict else fail_on]
        failure = any({"info": 0, "warning": 1, "error": 2}[f["severity"]] >= threshold for f in findings)
        applicable = all(r["literal_checks_passed"] is not None for r in results)
        data.update(status="completed", passed=(not failure if applicable else None),
                    checks_complete=applicable, exit_code=3 if failure else 0,
                    lint={"scope": "selected_literal_fields_only", "checked_ids": list(selected_ids),
                          "policy_sha256": policy.sha256, "glossary_sha256": glossary.sha256,
                          "reports": results, "diagnostics": findings})
        return ReadOnlyResult._create(data)
    except (ModelError, OSError, SafetyViolation) as error:
        return _failure(data, error)
