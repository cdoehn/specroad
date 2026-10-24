"""Derive ordinary Change Plan operations from owned artifact candidates.

The caller supplies the model snapshot, selected mapping and explicit source
metadata. This adapter neither parses source bytes nor performs target checks
or writes; all formats share the same candidate and conflict contracts.
"""
from dataclasses import dataclass

from ..changes._patch_policy import _mutable_pointer
from ..graph.relations import SourceRelations
from ..model.canonical import canonical_json_bytes, canonical_json_sha256
from ..model._requirement_inputs import REQUIREMENT_CONTENT_FIELDS, _prepare_requirement_inputs
from .comparison import ImportComparison
from .identities import ExternalIdentity, ImportIdentityError, NativeIdentityIndex


@dataclass
class _CandidateChanges:
    operations: list
    objects: list
    losses: list
    diagnostics: list
    conflicts: list


def _pointer(value):
    return "/" + value.replace("~", "~0").replace("/", "~1")


def _prepare_candidate_changes(model, candidates, selected, *, strategy,
                               input_bytes, planned_at, start_index=0, prior_objects=()):
    resource = selected.resource
    native = NativeIdentityIndex([SourceRelations(d.content, path=d.path) for d in model.documents])
    artifacts = {value["id"]: value for value in model.artifacts}
    operations, objects, losses, diagnostics, conflicts = [], [], [], [], []
    # A resumed window retains the original global positions and claims.
    # Reconstruct only uniqueness indexes; never remap completed candidates.
    keys = {ExternalIdentity(item['identity']).key for item in prior_objects}
    owners = {item['artifact_id'] for item in prior_objects}
    for number, candidate in enumerate(candidates, start=start_index):
        at = "/candidates/" + str(number)
        if type(candidate) is not dict or set(candidate) != {"identity", "external_type", "fields", "new_artifact"}:
            raise ImportIdentityError("import_artifact_candidate_required", pointer=at)
        identity = ExternalIdentity(candidate["identity"])
        if set(identity.data) - {"source_system", "source_document", "external_id", "external_revision"}:
            raise ImportIdentityError("import_source_identity_fields_unsupported", pointer=at + "/identity")
        if identity.key in keys:
            raise ImportIdentityError("duplicate_external_artifact_identity", pointer=at + "/identity")
        keys.add(identity.key)
        mapped = selected.artifact(candidate["external_type"], candidate["fields"])
        projection = mapped["artifact"]
        for name in projection:
            if name == "artifact_type":
                continue
            if name == "external_identities":
                raise ImportIdentityError("import_mapping_identity_mutation", pointer=at + "/fields")
            # Reuse the ordinary update contract, also for new-object mappings.
            _mutable_pointer(_pointer(name), at + "/fields")
        owner = native.lookup("artifact", *identity.key)
        old = None if owner is None else artifacts[owner["artifact_id"]]
        if old is None:
            template = candidate["new_artifact"]
            if type(template) is not dict:
                raise ImportIdentityError("import_creation_envelope_required", pointer=at + "/new_artifact")
            if template.get("artifact_type") != projection["artifact_type"]:
                raise ImportIdentityError("import_native_type_mismatch", pointer=at + "/new_artifact/artifact_type")
            if template.get("external_identities") or template.get("relations"):
                raise ImportIdentityError("import_creation_links_unsupported", pointer=at + "/new_artifact")
            native_id = template.get("id")
        else:
            if candidate["new_artifact"] is not None:
                raise ImportIdentityError("import_known_creation_envelope", pointer=at + "/new_artifact")
            if old["artifact_type"] != projection["artifact_type"]:
                raise ImportIdentityError("import_native_type_mismatch", pointer=at + "/external_type")
            native_id = old["id"]
        if type(native_id) is not str:
            raise ImportIdentityError("import_native_id_required", pointer=at + "/new_artifact/id")
        if native_id in owners:
            raise ImportIdentityError("import_duplicate_native_candidate", pointer=at)
        owners.add(native_id)
        for field, value in sorted(mapped["unmapped"].items()):
            pointer = at + "/fields" + _pointer(field)
            losses.append({"candidate_index": number, "artifact_id": native_id,
                "pointer": pointer, "reason": "unmapped_external_field", "value": value,
                "accepted": False})
            diagnostics.append(ImportIdentityError("unaccepted_import_loss", pointer=pointer).diagnostic())
        # A creation envelope or an existing native value is not a source
        # mapping for the requirement's normative content. Keep absence
        # distinct from an explicitly mapped null/empty value (which is still
        # checked by the ordinary native validator). Configured source-member
        # and value-table errors have already failed in the strict mapper.
        missing_content = [field for field in REQUIREMENT_CONTENT_FIELDS
                           if projection["artifact_type"] == "requirement" and field not in projection]
        for field in missing_content:
            pointer = at + "/fields"
            losses.append({"candidate_index": number, "artifact_id": native_id,
                "pointer": pointer, "reason": "unmapped_requirement_content",
                "target_field": field, "accepted": False})
            diagnostics.append({**ImportIdentityError("unaccepted_import_loss", pointer=pointer).diagnostic(),
                                "target_field": field})
        local = {} if old is None else {key: old[key] for key in projection if key in old}
        comparison = ImportComparison(None if owner is None else owner["identity"],
            mapping_id=resource.key, strategy=strategy, local_projection=local, source_projection=projection).data
        observed = {"candidate_index": number, "artifact_id": native_id,
            "identity": identity.data, "comparison": comparison["comparison"],
            "action": "reject" if missing_content else "create" if old is None else comparison["action"]}
        objects.append(observed)
        diagnostics.extend({**d, "candidate_index": number, "artifact_id": native_id}
                           for d in comparison["diagnostics"])
        if comparison["comparison"] == "diverged":
            conflicts.append({**observed, "code": "SRV148", "resolved": False})
        if missing_content:
            # Do not manufacture content or refresh import history, even in
            # the passive operations of a plan that cannot be executed.
            continue
        if old is not None and comparison["action"] != "adopt":
            # No-op may retain its baseline; skip/retain/reject MUST retain it.
            continue
        if projection["artifact_type"] == "requirement":
            # Use the M2 constructor's input resolution only after the loss
            # gate. No authoring default or new-draft normalization applies
            # to already mapped values, existing identities or import history.
            projection, _, _ = _prepare_requirement_inputs(projection)
        source_identity = identity.data if old is None else {**owner["identity"], **identity.data}
        history = ExternalIdentity(source_identity).with_import_history(mapping_id=resource.key,
            imported_projection=projection, source_projection=projection,
            source_payload=input_bytes, imported_at=planned_at).data
        if old is None:
            value = {**template, **projection, "external_identities": [history]}
            operations.append({"op": "create", "artifact": value, "result_id": native_id})
        else:
            identities = [history if ExternalIdentity(item).key == identity.key else item
                          for item in old["external_identities"]]
            desired = {**projection, "external_identities": identities}
            patch = [{"op": "replace" if key in old else "add", "path": _pointer(key), "value": value}
                     for key, value in sorted(desired.items())
                     if key not in old or canonical_json_bytes(old[key]) != canonical_json_bytes(value)]
            if patch:
                operations.append({"op": "update", "target": native_id,
                    "expected_sha256": canonical_json_sha256(old), "patch": patch})
    return _CandidateChanges(operations, objects, losses, diagnostics, conflicts)
