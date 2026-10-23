"""Pure native projection and explicit inverse mapping of ReqIF objects.

Typed source data stays separate from JSON representability. The public
facade supplies numeric conversion and XML validation/encoding boundaries.
No project writer, registry mutation or mapping inference is performed here.
"""
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256

from ..mappings import MappingError, select_mapping
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ..storage.json_syntax import parse_json_object
from .identities import ExternalIdentity
from ._reqif_scalars import _boolean, _compare_numbers, _identifier
from ._reqif_values import REQIF_NAMESPACE, ReqIFError, _Node, _SEP, _replace_node


def _project_value(value, *, number_parser):
    if value.family == "ENUMERATION":
        return sorted(value.lexical, key=lambda s: s.encode("utf-8")), None
    if value.family == "XHTML":
        return None, "xhtml_not_projected"
    if value.family == "BOOLEAN":
        return _boolean(value.lexical, value.element), None
    if value.family in ("STRING", "DATE"):
        return value.lexical, None
    token = value.lexical.strip(" \t\r\n")
    if token.startswith("-") and _compare_numbers(token, "0") == 0:
        return None, "negative_zero_not_representable"
    try:
        number = number_parser(token)
        # ReqIF accepts +1, leading zeroes and .1; JCS supplies native syntax.
        encoded = canonical_json_bytes(number)
        if _compare_numbers(encoded.decode(), token) != 0:
            return None, "number_roundtrip_loss"
        return number, None
    except ModelError as error:
        return None, error.reason


def _source_identity(identifier, source_system, source_document, external_revision):
    data = {"source_system": source_system, "source_document": source_document, "external_id": identifier}
    if external_revision is not None:
        data["external_revision"] = external_revision
    try:
        return ExternalIdentity(data).data
    except ModelError as error:
        raise ReqIFError(error.reason, exit_code=2, pointer=error.pointer) from error


def _native_value(definition, native, object_id):
    """Build a typed candidate from a validated inverse JSON value, never infer."""
    family = definition.family
    at = definition.element.pointer

    def node(tag, attrs=(), children=()):
        return _Node(REQIF_NAMESPACE + _SEP + tag, tuple(attrs), tuple(children), at)

    reference = node("DEFINITION", children=(node("ATTRIBUTE-DEFINITION-" + family + "-REF",
                                                 children=(definition.identifier,)),))
    attrs, content = (), (reference,)
    if family == "BOOLEAN" and type(native) is bool:
        literal = "true" if native else "false"
    elif family in ("INTEGER", "REAL") and type(native) in (int, float):
        literal = canonical_json_bytes(native).decode()
        if literal.startswith("-") and _compare_numbers(literal, "0") == 0:
            raise ReqIFError("reqif_inverse_not_representable", exit_code=6, object_id=object_id,
                             definition_id=definition.identifier, pointer=at)
        if family == "INTEGER":
            number = Decimal(literal)
            if number != number.to_integral_value():
                raise ReqIFError("reqif_inverse_not_representable", exit_code=6, object_id=object_id,
                                 definition_id=definition.identifier, pointer=at)
            literal = format(number, "f").split(".")[0]
    elif family in ("STRING", "DATE") and type(native) is str:
        literal = native
    elif family == "ENUMERATION" and type(native) is list and all(type(v) is str for v in native):
        content += (node("VALUES", children=tuple(node("ENUM-VALUE-REF", children=(v,)) for v in native)),)
        return node("ATTRIBUTE-VALUE-" + family, children=content)
    else:
        raise ReqIFError("reqif_inverse_not_representable", exit_code=6, object_id=object_id,
                         definition_id=definition.identifier, pointer=at)
    attrs = (("THE-VALUE", literal),)
    return node("ATTRIBUTE-VALUE-" + family, attrs, content)


def project_object(document, identifier, *, number_parser):
    obj = next((o for o in document.objects if o.identifier == identifier), None)
    if obj is None:
        raise ReqIFError("reqif_object_missing", object_id=identifier)
    definitions = next(t.definitions for t in document.types if t.identifier == obj.type_id)
    declared = {v.definition_id: v for v in obj.values}
    values, origins, losses = {}, {}, []
    for definition in definitions:
        key = definition.identifier
        value = declared.get(key, definition.default)
        origins[key] = "explicit" if key in declared else "default" if value is not None else "absent"
        if value is not None:
            projected, reason = _project_value(value, number_parser=number_parser)
            if reason:
                losses.append({"object_id": identifier, "definition_id": key, "reason": reason})
            else:
                values[key] = projected
    return {"external_id": identifier, "external_type": obj.type_id, "fields": values,
            "origins": origins, "unrepresentable": losses, "representable": not losses}


def map_object(document, identifier, *, mappings, key, expected_mapping_sha256,
               expected_source_sha256, source_system, source_document, external_revision=None):
    if expected_source_sha256 != document.source_sha256:
        raise ReqIFError("reqif_source_changed", exit_code=6, object_id=identifier)
    identity = _source_identity(identifier, source_system, source_document, external_revision)
    mapping = select_mapping(mappings, key=key, expected_sha256=expected_mapping_sha256)
    if mapping.resource.data["source_format"] != "reqif":
        raise ReqIFError("reqif_mapping_format_required", exit_code=2)
    projected = document.project_object(identifier)
    result = {"mapping": mapping.resource.binding(), "artifact": None, "unmapped": {}}
    if projected["representable"]:
        result = mapping.artifact(projected["external_type"], projected["fields"])
    return {**projected, **result, "external_identity": identity,
            "source_sha256": document.source_sha256, "mapping_complete": projected["representable"],
            "import_complete": False, "write_authorized": False, "execution_ready": False}


def export_object(document, identifier, native_fields, *, mappings, key, expected_mapping_sha256,
                  expected_source_sha256, source_system, source_document, validate, serialize, decode,
                  external_revision=None):
    """Return bytes for one inverse-mapped object in the explicitly bound source.

    The existing document owns definitions, IDs and metadata. Unchanged
    effective fields retain lexical spelling, enum order and absence. This
    is neither a whole native model exporter nor a writer/approval gate.
    """
    if expected_source_sha256 != document.source_sha256:
        raise ReqIFError("reqif_source_changed", exit_code=6, object_id=identifier)
    identity = _source_identity(identifier, source_system, source_document, external_revision)
    mapping = select_mapping(mappings, key=key, expected_sha256=expected_mapping_sha256)
    resource = mapping.resource
    if resource.data["source_format"] != "reqif":
        raise ReqIFError("reqif_mapping_format_required", exit_code=2)
    if document.unsupported:
        raise ReqIFError("reqif_uninterpreted_export", pointer=document.unsupported[0][0])
    projected = document.project_object(identifier)
    obj = next(o for o in document.objects if o.identifier == identifier)
    definitions = {d.identifier: d for t in document.types if t.identifier == obj.type_id for d in t.definitions}
    rows = resource.data
    typ = next((r for r in rows["types"] if r["external_type"] == obj.type_id), None)
    if typ is None:
        raise MappingError("mapping_type_unmapped", path=resource.key, pointer="/types")
    try:
        native_fields = parse_json_object(canonical_json_bytes(native_fields))
    except ModelError as error:
        raise ReqIFError(error.reason, exit_code=6, pointer=error.pointer, object_id=identifier) from error
    if native_fields.get("artifact_type") != typ["artifact_type"]:
        raise ReqIFError("reqif_inverse_type_mismatch", exit_code=6, object_id=identifier)
    replacements, expected, used = {}, {}, {"artifact_type"}
    for index, row in enumerate(rows["fields"]):
        if row["external_type"] != obj.type_id:
            continue
        aid, target = row["external_field"], row["target_field"]
        at = "/fields/" + str(index)
        if target not in native_fields:
            raise MappingError("mapping_source_field_missing", path=resource.key, pointer=at)
        if aid not in definitions:
            raise ReqIFError("reqif_definition_reference", definition_id=aid, object_id=identifier)
        external = native_fields[target]
        if row["value_map"] is not None:
            matches = [v["external_value"] for v in row["value_map"]
                       if canonical_json_bytes(v["target_value"]) == canonical_json_bytes(external)]
            if len(matches) != 1:
                reason = "reqif_inverse_mapping_ambiguous" if matches else "reqif_inverse_value_unmapped"
                raise ReqIFError(reason, exit_code=6, object_id=identifier, definition_id=aid, pointer=at)
            external = matches[0]
        expected[aid] = external
        used.add(target)
        if aid not in projected["fields"] or canonical_json_bytes(projected["fields"][aid]) != canonical_json_bytes(external):
            replacements[aid] = _native_value(definitions[aid], external, identifier)
    values = [replacements.pop(v.definition_id, v.element) for v in obj.values]
    values.extend(replacements.values())
    container = next((c for c in obj.element.children if c.tag == "VALUES"), None)
    new_values = _Node(REQIF_NAMESPACE + _SEP + "VALUES", (), tuple(values), obj.element.pointer + "/VALUES")
    if container is None:
        updated = replace(obj.element, content=(new_values,) + obj.element.content) if values else obj.element
    else:
        updated = _replace_node(obj.element, container, new_values)
    candidate = _replace_node(document._root, obj.element, updated)
    # Recheck the full typed object set, its bounds and actual serialized XML.
    try:
        validate(candidate)
        raw = serialize(candidate)
        checked = decode(raw, limits=document._limits).project_object(identifier)
    except ReqIFError as error:
        # The source already passed. A newly invalid value came from the
        # requested inverse projection; safety/resource failures stay real.
        if error.exit_code == 3:
            error.exit_code = 6
        raise
    for aid, external in expected.items():
        if aid not in checked["fields"] or canonical_json_bytes(checked["fields"][aid]) != canonical_json_bytes(external):
            raise ReqIFError("reqif_inverse_not_representable", exit_code=6, object_id=identifier, definition_id=aid)
    return {"xml_bytes": raw, "mapping": resource.binding(), "external_identity": identity,
            "source_sha256": document.source_sha256,
            "unmapped": {k: v for k, v in native_fields.items() if k not in used},
            "unrepresentable": checked["unrepresentable"], "export_complete": False,
            "write_authorized": False, "execution_ready": False}


def reqif_object_identifier(artifact, *, project_id, source_system, source_document, used_ids=()):
    """Stable first-export ID, or the unique identity in the explicit context.

    This pure reservation does not update any registry or prove native validity
    beyond identity fields. The higher export layer still validates the model.
    """
    native = artifact_identity(artifact)
    for value in (project_id, source_system, source_document):
        if type(value) is not str or not value.strip():
            raise ReqIFError("reqif_export_context_required", exit_code=2)
    existing = []
    for item in artifact.get("external_identities", []):
        value = ExternalIdentity(item).data
        if (value["source_system"], value["source_document"]) == (source_system, source_document):
            existing.append(value["external_id"])
    if len(existing) > 1:
        raise ReqIFError("reqif_external_identity_ambiguous", exit_code=6)
    candidate = existing[0] if existing else "_sr_" + sha256(canonical_json_bytes({
        "project_id": project_id, "artifact_type": native.artifact_type, "id": native.id})).hexdigest()
    if not _identifier(candidate) or candidate in used_ids:
        raise ReqIFError("reqif_export_identifier_conflict", exit_code=6)
    return candidate
