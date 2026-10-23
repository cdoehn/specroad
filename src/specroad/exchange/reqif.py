"""Passive ReqIF type/object transport and explicitly bound mapping projection.

This is the 14.h object subset, not a project importer or a general XSD engine.
The caller supplies per-document parser bounds and owns all input/output bytes.
Uninterpreted content stays in the source; it prevents a complete export claim.
"""
from dataclasses import dataclass, fields, replace
from decimal import Decimal
from hashlib import sha256
import re

from ..mappings import MappingError, select_mapping
from ..model.canonical import canonical_json_bytes
from ..model.errors import ModelError
from ..model.identity_values import artifact_identity
from ..model.numbers import number_from_token
from ..storage._xml_reader import read_bounded_xml
from ..storage.json_syntax import parse_json_object
from .identities import ExternalIdentity


REQIF_NAMESPACE = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"
_XML = "http://www.w3.org/XML/1998/namespace"
_SEP = "\x1f"
_FAMILIES = ("BOOLEAN", "INTEGER", "REAL", "STRING", "DATE", "ENUMERATION", "XHTML")
_COMMON = {"IDENTIFIER", "LAST-CHANGE", "LONG-NAME", "DESC"}
_INTEGER = re.compile(r"[+-]?[0-9]+\Z")
_REAL = re.compile(r"(?:[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?|INF|-INF|NaN)\Z")
_DATE = re.compile(r"(-?(?:[0-9]{4}|[1-9][0-9]{4,}))-([0-9]{2})-([0-9]{2})T"
                   r"([0-9]{2}):([0-9]{2}):([0-9]{2})(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})?\Z")
_START = "A-Za-z_\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u02ff\u0370-\u037d\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd\U00010000-\U000effff"
_ID = re.compile("[" + _START + "][" + _START + "0-9.\u00b7\u0300-\u036f\u203f-\u2040-]*\\Z")


class ReqIFError(ModelError):
    """Machine-readable format, source conflict or safety failure; no payload."""

    def __init__(self, reason, *, exit_code=3, object_id=None, definition_id=None, **location):
        super().__init__(reason, **location)
        self.exit_code = exit_code
        self.object_id = object_id
        self.definition_id = definition_id

    def diagnostic(self):
        return {**super().diagnostic(), "exit_code": self.exit_code,
                "object_id": self.object_id, "definition_id": self.definition_id}


@dataclass(frozen=True)
class ReqIFLimits:
    """Explicit positive per-document safety bounds, not a total job budget.

    No JUnit-specific file cap is silently imposed on ReqIF. Callers bind all
    seven bounds before parsing; the shared XML reader enforces them throughout.
    """
    max_bytes: int
    max_depth: int
    max_elements: int
    max_text_chars: int
    max_attributes_per_element: int
    max_name_chars: int
    max_expanded_name_chars: int

    def __post_init__(self):
        if any(type(getattr(self, f.name)) is not int or getattr(self, f.name) < 1
               for f in fields(self)):
            raise ReqIFError("invalid_xml_limits", exit_code=2)


@dataclass(frozen=True)
class _Node:
    name: str
    attributes: tuple
    content: tuple
    pointer: str = ""

    @property
    def tag(self):
        namespace, _, local = self.name.rpartition(_SEP)
        return local if namespace == REQIF_NAMESPACE else None

    @property
    def attrs(self):
        return dict(self.attributes)

    @property
    def children(self):
        return tuple(x for x in self.content if type(x) is _Node)


def _error(reason, node, **context):
    return ReqIFError(reason, pointer=node.pointer, **context)


def _identifier(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _date(value, node):
    match = _DATE.fullmatch(value.strip(" \t\r\n"))
    if match is None:
        raise _error("reqif_invalid_datetime", node)
    # Gregorian leap years depend only on year modulo 400. No host integer
    # digit limit or datetime year range may truncate a valid XML year.
    year_text = match.group(1).lstrip("-")
    year = int(year_text[-4:])
    month, day, hour, minute, second = (int(v) for v in match.groups()[1:6])
    fraction, zone = match.groups()[6:]
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if (not year_text.strip("0") or not 1 <= month <= 12 or not 1 <= day <= days[month - 1]
            or hour > 24 or minute > 59 or second > 59
            or (hour == 24 and (minute or second or (fraction and set(fraction[1:]) != {"0"})))):
        raise _error("reqif_invalid_datetime", node)
    if zone and zone != "Z":
        hours, minutes = int(zone[1:3]), int(zone[4:6])
        if hours > 14 or minutes > 59 or (hours == 14 and minutes):
            raise _error("reqif_invalid_datetime", node)
    return value


def _boolean(value, node):
    token = value.strip(" \t\r\n")
    if token not in ("true", "false", "1", "0"):
        raise _error("reqif_invalid_boolean", node)
    return token in ("true", "1")


def _number(value, family, node):
    token = value.strip(" \t\r\n")
    if not (_INTEGER if family == "INTEGER" else _REAL).fullmatch(token):
        raise _error("reqif_invalid_number", node)
    return token


def _shift_exponent(text, offset):
    """Add a small digit-count offset to an unbounded signed decimal exponent."""
    negative = text.startswith("-")
    digits = text.lstrip("+-").lstrip("0") or "0"
    if len(digits) <= 18:
        return str((-1 if negative else 1) * int(digits) + offset)
    # With longer exponents the sign cannot be changed by an input-size offset.
    carry = -offset if negative else offset
    result = []
    for digit in reversed(digits):
        carry, remainder = divmod(int(digit) + carry, 10)
        result.append(str(remainder))
    while carry:
        carry, remainder = divmod(carry, 10)
        result.append(str(remainder))
    return ("-" if negative else "") + ("".join(reversed(result)).lstrip("0") or "0")


def _signed_integer_compare(left, right):
    a, b = left.lstrip("-"), right.lstrip("-")
    if left.startswith("-") != right.startswith("-"):
        return -1 if left.startswith("-") else 1
    comparison = ((len(a), a) > (len(b), b)) - ((len(a), a) < (len(b), b))
    return -comparison if left.startswith("-") else comparison


def _numeric_parts(token):
    negative = token.startswith("-")
    mantissa, _, exponent = token.lstrip("+-").lower().partition("e")
    whole, _, fraction = mantissa.partition(".")
    digits = (whole + fraction).lstrip("0")
    if not digits:
        return 0, "0", "0"
    magnitude = _shift_exponent(exponent or "0", len(digits) - len(fraction))
    return -1 if negative else 1, magnitude, digits.rstrip("0")


def _compare_numbers(left, right):
    """Exact lexical range comparison without binary64/Decimal context limits."""
    if "NaN" in (left, right):
        return None
    if left == right:
        return 0
    if left == "-INF" or right == "INF":
        return -1
    if left == "INF" or right == "-INF":
        return 1
    ls, le, ld = _numeric_parts(left)
    rs, re, rd = _numeric_parts(right)
    if ls != rs:
        return (ls > rs) - (ls < rs)
    comparison = _signed_integer_compare(le, re)
    if not comparison:
        length = max(len(ld), len(rd))
        a, b = ld.ljust(length, "0"), rd.ljust(length, "0")
        comparison = (a > b) - (a < b)
    return ls * comparison


def _text(node):
    if node.children:
        raise _error("reqif_text_required", node)
    return "".join(node.content)


def _layout(node, allowed, required=()):
    if any(type(x) is str and x.strip() for x in node.content):
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
    if node.attributes or any(type(x) is str and x.strip() for x in node.content):
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


@dataclass(frozen=True)
class ReqIFValue:
    family: str
    definition_id: str
    lexical: object
    element: _Node


@dataclass(frozen=True)
class ReqIFDatatype:
    identifier: str
    family: str
    element: _Node
    enum_ids: tuple = ()


@dataclass(frozen=True)
class ReqIFDefinition:
    identifier: str
    family: str
    datatype_id: str
    default: object
    element: _Node


@dataclass(frozen=True)
class ReqIFType:
    identifier: str
    definitions: tuple
    element: _Node


@dataclass(frozen=True)
class ReqIFObject:
    identifier: str
    type_id: str
    values: tuple
    element: _Node


def _read(raw, limits):
    if type(limits) is not ReqIFLimits:
        raise ReqIFError("typed_xml_limits_required", exit_code=2)
    stack, roots = [], []

    def start(name, attributes, reject):
        pointer = (stack[-1][3] if stack else "") + "/" + name.rsplit(_SEP, 1)[-1]
        if stack:
            pointer += "[" + str(stack[-1][4]) + "]"
            stack[-1][4] += 1
        stack.append([name, tuple(sorted(attributes.items())), [], pointer, 0])

    def end(_):
        name, attrs, content, pointer, _ = stack.pop()
        node = _Node(name, attrs, tuple(content), pointer)
        (stack[-1][2] if stack else roots).append(node)

    def text(value):
        if stack:
            stack[-1][2].append(value)

    read_bounded_xml(raw, limits=limits, limit_type=ReqIFLimits, error_type=ReqIFError,
                     on_start=start, on_end=end, on_text=text)
    if len(roots) != 1 or roots[0].tag != "REQ-IF":
        raise ReqIFError("reqif_root_required", pointer="/")
    return roots[0]


def _validate(root):
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
        if family == "XHTML":
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
            if "IS-SIMPLIFIED" in node.attrs:
                _boolean(node.attrs["IS-SIMPLIFIED"], node)
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
        if node.tag != "SPEC-OBJECT-TYPE":
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
    objects = []
    for node in _items(cp.get("SPEC-OBJECTS"), {"SPEC-OBJECT"}):
        oid = identity(node)
        attributes(node, _COMMON)
        parts = _layout(node, {"ALTERNATIVE-ID", "TYPE", "VALUES"}, {"TYPE"})
        alternative(parts.get("ALTERNATIVE-ID"))
        tid = _reference(parts["TYPE"], "TYPE", "SPEC-OBJECT-TYPE-REF")
        if tid not in types:
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
        objects.append(ReqIFObject(oid, tid, tuple(values.values()), node))
    return tuple(datatypes.values()), tuple(types.values()), tuple(objects), tuple(unsupported)


def _project_value(value):
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
        number = number_from_token(token)
        # ReqIF accepts +1, leading zeroes and .1; JCS supplies native syntax.
        encoded = canonical_json_bytes(number)
        if _compare_numbers(encoded.decode(), token) != 0:
            return None, "number_roundtrip_loss"
        return number, None
    except ModelError as error:
        return None, error.reason


def _escape(value, *, attribute=False):
    value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\r", "&#13;")
    return value.replace('"', "&quot;").replace("\t", "&#9;").replace("\n", "&#10;") if attribute else value


def _serialize(root):
    # Known ReqIF + xml:lang only. Unknown namespace-bearing payload is never
    # rewritten under guessed prefix bindings; the document retains its bytes.
    def name(value):
        namespace, _, local = value.rpartition(_SEP)
        if not namespace or namespace == REQIF_NAMESPACE:
            return local
        if namespace == _XML:
            return "xml:" + local
        raise ReqIFError("reqif_uninterpreted_namespace")

    def emit(node, *, first=False):
        attrs = [('xmlns', REQIF_NAMESPACE)] if first else []
        attrs += [(name(k), v) for k, v in node.attributes]
        opening = "<" + name(node.name) + "".join(' ' + k + '="' + _escape(v, attribute=True) + '"' for k, v in sorted(attrs)) + ">"
        # Preserve scalar text and mixed content; discard only structural
        # indentation between elements so already canonical output is stable.
        content = node.content
        if node.children and all(type(x) is _Node or not x.strip() for x in content):
            content = node.children
        return opening + "".join(emit(x) if type(x) is _Node else _escape(x) for x in content) + "</" + name(node.name) + ">"
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + emit(root, first=True) + "\n").encode("utf-8")


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


def _replace_node(root, before, after):
    if root is before:
        return after
    return replace(root, content=tuple(_replace_node(v, before, after) if type(v) is _Node else v
                                       for v in root.content))


@dataclass(frozen=True, init=False)
class ReqIFDocument:
    source_bytes: bytes
    datatypes: tuple
    types: tuple
    objects: tuple
    unsupported: tuple
    _root: _Node
    _limits: ReqIFLimits

    def __init__(self, raw, *, limits):
        if hasattr(self, "_root"):
            raise AttributeError("ReqIFDocument is immutable")
        root = _read(raw, limits)
        datatypes, types, objects, unsupported = _validate(root)
        for name, value in (("source_bytes", raw), ("_root", root), ("_limits", limits),
                            ("datatypes", datatypes), ("types", types), ("objects", objects), ("unsupported", unsupported)):
            object.__setattr__(self, name, value)

    @property
    def source_sha256(self):
        return sha256(self.source_bytes).hexdigest()

    def __bool__(self):
        raise TypeError("A ReqIF object subset is not successful project import or write authority")

    def observation(self):
        return {"profile": "reqif-object-profile-v1", "source_sha256": self.source_sha256,
                "object_count": len(self.objects), "validation_scope": "reqif_type_object_subset",
                "uninterpreted": [{"pointer": p, "reason": r} for p, r in self.unsupported],
                "import_complete": False, "write_authorized": False, "execution_ready": False}

    def project_object(self, identifier):
        obj = next((o for o in self.objects if o.identifier == identifier), None)
        if obj is None:
            raise ReqIFError("reqif_object_missing", object_id=identifier)
        definitions = next(t.definitions for t in self.types if t.identifier == obj.type_id)
        declared = {v.definition_id: v for v in obj.values}
        values, origins, losses = {}, {}, []
        for definition in definitions:
            key = definition.identifier
            value = declared.get(key, definition.default)
            origins[key] = "explicit" if key in declared else "default" if value is not None else "absent"
            if value is not None:
                projected, reason = _project_value(value)
                if reason:
                    losses.append({"object_id": identifier, "definition_id": key, "reason": reason})
                else:
                    values[key] = projected
        return {"external_id": identifier, "external_type": obj.type_id, "fields": values,
                "origins": origins, "unrepresentable": losses, "representable": not losses}

    def map_object(self, identifier, *, mappings, key, expected_mapping_sha256,
                   expected_source_sha256, source_system, source_document, external_revision=None):
        if expected_source_sha256 != self.source_sha256:
            raise ReqIFError("reqif_source_changed", exit_code=6, object_id=identifier)
        identity = _source_identity(identifier, source_system, source_document, external_revision)
        mapping = select_mapping(mappings, key=key, expected_sha256=expected_mapping_sha256)
        if mapping.resource.data["source_format"] != "reqif":
            raise ReqIFError("reqif_mapping_format_required", exit_code=2)
        projected = self.project_object(identifier)
        result = {"mapping": mapping.resource.binding(), "artifact": None, "unmapped": {}}
        if projected["representable"]:
            result = mapping.artifact(projected["external_type"], projected["fields"])
        return {**projected, **result, "external_identity": identity,
                "source_sha256": self.source_sha256, "mapping_complete": projected["representable"],
                "import_complete": False, "write_authorized": False, "execution_ready": False}

    def export_object(self, identifier, native_fields, *, mappings, key, expected_mapping_sha256,
                      expected_source_sha256, source_system, source_document, external_revision=None):
        """Return bytes for one inverse-mapped object in the explicitly bound source.

        The existing document owns definitions, IDs and metadata. Unchanged
        effective fields retain lexical spelling, enum order and absence. This
        is neither a whole native model exporter nor a writer/approval gate.
        """
        if expected_source_sha256 != self.source_sha256:
            raise ReqIFError("reqif_source_changed", exit_code=6, object_id=identifier)
        identity = _source_identity(identifier, source_system, source_document, external_revision)
        mapping = select_mapping(mappings, key=key, expected_sha256=expected_mapping_sha256)
        resource = mapping.resource
        if resource.data["source_format"] != "reqif":
            raise ReqIFError("reqif_mapping_format_required", exit_code=2)
        if self.unsupported:
            raise ReqIFError("reqif_uninterpreted_export", pointer=self.unsupported[0][0])
        projected = self.project_object(identifier)
        obj = next(o for o in self.objects if o.identifier == identifier)
        definitions = {d.identifier: d for t in self.types if t.identifier == obj.type_id for d in t.definitions}
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
        candidate = _replace_node(self._root, obj.element, updated)
        # Recheck the full typed object set, its bounds and actual serialized XML.
        try:
            _validate(candidate)
            raw = _serialize(candidate)
            checked = decode_reqif(raw, limits=self._limits).project_object(identifier)
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
                "source_sha256": self.source_sha256,
                "unmapped": {k: v for k, v in native_fields.items() if k not in used},
                "unrepresentable": checked["unrepresentable"], "export_complete": False,
                "write_authorized": False, "execution_ready": False}


def decode_reqif(raw, *, limits):
    return ReqIFDocument(raw, limits=limits)


def encode_reqif(document):
    """Serialize supported typed source objects, preserving absence and defaults.

    Full unknown/XHTML/hierarchy transport is a later integration. Original
    bytes remain available; refusing serialization cannot silently lose them.
    """
    if type(document) is not ReqIFDocument:
        raise ReqIFError("reqif_document_required", exit_code=2)
    if document.unsupported:
        raise ReqIFError("reqif_uninterpreted_export", pointer=document.unsupported[0][0])
    raw = _serialize(document._root)
    _validate(_read(raw, document._limits))
    return raw


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
