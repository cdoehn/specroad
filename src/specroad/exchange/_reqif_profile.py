"""Validate the supported ReqIF source profile and resolve typed references.

This module validates the complete passive tree before exposing any objects;
it does not parse bytes, infer native fields or claim whole-project import.
"""
from dataclasses import replace

from ._reqif_scalars import _boolean, _compare_numbers, _date, _identifier, _number
from ._reqif_values import (
    ReqIFDatatype, ReqIFDefinition, ReqIFError, ReqIFObject, ReqIFType, ReqIFValue,
    ReqIFSpecification, ReqIFRelation, ReqIFHierarchy,
    _SEP, _XML, _error,
)

_FAMILIES = ("BOOLEAN", "INTEGER", "REAL", "STRING", "DATE", "ENUMERATION", "XHTML")
_COMMON = {"IDENTIFIER", "LAST-CHANGE", "LONG-NAME", "DESC"}


def _text(node):
    if node.children:
        raise _error("reqif_text_required", node)
    return "".join(node.content)


def _layout(node, allowed, required=()):
    if any(type(x) is str and x.strip(' \t\r\n') for x in node.content):
        raise _error("reqif_unexpected_text", node)
    result = {}
    for child in node.children:
        if child.tag not in allowed or child.tag in result:
            raise _error("reqif_element_placement", child)
        result[child.tag] = child
    if not set(required) <= result.keys():
        raise _error("reqif_missing_element", node)
    return result


def _items(node, allowed):
    if node is None:
        return ()
    if node.attributes or any(type(x) is str and x.strip(' \t\r\n') for x in node.content):
        raise _error("reqif_invalid_container", node)
    if any(child.tag not in allowed for child in node.children):
        raise _error("reqif_element_placement", node)
    return node.children


def _reference(node, wrapper, tag):
    parts = _layout(node, {tag}, {tag})
    if node.tag != wrapper or node.attributes or parts[tag].attributes:
        raise _error("reqif_invalid_reference", node)
    value = _text(parts[tag])
    if not _identifier(value):
        raise _error("reqif_invalid_reference", node)
    return value


def _validate(root, *, structure=False):
    ids, unsupported = {}, []

    # IDs of deferred ReqIF objects share the document's namespace too. Do not
    # interpret arbitrary extension/XHTML attributes as ReqIF global IDs.
    global_ids, pending = set(), [root]
    identified = {"REQ-IF-HEADER", "ENUM-VALUE", "SPEC-OBJECT", "SPEC-RELATION",
                  "SPECIFICATION", "SPEC-HIERARCHY", "RELATION-GROUP"}
    identified |= {"DATATYPE-DEFINITION-" + f for f in _FAMILIES}
    identified |= {"ATTRIBUTE-DEFINITION-" + f for f in _FAMILIES}
    identified |= {"SPEC-OBJECT-TYPE", "SPEC-RELATION-TYPE", "SPECIFICATION-TYPE", "RELATION-GROUP-TYPE"}
    while pending:
        node = pending.pop()
        if node.tag is None or node.tag == "TOOL-EXTENSIONS":
            continue
        if node.tag in identified:
            key = node.attrs.get("IDENTIFIER")
            if not _identifier(key) or key in global_ids:
                raise _error("reqif_invalid_or_duplicate_identifier", node)
            global_ids.add(key)
        pending.extend(reversed(node.children))

    def attributes(node, allowed, required=()):
        if not set(required) <= node.attrs.keys():
            raise _error("reqif_missing_attribute", node)
        for key in sorted(node.attrs.keys() - set(allowed)):
            unsupported.append((node.pointer + "/@" + key, "uninterpreted_attribute"))

    def identity(node, *, header=False):
        identifier = node.attrs.get("IDENTIFIER")
        if not _identifier(identifier) or identifier in ids:
            raise _error("reqif_invalid_or_duplicate_identifier", node)
        ids[identifier] = node
        if not header:
            if "LAST-CHANGE" not in node.attrs:
                raise _error("reqif_missing_last_change", node)
            _date(node.attrs["LAST-CHANGE"], node)
        return identifier

    def alternative(node):
        if node is None:
            return
        attributes(node, set())
        part = _layout(node, {"ALTERNATIVE-ID"}, {"ALTERNATIVE-ID"})["ALTERNATIVE-ID"]
        attributes(part, {"IDENTIFIER"}, {"IDENTIFIER"})
        _layout(part, set())
        # Alternative identifiers are preserved metadata, not global keys.

    attributes(root, {_XML + _SEP + "lang"})
    top = _layout(root, {"THE-HEADER", "CORE-CONTENT", "TOOL-EXTENSIONS"}, {"THE-HEADER", "CORE-CONTENT"})
    if tuple(c.tag for c in root.children) != tuple(t for t in ("THE-HEADER", "CORE-CONTENT", "TOOL-EXTENSIONS") if t in top):
        raise _error("reqif_root_order", root)
    header = _layout(top["THE-HEADER"], {"REQ-IF-HEADER"}, {"REQ-IF-HEADER"})["REQ-IF-HEADER"]
    identity(header, header=True)
    attributes(header, {"IDENTIFIER"}, {"IDENTIFIER"})
    required = {"CREATION-TIME", "REQ-IF-TOOL-ID", "REQ-IF-VERSION", "SOURCE-TOOL-ID", "TITLE"}
    hp = _layout(header, required | {"COMMENT", "REPOSITORY-ID"}, required)
    for node in hp.values():
        attributes(node, set())
        _text(node)
    if _text(hp["REQ-IF-VERSION"]) != "1.0":
        raise _error("reqif_header_version", hp["REQ-IF-VERSION"])
    _date(_text(hp["CREATION-TIME"]), hp["CREATION-TIME"])
    core = _layout(top["CORE-CONTENT"], {"REQ-IF-CONTENT"}, {"REQ-IF-CONTENT"})["REQ-IF-CONTENT"]
    cp = _layout(core, {"DATATYPES", "SPEC-TYPES", "SPEC-OBJECTS", "SPEC-RELATIONS", "SPECIFICATIONS", "SPEC-RELATION-GROUPS"})
    for node in (top["THE-HEADER"], top["CORE-CONTENT"], core):
        attributes(node, set())
    for tag in ("SPEC-RELATIONS", "SPECIFICATIONS", "SPEC-RELATION-GROUPS"):
        if structure and tag != "SPEC-RELATION-GROUPS":
            continue
        if tag in cp and (cp[tag].children or cp[tag].attrs
                          or any(type(x) is str and x.strip() for x in cp[tag].content)):
            unsupported.append((cp[tag].pointer, "later_reqif_integration"))
    if "TOOL-EXTENSIONS" in top:
        unsupported.append((top["TOOL-EXTENSIONS"].pointer, "uninterpreted_extensions"))
    datatypes = {}
    for node in _items(cp.get("DATATYPES"), {"DATATYPE-DEFINITION-" + f for f in _FAMILIES}):
        family = node.tag.removeprefix("DATATYPE-DEFINITION-")
        identifier = identity(node)
        attrs = _COMMON | ({"MIN", "MAX"} if family in ("INTEGER", "REAL") else set())
        attrs |= {"ACCURACY"} if family == "REAL" else {"MAX-LENGTH"} if family == "STRING" else set()
        attributes(node, attrs, attrs - _COMMON)
        parts = _layout(node, {"ALTERNATIVE-ID", "SPECIFIED-VALUES"} if family == "ENUMERATION" else {"ALTERNATIVE-ID"})
        alternative(parts.get("ALTERNATIVE-ID"))
        enum_ids = []
        for ev in _items(parts.get("SPECIFIED-VALUES"), {"ENUM-VALUE"}):
            enum_ids.append(identity(ev))
            attributes(ev, _COMMON)
            ep = _layout(ev, {"ALTERNATIVE-ID", "PROPERTIES"}, {"PROPERTIES"})
            alternative(ep.get("ALTERNATIVE-ID"))
            attributes(ep["PROPERTIES"], set())
            embedded = _layout(ep["PROPERTIES"], {"EMBEDDED-VALUE"}, {"EMBEDDED-VALUE"})["EMBEDDED-VALUE"]
            attributes(embedded, {"KEY", "OTHER-CONTENT"}, {"KEY", "OTHER-CONTENT"})
            _layout(embedded, set())
            _number(embedded.attrs["KEY"], "INTEGER", embedded)
        if family in ("INTEGER", "REAL"):
            minimum, maximum = (_number(node.attrs[k], family, node) for k in ("MIN", "MAX"))
            comparison = _compare_numbers(minimum, maximum)
            if comparison is None or comparison > 0:
                raise _error("reqif_invalid_range", node)
        if family in ("STRING", "REAL"):
            key = "MAX-LENGTH" if family == "STRING" else "ACCURACY"
            if _compare_numbers(_number(node.attrs[key], "INTEGER", node), "0") < 0:
                raise _error("reqif_invalid_type_bound", node)
        if family == "XHTML" and not structure:
            unsupported.append((node.pointer, "xhtml_not_projected"))
        datatypes[identifier] = ReqIFDatatype(identifier, family, node, tuple(enum_ids))

    def value(node, definition):
        family = definition.family
        if node.tag != "ATTRIBUTE-VALUE-" + family:
            raise _error("reqif_value_family_mismatch", node, definition_id=definition.identifier)
        allowed = {"DEFINITION", "VALUES"} if family == "ENUMERATION" else {"DEFINITION"}
        if family == "XHTML":
            allowed |= {"THE-VALUE", "THE-ORIGINAL-VALUE"}
        parts = _layout(node, allowed, {"DEFINITION"})
        target = _reference(parts["DEFINITION"], "DEFINITION", "ATTRIBUTE-DEFINITION-" + family + "-REF")
        if target != definition.identifier:
            raise _error("reqif_definition_reference", node, definition_id=definition.identifier)
        if family == "ENUMERATION":
            attributes(node, set())
            references = _items(parts.get("VALUES"), {"ENUM-VALUE-REF"})
            for reference in references:
                attributes(reference, set())
            chosen = tuple(_text(v) for v in references)
            datatype = datatypes[definition.datatype_id]
            if (len(set(chosen)) != len(chosen) or not set(chosen) <= set(datatype.enum_ids)
                    or (not _boolean(definition.element.attrs["MULTI-VALUED"], definition.element) and len(chosen) > 1)):
                raise _error("reqif_invalid_enum_selection", node, definition_id=definition.identifier)
            lexical = chosen
        elif family == "XHTML":
            attributes(node, {"IS-SIMPLIFIED"})
            simplified = _boolean(node.attrs["IS-SIMPLIFIED"], node) if "IS-SIMPLIFIED" in node.attrs else False
            if structure:
                from ._reqif_xhtml import validate_xhtml
                lexical = validate_xhtml(parts, simplified)
                unsupported.extend(lexical.unsupported)
            else:
                unsupported.append((node.pointer, "xhtml_not_projected"))
                lexical = None
        else:
            attributes(node, {"THE-VALUE"}, {"THE-VALUE"})
            lexical = node.attrs["THE-VALUE"]
            datatype = datatypes[definition.datatype_id]
            da = datatype.element.attrs
            if family == "BOOLEAN":
                _boolean(lexical, node)
            elif family == "DATE":
                _date(lexical, node)
            elif family == "STRING":
                if _compare_numbers(str(len(lexical)), da["MAX-LENGTH"].strip(" \t\r\n")) > 0:
                    raise _error("reqif_string_too_long", node, definition_id=definition.identifier)
            else:
                number = _number(lexical, family, node)
                if number != "NaN" and (
                        _compare_numbers(da["MIN"].strip(" \t\r\n"), number) > 0
                        or _compare_numbers(number, da["MAX"].strip(" \t\r\n")) > 0):
                    raise _error("reqif_value_out_of_range", node, definition_id=definition.identifier)
        return ReqIFValue(family, definition.identifier, lexical, node)

    types = {}
    stags = {"SPEC-OBJECT-TYPE", "SPEC-RELATION-TYPE", "SPECIFICATION-TYPE", "RELATION-GROUP-TYPE"}
    for node in _items(cp.get("SPEC-TYPES"), stags):
        if node.tag != "SPEC-OBJECT-TYPE" and (not structure or node.tag == "RELATION-GROUP-TYPE"):
            unsupported.append((node.pointer, "later_reqif_integration"))
            continue
        identifier = identity(node)
        attributes(node, _COMMON)
        parts = _layout(node, {"ALTERNATIVE-ID", "SPEC-ATTRIBUTES"})
        alternative(parts.get("ALTERNATIVE-ID"))
        definitions = []
        for ad in _items(parts.get("SPEC-ATTRIBUTES"), {"ATTRIBUTE-DEFINITION-" + f for f in _FAMILIES}):
            aid = identity(ad)
            family = ad.tag.removeprefix("ATTRIBUTE-DEFINITION-")
            attributes(ad, _COMMON | {"IS-EDITABLE"} | ({"MULTI-VALUED"} if family == "ENUMERATION" else set()),
                       {"MULTI-VALUED"} if family == "ENUMERATION" else set())
            if "IS-EDITABLE" in ad.attrs:
                _boolean(ad.attrs["IS-EDITABLE"], ad)
            if family == "ENUMERATION":
                _boolean(ad.attrs["MULTI-VALUED"], ad)
            ap = _layout(ad, {"ALTERNATIVE-ID", "TYPE", "DEFAULT-VALUE"}, {"TYPE"})
            alternative(ap.get("ALTERNATIVE-ID"))
            did = _reference(ap["TYPE"], "TYPE", "DATATYPE-DEFINITION-" + family + "-REF")
            if did not in datatypes or datatypes[did].family != family:
                raise _error("reqif_datatype_reference", ad, definition_id=aid)
            definition = ReqIFDefinition(aid, family, did, None, ad)
            if "DEFAULT-VALUE" in ap:
                children = _items(ap["DEFAULT-VALUE"], {"ATTRIBUTE-VALUE-" + family})
                if len(children) != 1:
                    raise _error("reqif_default_value_required", ad, definition_id=aid)
                try:
                    definition = replace(definition, default=value(children[0], definition))
                except ReqIFError as error:
                    error.definition_id = aid
                    raise
            definitions.append(definition)
        types[identifier] = ReqIFType(identifier, tuple(definitions), node)
    def record(node, tag, extra=()):
        oid = identity(node)
        attributes(node, _COMMON)
        parts = _layout(node, {"ALTERNATIVE-ID", "TYPE", "VALUES"} | set(extra), {"TYPE"})
        alternative(parts.get("ALTERNATIVE-ID"))
        tid = _reference(parts["TYPE"], "TYPE", tag + "-TYPE-REF")
        if tid not in types or types[tid].element.tag != tag + "-TYPE":
            raise _error("reqif_object_type_reference", node, object_id=oid)
        defs = {d.identifier: d for d in types[tid].definitions}
        values = {}
        for av in _items(parts.get("VALUES"), {"ATTRIBUTE-VALUE-" + f for f in _FAMILIES}):
            family = av.tag.removeprefix("ATTRIBUTE-VALUE-")
            dp = _layout(av, {"DEFINITION", "VALUES", "THE-VALUE", "THE-ORIGINAL-VALUE"}, {"DEFINITION"})
            aid = _reference(dp["DEFINITION"], "DEFINITION", "ATTRIBUTE-DEFINITION-" + family + "-REF")
            if aid not in defs or aid in values:
                raise _error("reqif_object_definition_reference", av, object_id=oid, definition_id=aid)
            try:
                values[aid] = value(av, defs[aid])
            except ReqIFError as error:
                error.object_id = oid
                error.definition_id = aid
                raise
        return ReqIFObject(oid, tid, tuple(values.values()), node), parts

    objects = tuple(record(node, "SPEC-OBJECT")[0]
                    for node in _items(cp.get("SPEC-OBJECTS"), {"SPEC-OBJECT"}))
    if not structure:
        return tuple(datatypes.values()), tuple(types.values()), objects, tuple(unsupported)

    object_ids = {o.identifier for o in objects}
    specifications, relations, hierarchies = [], [], []

    def hierarchy(node, owner_id):
        hid = identity(node)
        attributes(node, _COMMON | {"IS-EDITABLE", "IS-TABLE-INTERNAL"})
        for flag in ("IS-EDITABLE", "IS-TABLE-INTERNAL"):
            if flag in node.attrs:
                _boolean(node.attrs[flag], node)
        parts = _layout(node, {"ALTERNATIVE-ID", "OBJECT", "CHILDREN", "EDITABLE-ATTS"}, {"OBJECT"})
        alternative(parts.get("ALTERNATIVE-ID"))
        oid = _reference(parts["OBJECT"], "OBJECT", "SPEC-OBJECT-REF")
        if oid not in object_ids:
            raise _error("reqif_hierarchy_object_reference", node, object_id=hid)
        if "EDITABLE-ATTS" in parts:
            # Preserve metadata outside the current native structural adapter.
            unsupported.append((parts["EDITABLE-ATTS"].pointer, "reqif_editable_attributes_not_projected"))
        children = _items(parts.get("CHILDREN"), {"SPEC-HIERARCHY"})
        hierarchies.append(ReqIFHierarchy(hid, oid, owner_id,
                                         tuple(c.attrs["IDENTIFIER"] for c in children), node))
        for child in children:
            hierarchy(child, hid)
        return hid

    for node in _items(cp.get("SPECIFICATIONS"), {"SPECIFICATION"}):
        obj, parts = record(node, "SPECIFICATION", ("CHILDREN",))
        children = tuple(hierarchy(c, obj.identifier) for c in _items(parts.get("CHILDREN"), {"SPEC-HIERARCHY"}))
        specifications.append(ReqIFSpecification(obj.identifier, obj.type_id, obj.values, node, children))
    for node in _items(cp.get("SPEC-RELATIONS"), {"SPEC-RELATION"}):
        obj, parts = record(node, "SPEC-RELATION", ("SOURCE", "TARGET"))
        if not {"SOURCE", "TARGET"} <= parts.keys():
            raise _error("reqif_relation_endpoints_required", node)
        endpoints = tuple(_reference(parts[k], k, "SPEC-OBJECT-REF") for k in ("SOURCE", "TARGET"))
        if not set(endpoints) <= object_ids:
            raise _error("reqif_relation_object_reference", node, object_id=obj.identifier)
        relations.append(ReqIFRelation(obj.identifier, obj.type_id, obj.values, node, *endpoints))
    return (tuple(datatypes.values()), tuple(types.values()), objects, tuple(unsupported),
            tuple(specifications), tuple(relations), tuple(hierarchies))
